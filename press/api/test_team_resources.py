# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Tests for press.api.team_resources — picker-list endpoints."""
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.api.team_resources import (
	MAX_PICKER_RESULTS,
	list_my_release_groups,
	list_my_sites,
)


class TestTeamResources(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_list_my_release_groups_returns_minimal_fields(self):
		# Drift guard: picker UI breaks if the field set changes.
		result = list_my_release_groups()
		if result:
			required = {"name", "title"}
			self.assertEqual(set(result[0].keys()), required)

	def test_list_my_release_groups_capped(self):
		# Hard cap so a team with thousands of RGs doesn't ship them all.
		result = list_my_release_groups()
		self.assertLessEqual(len(result), MAX_PICKER_RESULTS)

	def test_list_my_sites_returns_minimal_fields(self):
		result = list_my_sites()
		if result:
			required = {"name", "group"}
			self.assertEqual(set(result[0].keys()), required)

	def test_list_my_sites_excludes_archived(self):
		# Status filter must exclude Archived/Broken sites — drift guard
		# against upstream changes to the status enum.
		result = list_my_sites()
		for site in result:
			# Re-check status from DB; the API doesn't return it
			status = frappe.db.get_value("Site", site["name"], "status")
			self.assertIn(
				status,
				("Active", "Inactive", "Suspended"),
				f"site {site['name']} has unexpected status {status!r}",
			)

	def test_list_my_sites_search_filters_by_name(self):
		# Server-side search via q param. Only sites whose name contains
		# the substring should be returned.
		result = list_my_sites(q="nonexistent-prefix-xyz")
		self.assertEqual(result, [], "no sites should match a bogus prefix")

	def test_list_my_sites_search_empty_q_returns_all(self):
		# q=None or empty should behave like no filter.
		all_sites = list_my_sites()
		empty_q = list_my_sites(q="")
		self.assertEqual(
			[s["name"] for s in all_sites],
			[s["name"] for s in empty_q],
		)

	def test_list_my_sites_capped(self):
		# Server-side cap; large teams don't ship 1000+ rows.
		result = list_my_sites()
		self.assertLessEqual(len(result), MAX_PICKER_RESULTS)
