"""Rollback trigger — Press-side proxy to site rollback API.

Press controls WHEN rollback happens (governance).
Sanad AI on the site controls HOW (SQL execution).

This module builds agent commands that Press sends to the site.
Actual agent execution is done by the Press agent system.

Pure Python — no Frappe dependency.
"""

from dataclasses import dataclass


@dataclass
class RollbackValidation:
    allowed: bool
    needs_confirm: bool = False
    message: str = ""


def validate_rollback_site(site_type: str) -> RollbackValidation:
    """Check if rollback is allowed on this site type."""
    if site_type in ("Dev", "Demo"):
        return RollbackValidation(allowed=True, message="Dev site — rollback allowed.")
    if site_type == "Staging":
        return RollbackValidation(
            allowed=True,
            needs_confirm=True,
            message="Staging site — confirm before rollback. This site has production-like data.",
        )
    if site_type == "Production":
        return RollbackValidation(
            allowed=False,
            message="Production site — rollback is blocked. Use manual restore from backup.",
        )
    return RollbackValidation(
        allowed=False,
        message=f"Unknown site type '{site_type}' — rollback blocked.",
    )


def build_enable_versioning_cmd(site_name: str, doctypes: list[str]) -> dict:
    """Build agent command to enable MariaDB system versioning."""
    return {
        "method": "sanad_business_intelligence_ai.ai_dev.api.enable_versioning",
        "site_name": site_name,
        "doctypes": doctypes,
    }


def build_rollback_cmd(site_name: str, session_id: str) -> dict:
    """Build agent command to execute rollback for a session."""
    return {
        "method": "sanad_business_intelligence_ai.ai_dev.api.rollback_session",
        "site_name": site_name,
        "session_id": session_id,
    }


def build_cleanup_cmd(site_name: str) -> dict:
    """Build agent command to cleanup expired sessions."""
    return {
        "method": "sanad_business_intelligence_ai.ai_dev.api.cleanup_expired",
        "site_name": site_name,
    }


def build_full_rollback_payload(
    site_name: str,
    session_id: str,
    include_git_revert: bool = False,
    bench_name: str | None = None,
    app_name: str | None = None,
    commit_hash: str | None = None,
) -> dict:
    """Build complete rollback payload (DB + optional git revert)."""
    payload = {
        "site_name": site_name,
        "session_id": session_id,
    }
    if include_git_revert and commit_hash:
        payload["include_git_revert"] = True
        payload["bench_name"] = bench_name
        payload["app_name"] = app_name
        payload["commit_hash"] = commit_hash
    return payload
