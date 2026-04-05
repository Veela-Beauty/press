"""Escalation state machine — manages Cat 1/2 violation escalation lifecycle.

State flow:
  pending_tl → (TL approves) → pending_admin → (Admin approves) → approved/approved_manual
  pending_tl → (TL rejects)  → rejected
  pending_admin → (Admin rejects) → rejected

Cat 1 (hard block): approved_manual — AI never executes, admin does it manually.
Cat 2 (approval):   approved — action can be auto-executed after approval.

Pure Python — no Frappe dependency.
"""

from dataclasses import dataclass, field
from datetime import datetime


class EscalationError(Exception):
    pass


VALID_STATUSES = {"pending_tl", "pending_admin", "approved", "approved_manual", "rejected"}

VALID_TRANSITIONS = {
    "pending_tl": {"pending_admin", "rejected"},
    "pending_admin": {"approved", "approved_manual", "rejected"},
}


@dataclass
class Escalation:
    violation_category: int
    pattern: str
    description: str
    user: str
    session_id: str
    site_name: str
    status: str = "pending_tl"
    reason: str = ""
    tl_user: str = ""
    tl_reason: str = ""
    admin_user: str = ""
    admin_reason: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    _history: list = field(default_factory=list, repr=False)

    @property
    def manual_only(self) -> bool:
        """Cat 1 actions are never auto-executed — even when approved."""
        return self.violation_category == 1

    def submit(self, reason: str):
        if not reason or not reason.strip():
            raise EscalationError("Escalation reason is required.")
        self.reason = reason
        self.status = "pending_tl"
        self._history.append({
            "action": "submitted",
            "user": self.user,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        })

    def tl_decide(self, approved: bool, tl_user: str, tl_reason: str):
        if self.status != "pending_tl":
            raise EscalationError(f"Cannot TL decide in status '{self.status}'. Expected 'pending_tl'.")
        self.tl_user = tl_user
        self.tl_reason = tl_reason
        if approved:
            self.status = "pending_admin"
            self._history.append({
                "action": "tl_approved",
                "user": tl_user,
                "reason": tl_reason,
                "timestamp": datetime.now().isoformat(),
            })
        else:
            self.status = "rejected"
            self._history.append({
                "action": "tl_rejected",
                "user": tl_user,
                "reason": tl_reason,
                "timestamp": datetime.now().isoformat(),
            })

    def admin_decide(self, approved: bool, admin_user: str, admin_reason: str):
        if self.status != "pending_admin":
            raise EscalationError(f"Cannot admin decide in status '{self.status}'. Expected 'pending_admin'.")
        self.admin_user = admin_user
        self.admin_reason = admin_reason
        if approved:
            self.status = "approved_manual" if self.manual_only else "approved"
            self._history.append({
                "action": "admin_approved",
                "user": admin_user,
                "reason": admin_reason,
                "timestamp": datetime.now().isoformat(),
            })
        else:
            self.status = "rejected"
            self._history.append({
                "action": "admin_rejected",
                "user": admin_user,
                "reason": admin_reason,
                "timestamp": datetime.now().isoformat(),
            })

    def get_history(self) -> list:
        return list(self._history)

    def to_dict(self) -> dict:
        return {
            "violation_category": self.violation_category,
            "pattern": self.pattern,
            "description": self.description,
            "user": self.user,
            "session_id": self.session_id,
            "site_name": self.site_name,
            "status": self.status,
            "reason": self.reason,
            "tl_user": self.tl_user,
            "tl_reason": self.tl_reason,
            "admin_user": self.admin_user,
            "admin_reason": self.admin_reason,
            "manual_only": self.manual_only,
            "created_at": self.created_at.isoformat(),
            "history": self.get_history(),
        }
