"""Token budget engine — per-user caps + project pools with optimistic reservation.

Hybrid budget: both user cap AND project pool enforced before every API call.
Optimistic reservation prevents race conditions in concurrent requests.

Pure Python — uses in-memory state. Frappe DB persistence is layered on top.
"""

import uuid
from dataclasses import dataclass, field


@dataclass
class BudgetResult:
    allowed: bool
    warning: bool
    user_remaining: int
    project_remaining: int
    reason: str = ""


@dataclass
class Reservation:
    reservation_id: str
    user: str
    project: str
    estimated_tokens: int


# Cost rates per 1M tokens (input/output) — updated periodically
COST_RATES = {
    ("anthropic", "claude-sonnet-4-20250514"): {"input": 3.0, "output": 15.0},
    ("anthropic", "claude-haiku-4-5-20251001"): {"input": 0.80, "output": 4.0},
    ("openai", "gpt-4o"): {"input": 2.50, "output": 10.0},
    ("z_ai", "glm-4-plus"): {"input": 0.50, "output": 0.50},
}

WARNING_THRESHOLD = 0.80  # Warn at 80% of cap


class BudgetEngine:
    """In-memory token budget tracker with reservation support."""

    def __init__(self, default_user_cap: int = 100_000, default_project_pool: int = 500_000):
        self.default_user_cap = default_user_cap
        self.default_project_pool = default_project_pool
        self._user_caps: dict[str, int] = {}
        self._project_pools: dict[str, int] = {}
        self._user_usage: dict[str, int] = {}
        self._project_usage: dict[str, int] = {}
        self._reservations: dict[str, Reservation] = {}
        self._usage_details: dict[str, dict] = {}

    def set_user_cap(self, user: str, daily_cap: int):
        self._user_caps[user] = daily_cap

    def set_project_pool(self, project: str, daily_pool: int):
        self._project_pools[project] = daily_pool

    def _get_user_cap(self, user: str) -> int:
        return self._user_caps.get(user, self.default_user_cap)

    def _get_project_pool(self, project: str) -> int:
        return self._project_pools.get(project, self.default_project_pool)

    def _get_user_total(self, user: str) -> int:
        """Total tokens used + reserved for a user."""
        used = self._user_usage.get(user, 0)
        reserved = sum(
            r.estimated_tokens for r in self._reservations.values() if r.user == user
        )
        return used + reserved

    def _get_project_total(self, project: str) -> int:
        """Total tokens used + reserved for a project."""
        used = self._project_usage.get(project, 0)
        reserved = sum(
            r.estimated_tokens for r in self._reservations.values() if r.project == project
        )
        return used + reserved

    def check_budget(self, user: str, project: str, estimated_tokens: int) -> BudgetResult:
        """Check if a request is within budget. Enforces both user cap and project pool."""
        user_cap = self._get_user_cap(user)
        project_pool = self._get_project_pool(project)
        user_total = self._get_user_total(user)
        project_total = self._get_project_total(project)

        # 0 = unlimited
        user_remaining = (user_cap - user_total) if user_cap > 0 else 999_999_999
        project_remaining = (project_pool - project_total) if project_pool > 0 else 999_999_999

        # Check hard block
        if user_cap > 0 and user_total + estimated_tokens > user_cap:
            return BudgetResult(
                allowed=False, warning=False,
                user_remaining=max(0, user_remaining),
                project_remaining=max(0, project_remaining),
                reason=f"User daily cap exceeded: {user_total}/{user_cap} tokens used.",
            )

        if project_pool > 0 and project_total + estimated_tokens > project_pool:
            return BudgetResult(
                allowed=False, warning=False,
                user_remaining=max(0, user_remaining),
                project_remaining=max(0, project_remaining),
                reason=f"Project daily pool exceeded: {project_total}/{project_pool} tokens used.",
            )

        # Check warning threshold
        warning = False
        if user_cap > 0 and user_total >= user_cap * WARNING_THRESHOLD:
            warning = True
        if project_pool > 0 and project_total >= project_pool * WARNING_THRESHOLD:
            warning = True

        return BudgetResult(
            allowed=True, warning=warning,
            user_remaining=max(0, user_remaining),
            project_remaining=max(0, project_remaining),
        )

    def reserve(self, user: str, project: str, estimated_tokens: int) -> Reservation:
        """Optimistically reserve tokens before API call."""
        reservation = Reservation(
            reservation_id=uuid.uuid4().hex[:16],
            user=user,
            project=project,
            estimated_tokens=estimated_tokens,
        )
        self._reservations[reservation.reservation_id] = reservation
        return reservation

    def reconcile(self, reservation_id: str, actual_tokens: int):
        """Replace reservation with actual usage after API response."""
        reservation = self._reservations.pop(reservation_id, None)
        if reservation:
            self.record_usage(reservation.user, reservation.project, tokens=actual_tokens)

    def cancel_reservation(self, reservation_id: str):
        """Cancel a reservation (API call failed)."""
        self._reservations.pop(reservation_id, None)

    def record_usage(self, user: str, project: str, tokens: int,
                     input_tokens: int = 0, output_tokens: int = 0,
                     provider: str = "", model: str = ""):
        """Record actual token usage."""
        self._user_usage[user] = self._user_usage.get(user, 0) + tokens
        self._project_usage[project] = self._project_usage.get(project, 0) + tokens

        key = f"{user}:{project}"
        if key not in self._usage_details:
            self._usage_details[key] = {
                "total_tokens": 0, "input_tokens": 0, "output_tokens": 0,
                "estimated_cost": 0.0, "sessions": 0,
            }
        detail = self._usage_details[key]
        detail["total_tokens"] += tokens
        detail["input_tokens"] += input_tokens
        detail["output_tokens"] += output_tokens
        detail["sessions"] += 1

        # Estimate cost
        rate = COST_RATES.get((provider, model))
        if rate and input_tokens and output_tokens:
            cost = (input_tokens * rate["input"] + output_tokens * rate["output"]) / 1_000_000
            detail["estimated_cost"] += cost

    def get_user_usage(self, user: str) -> int:
        return self._user_usage.get(user, 0)

    def get_project_usage(self, project: str) -> int:
        return self._project_usage.get(project, 0)

    def get_usage_detail(self, user: str, project: str) -> dict:
        key = f"{user}:{project}"
        return self._usage_details.get(key, {
            "total_tokens": 0, "input_tokens": 0, "output_tokens": 0,
            "estimated_cost": 0.0, "sessions": 0,
        })
