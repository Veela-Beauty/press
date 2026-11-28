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
from frappe.utils import cint

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

	if not plan or not frappe.db.exists("Site Plan", plan):
		plans = frappe.get_all("Site Plan", filters={"enabled": 1, "document_type": "Site"}, pluck="name")
		why = f"plan {plan!r} is not a Site Plan" if plan else "plan is required"
		frappe.throw(f"{why}: pass a Site Plan name, one of {plans}")

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
		"plan": plan,
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


def _deactivated_at(name: str):
	"""When the site was switched off: its last Deactivate Site activity, else its last change."""
	at = frappe.db.get_value(
		"Site Activity", {"site": name, "action": "Deactivate Site"}, "creation", order_by="creation desc"
	)
	return at or frappe.db.get_value("Site", name, "modified")


def _backup_problem(backup) -> str | None:
	"""Why this Site Backup cannot be trusted to bring the site back, or None when it can.

	Only an offsite copy survives the archive (a local backup lives in the site folder the
	archive deletes), and a backup is only as good as its database file in storage.
	"""
	if backup.status != "Success":
		return f"backup {backup.name} is {backup.status}"
	if not backup.offsite or backup.files_availability == "Unavailable":
		return f"backup {backup.name} has no offsite copy"
	if not (backup.with_files and backup.remote_public_file and backup.remote_private_file):
		return f"backup {backup.name} has no public and private files"
	for remote in (backup.remote_database_file, backup.remote_public_file, backup.remote_private_file):
		row = remote and frappe.db.get_value("Remote File", remote, ["status", "file_size"], as_dict=True)
		if not row or row.status == "Unavailable":
			return f"backup {backup.name}: file {remote!r} is missing from storage"
	size = frappe.db.get_value("Remote File", backup.remote_database_file, "file_size")
	if not cint(size):
		return f"backup {backup.name}: the database file is empty"
	return None


def _backup_since(name: str, since):
	rows = frappe.get_all(
		"Site Backup",
		filters={"site": name, "creation": (">=", since)},
		fields=[
			"name", "status", "offsite", "with_files", "files_availability",
			"remote_database_file", "remote_public_file", "remote_private_file",
		],
		order_by="creation desc",
		limit=1,
	)
	return rows[0] if rows else None


def site_archive(name: str) -> dict[str, Any]:
	"""Archive a switched-off site, only once a healthy offsite backup of it exists.

	Only an Inactive site is accepted, so dropping a site always takes site_deactivate
	first and one wrong call can never drop a live site. The site must also have a
	healthy offsite backup (with files) taken after it was switched off: when it has
	none, this call starts one and returns; call again until it reports the archive.
	"""
	_assert_site(name)
	status = frappe.db.get_value("Site", name, "status", for_update=True)
	if status != "Inactive":
		frappe.throw(
			f"Site {name!r} is {status}. Only a deactivated (Inactive) site can be archived : "
			"run site_deactivate first, once you are sure nobody uses it.",
			frappe.ValidationError,
		)

	backup = _backup_since(name, _deactivated_at(name))
	if backup and backup.status in ("Pending", "Running"):
		return {"site": name, "stage": "backup_running", "backup": backup.name,
			"note": "The backup taken before the archive is still running. Call site_archive again."}
	problem = _backup_problem(backup) if backup else "no backup since the site was switched off"
	if problem:
		new = frappe.get_doc("Site", name).backup(with_files=True, offsite=True)
		frappe.db.commit()
		return {"site": name, "stage": "backup_started", "backup": new.name, "reason": problem,
			"note": "A backup with files, offsite, was started first. Call site_archive again once it ends."}

	started = frappe.utils.now_datetime()
	try:
		site_api.archive(name=name, force=False)
	except Exception:
		# Site.archive saves the site as Pending before its later steps; a half-done
		# archive must not be committed, or the site is stuck Pending and cannot retry.
		frappe.db.rollback()
		raise
	frappe.db.commit()

	job = frappe.get_all(
		"Agent Job",
		filters={"site": name, "job_type": "Archive Site", "creation": (">=", started)},
		fields=["name", "status"],
		order_by="creation desc",
		limit=1,
	)
	return {
		"site": name,
		"stage": "archive_queued",
		"backup": backup.name,
		"site_status": frappe.db.get_value("Site", name, "status"),
		"agent_job": job[0].name if job else None,
		"agent_job_status": job[0].status if job else None,
		"note": (
			f"Archive runs as an agent job; on success the site ends Archived. Backup {backup.name} "
			"(offsite, checked) restores it. agent_job is the job this call created : if it is null, "
			"nothing was queued. Poll site_status."
		),
	}
