# Copyright (c) 2026, Frappe and contributors
# License: see license.txt
"""Single source of truth for "is this resource decommissioned?" checks
used by Press scheduled crons.

The `is_decommissioned` flag lives ONLY on `tabServer`. Database Server
and Proxy Server doctypes do NOT have their own flag — the app Server's
flag is authoritative for the whole cluster (app + DB + proxy).

When you add a new scheduled cron that picks targets from any of the
lower-level doctypes (Virtual Machine, Site, Bench, Agent Job), check
the linked Server's flag using these helpers BEFORE doing work on the
target. Without this guard, decommissioning a server has no effect on
the scheduler — see 2026-05-21 incident where 1798 wasted Snapshot Disk
jobs accumulated against 4 decommissioned test servers in 2 days.

All helpers fail OPEN — if a lookup itself errors, the function returns
False (don't skip). The cost of a false-negative is one wasted job; the
cost of a false-positive is silently broken scheduling for everyone.

Audit-trail of crons using these helpers: search the codebase for
`from press.utils.decom import` or `decom.is_server_decommissioned`.
"""
from __future__ import annotations

import frappe


def is_server_decommissioned(server_name: str | None) -> bool:
	"""True if the named Server (tabServer.name) is decommissioned.

	Use this in crons that iterate over Server / Database Server / Press Job
	rows and want to skip work for decommissioned servers.

	Fail-open: missing server, lookup error → False (proceed normally).
	"""
	if not server_name:
		return False
	try:
		return bool(frappe.db.get_value("Server", server_name, "is_decommissioned"))
	except Exception:  # noqa: BLE001 — fail open, never block legitimate work
		return False


def is_database_server_in_decommissioned_cluster(db_server_name: str | None) -> bool:
	"""True if the named Database Server belongs to a decommissioned cluster.

	Database Server doctype has no is_decommissioned flag of its own — the
	cluster's app Server is authoritative. Walks the link.
	"""
	if not db_server_name:
		return False
	try:
		app_server = frappe.db.get_value(
			"Server",
			{"database_server": db_server_name, "is_decommissioned": 1},
			"name",
		)
		return bool(app_server)
	except Exception:  # noqa: BLE001
		return False


def is_site_on_decommissioned_server(site_name: str | None) -> bool:
	"""True if the named Site is hosted on a decommissioned server.

	tabSite has `server` (app) and `bench` link columns — NO direct
	`database_server` column. The DB-server check goes through the bench:
	Site → Bench → (server, database_server) → decom check on the cluster.
	"""
	if not site_name:
		return False
	try:
		row = frappe.db.get_value(
			"Site", site_name, ["server", "bench"], as_dict=True
		)
		if not row:
			return False
		if is_server_decommissioned(row.server):
			return True
		# Indirect: walk via Bench to catch DB-server-only decom (rare but possible)
		if row.bench and is_bench_on_decommissioned_server(row.bench):
			return True
		return False
	except Exception:  # noqa: BLE001
		return False


def is_bench_on_decommissioned_server(bench_name: str | None) -> bool:
	"""True if the named Bench is hosted on a decommissioned server.

	tabBench has both `server` and `database_server` columns.
	"""
	if not bench_name:
		return False
	try:
		row = frappe.db.get_value(
			"Bench", bench_name, ["server", "database_server"], as_dict=True
		)
		if not row:
			return False
		if is_server_decommissioned(row.server):
			return True
		if is_database_server_in_decommissioned_cluster(row.database_server):
			return True
		return False
	except Exception:  # noqa: BLE001
		return False


