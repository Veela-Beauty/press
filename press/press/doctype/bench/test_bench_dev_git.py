"""
Unit tests for bench_dev_git.py (no site or database needed; the shell is run against real git repositories).

Run:
  python3 -m unittest press.press.doctype.bench.test_bench_dev_git -v
"""

import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_frappe_stub = types.ModuleType("frappe")
_frappe_stub.db = MagicMock()
_frappe_stub.logger = MagicMock()
_frappe_stub.get_doc = MagicMock()
_frappe_stub.log_error = MagicMock()
sys.modules.setdefault("frappe", _frappe_stub)

from press.press.doctype.bench import bench_dev_git as dg  # noqa: E402

PATCH = "press.press.doctype.bench.bench_dev_git.frappe"
WATCH_MODULE = "press.press.doctype.bench.bench_dev_watch"


class TestHttpsUrl(unittest.TestCase):
	def test_github_urls_become_https(self):
		for url in ("https://github.com/acme/demo", "https://github.com/acme/demo.git", "git@github.com:acme/demo.git",
			"https://github.com/acme/demo/"):
			self.assertEqual(dg.https_url(url), "https://github.com/acme/demo.git")
		self.assertEqual(dg.https_url("https://github.com/Acme-Co/my_app.v2"), "https://github.com/Acme-Co/my_app.v2.git")

	def test_anything_else_is_none(self):
		for url in (None, "", "file:///home/frappe/context/apps/demo", "https://gitlab.com/acme/demo",
			"https://github.com/acme/demo;rm -rf ~", "http://github.com/acme/demo", "https://github.com/acme/demo/tree/main",
			"https://x:token@github.com/acme/demo.git", "https://github.com/../demo", "https://github.com/acmé/demo"):
			self.assertIsNone(dg.https_url(url))

	@patch(PATCH)
	def test_a_bad_branch_is_skipped(self, mf):
		mf.db.get_value.side_effect = [types.SimpleNamespace(repository_url="https://github.com/acme/a", branch=b)
			for b in ("main", "-x", "a b", "release/1.2")]
		bench = types.SimpleNamespace(apps=[types.SimpleNamespace(app=f"a{i}", source="s") for i in range(4)])
		self.assertEqual([r[2] for r in dg.app_remotes(bench)], ["main", "release/1.2"])


def _git(*args, cwd):
	return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class _Bench(unittest.TestCase):
	"""A bench folder like the image's: apps/demo cloned from a local path, its remote named upstream, a detached commit
	and no local branch."""

	def setUp(self):
		self.tmp = Path(tempfile.mkdtemp())
		src = self.tmp / "src"
		src.mkdir()
		_git("init", "-q", cwd=src)
		for message in ("one", "two"):
			_git(
				"-c",
				"user.email=t@t",
				"-c",
				"user.name=t",
				"commit",
				"-q",
				"--allow-empty",
				"-m",
				message,
				cwd=src,
			)
		_git("branch", "-q", "-M", "main", cwd=src)
		self.bench = self.tmp / "bench"
		(self.bench / "apps").mkdir(parents=True)
		_git("clone", "-q", f"file://{src}", "apps/demo", cwd=self.bench)
		self.app = self.bench / "apps" / "demo"
		_git("remote", "rename", "origin", "upstream", cwd=self.app)
		_git("checkout", "-q", "--detach", "HEAD", cwd=self.app)
		_git("branch", "-q", "-D", "main", cwd=self.app)

	def tearDown(self):
		shutil.rmtree(self.tmp)

	def run_script(self):
		script = dg.app_script("demo", "https://github.com/acme/demo.git", "main")
		return subprocess.run(
			["bash", "-c", script], cwd=self.bench, check=True, capture_output=True, text=True
		).stdout


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class TestAppScript(_Bench):
	def test_a_fresh_checkout_gets_origin_and_its_branch(self):
		out = self.run_script()
		self.assertEqual(out.strip(), "demo: https://github.com/acme/demo.git on main")
		self.assertEqual(_git("config", "branch.main.merge", cwd=self.app), "refs/heads/main")
		self.assertEqual(_git("config", "branch.main.remote", cwd=self.app), "origin")

	def test_running_again_changes_nothing(self):
		self.run_script()
		self.assertEqual(self.run_script().strip(), "demo: https://github.com/acme/demo.git on main")

	def test_a_developer_on_a_feature_branch_is_not_switched(self):
		_git("checkout", "-q", "-b", "feat/x", cwd=self.app)
		self.assertTrue(self.run_script().strip().endswith("on feat/x"))

	def test_a_branch_pointing_elsewhere_is_not_moved(self):
		self.run_script()
		_git("checkout", "-q", "--detach", "main~1", cwd=self.app)
		self.assertTrue(self.run_script().strip().endswith("on detached"))
		self.assertEqual(_git("log", "-1", "--format=%s", "main", cwd=self.app), "two")


	def test_the_build_upstream_remote_is_removed(self):
		self.run_script()
		self.assertEqual(_git("remote", cwd=self.app), "origin")

	def test_an_origin_still_at_the_build_folder_is_replaced(self):
		_git("remote", "rename", "upstream", "origin", cwd=self.app)
		self.assertTrue(self.run_script().strip().startswith("demo: https://github.com/acme/demo.git"))

	def test_an_origin_the_developer_set_is_kept(self):
		_git("remote", "add", "origin", "https://github.com/dev/fork.git", cwd=self.app)
		self.assertTrue(self.run_script().strip().startswith("demo: https://github.com/dev/fork.git"))

	def test_a_branch_already_at_head_is_checked_out(self):
		_git("branch", "main", "HEAD", cwd=self.app)
		self.assertTrue(self.run_script().strip().endswith("on main"))

	def test_tracking_the_developer_set_is_kept(self):
		_git("checkout", "-q", "-b", "main", cwd=self.app)
		_git("config", "branch.main.remote", "fork", cwd=self.app)
		self.run_script()
		self.assertEqual(_git("config", "branch.main.remote", cwd=self.app), "fork")


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class TestConnectInAShell(_Bench):
	"""The whole command as the agent runs it: `docker exec -w <bench> ... <command>` through a shell."""

	@patch(PATCH)
	def test_a_missing_app_is_logged_and_the_others_still_run(self, mf):
		sources = {"src-gone": types.SimpleNamespace(repository_url="https://github.com/acme/gone", branch="main"),
			"src-demo": types.SimpleNamespace(repository_url="https://github.com/acme/demo", branch="main")}
		mf.db.get_value.side_effect = lambda _dt, name, _fields, as_dict: sources[name]

		def docker_execute(cmd):
			run = subprocess.run(cmd, shell=True, cwd=self.bench, capture_output=True, text=True)
			return {"output": run.stdout + run.stderr, "returncode": run.returncode}

		bench = types.SimpleNamespace(name="bench-1", docker_execute=docker_execute,
			apps=[types.SimpleNamespace(app="gone", source="src-gone"), types.SimpleNamespace(app="demo", source="src-demo")])
		output = dg.connect_app_remotes(bench)
		self.assertIn("demo: https://github.com/acme/demo.git on main", output)
		self.assertIn("gone", mf.log_error.call_args.kwargs["title"])


class TestConnect(unittest.TestCase):
	@patch(PATCH)
	def test_one_command_for_every_github_app(self, mf):
		sources = {
			"src-a": {"repository_url": "https://github.com/acme/a", "branch": "main"},
			"src-b": {"repository_url": "file:///tmp/b", "branch": "main"},
			"src-c": {"repository_url": "git@github.com:acme/c.git", "branch": "develop"},
		}
		mf.db.get_value.side_effect = lambda _dt, name, _fields, as_dict: types.SimpleNamespace(
			**sources[name]
		)
		bench = MagicMock()
		bench.apps = [
			types.SimpleNamespace(app=a, source=s)
			for a, s in (("a", "src-a"), ("b", "src-b"), ("c", "src-c"))
		]
		bench.docker_execute.return_value = {"output": "a: ... on main"}
		self.assertEqual(dg.connect_app_remotes(bench), "a: ... on main")
		command = bench.docker_execute.call_args.args[0]
		self.assertIn("https://github.com/acme/a.git", command)
		self.assertIn("https://github.com/acme/c.git", command)
		self.assertNotIn("apps/b", command)

	@patch(PATCH)
	def test_no_github_app_runs_nothing(self, mf):
		mf.db.get_value.return_value = None
		bench = MagicMock()
		bench.apps = [types.SimpleNamespace(app="a", source="src-a")]
		self.assertEqual(dg.connect_app_remotes(bench), "")
		bench.docker_execute.assert_not_called()


class TestApplyDevelopmentMode(unittest.TestCase):
	def _run(self, is_dev, watch_error=None, remotes_error=None):
		start, stop = MagicMock(side_effect=watch_error), MagicMock()
		watch = types.SimpleNamespace(start_watch=start, stop_watch=stop)
		bench = types.SimpleNamespace(name="bench-1", is_development_bench=is_dev)
		with (
			patch.dict(sys.modules, {WATCH_MODULE: watch}),
			patch.object(dg, "connect_app_remotes", MagicMock(side_effect=remotes_error)) as connect,
			patch(PATCH) as mf,
		):
			dg.apply_development_mode(bench)
		return start, stop, connect, mf

	def test_on_starts_the_watch_and_connects_the_remotes(self):
		start, stop, connect, _ = self._run(1)
		start.assert_called_once()
		connect.assert_called_once()
		stop.assert_not_called()

	def test_off_stops_the_watch_only(self):
		start, stop, connect, _ = self._run(0)
		stop.assert_called_once()
		connect.assert_not_called()
		start.assert_not_called()

	def test_failures_are_logged_not_raised(self):
		_, _, connect, mf = self._run(1, watch_error=RuntimeError("watch"), remotes_error=RuntimeError("git"))
		connect.assert_called_once()  # a failed watch does not skip the remotes
		self.assertEqual(mf.logger.return_value.error.call_count, 2)


class TestCarryOverConnects(unittest.TestCase):
	def test_the_carry_over_points_the_new_bench_at_github(self):
		from press.press.doctype.bench import bench_dev_carry_over as co

		watch = types.SimpleNamespace(start_watch=MagicMock())
		with (
			patch.dict(sys.modules, {WATCH_MODULE: watch}),
			patch.object(dg, "connect_app_remotes") as connect,
			patch("press.press.doctype.bench.bench_dev_carry_over.frappe") as mf,
		):
			mf.db.exists.return_value = "cs-new"  # a Code Server already there: no creation in this test
			co.finish_development_bench_carry_over("bench-0081-000002", with_code_server=False)
		connect.assert_called_once()


if __name__ == "__main__":
	unittest.main()
