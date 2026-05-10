"""Backfill: sync every existing Team Member to a matching Press Role User
membership so the dashboard's user_permissions API returns the right flags.

Why: we added Team Member.press_role (text Custom Field) in 2026-04-23 but
never wired it to the stock Press Role doctype + Press Role User child
that `press.api.account.user_permissions` actually queries. Result: users
appeared as "Platform Admin" / "DevOps Admin" but had no actual action
permissions in the dashboard (Update / Restart / Deploy buttons missing).

This patch walks every Team Member, calls sync_team_member, and creates/
updates the matching Press Role + Press Role User rows. Idempotent — safe
to re-run. New Team Member inserts/updates flow through the doc_events hook
in hooks.py from now on.
"""
import frappe

from press.press.doctype.team.press_role_bridge import backfill_all_team_members


def execute():
	result = backfill_all_team_members()
	frappe.logger().info(
		f"sync_team_member_to_press_role backfill: scanned={result['scanned']} "
		f"synced={result['synced']} errors={len(result['errors'])}"
	)
	if result["errors"]:
		# Log first 10 errors — full list goes to the error log if needed
		for err in result["errors"][:10]:
			frappe.logger().warning(f"  sync error: {err}")
	# Print to stdout so `bench migrate` shows progress
	print(
		f"[press_role_bridge backfill] scanned={result['scanned']} "
		f"synced={result['synced']} errors={len(result['errors'])}"
	)
