"""
GitHub remotes for a Development Bench's apps.

The bench image is built with `bench get-app file:///home/frappe/context/apps/<app>`, so in the running container
each app's only remote is that build folder (gone) and its checkout is a detached commit: a developer could not push
from a fresh development bench (27 Nov 2026, filming the AutoDeploy course). When a bench becomes a development bench
this does the dashboard guide's steps 3.5 and 3.6 for every app whose source is a GitHub repository: `origin` is the
repository's HTTPS URL (the guide's git auth script needs HTTPS), and a detached checkout moves onto the source's
branch at the same commit, tracking origin/<branch>. Nothing is fetched or pushed: a private repository needs the
developer's own GitHub sign-in (guide step 3), and no git identity is set. A checkout already on a branch is never
switched, and a local branch that points elsewhere is never moved. Safe to run again.
"""

import re
import shlex

import frappe

GITHUB_URL = re.compile(r"^(?:https://github\.com/|git@github\.com:)([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")


def https_url(url: str | None) -> str | None:
	"""https://github.com/<owner>/<repo>.git for an https:// or git@ GitHub URL; None for anything else."""
	match = GITHUB_URL.match((url or "").strip())
	return f"https://github.com/{match.group(1)}/{match.group(2)}.git" if match else None


def app_remotes(bench_doc) -> list[tuple[str, str, str]]:
	"""(app, HTTPS URL, branch) for each app of the bench whose App Source is a GitHub repository with a branch."""
	remotes = []
	for row in bench_doc.apps:
		source = frappe.db.get_value("App Source", row.source, ["repository_url", "branch"], as_dict=True)
		url = https_url(source.repository_url) if source else None
		if url and source.branch:
			remotes.append((row.app, url, source.branch))
	return remotes


def app_script(app: str, url: str, branch: str) -> str:
	"""The shell for one app, run in the bench folder: origin to GitHub, then a detached checkout onto its branch."""
	a, u, b = shlex.quote(app), shlex.quote(url), shlex.quote(branch)
	ref = shlex.quote(f"refs/heads/{branch}")
	return (
		f"cd apps/{a} && "
		f"{{ git remote get-url origin >/dev/null 2>&1 && git remote set-url origin {u} || git remote add origin {u}; }} && "
		f"if ! git symbolic-ref -q HEAD >/dev/null; then "
		f"if ! git show-ref -q --verify {ref}; then git checkout -q -b {b}; "
		f'elif [ "$(git rev-parse {ref})" = "$(git rev-parse HEAD)" ]; then git checkout -q {b}; fi; fi && '
		f'if [ "$(git symbolic-ref -q --short HEAD)" = {b} ]; then '
		f"git config branch.{b}.remote origin && git config branch.{b}.merge {ref}; fi && "
		f'echo {a}": $(git remote get-url origin) on $(git symbolic-ref -q --short HEAD || echo detached)"'
	)


def connect_app_remotes(bench_doc) -> str:
	"""Run every app's script in the bench container (one app failing does not stop the others); the output names
	each app's origin and branch."""
	remotes = app_remotes(bench_doc)
	if not remotes:
		return ""
	command = " ; ".join(f"( {app_script(*r)} )" for r in remotes)
	result = bench_doc.docker_execute(f"bash -c {shlex.quote(command)}")
	return (result or {}).get("output") or ""


def apply_development_mode(bench_doc) -> None:
	"""The container side of the Development Bench flag: bench watch on or off and, when on, the apps' GitHub remotes.
	A failure is logged, never raised: the flag itself is already saved, and the dashboard shows the watch status."""
	from press.press.doctype.bench.bench_dev_watch import start_watch, stop_watch

	try:
		(start_watch if bench_doc.is_development_bench else stop_watch)(bench_doc)
	except Exception as e:
		frappe.logger().error(f"{bench_doc.name}: bench watch toggle failed: {e}")
	if bench_doc.is_development_bench:
		try:
			connect_app_remotes(bench_doc)
		except Exception as e:
			frappe.logger().error(f"{bench_doc.name}: app git remotes failed: {e}")
