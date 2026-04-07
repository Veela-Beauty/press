"""Site scope guard — enforces AI behavior rules based on site type and branch.

Site type rules:
  Dev/Demo:    AI can write freely (after diff preview)
  Staging:     AI can write only with explicit user confirmation
  Production:  HARD BLOCK — AI is read-only, Apply button hidden

Branch rules:
  dev-* branches: AI commits allowed
  All other branches: AI commits blocked

Pure Python — no Frappe dependency.
"""

from dataclasses import dataclass


@dataclass
class ScopeResult:
    allowed: bool
    needs_confirm: bool
    message: str


# Actions the AI can take
KNOWN_ACTIONS = {
    "read",
    "write_file",
    "git_commit",
    "bench_execute",
    "demo_data",
    "config_change",
}

# Write actions that modify the site/branch
WRITE_ACTIONS = {
    "write_file",
    "git_commit",
    "bench_execute",
    "demo_data",
    "config_change",
}


def check_scope(site_type: str, action: str) -> ScopeResult:
    """Check if an AI action is allowed on a given site type.

    Returns ScopeResult with allowed, needs_confirm, and message.
    """
    if action not in KNOWN_ACTIONS:
        return ScopeResult(
            allowed=False,
            needs_confirm=False,
            message=f"Unknown action '{action}' — blocked by default.",
        )

    is_write = action in WRITE_ACTIONS

    if site_type == "Dev":
        return ScopeResult(
            allowed=True,
            needs_confirm=False,
            message="Dev site — AI actions allowed.",
        )

    if site_type in ("Demo", "Staging"):
        if is_write:
            return ScopeResult(
                allowed=True,
                needs_confirm=True,
                message="Staging site — please confirm before applying. This site may contain production-like data.",
            )
        return ScopeResult(
            allowed=True,
            needs_confirm=False,
            message="Staging site — read access granted.",
        )

    if site_type == "Production":
        if is_write:
            return ScopeResult(
                allowed=False,
                needs_confirm=False,
                message="Production site — AI write operations are blocked. AI panel is read-only on production.",
            )
        return ScopeResult(
            allowed=True,
            needs_confirm=False,
            message="Production site — read-only access.",
        )

    # Unknown site type — block by default
    return ScopeResult(
        allowed=False,
        needs_confirm=False,
        message=f"Unknown site type '{site_type}' — blocked by default.",
    )


def check_branch(branch_name: str) -> ScopeResult:
    """Check if AI commits are allowed on this branch.

    Only dev-* branches allow AI commits.
    """
    if branch_name.startswith("dev-"):
        return ScopeResult(
            allowed=True,
            needs_confirm=False,
            message=f"Branch '{branch_name}' — AI commits allowed.",
        )

    return ScopeResult(
        allowed=False,
        needs_confirm=False,
        message=f"Branch '{branch_name}' — AI commits only allowed on dev-* branches. Create a dev- branch first.",
    )
