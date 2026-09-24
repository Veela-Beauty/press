"""Character allowlists for MCP args that end up inside a host shell command.

These tools build a command string that the Press agent runs with shell=True on the
app server, outside any bench container. A quote, `$(` or `;` in one of these args ran
on the host and reached every team's benches there, so only plain names get through.
"""

from __future__ import annotations

import re

import frappe

_APP = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
# New app names are normalised by the handler (lowercased, - to _); a leading letter keeps
# them from being read as an option flag.
_NEW_APP = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_TITLE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.,()&-]{0,79}$")
_GITHUB_OWNER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_GLOB = re.compile(r"^[A-Za-z0-9_.*?-]{1,100}$")

_RULES: dict[str, dict[str, re.Pattern | str]] = {
	"app_create_locally": {"app_name": _NEW_APP, "app_title": _TITLE},
	"app_init_github": {"app_name": _NEW_APP, "github_owner": _GITHUB_OWNER, "repo_name": _REPO},
	"bench_read_app_file": {"app": _APP, "relative_path": "path"},
	"bench_list_app_files": {"app": _APP, "relative_path": "path", "pattern": _GLOB},
}


def assert_safe_args(tool: str, args: dict) -> None:
	for arg, rule in _RULES.get(tool, {}).items():
		value = args.get(arg)
		if value in (None, ""):
			continue
		if not isinstance(value, str) or not _matches(rule, value):
			raise frappe.ValidationError(
				f"{arg!r} for {tool!r} may only contain letters, digits and _ . - "
				"(paths: those plus '/', no '..')"
			)


def _matches(rule: re.Pattern | str, value: str) -> bool:
	if rule == "path":
		segments = value.split("/")
		return not value.startswith("/") and all(
			s not in ("", ".", "..") and _PATH_SEGMENT.match(s) for s in segments
		)
	return bool(rule.match(value))
