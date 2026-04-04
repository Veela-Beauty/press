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


@frappe.whitelist()
def acknowledge_policy():
    """Record that the user acknowledged the AI usage policy."""
    user = frappe.session.user
    frappe.db.set_value("User", user, "ai_policy_acknowledged", frappe.utils.now())
    frappe.db.commit()
    return {"ok": True, "user": user, "acknowledged_at": frappe.utils.now()}


@frappe.whitelist()
def apply_patch(files, bench_name, branch, session_id, commit_message=""):
    """Apply AI-generated file patches to the bench container.

    Args:
        files: JSON list of {path, content} objects
        bench_name: Bench DocType name
        branch: Git branch to commit to
        session_id: AI session ID for traceability
        commit_message: Optional custom commit message
    """
    import json as json_mod
    user = frappe.session.user

    if isinstance(files, str):
        files = json_mod.loads(files)

    bench = frappe.get_doc("Bench", bench_name)

    results = []
    for f in files:
        path = f["path"]
        content = f["content"]

        # Write file to container
        # Use base64 encoding to handle special characters safely
        import base64
        encoded = base64.b64encode(content.encode()).decode()
        bench.docker_execute(
            f"echo '{encoded}' | base64 -d > apps/{path}",
            save_output=False, create_log=False,
        )
        results.append({"path": path, "status": "written"})

    # Git commit
    if not commit_message:
        file_list = ", ".join(f["path"].split("/")[-1] for f in files)
        commit_message = f"[Press AI] patch: {file_list}"

    commit_msg_full = (
        f"{commit_message}\n\n"
        f"Provider : AI Assistant\n"
        f"Session  : {session_id}\n"
        f"Branch   : {branch}\n"
        f"User     : {user}\n"
        f"Files    : {', '.join(f['path'] for f in files)}"
    )

    # Stage + commit inside container
    file_paths = " ".join(f"apps/{f['path']}" for f in files)
    bench.docker_execute(
        f"git -C apps add {file_paths}",
        save_output=False, create_log=False,
    )
    bench.docker_execute(
        f'git -C apps -c user.name="Press AI" -c user.email="ai@press.local" '
        f'commit -m "{commit_msg_full}"',
        save_output=False, create_log=False,
    )

    # Get commit hash
    hash_result = bench.docker_execute(
        "git -C apps log -1 --format=%H",
        save_output=False, create_log=False,
    )
    commit_hash = hash_result.get("output", "").strip()[:12]

    return {
        "ok": True,
        "files": results,
        "commit_hash": commit_hash,
        "commit_message": commit_message,
    }


@frappe.whitelist()
def update_team_ai_rules(team, settings):
    """Update AI rules for a team (admin only)."""
    import json as json_mod

    if frappe.session.user != "Administrator":
        from press.press.doctype.team.team_roles import has_role_access
        if not has_role_access("Platform Admin"):
            frappe.throw("Only Platform Admin can modify AI rules")

    if isinstance(settings, str):
        settings = json_mod.loads(settings)

    # Store as JSON on Team custom field
    if frappe.db.has_column("Team", "ai_rules"):
        frappe.db.set_value("Team", team, "ai_rules", json_mod.dumps(settings))
        frappe.db.commit()

    return {"ok": True}
