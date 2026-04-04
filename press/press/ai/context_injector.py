"""AI context injector — builds sanitized context payloads for LLM prompts.

Collects bench/site metadata and injects it into the system prompt.
Credentials and secrets are NEVER included.

Pure Python core — Frappe-dependent collection functions are separate.
"""

import json

# Fields that must NEVER be sent to LLM context
BLOCKED_CONFIG_KEYS = {
    "db_password",
    "admin_password",
    "encryption_key",
    "secret_key",
    "mail_password",
    "rq_password",
    "redis_password",
    "api_key",
    "api_secret",
    "publishable_key",
    "private_key",
    "stripe_secret_key",
    "razorpay_key",
    "razorpay_secret",
    "paypal_client_id",
    "paypal_client_secret",
}

# Also block any key containing these substrings
BLOCKED_SUBSTRINGS = {"password", "secret", "token", "encryption_key"}


def filter_site_config(config: dict) -> dict:
    """Remove credentials and secrets from site_config before injection."""
    filtered = {}
    for key, value in config.items():
        if key in BLOCKED_CONFIG_KEYS:
            continue
        key_lower = key.lower()
        if any(sub in key_lower for sub in BLOCKED_SUBSTRINGS):
            continue
        filtered[key] = value
    return filtered


def truncate_error_log(log: str, max_lines: int = 50) -> str:
    """Truncate error log, keeping the LAST lines (most relevant for debugging)."""
    if not log:
        return ""
    lines = log.strip().split("\n")
    if len(lines) <= max_lines:
        return log
    kept = lines[-max_lines:]
    return f"... (truncated {len(lines) - max_lines} lines) ...\n" + "\n".join(kept)


def generate_system_prompt(
    frappe_version: str,
    installed_apps: list,
    site_name: str,
    error_log: str = "",
    doctype_schema: dict = None,
    site_config: dict = None,
) -> str:
    """Generate the system prompt with injected context."""
    parts = []

    parts.append(
        f"""You are a Frappe/ERPNext development assistant embedded in Press.

## Environment
- Frappe version: {frappe_version}
- Site: {site_name}
- Installed apps: {', '.join(installed_apps)}"""
    )

    if site_config:
        safe_config = filter_site_config(site_config)
        parts.append(
            f"\n## Site Configuration (filtered — no credentials)\n```json\n{json.dumps(safe_config, indent=2)}\n```"
        )

    parts.append(
        """
## Safety Rules
- NEVER generate raw SQL with DELETE, DROP, or TRUNCATE
- NEVER suggest bench destroy, bench uninstall-app, or rm -rf
- NEVER modify production sites — all production operations are blocked
- Use frappe ORM (frappe.get_doc, frappe.db.set_value) instead of raw SQL
- Use frappe.delete_doc() for single document deletion (confirmed by user)
- All code must be reviewed before applying"""
    )

    if error_log:
        truncated = truncate_error_log(error_log)
        parts.append(
            f"\n## Latest Error (user requested debug)\n```\n{truncated}\n```\nAnalyze this error and suggest a fix."
        )

    if doctype_schema:
        schema_str = json.dumps(doctype_schema, indent=2, default=str)
        parts.append(
            f"\n## DocType Schema: {doctype_schema.get('name', 'Unknown')}\n```json\n{schema_str}\n```\nUse this schema for accurate field references."
        )

    return "\n".join(parts)


def build_context(
    frappe_version: str,
    installed_apps: list,
    site_name: str,
    error_log: str = "",
    doctype_schema: dict = None,
    site_config: dict = None,
) -> dict:
    """Build the full context payload for an AI request.

    Returns a dict with structured data + the assembled system_prompt.
    """
    ctx = {
        "frappe_version": frappe_version,
        "installed_apps": installed_apps,
        "site_name": site_name,
    }

    if error_log:
        ctx["error_log"] = truncate_error_log(error_log)

    if doctype_schema:
        ctx["doctype_schema"] = doctype_schema

    if site_config:
        ctx["site_config"] = filter_site_config(site_config)

    ctx["system_prompt"] = generate_system_prompt(
        frappe_version=frappe_version,
        installed_apps=installed_apps,
        site_name=site_name,
        error_log=error_log,
        doctype_schema=doctype_schema,
        site_config=site_config,
    )

    return ctx
