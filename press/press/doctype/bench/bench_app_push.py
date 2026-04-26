"""
Push committed changes from a bench's app working tree back to its GitHub repo.

Replaces the original push_app_to_github implementation that chained
git add -A && git commit && git push into a single docker_execute call —
that broke because && executes on the HOST after only the first command
runs inside the container (a docker_execute quirk documented in the project's
CLAUDE.md). This module runs each git command as its own docker_execute call.
"""
import re

import frappe
from frappe import _

from press.press.doctype.bench.bench_dev_overview import _ensure_team_access
from press.press.doctype.bench.bench_app_ownership import is_app_owned_by_current_team


_BRANCH_RE = re.compile(r"[a-zA-Z0-9_./-]+")


def _docker_run(bench_doc, cmd: str, subdir: str) -> dict:
	"""Wrap bench.docker_execute and normalize the return shape."""
	return bench_doc.docker_execute(cmd, subdir=subdir)


def _get_app_repo_url(bench_name: str, app: str) -> str | None:
	"""Return the App Source's repository_url for (bench, app), or None."""
	source = frappe.db.get_value("Bench App", {"parent": bench_name, "app": app}, "source")
	if not source:
		return None
	return frappe.db.get_value("App Source", source, "repository_url")


def push_app_to_github(bench_name: str, app: str, message: str, branch_name: str = None) -> dict:
	"""
	Add → commit → push the working tree of <app> on <bench> to its GitHub repo.
	Each git command runs as its own docker_execute (no && chains — they break
	because the second && command runs on the HOST not in the container).

	Refuses to push when the app's App Source is not owned by the current team
	(e.g. upstream frappe/erpnext/hrms) — those would fail at GitHub auth
	anyway and the better UX is a clear early error.

	If branch_name is provided, the local branch is created/reset to current HEAD
	before push (`git checkout -B`). This lets users push to a feature branch
	without first SSH-ing into the container. Returns a `pr_url` pointing at
	GitHub's compare-and-create-PR page when pushing to a non-default branch.

	Commit author/committer identity is set from the dashboard session user via
	per-invocation `git -c user.name=… -c user.email=…` flags. Without this,
	GitHub blame/PR review attributes every dashboard-driven commit to whoever
	set git config in the container at build time — fine for one dev, wrong
	for a team.
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

	# Author identity: dashboard session user. Falls back to email when full_name is empty.
	user_email = frappe.session.user or "press@unknown"
	user_name = frappe.db.get_value("User", user_email, "full_name") or user_email
	safe_user_name = user_name.replace("'", "'\\''")
	safe_user_email = user_email.replace("'", "'\\''")
	commit_with_id = (
		f"git -c user.name='{safe_user_name}' -c user.email='{safe_user_email}' commit"
	)

	# Optional: switch to (or create) a target feature branch before commit
	if branch_name:
		branch_name = branch_name.strip()
		if not _BRANCH_RE.fullmatch(branch_name):
			frappe.throw(
				_("Invalid branch name {0}. Allowed: letters, digits, '_', '.', '/', '-'.").format(branch_name)
			)
		checkout = _docker_run(bench, f"git checkout -B {branch_name} HEAD", subdir)
		if checkout.get("returncode") != 0:
			return {"step": "checkout", "branch": branch_name, **checkout}

	add_result = _docker_run(bench, "git add -A", subdir)
	if add_result.get("returncode") != 0:
		return {"step": "add", **add_result}

	commit_result = _docker_run(bench, f"{commit_with_id} -m '{safe_message}'", subdir)
	# commit can fail benignly with "nothing to commit" — proceed to push so
	# already-committed-but-not-pushed work still ships.
	nothing_to_commit = (
		commit_result.get("returncode") != 0
		and "nothing to commit" in (commit_result.get("output") or "").lower()
	)
	if commit_result.get("returncode") != 0 and not nothing_to_commit:
		return {"step": "commit", **commit_result}

	# When pushing a (potentially new) feature branch, set its upstream explicitly.
	push_cmd = f"git push -u origin {branch_name}" if branch_name else "git push"
	push_result = _docker_run(bench, push_cmd, subdir)
	if push_result.get("returncode") != 0:
		# Surface a more useful diagnosis up front; full output still attached.
		out = (push_result.get("output") or "").lower()
		hint = None
		if "permission denied" in out or "publickey" in out:
			hint = "GitHub auth failed — bench's deploy key may be read-only or missing."
		elif "no upstream branch" in out or "matching ref" in out:
			hint = "No upstream branch — checkout/create a branch in the container first."
		elif (
			"no configured push destination" in out
			or "no such remote" in out
			or "does not appear to be a git repo" in out
		):
			hint = (
				"No GitHub remote configured for this app on the bench. Use the "
				"'GitHub' button next to the app row to register it first, then push."
			)
		return {"step": "push", "hint": hint, **push_result}

	# Build a PR-creation URL when pushing to a non-default branch so users
	# can open a pull request straight from the dashboard. Repo URL comes from
	# the App Source so we don't have to parse the (token-bearing) origin URL.
	pr_url = None
	if branch_name:
		repo_url = _get_app_repo_url(bench_name, app)
		if repo_url:
			# Strip trailing .git if present, then build compare URL for the new branch
			repo_url_clean = repo_url[:-4] if repo_url.endswith(".git") else repo_url
			pr_url = f"{repo_url_clean}/pull/new/{branch_name}"

	return {
		"step": "done",
		"status": "Success",
		"output": (push_result.get("output") or "").strip()
			or "Pushed (nothing committed — already in sync)",
		"branch": branch_name,
		"pr_url": pr_url,
		"returncode": 0,
	}
