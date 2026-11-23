"""
Unit tests for push_app_to_github() in bench_app_push.py (the dashboard's Push to GitHub and the MCP app_git_push).

Run (press-ctrl, mock-only): press-ops scripts/mcp-speed-2026-11-23/run_new_module_tests.py
"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ─── Install frappe stub BEFORE importing bench_app_push ──────────────────────
_frappe_stub = types.ModuleType("frappe")
_frappe_stub._ = lambda s: s
_frappe_stub.whitelist = lambda fn=None, **kw: (lambda f: f) if fn is None else fn
_frappe_stub.db = MagicMock()
sys.modules.setdefault("frappe", _frappe_stub)

import press.press.doctype.bench.bench_app_push as _push  # noqa: E402


class _Refused(Exception):
	pass


def _result(output="", returncode=0):
	return {"status": "Success" if returncode == 0 else "Failure", "output": output, "returncode": returncode}


class TestPushAppToGithub(unittest.TestCase):
	def setUp(self):
		self.mf = MagicMock()
		self.mf.session.user = "dev@example.com"
		self.mf.throw.side_effect = _Refused
		self.mf.db.get_value.side_effect = self._get_value
		self.bench = MagicMock()
		self.mf.get_doc.return_value = self.bench
		self.outputs = {}
		self.bench.docker_execute.side_effect = self._run
		for name, value in (
			("frappe", self.mf),
			("_", lambda s: s),
			("ensure_team_access", MagicMock()),
			("is_app_owned_by_current_team", MagicMock(return_value=True)),
		):
			patcher = patch.object(_push, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)

	@staticmethod
	def _get_value(doctype, filters, field):
		return {
			"User": "Dev User",
			"Bench App": "src-myapp",
			"App Source": "https://github.com/org/myapp.git",
		}[doctype]

	def _run(self, cmd, subdir):
		"""docker_execute: each git command's result, by its first words."""
		for start, result in self.outputs.items():
			if cmd.startswith(start):
				return result
		return _result()

	def _commands(self):
		return [c.args[0] for c in self.bench.docker_execute.call_args_list]

	def test_checks_team_access_first(self):
		_push.ensure_team_access.side_effect = PermissionError("Not allowed")
		with self.assertRaises(PermissionError):
			_push.push_app_to_github("bench-0001", "myapp", "WIP")
		_push.ensure_team_access.assert_called_once_with(bench_name="bench-0001")
		self.bench.docker_execute.assert_not_called()

	def test_refuses_an_upstream_app(self):
		_push.is_app_owned_by_current_team.return_value = False
		with self.assertRaises(_Refused):
			_push.push_app_to_github("bench-0001", "frappe", "WIP")
		self.mf.get_doc.assert_not_called()

	def test_add_commit_push_run_as_separate_calls_in_the_app_folder(self):
		result = _push.push_app_to_github("bench-0001", "myapp", "WIP")
		commands = self._commands()
		self.assertEqual(len(commands), 3)
		self.assertEqual(commands[0], "git add -A")
		self.assertIn(" commit -m 'WIP'", commands[1])
		self.assertEqual(commands[2], "git push")
		self.assertEqual(
			{c.kwargs["subdir"] for c in self.bench.docker_execute.call_args_list}, {"apps/myapp"}
		)
		self.mf.get_doc.assert_called_once_with("Bench", "bench-0001")
		self.assertEqual((result["step"], result["returncode"]), ("done", 0))

	def test_commit_author_is_the_session_user(self):
		_push.push_app_to_github("bench-0001", "myapp", "my feature")
		commit = self._commands()[1]
		self.assertIn("-c user.name='Dev User' -c user.email='dev@example.com' commit", commit)
		self.assertIn("-m 'my feature'", commit)

	def test_single_quote_in_message_escaped(self):
		_push.push_app_to_github("bench-0001", "myapp", "it's done")
		self.assertIn("-m 'it'\\''s done'", self._commands()[1])

	def test_nothing_to_commit_still_pushes(self):
		self.outputs["git -c"] = _result("nothing to commit, working tree clean", returncode=1)
		result = _push.push_app_to_github("bench-0001", "myapp", "WIP")
		self.assertEqual(self._commands()[-1], "git push")
		self.assertEqual(result["step"], "done")

	def test_failed_commit_stops_before_push(self):
		self.outputs["git -c"] = _result("fatal: unable to write new index file", returncode=128)
		result = _push.push_app_to_github("bench-0001", "myapp", "WIP")
		self.assertNotIn("git push", self._commands())
		self.assertEqual(result["step"], "commit")

	def test_push_auth_failure_gives_a_hint(self):
		self.outputs["git push"] = _result("git@github.com: Permission denied (publickey).", returncode=128)
		result = _push.push_app_to_github("bench-0001", "myapp", "WIP")
		self.assertEqual(result["step"], "push")
		self.assertTrue(result["hint"].startswith("GitHub auth failed"))

	def test_branch_name_checks_out_sets_upstream_and_links_a_pr(self):
		result = _push.push_app_to_github("bench-0001", "myapp", "WIP", branch_name=" feat/x ")
		commands = self._commands()
		self.assertEqual(commands[0], "git checkout -B feat/x HEAD")
		self.assertEqual(commands[-1], "git push -u origin feat/x")
		self.assertEqual(result["pr_url"], "https://github.com/org/myapp/pull/new/feat/x")

	def test_invalid_branch_name_refused_before_any_command(self):
		with self.assertRaises(_Refused):
			_push.push_app_to_github("bench-0001", "myapp", "WIP", branch_name="feat x; rm -rf ~")
		self.bench.docker_execute.assert_not_called()


if __name__ == "__main__":
	unittest.main(verbosity=2)
