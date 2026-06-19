"""Trigger a deploy of latest wazin_mx commit on bench-0005 release group."""
from __future__ import annotations

import frappe


RG_NAME = "bench-0005"
APP = "wazin_mx"


def run():
	rg = frappe.get_doc("Release Group", RG_NAME)

	current_hash = next(
		(a.hash for a in rg.apps if a.app == APP), None
	)
	print(f"PRESS_LOG current {APP} hash on RG: {current_hash[:10] if current_hash else None}")

	# 1. Pull latest commit info from GitHub for the wazin_mx app
	rg.fetch_latest_app_update(APP)
	rg.reload()
	new_hash = next(
		(a.hash for a in rg.apps if a.app == APP), None
	)
	print(f"PRESS_LOG fetched latest {APP} hash: {new_hash[:10] if new_hash else None}")

	if not new_hash:
		print("PRESS_LOG no new release fetched; aborting")
		return None

	if new_hash == current_hash:
		print("PRESS_LOG hash unchanged — RG already at latest. Will still create a DC to force rebuild.")

	# 2. Create new Deploy Candidate. Press requires explicit apps_to_ignore list,
	# default empty means deploy all apps from RG.
	dc = rg.create_deploy_candidate()
	print(f"PRESS_LOG DC created: {dc.name} status={dc.status}")

	# 3. Approve + build. Press worker picks up Approved DC and starts the build.
	dc.deploy_to_production()
	print(f"PRESS_LOG DC {dc.name} deploy_to_production triggered")

	frappe.db.commit()
	return dc.name
