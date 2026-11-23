# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""The browser code editor (code-server) of a bench: status, setup, password rotation and expiry, restart
(moved from bench_dev_overview.py in 0.7.56)."""

import frappe

from press.utils import ensure_team_access


def _can_use_code_server(bench_name, team):
	"""Non-raising variant of the role check — returns bool for UI rendering.

	Logs unexpected exceptions via frappe.log_error so silent denial doesn't
	mask bugs (e.g. schema changes, import failures, cross-team probes).
	"""
	from press.api.feature_access import has_feature
	try:
		return bool(has_feature(team=team, feature_id="code_server"))
	except Exception:
		frappe.log_error(
			title="Code Server can_use probe failed",
			message=f"bench={bench_name} team={team}\n{frappe.get_traceback()}",
		)
		return False


@frappe.whitelist()
def get_code_server_status(bench_name):
	"""Return code-server status and URL for a bench (if one exists)."""
	ensure_team_access(bench_name=bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	cs_row = frappe.db.get_value(
		"Code Server",
		{"bench": bench_name, "status": ["!=", "Archived"]},
		["name", "status", "password", "password_set_at", "password_expiry_days"],
		as_dict=True,
	)
	result = {
		"enabled": bool(bench.is_code_server_enabled) or bool(bench.is_development_bench),
		"can_use": _can_use_code_server(bench_name, bench.team),
		"exists": bool(cs_row),
		"name": cs_row.name if cs_row else None,
		"status": cs_row.status if cs_row else None,
		"url": f"https://{cs_row.name}" if cs_row and cs_row.status == "Running" else None,
		"password": None,
	}
	if cs_row:
		# Always attach expiry info (even while Pending) so UI can render countdown.
		# Password fieldtype masks via frappe.db.get_value — must call get_password()
		# on the doc to decrypt. Only return it when Running.
		cs_doc = frappe.get_doc("Code Server", cs_row.name)
		if cs_row.status == "Running":
			result["password"] = cs_doc.get_password("password")
		result["password_set_at"] = cs_row.password_set_at
		result["password_expires_at"] = cs_doc.get_password_expires_at()
		result["password_expiry_days"] = cs_doc.get_password_expiry_days()
		result["password_is_expired"] = cs_doc.is_password_expired()
	return result


def _ensure_code_server_role_access(bench_name):
	"""Team-member check + role-level Code Server feature-access check.

	Use at every Code Server mutation endpoint. Returns the team name on success
	so callers don't re-query. Raises PermissionError when the caller's role has
	Code Server disabled — the role/team config is enforced by has_feature.
	"""
	ensure_team_access(bench_name=bench_name)
	team = frappe.db.get_value("Bench", bench_name, "team")
	from press.api.feature_access import has_feature
	if not has_feature(team=team, feature_id="code_server"):
		frappe.throw(
			"Code Server is not enabled for your role. Ask an admin to grant the Code Server feature on your role.",
			frappe.PermissionError,
		)
	return team


@frappe.whitelist()
def setup_code_server(bench_name, subdomain):
	"""Create and setup a Code Server for a bench."""
	_ensure_code_server_role_access(bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	# Code Server is available for all benches in this Press instance.
	# The Code Server doctype validate() requires Bench.is_code_server_enabled,
	# AND the bench container's supervisor.conf needs a [program:code-server]
	# block which is only rendered when is_code_server_enabled is in the bench
	# config JSON. save() triggers Bench.on_update → update_bench_config job
	# which regenerates supervisor.conf + reread + update inside the container.
	# Without this, "Setup Code Server" fails with "supervisorctl start code-server:"
	# exit 2 (program not found).
	# Flag lives in TWO places: the Bench DB column (Code Server validate gate)
	# and the bench_config JSON (agent's supervisor.conf template reads this).
	#
	# bench.save() unfortunately resets this field back to 0 somewhere in
	# Press's validate chain (the rebuild of bench_config reads self.
	# is_code_server_enabled at line 345 of bench.py but something earlier
	# clears it — even direct assignment before save() fails). So we bypass
	# the doctype save entirely: write both column and JSON directly, then
	# manually queue the Update Bench Configuration agent job to regenerate
	# supervisor.conf inside the container.
	import json as _json
	from press.agent import Agent
	config_json = _json.loads(bench.bench_config or "{}")
	if not bench.is_code_server_enabled or not config_json.get("is_code_server_enabled"):
		config_json["is_code_server_enabled"] = True
		frappe.db.set_value(
			"Bench",
			bench_name,
			{
				"is_code_server_enabled": 1,
				"bench_config": _json.dumps(config_json, indent=4),
			},
			update_modified=False,
		)
		frappe.db.commit()
		# Reload bench so Agent.update_bench_config sees the new JSON
		bench = frappe.get_doc("Bench", bench_name)
		Agent(bench.server).update_bench_config(bench)
	# Block retry if there's a non-archived Code Server already
	existing = frappe.db.exists("Code Server", {"bench": bench_name, "status": ["!=", "Archived"]})
	if existing:
		return {"error": f"Code Server already exists: {existing}"}

	# Clean up orphan Archived rows with the same target name — the Code Server
	# doctype name is subdomain+domain, so archived failed attempts collide with
	# new creates. Delete them to free the name for a clean retry.
	domain = frappe.db.get_value("Press Settings", None, "domain") or "sandbox.mvpstorm.com"
	candidate_name = f"{subdomain}.{domain}"
	for stale in frappe.db.get_all(
		"Code Server",
		filters={"name": candidate_name, "status": "Archived"},
		pluck="name",
	):
		frappe.delete_doc("Code Server", stale, force=True, ignore_permissions=True)
	frappe.db.commit()

	cs = frappe.get_doc({
		"doctype": "Code Server",
		"bench": bench_name,
		"subdomain": subdomain,
		"domain": domain,
		"server": bench.server,
	})
	cs.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": cs.name, "status": "Pending"}


@frappe.whitelist()
def rotate_code_server_password(bench_name):
	"""Rotate the Code Server password for this bench. Team-member access only."""
	_ensure_code_server_role_access(bench_name)
	name = frappe.db.exists(
		"Code Server", {"bench": bench_name, "status": ["!=", "Archived"]}
	)
	if not name:
		return {"error": "No active Code Server for this bench"}
	doc = frappe.get_doc("Code Server", name)
	return doc.rotate_password()


@frappe.whitelist()
def restart_code_server(bench_name):
	"""Restart the Code Server process for this bench.

	Idempotent recovery path: re-asserts is_code_server_enabled on the bench,
	queues an agent config update (so supervisor.conf regenerates with the
	code-server block), then starts the process with the current password.
	Team-member access only.
	"""
	_ensure_code_server_role_access(bench_name)
	import json as _json
	from press.agent import Agent
	from frappe.utils.password import get_decrypted_password

	cs_name = frappe.db.exists(
		"Code Server", {"bench": bench_name, "status": ["!=", "Archived"]}
	)
	if not cs_name:
		return {"error": "No active Code Server for this bench — click Launch Code Server first."}

	bench = frappe.get_doc("Bench", bench_name)
	# Always re-assert the flag in BOTH places (column + bench_config JSON) even
	# if they look set — the canonical cause of a broken CS is that one of them
	# drifted. Writing both then queueing update_bench_config guarantees the
	# agent regenerates supervisor.conf with the code-server block before we try
	# to start the process.
	config_json = _json.loads(bench.bench_config or "{}")
	config_json["is_code_server_enabled"] = True
	frappe.db.set_value(
		"Bench",
		bench_name,
		{"is_code_server_enabled": 1, "bench_config": _json.dumps(config_json, indent=4)},
		update_modified=False,
	)
	frappe.db.commit()
	bench = frappe.get_doc("Bench", bench_name)

	agent = Agent(bench.server, server_type="Server")
	# Always queue update_bench_config — this regenerates supervisor.conf with the
	# code-server block (required before start_code_server can find the program).
	# Agent Jobs on the same bench run sequentially, so start_code_server will see
	# the fresh supervisor when it runs.
	try:
		agent.update_bench_config(bench)
	except Exception as e:
		frappe.log_error(title="Restart Code Server: update_bench_config failed", message=str(e))
		return {"error": "Failed to queue config update — check Error Log"}

	password = get_decrypted_password("Code Server", cs_name, "password")
	try:
		agent.start_code_server(bench_name, cs_name, password)
		frappe.db.set_value("Code Server", cs_name, "status", "Pending", update_modified=False)
		frappe.db.commit()
	except Exception as e:
		frappe.log_error(title="Restart Code Server: start_code_server failed", message=str(e))
		return {"error": "Failed to queue start job — check Error Log"}

	return {"restarted": True, "status": "Pending"}


@frappe.whitelist()
def set_code_server_password_expiry_days(bench_name, days):
	"""Set the per-CS override for how many days the password stays valid.

	Pass 0 (or empty) to clear the override — the global Press Settings default applies.
	Team-member access only.
	"""
	_ensure_code_server_role_access(bench_name)
	try:
		days_int = int(days or 0)
	except (TypeError, ValueError):
		frappe.throw("days must be an integer")
	if days_int < 0:
		frappe.throw("days must be zero or positive")
	name = frappe.db.exists(
		"Code Server", {"bench": bench_name, "status": ["!=", "Archived"]}
	)
	if not name:
		return {"error": "No active Code Server for this bench"}
	frappe.db.set_value("Code Server", name, "password_expiry_days", days_int)
	frappe.db.commit()
	return {"updated": True, "password_expiry_days": days_int}
