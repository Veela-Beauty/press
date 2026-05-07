# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import frappe

from press.api.site import _new

VALID_MODES = ("latest_backup", "fresh_backup", "empty")


@frappe.whitelist()
def clone_site(
	site: str,
	target_bench: str,
	new_subdomain: str,
	mode: str = "latest_backup",
) -> str:
	"""Clone a Site onto target_bench with three data-source modes.

	Returns the name of the new Site.
	"""
	if mode not in VALID_MODES:
		frappe.throw(
			f"mode must be one of {VALID_MODES}, got {mode!r}",
			frappe.ValidationError,
		)

	source = frappe.get_doc("Site", site)
	_check_team_access(source)

	bench = frappe.get_doc("Bench", target_bench)
	domain = source.domain
	full_name = f"{new_subdomain}.{domain}"
	if frappe.db.exists("Site", full_name):
		frappe.throw(
			f"Site {full_name} already exists",
			frappe.ValidationError,
		)

	payload = {
		"name": new_subdomain,
		"domain": domain,
		"apps": [a.app for a in source.apps],
		"group": bench.group,
		"cluster": source.cluster,
		"plan": source.plan,
		"version": source.version,
		"bench": target_bench,
	}

	if mode == "latest_backup":
		files = _get_latest_backup_files(source.name)
		if not files:
			frappe.throw(
				f"No usable offsite backup found for site {source.name}",
				frappe.ValidationError,
			)
		payload["files"] = files
	elif mode == "fresh_backup":
		files = _trigger_fresh_backup_and_get_files(source)
		payload["files"] = files
	# else mode == "empty": no files key added

	return _call_press_new(payload)


def _call_press_new(payload: dict) -> str:
	return _new(payload)


def _get_latest_backup_files(site_name: str) -> dict | None:
	backups = frappe.get_all(
		"Site Backup",
		filters={
			"site": site_name,
			"status": "Success",
			"files_availability": "Available",
			"offsite": 1,
		},
		order_by="creation desc",
		limit=1,
		pluck="name",
	)
	if not backups:
		return None
	b = frappe.get_doc("Site Backup", backups[0])
	return {
		"config": b.remote_config_file,
		"database": b.remote_database_file,
		"public": b.remote_public_file,
		"private": b.remote_private_file,
	}


def _trigger_fresh_backup_and_get_files(source) -> dict:
	backup = source.backup(with_files=True, offsite=True)
	backup.reload()
	if backup.status != "Success" or not backup.files_availability == "Available":
		frappe.throw(
			"Fresh backup not yet ready. Retry in a few minutes "
			"or use latest_backup mode.",
			frappe.ValidationError,
		)
	return {
		"config": backup.remote_config_file,
		"database": backup.remote_database_file,
		"public": backup.remote_public_file,
		"private": backup.remote_private_file,
	}


def _check_team_access(source) -> None:
	"""Mirror Press's standard pattern: System Users bypass team check."""
	if frappe.session.data.user_type == "System User":
		return
	from press.utils import get_current_team

	team = get_current_team(get_doc=True)
	if source.team != team.name:
		frappe.throw(
			f"You don't have access to site {source.name}",
			frappe.PermissionError,
		)
