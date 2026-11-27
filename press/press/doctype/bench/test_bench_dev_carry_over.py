"""
Unit tests for bench_dev_carry_over.py (no site or database needed).

Run:
  python3 -m unittest press.press.doctype.bench.test_bench_dev_carry_over -v
"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

_frappe_stub = types.ModuleType("frappe")
_frappe_stub.db = MagicMock()
_frappe_stub.get_all = MagicMock()
_frappe_stub.get_doc = MagicMock()
_frappe_stub.log_error = MagicMock()
sys.modules.setdefault("frappe", _frappe_stub)

from press.press.doctype.bench import bench_dev_carry_over as co  # noqa: E402

PATCH = "press.press.doctype.bench.bench_dev_carry_over.frappe"
CS_MODULE = "press.press.doctype.bench.dev_overview.code_server"
WATCH_MODULE = "press.press.doctype.bench.bench_dev_watch"


def _new_bench(status="Active", is_dev=0):
	return types.SimpleNamespace(
		status=status, group="rg-1", server="srv-1", creation="2026-11-26 10:00:00", is_development_bench=is_dev
	)


def _fake_modules(create=None, start=None):
	return patch.dict(
		sys.modules,
		{
			CS_MODULE: types.SimpleNamespace(create_code_server=create or MagicMock()),
			WATCH_MODULE: types.SimpleNamespace(start_watch=start or MagicMock()),
		},
	)


class TestSubdomain(unittest.TestCase):
	def test_dashboard_rule(self):
		self.assertEqual(co.code_server_subdomain("bench-0081-000002"), "code-bench-0081-000002")

	def test_cut_to_30_characters(self):
		name = "bench-" + "a" * 60
		self.assertEqual(len(co.code_server_subdomain(name)), len("code-") + 30)


class TestCarryOver(unittest.TestCase):
	@patch(PATCH)
	def test_flag_and_code_server_follow_the_old_bench(self, mf):
		mf.db.get_value.return_value = _new_bench()
		mf.get_all.return_value = ["bench-0081-000001"]
		# old bench has a live Code Server, new one has none
		mf.db.exists.side_effect = lambda dt, f: "cs-old" if f["bench"] == "bench-0081-000001" else None
		create, start = MagicMock(), MagicMock()
		with _fake_modules(create, start):
			co.carry_over_development_bench("bench-0081-000002")
		mf.db.set_value.assert_called_once_with("Bench", "bench-0081-000002", "is_development_bench", 1)
		start.assert_called_once()
		create.assert_called_once_with("bench-0081-000002", "code-bench-0081-000002")

	@patch(PATCH)
	def test_old_bench_not_development_changes_nothing(self, mf):
		mf.db.get_value.return_value = _new_bench()
		mf.get_all.return_value = []
		create = MagicMock()
		with _fake_modules(create):
			co.carry_over_development_bench("bench-0081-000002")
		mf.db.set_value.assert_not_called()
		create.assert_not_called()

	@patch(PATCH)
	def test_bench_not_active_changes_nothing(self, mf):
		mf.db.get_value.return_value = _new_bench(status="Broken")
		co.carry_over_development_bench("bench-0081-000002")
		mf.get_all.assert_not_called()
		mf.db.set_value.assert_not_called()

	@patch(PATCH)
	def test_second_run_is_idempotent(self, mf):
		mf.db.get_value.return_value = _new_bench(is_dev=1)
		mf.get_all.return_value = ["bench-0081-000001"]
		mf.db.exists.return_value = "cs-exists"  # both benches have a live Code Server
		create, start = MagicMock(), MagicMock()
		with _fake_modules(create, start):
			co.carry_over_development_bench("bench-0081-000002")
		mf.db.set_value.assert_not_called()
		start.assert_not_called()
		create.assert_not_called()

	@patch(PATCH)
	def test_no_code_server_on_old_bench_means_none_on_new(self, mf):
		mf.db.get_value.return_value = _new_bench()
		mf.get_all.return_value = ["bench-0081-000001"]
		mf.db.exists.return_value = None
		create = MagicMock()
		with _fake_modules(create):
			co.carry_over_development_bench("bench-0081-000002")
		mf.db.set_value.assert_called_once()
		create.assert_not_called()

	@patch(PATCH)
	def test_code_server_failure_is_logged_not_raised(self, mf):
		mf.db.get_value.return_value = _new_bench()
		mf.get_all.return_value = ["bench-0081-000001"]
		mf.db.exists.side_effect = lambda dt, f: "cs-old" if f["bench"] == "bench-0081-000001" else None
		with _fake_modules(create=MagicMock(side_effect=RuntimeError("boom"))):
			co.carry_over_development_bench("bench-0081-000002")
		mf.log_error.assert_called_once()


class TestArchiveCodeServer(unittest.TestCase):
	@patch(PATCH)
	def test_archives_live_code_server(self, mf):
		mf.db.exists.return_value = "code-x.example.com"
		co.archive_code_server_of_bench("bench-0081-000001")
		mf.get_doc.assert_called_once_with("Code Server", "code-x.example.com")
		mf.get_doc.return_value.archive.assert_called_once()

	@patch(PATCH)
	def test_no_code_server_does_nothing(self, mf):
		mf.db.exists.return_value = None
		co.archive_code_server_of_bench("bench-0081-000001")
		mf.get_doc.assert_not_called()


if __name__ == "__main__":
	unittest.main()
