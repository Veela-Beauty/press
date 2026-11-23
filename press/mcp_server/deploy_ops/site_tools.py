# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Site tools over MCP: status, a scheduled update, the sites of a release group, and a one-use dashboard
login link (moved from deploy_flow.py in 0.7.54)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import add_to_date, now_datetime


@frappe.whitelist()
def site_schedule_update(
	site_name: str,
	skip_failing_patches: bool = False,
	skip_backups: bool = False,
) -> dict[str, Any]:
	"""Schedule a Site Update (migrate to latest bench in same Release Group)."""
	site = frappe.get_doc("Site", site_name)
	job_name = site.schedule_update(
		skip_failing_patches=skip_failing_patches,
		skip_backups=skip_backups,
	)
	return {"site": site_name, "site_update": job_name}


@frappe.whitelist()
def site_status(
	site_name: str,
	jobs_window_minutes: int = 120,
	jobs_limit: int = 10,
) -> dict[str, Any]:
	"""Current site bench + status + recent agent jobs.

	The recent_agent_jobs list is the polling primitive — agents can call
	this repeatedly until the desired job lands in Success or the bench flips.
	Window defaults to 120 minutes so that long-running deploys (build + push +
	migrate cycle commonly takes 10-30 min) stay visible across the full poll
	loop. Use `agent_job_list` for finer control.
	"""
	row = frappe.db.get_value(
		"Site",
		site_name,
		["name", "bench", "status", "modified"],
		as_dict=True,
	)
	if not row:
		frappe.throw(f"Site {site_name!r} does not exist", frappe.DoesNotExistError)
	jobs_window_minutes = max(1, min(1440, int(jobs_window_minutes)))
	jobs_limit = max(1, min(100, int(jobs_limit)))
	since = add_to_date(now_datetime(), minutes=-jobs_window_minutes)
	jobs = frappe.get_all(
		"Agent Job",
		filters={"site": site_name, "creation": (">=", since)},
		fields=["name", "job_type", "status", "creation"],
		order_by="creation desc",
		limit=jobs_limit,
	)
	for j in jobs:
		if j.get("creation"):
			j["creation"] = j["creation"].isoformat()
	return {
		"name": row.name,
		"bench": row.bench,
		"status": row.status,
		"last_modified": row.modified.isoformat() if row.modified else None,
		"recent_agent_jobs": jobs,
	}


@frappe.whitelist()
def list_sites_on_release_group(release_group: str, status: str | None = None) -> list[dict[str, Any]]:
	"""List sites whose bench belongs to the given Release Group, team-scoped.

	`press.api.site.all()` doesn't accept a `release_group` filter — it filters
	by status/tag/team. This shim does the cluster->bench->site join for you.
	Useful for agents wanting "show me every site that'd be touched by a bench
	rebuild of RG X" without manually iterating press.api.site.all().

	Returns list of {name, status, bench, team, host_name}. Team-scoped:
	non-System users only see sites owned by their team.
	"""
	from press.utils import get_current_team

	filters: dict[str, Any] = {"group": release_group}
	if status:
		filters["status"] = status
	if frappe.session.data.user_type != "System User":
		filters["team"] = get_current_team()
	return frappe.get_all(
		"Site",
		filters=filters,
		fields=["name", "status", "bench", "team", "host_name", "group"],
		order_by="creation desc",
		limit=200,
	)


@frappe.whitelist()
def mint_dashboard_login_url(redirect_to: str = "/dashboard") -> dict[str, Any]:
	"""Mint a one-shot ?sid= URL that logs the browser in as the MCP token's
	user on the Press dashboard. Designed for Playwright / E2E tests so they
	don't have to handle password typing or password rotation.

	The token's user (Administrator for the Master token) is logged in via
	Frappe's LoginManager, a real Session row is created, and a URL is
	returned that Frappe's `?sid=<sid>` handler will pick up as the session
	cookie. No password is ever transmitted by the caller.

	Args:
		redirect_to: dashboard path to land on after auth, default
			'/dashboard'. Common choices: '/dashboard/devtools/mcp',
			'/dashboard/sites/<site>/overview'.

	Returns:
		{
			"url": "https://<press-host>/<redirect>?sid=<sid>",
			"sid": <sid>,
			"user": <user that owns the session>,
			"expires_in_seconds": <int — inherits the Press session TTL>,
		}

	Audit: the login is recorded in Frappe's standard Activity Log + the MCP
	Call Log (via the dispatcher's _log_call). Anyone with bench console can
	revoke the SID via `frappe.local.session.sid = None` + db.commit().
	"""
	from frappe.auth import LoginManager

	target_user = frappe.session.user
	if not target_user or target_user == "Guest":
		frappe.throw(
			"mint_dashboard_login_url: token does not resolve to a Press user",
			frappe.PermissionError,
		)

	# Mint a real session via LoginManager (creates the Sessions row +
	# rotates frappe.session.sid). Frappe's CookieManager handles the
	# rest when the browser hits ?sid=<sid>.
	lm = LoginManager()
	lm.login_as(target_user)
	sid = frappe.session.sid
	if not sid or sid == "Guest":
		frappe.throw(
			"mint_dashboard_login_url: LoginManager did not produce a usable SID",
			frappe.ValidationError,
		)
	frappe.db.commit()

	# Press session lifetime — Frappe defaults to 6 hours unless overridden
	# in System Settings.session_expiry. Best-effort: don't fail if missing.
	try:
		expiry = frappe.db.get_single_value("System Settings", "session_expiry") or "06:00:00"
		h, m, *_ = (str(expiry).split(":") + ["0"])[:2]
		expires_in_seconds = int(h) * 3600 + int(m) * 60
	except Exception:  # noqa: BLE001
		expires_in_seconds = 21600

	# Normalize redirect path
	if not redirect_to.startswith("/"):
		redirect_to = "/" + redirect_to

	base = frappe.utils.get_url().rstrip("/")
	url = f"{base}{redirect_to}?sid={sid}"
	return {
		"url": url,
		"sid": sid,
		"user": target_user,
		"expires_in_seconds": expires_in_seconds,
	}
