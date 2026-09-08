"""Stranded-server detection (Sanad fork — not in upstream).

A Server whose `status` is anything other than "Active" is silently and
completely dropped by two schedulers:

  * poll_pending_jobs_server() returns immediately, so NO agent job on that
    server is ever polled again — every job stays Pending forever even though
    the agent has already finished the work.
  * schedule_updates() selects only Active servers, so NO site on that server
    is ever auto-updated — every site is pinned to its current bench.

Neither path logs anything. The dashboard renders the benches as "Pending"
and the sites as normal, so the box reads as busy rather than abandoned.

Observed 2026-09-08: u5-default sat at status "Pending" from 2026-08-31 09:45
while still owning an Active bench and four sites. Four benches froze at
"Pending" and the sites could not leave their 24-day-old bench. The client
reported it as "pending for ever ... and it keep in old bench".

Runs hourly. It deliberately does NOT auto-correct the status: a server can be
legitimately Installing or Broken, and guessing "Active" for a genuinely broken
box would be worse than the silence. The point is to make the state visible.

Wired in press/hooks.py scheduler_events["hourly"].
"""

from __future__ import annotations

import frappe

from press.utils import log_error

# A server in one of these is either working normally or intentionally gone.
EXPECTED_STATUSES = ("Active", "Archived")


def detect_stranded_servers() -> dict:
	"""Report servers excluded from polling and updates that still own live work."""
	stranded = []

	servers = frappe.get_all(
		"Server",
		filters={"status": ("not in", EXPECTED_STATUSES), "is_decommissioned": 0},
		fields=["name", "status"],
	)

	for server in servers:
		active_benches = frappe.db.count("Bench", {"server": server.name, "status": "Active"})
		live_sites = frappe.db.count("Site", {"server": server.name, "status": ("!=", "Archived")})

		if not (active_benches or live_sites):
			# Nothing depends on it yet — a server mid-provision looks like this.
			continue

		stranded.append(
			{
				"server": server.name,
				"status": server.status,
				"active_benches": active_benches,
				"live_sites": live_sites,
			}
		)

		log_error(
			"Stranded Server",
			message=(
				f"Server {server.name} has status {server.status!r}, so Press is neither "
				f"polling its agent jobs nor auto-updating its sites — yet it still owns "
				f"{active_benches} Active bench(es) and {live_sites} live site(s). Every job "
				f"on this server will sit Pending forever until the status is corrected. "
				f"Verify the box is healthy, then set the status back to Active."
			),
			reference_doctype="Server",
			reference_name=server.name,
		)

	return {"checked": len(servers), "stranded": stranded}
