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
		status=status,
		group="rg-1",
		server="srv-1",
		creation="2026-11-26 10:00:00",
		is_development_bench=is_dev,
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


def _old_has_code_server(mf, old="bench-0081-000001"):
	mf.db.exists.side_effect = lambda dt, f: "cs-old" if f["bench"] == old else None


class TestCarryOver(unittest.TestCase):
	@patch(PATCH)
	def test_flag_set_and_background_step_queued(self, mf):
		mf.db.get_value.return_value = _new_bench()
		mf.get_all.return_value = ["bench-0081-000001"]
		_old_has_code_server(mf)
		co.carry_over_development_bench("bench-0081-000002")
		mf.db.set_value.assert_called_once_with("Bench", "bench-0081-000002", "is_development_bench", 1)
		mf.db.commit.assert_not_called()
		mf.enqueue.assert_called_once_with(
			"press.press.doctype.bench.bench_dev_carry_over.finish_development_bench_carry_over",
			enqueue_after_commit=True,
			bench_name="bench-0081-000002",
			with_code_server=True,
		)

	@patch(PATCH)
	def test_old_bench_query_filters(self, mf):
		mf.db.get_value.return_value = _new_bench()
		mf.get_all.return_value = []
		co.carry_over_development_bench("bench-0081-000002")
		args, kwargs = mf.get_all.call_args
		self.assertEqual(args, ("Bench",))
		self.assertEqual(
			kwargs["filters"],
			{
				"group": "rg-1",
				"server": "srv-1",
				"status": ["in", ["Active", "Pending"]],
				"is_development_bench": 1,
				"name": ["!=", "bench-0081-000002"],
				"creation": ["<", "2026-11-26 10:00:00"],
			},
		)

	@patch(PATCH)
	def test_old_bench_not_development_changes_nothing(self, mf):
		mf.db.get_value.return_value = _new_bench()
		mf.get_all.return_value = []
		co.carry_over_development_bench("bench-0081-000002")
		mf.db.set_value.assert_not_called()
		mf.enqueue.assert_not_called()

	@patch(PATCH)
	def test_bench_not_active_changes_nothing(self, mf):
		mf.db.get_value.return_value = _new_bench(status="Broken")
		co.carry_over_development_bench("bench-0081-000002")
		mf.get_all.assert_not_called()
		mf.db.set_value.assert_not_called()

	@patch(PATCH)
	def test_second_run_does_not_set_flag_again(self, mf):
		mf.db.get_value.return_value = _new_bench(is_dev=1)
		mf.get_all.return_value = ["bench-0081-000001"]
		_old_has_code_server(mf)
		co.carry_over_development_bench("bench-0081-000002")
		mf.db.set_value.assert_not_called()

	@patch(PATCH)
	def test_no_code_server_on_old_bench_is_passed_on(self, mf):
		mf.db.get_value.return_value = _new_bench()
		mf.get_all.return_value = ["bench-0081-000001"]
		mf.db.exists.return_value = None
		co.carry_over_development_bench("bench-0081-000002")
		self.assertFalse(mf.enqueue.call_args.kwargs["with_code_server"])

	@patch(PATCH)
	def test_errors_are_logged_not_raised(self, mf):
		mf.db.get_value.side_effect = RuntimeError("boom")
		co.carry_over_development_bench("bench-0081-000002")
		mf.log_error.assert_called_once()


class TestFinishCarryOver(unittest.TestCase):
	def _run(self, mf, with_cs=True, feature=True, create=None, new_has_cs=False):
		mf.db.get_value.return_value = "team-1"
		mf.db.exists.return_value = "cs-new" if new_has_cs else None
		create = create or MagicMock()
		start = MagicMock()
		fa = types.SimpleNamespace(has_feature=MagicMock(return_value=feature))
		with _fake_modules(create, start), patch.dict(sys.modules, {"press.api.feature_access": fa}):
			co.finish_development_bench_carry_over("bench-0081-000002", with_cs)
		return create, start

	@patch(PATCH)
	def test_starts_watch_and_creates_code_server(self, mf):
		create, start = self._run(mf)
		start.assert_called_once()
		create.assert_called_once_with("bench-0081-000002", "code-bench-0081-000002")

	@patch(PATCH)
	def test_no_code_server_when_old_had_none(self, mf):
		create, start = self._run(mf, with_cs=False)
		start.assert_called_once()
		create.assert_not_called()

	@patch(PATCH)
	def test_existing_code_server_is_kept(self, mf):
		create, _ = self._run(mf, new_has_cs=True)
		create.assert_not_called()

	@patch(PATCH)
	def test_feature_off_skips_and_logs(self, mf):
		create, _ = self._run(mf, feature=False)
		create.assert_not_called()
		mf.log_error.assert_called_once()

	@patch(PATCH)
	def test_code_server_failure_is_logged_not_raised(self, mf):
		self._run(mf, create=MagicMock(side_effect=RuntimeError("boom")))
		mf.log_error.assert_called_once()


class TestWiring(unittest.TestCase):
	"""bench.py cannot be imported without frappe, so check its call order in the source."""

	@classmethod
	def setUpClass(cls):
		import pathlib

		cls.src = (pathlib.Path(__file__).parent / "bench.py").read_text()

	def _body(self, name):
		start = self.src.index(f"def {name}(")
		end = self.src.find("\ndef ", start + 1)
		return self.src[start:end]

	def test_carry_over_runs_before_old_benches_are_queued_for_archive(self):
		body = self._body("process_new_bench_job_update")
		self.assertLess(
			body.index("carry_over_development_bench(bench.name)"),
			body.index('"press.press.doctype.bench.bench.archive_obsolete_benches"'),
		)

	def test_code_server_archived_only_after_bench_is_archived(self):
		archive_method = self.src[
			self.src.index("	def archive(self") : self.src.index("	def take_process_snapshot")
		]
		self.assertNotIn("archive_code_server_of_bench", archive_method)
		body = self._body("process_archive_bench_job_update")
		self.assertIn("archive_code_server_of_bench(job.bench)", body)
		self.assertLess(
			body.index('if updated_status == "Archived":\n\t\t\tfrom'),
			body.index("archive_code_server_of_bench(job.bench)"),
		)


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
