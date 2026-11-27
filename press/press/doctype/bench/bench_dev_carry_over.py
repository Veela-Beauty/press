"""Keep a development bench and its Code Server across a deploy.

A deploy builds a new bench and moves the sites onto it. The new bench starts as a
normal bench, so without this the development flag and Code Server stay on the old
bench, which then archives. When the new bench becomes Active and the bench it
replaces (same release group, same server) is a development bench, the new bench
becomes one too and gets its own Code Server. The old Code Server is archived once the old
bench is confirmed Archived (process_archive_bench_job_update).

Runs from a job callback as Administrator, so it skips the role checks of
Bench.set_development_bench and setup_code_server, which exist for people clicking. The
Code Server is still skipped (and logged) when the team's roles have the feature off.
"""

import re

import frappe


def code_server_subdomain(bench_name: str) -> str:
	"""Same rule as the dashboard: "code-" plus the bench name cut to 30 characters."""
	return "code-" + re.sub(r"[^a-z0-9]", "-", bench_name)[:30]


def _live_code_server(bench_name: str):
	return frappe.db.exists("Code Server", {"bench": bench_name, "status": ["!=", "Archived"]})


def carry_over_development_bench(bench_name: str):
	"""Mark the new bench as a development bench when the bench it replaces was one.

	Runs inside the "Create Bench" job callback, before archive_obsolete_benches is
	enqueued, so the old bench is still Active and cannot be archived under us. The old
	bench's Code Server is only archived after the old bench is confirmed Archived
	(process_archive_bench_job_update), so the decision made here stays valid for the
	background step. Safe to run twice for the same bench.
	"""
	try:
		new = frappe.db.get_value(
			"Bench",
			bench_name,
			["status", "group", "server", "creation", "is_development_bench"],
			as_dict=True,
		)
		if not new or new.status != "Active":
			return

		old_benches = frappe.get_all(
			"Bench",
			filters={
				"group": new.group,
				"server": new.server,
				"status": ["in", ["Active", "Pending"]],
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

		frappe.enqueue(
			"press.press.doctype.bench.bench_dev_carry_over.finish_development_bench_carry_over",
			enqueue_after_commit=True,
			bench_name=bench_name,
			with_code_server=any(_live_code_server(b) for b in old_benches),
		)
	except Exception:
		frappe.log_error(title="Dev bench carry-over failed", message=bench_name)


def finish_development_bench_carry_over(bench_name: str, with_code_server: bool):
	"""Background step: start bench watch, point the apps at GitHub and, when the old bench had one, create the Code Server."""
	try:
		from press.press.doctype.bench.bench_dev_watch import start_watch

		start_watch(frappe.get_doc("Bench", bench_name))
	except Exception:
		frappe.log_error(title="Dev bench carry-over: bench watch failed", message=bench_name)
	try:
		from press.press.doctype.bench.bench_dev_git import connect_app_remotes

		connect_app_remotes(frappe.get_doc("Bench", bench_name))
	except Exception:
		frappe.log_error(title="Dev bench carry-over: app git remotes failed", message=bench_name)

	if not with_code_server or _live_code_server(bench_name):
		return
	team = frappe.db.get_value("Bench", bench_name, "team")
	try:
		from press.api.feature_access import has_feature

		if not has_feature(team=team, feature_id="code_server"):
			frappe.log_error(
				title="Dev bench carry-over: Code Server skipped, feature is off for the team roles",
				message=bench_name,
			)
			return
		from press.press.doctype.bench.dev_overview.code_server import create_code_server

		create_code_server(bench_name, code_server_subdomain(bench_name))
	except Exception:
		frappe.log_error(title="Dev bench carry-over: Code Server setup failed", message=bench_name)


def archive_code_server_of_bench(bench_name: str):
	"""Archive the bench's live Code Server (DNS, upstream, container) after the bench is confirmed archived."""
	name = frappe.db.exists(
		"Code Server", {"bench": bench_name, "status": ["in", ["Running", "Stopped", "Broken"]]}
	)
	if not name:
		return
	try:
		frappe.get_doc("Code Server", name).archive()
	except Exception:
		frappe.log_error(title="Archive Code Server before bench archive failed", message=name)
