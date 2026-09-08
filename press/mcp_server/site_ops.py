# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""MCP site-provisioning wrappers : create a site, restore a backup into one.

Thin wrappers over `press.api.site` whitelisted methods so an MCP agent can seed a
throwaway site from an existing database without touching the dashboard. Every other
site operation was already automatable (migrate, update, clone, backup, install app);
these two were the gap.

Each wrapper runs inside the dispatcher's `_as_user()` context, so the underlying
team checks still apply. Mutating wrappers `frappe.db.commit()` explicitly : the MCP
request context does NOT auto-commit (same gotcha as bench_ops and site_run_python),
so without it the change silently rolls back when the request ends.

Uploading the backup itself is deliberately NOT a tool here. MCP dispatch passes JSON
args and a multipart binary body has no representation in that protocol, and
`press.api.site.upload_backup_file` already does the job (streaming, 5 GiB cap, creates
the Remote File). Callers mint a dashboard sid, POST the file to that endpoint, then
pass the returned Remote File docname to `site_create(files=...)` or `site_restore`.
"""

from __future__ import annotations

from typing import Any

import frappe

from press.api import site as site_api



def _assert_site(name: str) -> None:
	if not frappe.db.exists("Site", name):
		frappe.throw(f"Site {name!r} not found", frappe.DoesNotExistError)


def _assert_remote_files(files: dict[str, str]) -> None:
	"""Every supplied value must be an existing Remote File docname.

	Without this check a typo reaches `api.site.restore`, which writes the bad name
	onto the Site and only fails later inside the agent job : the tool would report
	success for a restore that never had a source.
	"""
	for key, value in files.items():
		if value and not frappe.db.exists("Remote File", value):
			frappe.throw(
				f"Remote File {value!r} (for {key!r}) not found. Upload the backup via "
				f"press.api.site.upload_backup_file first and pass the docname it returns.",
				frappe.DoesNotExistError,
			)


def _collect_files(database: str, public: str, private: str, config: str) -> dict[str, str]:
	files = {
		"database": database or "",
		"public": public or "",
		"private": private or "",
		"config": config or "",
	}
	return {k: v for k, v in files.items() if v}


def site_create(
	new_subdomain: str,
	release_group: str,
	apps: list[str] | None = None,
	plan: str = "",
	cluster: str = "",
	server: str = "",
	root_domain: str = "",
	database: str = "",
	public: str = "",
	private: str = "",
	config: str = "",
) -> dict[str, Any]:
	"""Create a site on a specific Release Group, optionally seeded from a backup.

	`new_subdomain` is the subdomain only : api.site.new joins it with the root domain
	itself. Passing a Remote File as `database` restores at creation time rather than
	as a second step, which is how the dashboard's New Site + Restore flow works.
	"""
	if not frappe.db.exists("Release Group", release_group):
		frappe.throw(f"Release Group {release_group!r} not found", frappe.DoesNotExistError)

	subdomain = (new_subdomain or "").strip().lower()
	if not subdomain:
		frappe.throw("new_subdomain is required")
	if "." in subdomain:
		frappe.throw(
			f"new_subdomain must be a subdomain, not an FQDN : got {new_subdomain!r}. "
			f"Pass 'mysite' and let 'root_domain' supply the rest."
		)

	root_domain = root_domain or frappe.db.get_single_value("Press Settings", "domain")
	fqdn = f"{subdomain}.{root_domain}"
	if frappe.db.exists("Site", fqdn):
		frappe.throw(f"Site {fqdn!r} already exists")

	files = _collect_files(database, public, private, config)
	if files:
		_assert_remote_files(files)

	payload = {
		"name": subdomain,
		"group": release_group,
		"apps": apps or ["frappe"],
		"domain": root_domain,
		"cluster": cluster or "",
		"plan": plan or "",
		"server": server or "",
		"files": files,
	}
	result = site_api.new(payload)
	frappe.db.commit()

	created = result.get("site") if isinstance(result, dict) else result
	return {
		"site": created or fqdn,
		"group": release_group,
		"apps": payload["apps"],
		"restored_from": files or None,
		"created": True,
	}


def site_restore(
	site: str,
	database: str = "",
	public: str = "",
	private: str = "",
	config: str = "",
	skip_failing_patches: bool = False,
	skip_tables: list[str] | None = None,
) -> dict[str, Any]:
	"""Restore backup files into an EXISTING site. Overwrites its database.

	High-risk by design : there is no undo. Use site_create(files=...) when the target
	is a fresh site, and this when refreshing a site that already exists.
	"""
	_assert_site(site)

	files = _collect_files(database, public, private, config)
	if not files:
		frappe.throw(
			"At least one of database/public/private/config is required : "
			"each takes a Remote File docname."
		)
	_assert_remote_files(files)

	site_api.restore(
		name=site,
		files=files,
		skip_failing_patches=bool(skip_failing_patches),
		skip_tables=skip_tables or [],
	)
	frappe.db.commit()

	# Report what Press actually did, not what we asked for. A hardcoded
	# "queued" is how site_config_set came to answer "set" for a call that had
	# raised : the caller then polls for a job that was never created. Read the
	# state back instead.
	site_status = frappe.db.get_value("Site", site, "status")
	job = frappe.get_all(
		"Agent Job",
		filters={"site": site, "job_type": ("like", "%Restore%")},
		fields=["name", "status", "creation"],
		order_by="creation desc",
		limit=1,
	)

	return {
		"site": site,
		"files": files,
		"skip_failing_patches": bool(skip_failing_patches),
		"skip_tables": skip_tables or [],
		"site_status": site_status,
		"agent_job": job[0].name if job else None,
		"agent_job_status": job[0].status if job else None,
		"note": (
			"Restore runs as an agent job. agent_job is the job Press created : if it is "
			"null, nothing was queued. Poll agent_job_progress or site_status for progress."
		),
	}
