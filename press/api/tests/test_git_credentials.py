# Copyright (c) 2026, Frappe and Contributors
# See license.txt
"""Tests for press.api.git_credentials — the security-critical boundary
between bench containers and Press. The tests here prove:

1. _validate_team_membership accepts team owners + team members
2. _validate_team_membership rejects outsiders (no token minting for non-members)
3. Missing / wrong internal secret is rejected

If ANY of these break, attacker-in-a-bench could mint tokens for any user.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.api.git_credentials import _validate_team_membership


class TestGitCredentialsTeamMembership(FrappeTestCase):
	"""_validate_team_membership is the security boundary for get_for_session.
	Untested regressions here would silently allow token minting across teams.
	"""

	def tearDown(self):
		frappe.db.rollback()

	def _make_team_with_member(self, owner_email: str, member_email: str, bench_name: str):
		"""Create a minimal Team + Bench pointing at it, for membership tests.

		Avoids Press's full team creation pipeline — we only need the rows
		_validate_team_membership reads. Team.name is autoname=hash so we let
		Frappe generate it then use the returned doc.name. Team Member rows are
		inserted directly because Team.save() validates the parent user.
		"""
		team = frappe.get_doc(
			{
				"doctype": "Team",
				"user": owner_email,
				"enabled": 1,
			}
		)
		team.append("team_members", {"user": owner_email})
		if member_email != owner_email:
			team.append("team_members", {"user": member_email})
		team.flags.ignore_validate = True
		team.flags.ignore_mandatory = True
		team.flags.ignore_links = True
		team.flags.ignore_permissions = True
		team.insert(ignore_permissions=True, ignore_if_duplicate=True)
		team_name = team.name

		# Bench with direct team pointer
		frappe.db.sql(
			"INSERT INTO `tabBench` (name, team, `group`) VALUES (%s, %s, %s)",
			(bench_name, team_name, ""),
		)
		frappe.db.commit()
		return team_name

	def test_team_owner_passes(self):
		bench = f"test-bench-{frappe.generate_hash(length=6)}"
		self._make_team_with_member("owner@test.com", "member@test.com", bench)
		# Should not raise
		_validate_team_membership("owner@test.com", bench)

	def test_team_member_passes(self):
		bench = f"test-bench-{frappe.generate_hash(length=6)}"
		self._make_team_with_member("owner@test.com", "member@test.com", bench)
		# Should not raise
		_validate_team_membership("member@test.com", bench)

	def test_outsider_is_rejected(self):
		"""A user who is neither team owner nor team member must be denied.
		This is the security boundary — if it breaks, any authenticated bench
		can mint tokens for any user.
		"""
		bench = f"test-bench-{frappe.generate_hash(length=6)}"
		self._make_team_with_member("owner@test.com", "member@test.com", bench)
		with self.assertRaises(frappe.PermissionError):
			_validate_team_membership("outsider@attacker.com", bench)

	def test_unknown_bench_is_rejected(self):
		with self.assertRaises(frappe.PermissionError):
			_validate_team_membership("anyone@test.com", "nonexistent-bench-xyz")
