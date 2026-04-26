"""
Push committed changes from a bench's app working tree back to its GitHub repo.

Replaces the original push_app_to_github implementation that chained
git add -A && git commit && git push into a single docker_execute call —
that broke because && executes on the HOST after only the first command
runs inside the container (a docker_execute quirk documented in the project's
CLAUDE.md). This module runs each git command as its own docker_execute call.
"""
import frappe
from frappe import _

from press.press.doctype.bench.bench_dev_overview import _ensure_team_access
from press.press.doctype.bench.bench_app_ownership import is_app_owned_by_current_team


def _docker_run(bench_doc, cmd: str, subdir: str) -> dict:
	"""Wrap bench.docker_execute and normalize the return shape."""
	return bench_doc.docker_execute(cmd, subdir=subdir)


def push_app_to_github(bench_name: str, app: str, message: str) -> dict:
	"""
	Add → commit → push the working tree of <app> on <bench> to its GitHub repo.
	Each git command runs as its own docker_execute (no && chains — they break
	because the second && command runs on the HOST not in the container).

	Refuses to push when the app's App Source is not owned by the current team
	(e.g. upstream frappe/erpnext/hrms) — those would fail at GitHub auth
	anyway and the better UX is a clear early error.
	"""
	_ensure_team_access(bench_name=bench_name)
	if not is_app_owned_by_current_team(bench_name, app):
		frappe.throw(
			_("App {0} is upstream (read-only). Push only works on apps your team owns.").format(app),
			title=_("Push not allowed"),
		)
	bench = frappe.get_doc("Bench", bench_name)
	safe_message = message.replace("'", "'\\''")
	subdir = f"apps/{app}"

	add_result = _docker_run(bench, "git add -A", subdir)
	if add_result.get("returncode") != 0:
		return {"step": "add", **add_result}

	commit_result = _docker_run(bench, f"git commit -m '{safe_message}'", subdir)
	# commit can fail benignly with "nothing to commit" — proceed to push so
	# already-committed-but-not-pushed work still ships.
	nothing_to_commit = (
		commit_result.get("returncode") != 0
		and "nothing to commit" in (commit_result.get("output") or "").lower()
	)
	if commit_result.get("returncode") != 0 and not nothing_to_commit:
		return {"step": "commit", **commit_result}

	push_result = _docker_run(bench, "git push", subdir)
	if push_result.get("returncode") != 0:
		# Surface a more useful diagnosis up front; full output still attached.
		out = (push_result.get("output") or "").lower()
		hint = None
		if "permission denied" in out or "publickey" in out:
			hint = "GitHub auth failed — bench's deploy key may be read-only or missing."
		elif "no upstream branch" in out or "matching ref" in out:
			hint = "No upstream branch — checkout/create a branch in the container first."
		elif "no such remote" in out or "does not appear to be a git repo" in out:
			hint = "No origin remote configured. Use the 'GitHub' button to register the repo first."
		return {"step": "push", "hint": hint, **push_result}

	return {
		"step": "done",
		"status": "Success",
		"output": (push_result.get("output") or "").strip()
			or "Pushed (nothing committed — already in sync)",
		"returncode": 0,
	}
