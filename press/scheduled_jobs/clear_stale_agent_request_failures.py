# press/scheduled_jobs/clear_stale_agent_request_failures.py
"""Auto-clear stale `Agent Request Failure` rows so the
Agent.should_skip_requests() circuit breaker self-heals once a server is
reachable again.

Without this, a single transient network blip leaves a Failure row in place
forever — every subsequent agent job for that server then silently goes
Undelivered (the 2026-04-30 incident).

Schedule (in hooks.py): every 10 minutes.
"""

from __future__ import annotations

import frappe

from press.agent import Agent

STALE_THRESHOLD_MINUTES = 10


def execute() -> None:
    """Cron entry point — called by hooks.py scheduler_events.cron."""
    cutoff = frappe.utils.add_to_date(None, minutes=-STALE_THRESHOLD_MINUTES)
    failures = frappe.get_all(
        "Agent Request Failure",
        filters={"creation": ["<", cutoff]},
        fields=["name", "server", "server_type"],
    )
    if not failures:
        return

    for fail in failures:
        if not frappe.db.exists(fail.server_type, fail.server):
            # Server doc was deleted — drop the orphaned row.
            frappe.delete_doc("Agent Request Failure", fail.name)
            continue

        if _is_agent_alive(fail.server, fail.server_type):
            frappe.delete_doc("Agent Request Failure", fail.name)


def _is_agent_alive(server_name: str, server_type: str) -> bool:
    """Lightweight liveness probe via Agent.ping() (GET /agent/ping with 2s/5s timeouts).

    A successful return — or any HTTP-level error short of a network failure —
    indicates the agent is reachable. We treat ANY exception as 'not alive'
    to stay on the safe side: a failure here means the row stays put for
    another cycle.
    """
    try:
        Agent(server_name, server_type=server_type).ping()
        return True
    except Exception:
        return False
