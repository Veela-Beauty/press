"""Press AI API — whitelisted endpoints for the AI Dev Tab.

All endpoints require System Manager role (enforced per-method).
Sibling file pattern — does not modify any upstream Press controllers.
"""

import uuid
import frappe

from press.press.ai.gateway import process_ai_request, get_budget_engine
from press.press.ai.key_storage import resolve_provider_key
from press.press.ai.context_injector import build_context


@frappe.whitelist()
def chat(prompt, site_name="", bench_name="", site_type="Dev",
         branch="", session_id=None):
    """Process a chat message through the AI gateway.

    Returns: {success, response_text, violations, tokens_used, budget, needs_confirm, session_id, error}
    """
    user = frappe.session.user

    # Resolve API key (personal -> company -> error)
    personal_key = frappe.db.get_value(
        "User", user, "ai_api_key"
    ) if frappe.db.has_column("User", "ai_api_key") else None

    team = getattr(frappe.local, "team", None)
    team_name = team.name if team else None
    company_key = None
    if team_name:
        company_key = frappe.db.get_value(
            "Team", team_name, "ai_company_key"
        ) if frappe.db.has_column("Team", "ai_company_key") else None

    provider = _get_user_provider(user)

    # Build context
    context = None
    if bench_name:
        try:
            bench = frappe.get_doc("Bench", bench_name)
            apps_raw = bench.docker_execute("ls apps/", save_output=False, create_log=False)
            apps = [a.strip() for a in apps_raw.get("output", "").split() if a.strip()]
            version_raw = bench.docker_execute(
                "cat apps/frappe/frappe/__init__.py | grep __version__",
                save_output=False, create_log=False,
            )
            version = version_raw.get("output", "").split("=")[-1].strip().strip("'\"") if version_raw.get("output") else "unknown"
            context = build_context(
                frappe_version=version,
                installed_apps=apps,
                site_name=site_name,
            )
        except Exception:
            pass  # Context is optional — proceed without it

    # Generate session ID if new
    if not session_id:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"

    # Call gateway
    result = process_ai_request(
        user=user,
        project=team_name or "default",
        site_type=site_type,
        branch=branch or "dev-default",
        prompt=prompt,
        provider=provider,
        api_key=personal_key,
        company_key=company_key,
        context=context,
    )

    # Build budget info for frontend
    engine = get_budget_engine()
    budget = {
        "used": engine.get_user_usage(user),
        "cap": engine._get_user_cap(user),
    }

    return {
        "success": result.success,
        "response_text": result.response_text,
        "violations": [
            {"category": v.category, "pattern": v.pattern, "description": v.description}
            for v in (result.lint_result.violations if result.lint_result else [])
        ],
        "tokens_used": result.tokens_used,
        "budget": budget,
        "needs_confirm": result.needs_confirm,
        "session_id": session_id,
        "error": result.error,
    }


@frappe.whitelist()
def get_ai_config():
    """Return AI configuration for the current user."""
    user = frappe.session.user
    provider = _get_user_provider(user)
    has_key = bool(_get_user_key(user))

    engine = get_budget_engine()
    budget = {
        "used": engine.get_user_usage(user),
        "cap": engine._get_user_cap(user),
    }

    return {
        "provider": provider,
        "has_key": has_key,
        "budget": budget,
    }


def _get_user_provider(user):
    """Get the user's preferred AI provider. Default: anthropic."""
    if frappe.db.has_column("User", "ai_provider"):
        return frappe.db.get_value("User", user, "ai_provider") or "anthropic"
    return "anthropic"


def _get_user_key(user):
    """Get the user's personal AI API key (encrypted)."""
    if frappe.db.has_column("User", "ai_api_key"):
        return frappe.db.get_value("User", user, "ai_api_key")
    return None
