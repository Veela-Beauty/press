# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Count

from press.api.client import dashboard_whitelist
from press.guards import team_guard
from press.utils import get_current_team

if TYPE_CHECKING:
	from press.press.doctype.team.team import Team


class PressRole(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from press.press.doctype.press_role_resource.press_role_resource import PressRoleResource
		from press.press.doctype.press_role_user.press_role_user import PressRoleUser

		admin_access: DF.Check
		all_release_groups: DF.Check
		all_servers: DF.Check
		all_sites: DF.Check
		allow_apps: DF.Check
		allow_bench_creation: DF.Check
		allow_billing: DF.Check
		allow_contribution: DF.Check
		allow_customer: DF.Check
		allow_dashboard: DF.Check
		allow_leads: DF.Check
		allow_partner: DF.Check
		allow_server_creation: DF.Check
		allow_site_creation: DF.Check
		allow_webhook_configuration: DF.Check
		resources: DF.Table[PressRoleResource]
		team: DF.Link
		title: DF.Data
		users: DF.Table[PressRoleUser]
	# end: auto-generated types

	dashboard_fields = (
		"admin_access",
		"all_servers",
		"all_sites",
		"all_release_groups",
		"allow_apps",
		"allow_bench_creation",
		"allow_billing",
		"allow_contribution",
		"allow_customer",
		"allow_dashboard",
		"allow_leads",
		"allow_partner",
		"allow_server_creation",
		"allow_site_creation",
		"allow_webhook_configuration",
		"resources",
		"team",
		"title",
		"users",
	)

	# A fresh Press Role starts with every flag at 0 — assigning a member to such
	# a role completely locks them out of the dashboard. before_insert pre-ticks
	# a sensible Developer baseline so a half-configured role isn't a brick.
	# Admins can still untick anything before saving. Sensitive flags (billing,
	# admin_access, server_creation, team-management) stay OFF by default.
	DEVELOPER_PRESET_FLAGS = (
		"allow_dashboard",
		"all_release_groups",
		"all_sites",
		"all_servers",
		"allow_apps",
		"allow_bench_creation",
		"allow_site_creation",
	)

	def before_insert(self):
		for flag in self.DEVELOPER_PRESET_FLAGS:
			if not self.get(flag):
				self.set(flag, 1)

	# Every boolean flag — for the empty-role lockout check below.
	ALL_FLAGS = (
		"admin_access",
		"allow_apps",
		"allow_bench_creation",
		"allow_billing",
		"allow_contribution",
		"allow_customer",
		"allow_dashboard",
		"allow_invite_team_members",
		"allow_leads",
		"allow_manage_team_members",
		"allow_manage_team_roles",
		"allow_partner",
		"allow_server_creation",
		"allow_site_creation",
		"allow_webhook_configuration",
		"all_release_groups",
		"all_servers",
		"all_sites",
	)

	@team_guard.only_admin()
	def validate(self):
		self.validate_duplicate_title()
		self.warn_if_zero_flag_lockout()

	def warn_if_zero_flag_lockout(self):
		"""Surface a warning when a role grants zero access AND has assigned users.

		Not a hard block — admins may legitimately save a placeholder role before
		assigning users, or use this to revoke access en-masse. Just makes the
		lockout visible instead of silent.
		"""
		if self.users and not any(self.get(f) for f in self.ALL_FLAGS):
			frappe.msgprint(
				_(
					"This role grants no access. Members assigned will be unable "
					"to view or use anything in the dashboard. Tick at least one "
					"allow_* / all_* flag, or remove the assigned users."
				),
				title=_("Empty role — members will be locked out"),
				indicator="orange",
			)

	def validate_duplicate_title(self):
		exists = frappe.db.exists({"doctype": "Press Role", "title": self.title, "team": self.team})
		if self.is_new() and exists:
			message = _("Role with title {0} already exists in this team").format(self.title)
			frappe.throw(message, frappe.DuplicateEntryError)

	def add_press_admin_role(self, user):
		user = frappe.get_doc("User", user)
		user.append_roles("Press Admin")
		user.save(ignore_permissions=True)

	def remove_press_admin_role(self, user):
		if frappe.db.exists("Team", {"enabled": 1, "user": user}):
			return
		user = frappe.get_doc("User", user)
		existing_roles = {d.role: d for d in user.get("roles")}
		if "Press Admin" in existing_roles:
			user.get("roles").remove(existing_roles["Press Admin"])
			user.save(ignore_permissions=True)

	@dashboard_whitelist()
	@team_guard.only_admin(skip=lambda _, args: args.get("skip_validations", False))
	@team_guard.only_member(
		user=lambda _, args: str(args.get("user")),
		error_message=_("User is not a member of the team"),
	)
	def add_user(self, user, skip_validations=False):
		user_dict = {"user": user}
		if self.get("users", user_dict):
			message = _("{0} already belongs to {1}").format(user, self.title)
			frappe.throw(message, frappe.ValidationError)
		self.append("users", user_dict)
		self.save()
		if self.admin_access or self.allow_billing:
			self.add_press_admin_role(user)

	@dashboard_whitelist()
	@team_guard.only_admin()
	def remove_user(self, user):
		users = self.get("users", {"user": user})
		if not users:
			message = _("User {0} does not belong to {1}").format(user, self.title)
			frappe.throw(message, frappe.ValidationError)
		self.remove(users.pop())
		self.save()
		if self.admin_access or self.allow_billing:
			self.remove_press_admin_role(user)

	@dashboard_whitelist()
	@team_guard.only_admin()
	def add_resource(self, resources: list[dict[str, str]]):
		for resource in resources:
			document_type = resource["document_type"]
			document_name = resource["document_name"]
			resource_dict = {"document_type": document_type, "document_name": document_name}
			if self.get("resources", resource_dict):
				message = _("{0} already belongs to {1}").format(document_name, self.title)
				frappe.throw(message, frappe.ValidationError)
			self.append("resources", resource_dict)
		self.save()

	@dashboard_whitelist()
	@team_guard.only_admin()
	def remove_resource(self, document_type: str, document_name: str):
		resources = self.get("resources", {"document_type": document_type, "document_name": document_name})
		if not resources:
			message = _("Resource {0} does not belong to {1}").format(document_name, self.title)
			frappe.throw(message, frappe.ValidationError)
		self.remove(resources.pop())
		self.save()

	@dashboard_whitelist()
	@team_guard.only_owner()
	def delete(self, *_args, **_kwargs):
		return super().delete()

	def on_trash(self) -> None:
		frappe.db.delete("Account Request Press Role", {"press_role": self.name})


def create_user_resource(document: Document, _):
	user = frappe.session.user
	team: Team = get_current_team(get_doc=True)

	roles_enabled = bool(
		frappe.db.exists(
			{
				"doctype": "Press Role",
				"team": team.name,
			}
		)
	)

	if (
		(not user)
		or (not roles_enabled)
		or (not user_has_roles())
		or team.is_team_owner()
		or team.is_admin_user()
	):
		return

	title = user + " / " + document.name

	role_exists = bool(
		frappe.db.exists(
			{
				"doctype": "Press Role",
				"team": team.name,
				"title": title,
			}
		)
	)

	if role_exists:
		return

	frappe.get_doc(
		{
			"doctype": "Press Role",
			"title": title,
			"team": team.name,
			"users": [
				{
					"user": user,
				}
			],
			"resources": [
				{
					"document_type": document.doctype,
					"document_name": document.name,
				}
			],
		}
	).save(ignore_permissions=True)


def user_has_roles() -> bool:
	PressRole = frappe.qb.DocType("Press Role")
	PressRoleUser = frappe.qb.DocType("Press Role User")
	return (
		frappe.qb.from_(PressRole)
		.inner_join(PressRoleUser)
		.on(PressRole.name == PressRoleUser.parent)
		.where(PressRole.team == get_current_team())
		.where(PressRoleUser.user == frappe.session.user)
		.select(Count(PressRole.name).as_("role_count"))
		.run(as_dict=True)
		.pop()
		.get("role_count", 0)
	) > 0


def has_role_flag_on_team(user: str, team: str, flag: str) -> bool:
	"""True if `user` belongs to any Press Role on `team` with `flag = 1`.

	`flag` is a column name — callers must pass a value from the allow_*
	allowlist. Parameterising a column name is not supported by the DB
	driver; we interpolate via f-string after strict allowlist validation.
	"""
	allowed = {
		"allow_manage_team_roles",
		"allow_manage_team_members",
		"allow_invite_team_members",
	}
	if flag not in allowed:
		raise ValueError(f"has_role_flag_on_team: flag {flag!r} not in allowlist")

	import frappe
	return bool(frappe.db.sql(f"""
		SELECT 1
		  FROM `tabPress Role` pr
		  JOIN `tabPress Role User` pru ON pru.parent = pr.name
		 WHERE pr.team = %s AND pru.user = %s AND pr.`{flag}` = 1
		 LIMIT 1
	""", (team, user)))
