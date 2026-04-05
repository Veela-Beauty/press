"""Policy gate — AI usage policy acknowledgment before first use.

Users must acknowledge the policy before using AI features.
Supports versioned policies — new version requires re-acknowledgment.

Pure Python — no Frappe dependency. Storage is in-memory for the gate logic;
persistence is handled by the caller (Press DB or user record).
"""

from dataclasses import dataclass, field
from datetime import datetime

POLICY_RULES = [
    {"text": "No destructive SQL — DELETE, DROP, TRUNCATE are blocked automatically", "icon": "ban"},
    {"text": "No production writes — AI panel is read-only on production sites", "icon": "ban"},
    {"text": "Review all output — diffs are mandatory before applying changes", "icon": "check"},
    {"text": "Staging confirm — explicit approval required for staging actions", "icon": "check"},
    {"text": "Company keys for client code — use company API key, not personal", "icon": "shield"},
    {"text": "Token limits enforced — per-user and per-project daily caps", "icon": "shield"},
]


@dataclass
class PolicyResult:
    allowed: bool
    message: str


class PolicyGate:
    def __init__(self, current_version: str = "1.0"):
        self.current_version = current_version
        self._acknowledgments: dict[str, dict] = {}

    def acknowledge(self, user: str):
        self._acknowledgments[user] = {
            "timestamp": datetime.now().isoformat(),
            "version": self.current_version,
        }

    def check(self, user: str) -> PolicyResult:
        record = self._acknowledgments.get(user)
        if not record:
            return PolicyResult(
                allowed=False,
                message="You must acknowledge the AI Usage Policy before using AI features.",
            )
        if record["version"] != self.current_version:
            return PolicyResult(
                allowed=False,
                message="The AI Usage Policy has been updated. Please acknowledge the new version.",
            )
        return PolicyResult(allowed=True, message="Policy acknowledged.")

    def get_acknowledgment(self, user: str) -> dict | None:
        return self._acknowledgments.get(user)

    def get_status(self, user: str) -> dict:
        record = self._acknowledgments.get(user)
        return {
            "user": user,
            "acknowledged": record is not None and record.get("version") == self.current_version,
            "version": record["version"] if record else None,
            "timestamp": record["timestamp"] if record else None,
            "rules": POLICY_RULES,
        }
