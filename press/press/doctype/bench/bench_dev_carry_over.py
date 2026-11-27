"""Keep a development bench and its Code Server across a deploy.

A deploy builds a new bench and moves the sites onto it. The new bench starts as a
normal bench, so without this the development flag and Code Server stay on the old
bench, which then archives. When the new bench becomes Active and the bench it
replaces (same release group, same server) is a development bench, the new bench
becomes one too and gets its own Code Server. The old Code Server is archived when
the old bench archives (Bench.archive).

Runs from a background job as Administrator, so it skips the role checks of
Bench.set_development_bench and setup_code_server, which exist for people clicking.
"""

import re

import frappe


def code_server_subdomain(bench_name: str) -> str:
	"""Same rule as the dashboard: "code-" plus the bench name cut to 30 characters."""
	return "code-" + re.sub(r"[^a-z0-9]", "-", bench_name)[:30]


def _live_code_server(bench_name: str):
	return frappe.db.exists("Code Server", {"bench": bench_name, "status": ["!=", "Archived"]})


def carry_over_development_bench(bench_name: str):
	"""Idempotent: safe to run again for the same bench."""
	new = frappe.db.get_value(
		"Bench", bench_name, ["status", "group", "server", "creation", "is_development_bench"], as_dict=True
	)
	if not new or new.status != "Active":
		return

	old_benches = frappe.get_all(
		"Bench",
		filters={
			"group": new.group,
			"server": new.server,
			"status": "Active",
			"is_development_bench": 1,
			"name": ["!=", bench_name],
			"creation": ["<", new.creation],
		},
		pluck="name",
	)
	if not old_benches:
		return

	if not new.is_development_bench:
		frappe.db.set_value("Bench", bench_name, "is_development_bench", 1)
		frappe.db.commit()
		try:
			from press.press.doctype.bench.bench_dev_watch import start_watch

			start_watch(frappe.get_doc("Bench", bench_name))
		except Exception:
			frappe.log_error(title="Dev bench carry-over: bench watch failed", message=bench_name)

	if _live_code_server(bench_name) or not any(_live_code_server(b) for b in old_benches):
		return
	try:
		from press.press.doctype.bench.dev_overview.code_server import create_code_server

		create_code_server(bench_name, code_server_subdomain(bench_name))
	except Exception:
		frappe.log_error(title="Dev bench carry-over: Code Server setup failed", message=bench_name)


def archive_code_server_of_bench(bench_name: str):
	"""Archive the bench's live Code Server (DNS, upstream, container) before the bench archives."""
	name = frappe.db.exists("Code Server", {"bench": bench_name, "status": ["in", ["Running", "Stopped", "Broken"]]})
	if not name:
		return
	try:
		frappe.get_doc("Code Server", name).archive()
	except Exception:
		frappe.log_error(title="Archive Code Server before bench archive failed", message=name)
