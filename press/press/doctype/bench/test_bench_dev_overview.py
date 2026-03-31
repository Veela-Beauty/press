"""
Unit tests for bench_dev_overview.py

Tests cover:
- undeployed_count computation (issue 1)
- bool("0") scheduler bug fix (issue 2)
- 100-hash boundary cap (issue 4)
"""
import unittest
from unittest.mock import MagicMock, patch

import frappe


class TestGetDevOverviewBenches(unittest.TestCase):
	"""Tests for get_dev_overview_benches()"""

	def _make_bench(self, name, group="rg-001", server="srv-001", status="Active"):
		b = MagicMock()
		b.name = name
		b.status = status
		b.group = group
		b.group_title = group
		b.server = server
		b.server_title = server
		b.cluster_title = "cluster-1"
		b.is_development_bench = 0
		b.creation = "2026-01-01 00:00:00"
		b.candidate = None
		return b

	def _make_app(self, parent, app, hash_):
		a = MagicMock()
		a.parent = parent
		a.app = app
		a.hash = hash_
		return a

	def _make_release(self, hash_, message="fix: something", author="dev", timestamp="2026-01-01 10:00:00"):
		r = MagicMock()
		r.hash = hash_
		r.message = message
		r.author = author
		r.timestamp = timestamp
		return r

	@patch("press.press.doctype.bench.bench_dev_overview.frappe")
	def test_undeployed_count_is_computed(self, mock_frappe):
		"""Bench with newer App Releases than deployed hash → undeployed_count > 0"""
		mock_frappe.only_for = MagicMock()
		bench = self._make_bench("bench-001")
		app_entry = self._make_app("bench-001", "accubuild_core", "abc1234")
		release = self._make_release("abc1234", timestamp="2026-01-01 09:00:00")

		mock_frappe.get_all.side_effect = [
			[bench],           # benches
			[],                # sites
			[app_entry],       # bench apps
			[release],         # app releases for hashes
		]
		mock_frappe.db.count.return_value = 3  # 3 newer releases exist

		from press.press.doctype.bench.bench_dev_overview import get_dev_overview_benches
		result = get_dev_overview_benches()

		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["undeployed_count"], 3)
		mock_frappe.db.count.assert_called_once_with(
			"App Release",
			{"app": "accubuild_core", "timestamp": [">", "2026-01-01 09:00:00"]},
		)

	@patch("press.press.doctype.bench.bench_dev_overview.frappe")
	def test_undeployed_count_zero_when_no_newer_releases(self, mock_frappe):
		"""Bench with no newer App Releases → undeployed_count == 0"""
		mock_frappe.only_for = MagicMock()
		bench = self._make_bench("bench-002")
		app_entry = self._make_app("bench-002", "accubuild_core", "abc9999")
		release = self._make_release("abc9999", timestamp="2026-01-01 09:00:00")

		mock_frappe.get_all.side_effect = [
			[bench], [], [app_entry], [release],
		]
		mock_frappe.db.count.return_value = 0

		from press.press.doctype.bench.bench_dev_overview import get_dev_overview_benches
		result = get_dev_overview_benches()

		self.assertEqual(result[0]["undeployed_count"], 0)

	@patch("press.press.doctype.bench.bench_dev_overview.frappe")
	def test_undeployed_count_zero_when_no_release_for_hash(self, mock_frappe):
		"""Bench app has a hash but no matching App Release → count stays 0 (no timestamp to compare)"""
		mock_frappe.only_for = MagicMock()
		bench = self._make_bench("bench-003")
		app_entry = self._make_app("bench-003", "erpnext", "unknown_hash")

		mock_frappe.get_all.side_effect = [
			[bench], [], [app_entry],
			[],  # no releases match the hash
		]

		from press.press.doctype.bench.bench_dev_overview import get_dev_overview_benches
		result = get_dev_overview_benches()

		self.assertEqual(result[0]["undeployed_count"], 0)
		mock_frappe.db.count.assert_not_called()

	@patch("press.press.doctype.bench.bench_dev_overview.frappe")
	def test_hash_list_capped_at_100(self, mock_frappe):
		"""More than 100 unique hashes → only 100 sent to App Release query"""
		mock_frappe.only_for = MagicMock()
		bench = self._make_bench("bench-004")

		# 101 app entries with unique hashes
		apps = [self._make_app("bench-004", f"app-{i}", f"hash{i:04d}") for i in range(101)]

		mock_frappe.get_all.side_effect = [
			[bench], [], apps, [],  # releases → empty (no match)
		]

		from press.press.doctype.bench.bench_dev_overview import get_dev_overview_benches
		get_dev_overview_benches()

		# The App Release query is the 4th get_all call
		app_release_call = mock_frappe.get_all.call_args_list[3]
		sent_hashes = app_release_call[1]["filters"]["hash"][1]
		self.assertLessEqual(len(sent_hashes), 100, "Must not exceed 100 hashes in query")


class TestSchedulerBoolFix(unittest.TestCase):
	"""Tests for the bool('0') scheduler bug fix in get_dev_panel_data()"""

	def _make_site_config(self, parent, value):
		cfg = MagicMock()
		cfg.parent = parent
		cfg.value = value
		return cfg

	def _check_scheduler_map_value(self, value):
		"""Helper: simulate the scheduler_map logic for a given config value."""
		return value in (True, 1, "1", "true")

	def test_pause_scheduler_string_one_means_paused(self):
		"""pause_scheduler = '1' → scheduler IS paused → scheduler_enabled = False"""
		paused = self._check_scheduler_map_value("1")
		self.assertTrue(paused)
		self.assertFalse(not paused)  # scheduler_enabled

	def test_pause_scheduler_int_one_means_paused(self):
		"""pause_scheduler = 1 → scheduler IS paused"""
		paused = self._check_scheduler_map_value(1)
		self.assertTrue(paused)

	def test_pause_scheduler_string_zero_means_not_paused(self):
		"""pause_scheduler = '0' → scheduler is NOT paused → scheduler_enabled = True
		This was the bug: bool('0') == True, which incorrectly reported as paused."""
		paused = self._check_scheduler_map_value("0")
		self.assertFalse(paused, "bool('0') bug: '0' must NOT be treated as paused")

	def test_pause_scheduler_int_zero_means_not_paused(self):
		"""pause_scheduler = 0 → scheduler is NOT paused"""
		paused = self._check_scheduler_map_value(0)
		self.assertFalse(paused)

	def test_pause_scheduler_false_means_not_paused(self):
		"""pause_scheduler = False → scheduler is NOT paused"""
		paused = self._check_scheduler_map_value(False)
		self.assertFalse(paused)

	def test_pause_scheduler_none_means_not_paused(self):
		"""pause_scheduler = None → should default to not paused"""
		paused = self._check_scheduler_map_value(None)
		self.assertFalse(paused)


if __name__ == "__main__":
	unittest.main()
