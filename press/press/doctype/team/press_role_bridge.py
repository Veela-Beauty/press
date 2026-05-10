"""Bridge between Team Member.press_role (our role text field) and the
stock Press Role doctype + Press Role User child (what user_permissions
actually checks).

The conflict this fixes:
- We added `Team Member.press_role` (Custom Field) in the 2026-04-23
  team-role-management work. It's a Select field with values like
  "Platform Admin" / "DevOps Admin" / "Developer" etc. Used by our own
  team_roles.has_role_access() + Admin Panel feature gating.
- Stock Press has a separate `Press Role` doctype with 14 boolean flags
  (admin_access, allow_apps, allow_bench_creation, ...) and a child
  table Press Role User. press.api.account.user_permissions joins these
  on (team, user) — that's what the Vue dashboard reads to decide
  whether to render Update/Restart/Deploy buttons.

Without this bridge, setting Team Member.press_role = "Platform Admin"
only changed the badge text — actual action buttons stayed disabled
because no Press Role doc existed for the user on that team.

This module ensures the two stay in sync:
  - When a Team Member is inserted/updated/deleted, sync their Press
    Role User row to match Team Member.press_role.
  - Per (team, role text) we maintain ONE Press Role doc with the
    canonical flags for that role.
"""
from __future__ import annotations

import frappe

# Canonical flag map. One source of truth for "what does each role mean
# in terms of stock Press flags". Update here, sync runs everywhere.
ROLE_TO_FLAGS: dict[str, dict[str, int]] = {
	"Platform Admin": {
		# Full access — same as Eslam's manually-configured role
		"admin_access": 1,
		"all_servers": 1,
		"all_sites": 1,
		"all_release_groups": 1,
		"allow_apps": 1,
		"allow_bench_creation": 1,
		"allow_billing": 1,
		"allow_contribution": 1,
		"allow_customer": 1,
		"allow_dashboard": 1,
		"allow_leads": 1,
		"allow_partner": 1,
		"allow_server_creation": 1,
		"allow_site_creation": 1,
		"allow_webhook_configuration": 1,
	},
	"DevOps Admin": {
		# Manage servers/benches/deploys but NOT billing/partner
		"admin_access": 0,
		"all_servers": 1,
		"all_sites": 1,
		"all_release_groups": 1,
		"allow_apps": 1,
		"allow_bench_creation": 1,
		"allow_billing": 0,
		"allow_contribution": 0,
		"allow_customer": 0,
		"allow_dashboard": 1,
		"allow_leads": 0,
		"allow_partner": 0,
		"allow_server_creation": 1,
		"allow_site_creation": 1,
		"allow_webhook_configuration": 1,
	},
	"DevOps User": {
		# View + trigger but no creation
		"admin_access": 0,
		"all_servers": 1,
		"all_sites": 1,
		"all_release_groups": 1,
		"allow_apps": 1,
		"allow_bench_creation": 0,
		"allow_billing": 0,
		"allow_contribution": 0,
		"allow_customer": 0,
		"allow_dashboard": 1,
		"allow_leads": 0,
		"allow_partner": 0,
		"allow_server_creation": 0,
		"allow_site_creation": 0,
		"allow_webhook_configuration": 0,
	},
	"Developer": {
		# Dev/staging sites + dev tools, no infra
		"admin_access": 0,
		"all_servers": 0,
		"all_sites": 1,
		"all_release_groups": 1,
		"allow_apps": 1,
		"allow_bench_creation": 0,
		"allow_billing": 0,
		"allow_contribution": 0,
		"allow_customer": 0,
		"allow_dashboard": 1,
		"allow_leads": 0,
		"allow_partner": 0,
		"allow_server_creation": 0,
		"allow_site_creation": 1,
		"allow_webhook_configuration": 0,
	},
	"Implementor": {
		# Configure sites, install apps
		"admin_access": 0,
		"all_servers": 0,
		"all_sites": 1,
		"all_release_groups": 0,
		"allow_apps": 1,
		"allow_bench_creation": 0,
		"allow_billing": 0,
		"allow_contribution": 0,
		"allow_customer": 0,
		"allow_dashboard": 1,
		"allow_leads": 0,
		"allow_partner": 0,
		"allow_server_creation": 0,
		"allow_site_creation": 1,
		"allow_webhook_configuration": 0,
	},
	"Viewer": {
		# Read-only dashboard
		"admin_access": 0,
		"all_servers": 0,
		"all_sites": 0,
		"all_release_groups": 0,
		"allow_apps": 0,
		"allow_bench_creation": 0,
		"allow_billing": 0,
		"allow_contribution": 0,
		"allow_customer": 0,
		"allow_dashboard": 1,
		"allow_leads": 0,
		"allow_partner": 0,
		"allow_server_creation": 0,
		"allow_site_creation": 0,
		"allow_webhook_configuration": 0,
	},
}


def _ensure_press_role(team: str, role_title: str) -> str:
	"""Find or create the Press Role doc for (team, role_title) with the
	canonical flags. Returns the Press Role docname.
	"""
	flags = ROLE_TO_FLAGS.get(role_title)
	if not flags:
		# Unknown role — coerce to Viewer so we never silently grant more.
		role_title = "Viewer"
		flags = ROLE_TO_FLAGS["Viewer"]

	existing = frappe.db.get_value(
		"Press Role",
		{"team": team, "title": role_title},
		"name",
	)
	if existing:
		# Make sure flags haven't drifted from canonical (e.g. someone hand-edited)
		current_flags = frappe.db.get_value(
			"Press Role", existing, list(flags.keys()), as_dict=True
		)
		if current_flags and any(current_flags.get(k) != v for k, v in flags.items()):
			for k, v in flags.items():
				frappe.db.set_value("Press Role", existing, k, v, update_modified=False)
		return existing

	# Create a new Press Role for this team/title
	role_doc = frappe.get_doc({
		"doctype": "Press Role",
		"team": team,
		"title": role_title,
		**flags,
	}).insert(ignore_permissions=True)
	return role_doc.name


def _add_user_to_role(role_name: str, user: str) -> bool:
	"""Insert user into Press Role's users child if not already present.
	Returns True if a row was added.
	"""
	if frappe.db.exists("Press Role User", {"parent": role_name, "user": user}):
		return False
	rid = frappe.generate_hash(length=10)
	frappe.db.sql(
		"""INSERT INTO `tabPress Role User`
		(name, parent, parenttype, parentfield, user,
		 creation, modified, owner, modified_by, docstatus, idx)
		VALUES (%s, %s, 'Press Role', 'users', %s,
		        NOW(), NOW(), 'Administrator', 'Administrator', 0, 1)""",
		(rid, role_name, user),
	)
	return True


def _remove_user_from_role(role_name: str, user: str) -> bool:
	"""Remove user from Press Role's users child. Returns True if removed."""
	row = frappe.db.get_value(
		"Press Role User", {"parent": role_name, "user": user}, "name"
	)
	if not row:
		return False
	frappe.db.delete("Press Role User", {"name": row})
	return True


def _bust_user_permissions_cache(team: str, user: str) -> None:
	"""Clear the 5-min cache so the dashboard sees updated permissions on
	the next API call instead of waiting for the cache to expire."""
	try:
		frappe.cache.delete_value(f"user_permissions.{team}.{user}")
	except Exception:
		# Cache failures must never break the bridge.
		pass


def sync_team_member(doc, method=None) -> None:
	"""doc_event hook on Team Member — sync user's Press Role membership
	to match Team Member.press_role.

	Bound to after_insert + on_update + on_trash in hooks.py.

	The flow:
	1. Read Team Member.parent (team) + .user + .press_role
	2. Ensure a Press Role doc exists for (team, press_role) with canonical flags
	3. If on_trash: remove user from the role's users child
	4. Else: add user to the role's users child + remove from any OTHER role on this team
	5. Clear user_permissions cache for (team, user)
	"""
	if _is_bridge_disabled():
		return
	team = doc.parent
	user = doc.get("user")
	role = doc.get("press_role") or "Viewer"
	if not team or not user:
		return

	# on_trash → remove from all roles on this team
	if method == "on_trash":
		role_names = frappe.db.get_all(
			"Press Role", filters={"team": team}, pluck="name"
		)
		for rn in role_names:
			_remove_user_from_role(rn, user)
		_bust_user_permissions_cache(team, user)
		return

	# Insert/update path — ensure target role exists, add user, clean up old
	target_role = _ensure_press_role(team, role)
	_add_user_to_role(target_role, user)

	# Remove from any OTHER Press Role on this team (so role changes are clean)
	other_roles = frappe.db.get_all(
		"Press Role",
		filters={"team": team, "name": ("!=", target_role)},
		pluck="name",
	)
	for rn in other_roles:
		_remove_user_from_role(rn, user)

	_bust_user_permissions_cache(team, user)


def backfill_all_team_members() -> dict:
	"""Walk every Team Member row and sync them. Idempotent. Used by patches.

	Returns: {scanned, synced, errors}
	"""
	scanned = 0
	synced = 0
	errors: list[str] = []
	rows = frappe.db.get_all(
		"Team Member",
		fields=["name", "parent", "user", "press_role"],
		limit=0,  # Frappe convention for "all"
	)
	for r in rows:
		scanned += 1
		try:
			# Synthesize a doc-like object the hook expects
			doc = frappe._dict(
				name=r.name,
				parent=r.parent,
				user=r.user,
				press_role=r.press_role,
			)
			# Bind .get for hook compatibility — frappe._dict already does this
			sync_team_member(doc, method="after_insert")
			synced += 1
		except Exception as e:
			errors.append(f"team={r.parent} user={r.user}: {e!r}")
	frappe.db.commit()
	return {"scanned": scanned, "synced": synced, "errors": errors}


# ── Guards (added 2026-05-10) ────────────────────────────────────────────────


def _is_bridge_disabled() -> bool:
	"""Emergency safety valve: site_config flag disable_press_role_bridge=1
	disables ALL bridge enforcement (validate + sync + audit). Used during
	migrations or recovery when you need to hand-edit Press Role docs without
	the bridge fighting back. Set in site_config.json + clear cache.
	"""
	try:
		return bool(frappe.conf.get("disable_press_role_bridge"))
	except Exception:
		return False


def validate_press_role_flags(doc, method=None) -> None:
	"""Guard 1: doc_events validate hook on Press Role.

	If a Press Role's title is one of our canonical roles (Platform Admin /
	DevOps Admin / Developer / etc.), enforce that its flags match
	ROLE_TO_FLAGS. Prevents silent drift from someone unchecking
	'admin_access' on a Platform Admin role through the Desk UI.

	Custom roles (titles NOT in ROLE_TO_FLAGS like 'OptiFlowERP Developer')
	are left alone — admins can hand-craft those.
	"""
	if _is_bridge_disabled():
		return
	title = doc.get("title")
	if not title or title not in ROLE_TO_FLAGS:
		return  # Custom role — admin owns the flags
	canonical = ROLE_TO_FLAGS[title]
	drift: list[str] = []
	for flag, expected in canonical.items():
		actual = doc.get(flag)
		# Coerce truthy/falsy to 0/1 for comparison
		if int(bool(actual)) != int(bool(expected)):
			drift.append(f"{flag}: expected={expected} got={actual}")
	if drift:
		# Auto-correct silently — log a warning so we know it happened, but
		# don't throw (would block legitimate doc.save() in the bridge itself).
		# The validate hook fires INSIDE the bridge's flag-fix path; throwing
		# would cause a chicken-and-egg problem. Soft-correct + log instead.
		for flag, expected in canonical.items():
			doc.set(flag, expected)
		frappe.logger("press_role_bridge").info(
			f"validate_press_role_flags: corrected drift on {doc.name} "
			f"(title={title!r}): {'; '.join(drift)}"
		)


def audit_press_role_drift() -> dict:
	"""Guard 2: scheduler daily — walk all Team Members + Press Roles,
	re-sync any drift detected.

	Catches:
	- Team Members whose press_role text doesn't match their Press Role User
	  membership (someone hand-edited tabPress Role User SQL-direct)
	- Press Role docs whose flags drifted from canonical (someone unchecked
	  flags through the Desk UI)
	- Team Members with no Press Role User row at all (legacy data, missed
	  inserts during a migration)

	Returns: {team_members_scanned, drift_corrected, errors}
	Logs to frappe error log if drift_corrected > 0 so we get a notification.
	"""
	if _is_bridge_disabled():
		return {"team_members_scanned": 0, "drift_corrected": 0, "skipped": True}

	scanned = 0
	corrected = 0
	errors: list[str] = []

	# Phase 1: re-sync every Team Member (catches missing/wrong Press Role memberships)
	tm_rows = frappe.db.get_all(
		"Team Member",
		fields=["name", "parent", "user", "press_role"],
		limit=0,
	)
	for r in tm_rows:
		scanned += 1
		try:
			# Snapshot which Press Role this user is in BEFORE sync
			before = frappe.db.get_value(
				"Press Role User",
				{"user": r.user},
				"parent",
				cache=False,
			)
			doc = frappe._dict(
				name=r.name, parent=r.parent, user=r.user, press_role=r.press_role,
			)
			sync_team_member(doc, method="after_insert")
			# Check if anything actually changed
			after = frappe.db.get_value(
				"Press Role User",
				{"user": r.user, "parent": ("in", frappe.db.get_all(
					"Press Role", filters={"team": r.parent}, pluck="name"
				) or ["__none__"])},
				"parent",
				cache=False,
			)
			if before != after:
				corrected += 1
		except Exception as e:
			errors.append(f"team={r.parent} user={r.user}: {e!r}")

	# Phase 2: audit Press Role flag drift on canonical titles
	all_canonical_roles = frappe.db.get_all(
		"Press Role",
		filters={"title": ("in", list(ROLE_TO_FLAGS.keys()))},
		fields=["name", "title"] + [f for f in ROLE_TO_FLAGS["Platform Admin"]],
	)
	for role in all_canonical_roles:
		canonical = ROLE_TO_FLAGS.get(role.title)
		if not canonical:
			continue
		drift_flags: dict[str, int] = {}
		for flag, expected in canonical.items():
			if int(bool(role.get(flag))) != int(bool(expected)):
				drift_flags[flag] = expected
		if drift_flags:
			for flag, expected in drift_flags.items():
				frappe.db.set_value(
					"Press Role", role.name, flag, expected, update_modified=False
				)
			corrected += 1

	frappe.db.commit()

	if corrected > 0:
		# Log so we get a daily-digest notification of any drift
		frappe.log_error(
			title="press_role_bridge: drift corrected during audit",
			message=(
				f"Daily audit corrected {corrected} drift event(s) across "
				f"{scanned} Team Members.\n"
				f"Errors: {errors[:10]}"
			),
		)

	return {
		"team_members_scanned": scanned,
		"drift_corrected": corrected,
		"errors": errors,
	}
