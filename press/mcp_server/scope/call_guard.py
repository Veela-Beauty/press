"""Check every resource an MCP call names, not only the one _extract_target picks.

_extract_target returns ONE target per call. Tools that take a second resource (a
destination bench, a deploy candidate, an app source, a backup file, a server) were
checked on the first and acted on the second, so a token could reach another team
through the argument nobody looked at.
"""

from __future__ import annotations

import frappe

from press.mcp_server.scope.targets import _candidate_to_release_group
from press.mcp_server.scope.teams import assert_in_team, not_visible

_SITE_ARGS = ("site", "site_name")
_RG_ARGS = ("release_group", "target_release_group")
_BENCH_ARGS = ("bench_name", "target_bench")
_CANDIDATE_ARGS = ("dn", "candidate_name", "target_candidate", "dc_name")
_SOURCE_ARGS = ("app_source", "source")
_REMOTE_FILE_ARGS = ("database", "public", "private", "config")
# Placement tools may use a public server; tools that read a server's jobs or memory may not.
_PLACEMENT_TOOLS = frozenset({"release_group_create", "site_create"})
# Tools that execute code or read files inside the bench container, which every site on
# that bench shares.
_IN_CONTAINER_TOOLS = frozenset(
	{
		"site_run_python",
		"site_run_sql",
		"site_db_processlist",
		"site_file_read",
		"site_file_write",
		"site_config_get",
		"site_config_set",
		"bench_recent_logs",
		"bench_run_repo_script",
		"bench_read_app_file",
		"bench_list_app_files",
		"app_create_locally",
		"app_init_github",
		"app_git_push",
		"app_git_status",
		"bench_ssh_connect",
		"bench_ssh_cert_get",
		"bench_ssh_cert_generate",
	}
)


def assert_call_in_team(tool: str, args: dict, team: str) -> None:
	for arg, check in _ARG_CHECKS.items():
		if args.get(arg):
			check(team, args[arg])
	_assert_server(team, args.get("server"), allow_public=tool in _PLACEMENT_TOOLS)
	_assert_nested(team, args)
	_TOOL_RULES.get(tool, _no_rule)(team, args)
	if tool in _IN_CONTAINER_TOOLS:
		_assert_bench_single_tenant(team, _bench_of_call(args))


def _no_rule(team: str, args: dict) -> None:
	pass


def _assert_same_team(team: str, value: str) -> None:
	if value != team:
		raise frappe.PermissionError("a token can only act for its own team")


def _assert_nested(team: str, args: dict) -> None:
	for row in args.get("new_apps") or []:
		if isinstance(row, dict):
			_assert_source_usable(team, row.get("source"))
	for row in args.get("apps") or []:
		if isinstance(row, dict):
			_assert_release(team, row.get("release"))


def _rule_remote_files(team: str, args: dict) -> None:
	for arg in _REMOTE_FILE_ARGS:
		_assert_remote_file(team, args.get(arg))


def _assert_candidate(team: str, name: str | None) -> None:
	if not name:
		return
	rg = _candidate_to_release_group(name)
	if not rg:
		raise frappe.PermissionError(not_visible("Deploy Candidate", name))
	assert_in_team(team, "Release Group", rg)


def _assert_source_usable(team: str, name: str | None) -> None:
	"""Own sources, or public (marketplace) sources such as frappe/erpnext."""
	if not name:
		return
	row = frappe.db.get_value("App Source", name, ["team", "public"], as_dict=True)
	if not row or (row.team != team and not row.public):
		raise frappe.PermissionError(not_visible("App Source", name))


def _assert_source_owned(team: str, name: str | None) -> None:
	"""Changing a source changes every bench built from it, so it must be ours alone."""
	if not name:
		return
	assert_in_team(team, "App Source", name)
	users = frappe.get_all(
		"Release Group App", filters={"source": name, "parenttype": "Release Group"}, pluck="parent"
	)
	if users and frappe.db.count("Release Group", {"name": ["in", users], "team": ["!=", team]}):
		raise frappe.PermissionError(
			f"App Source {name!r} is also used by another team's bench; change it from the dashboard"
		)


def _assert_server(team: str, name: str | None, allow_public: bool) -> None:
	if not name:
		return
	row = frappe.db.get_value("Server", name, ["team", "public"], as_dict=True)
	if not row or (row.team != team and not (allow_public and row.public)):
		raise frappe.PermissionError(not_visible("Server", name))


def _assert_job(team: str, name: str | None) -> None:
	if not name:
		return
	row = frappe.db.get_value("Agent Job", name, ["site", "bench", "server"], as_dict=True)
	if not row or job_team(row) != team:
		raise frappe.PermissionError(not_visible("Agent Job", name))


def job_team(row) -> str | None:
	if row.get("site"):
		return frappe.db.get_value("Site", row["site"], "team")
	if row.get("bench"):
		return frappe.db.get_value("Bench", row["bench"], "team")
	if row.get("server"):
		return frappe.db.get_value("Server", row["server"], "team")
	return None


def _assert_release(team: str, name: str | None) -> None:
	if not name:
		return
	row = frappe.db.get_value("App Release", name, ["source", "public"], as_dict=True)
	if not row:
		raise frappe.PermissionError(not_visible("App Release", name))
	_assert_source_usable(team, row.source)


def _assert_remote_file(team: str, name: str | None) -> None:
	"""A backup file belongs to the team whose site it was taken from."""
	if not name:
		return
	site = frappe.db.get_value("Remote File", name, "site")
	sites = {site} if site else set()
	for field in ("remote_database_file", "remote_public_file", "remote_private_file", "remote_config_file"):
		sites.update(frappe.get_all("Site Backup", filters={field: name}, pluck="site"))
	for s in sites:
		if frappe.db.get_value("Site", s, "team") != team:
			raise frappe.PermissionError(not_visible("Remote File", name))


def _bench_of_call(args: dict) -> str | None:
	for arg in ("site_name", "site"):
		if args.get(arg):
			return frappe.db.get_value("Site", args[arg], "bench")
	return args.get("bench_name")


def _assert_bench_single_tenant(team: str, bench: str | None) -> None:
	"""Code or file access inside a bench container reaches every site on that bench."""
	if not bench:
		return
	if frappe.db.count("Site", {"bench": bench, "team": ["!=", team], "status": ["!=", "Archived"]}):
		raise frappe.PermissionError(
			f"bench {bench!r} also hosts another team's sites, so in-container access is refused"
		)


def _rule_set_app_branch(team: str, args: dict) -> None:
	source = frappe.db.get_value(
		"Release Group App", {"parent": args.get("release_group"), "app": args.get("app")}, "source"
	)
	_assert_source_owned(team, source)


def _rule_fetch_latest(team: str, args: dict) -> None:
	source = args.get("app_source")
	if not source and args.get("release_group") and args.get("app"):
		source = frappe.db.get_value(
			"Release Group App", {"parent": args["release_group"], "app": args["app"]}, "source"
		)
	if not source:
		raise frappe.PermissionError("pass app_source, or app together with release_group")
	# Fetching creates a release, and auto-deploy then rebuilds every bench on this source.
	_assert_source_owned(team, source)


def _rule_release_approve(team: str, args: dict) -> None:
	row = frappe.db.get_value("App Release", args.get("release_name"), ["source", "public"], as_dict=True)
	if not row or row.public:
		raise frappe.PermissionError(not_visible("App Release", args.get("release_name")))
	_assert_source_owned(team, row.source)


def _rule_register_app(team: str, args: dict) -> None:
	owner = _repository_owner(args.get("repository_url") or "")
	given = args.get("github_installation_id")
	ours = set(
		frappe.get_all(
			"App Source",
			filters={"team": team, "github_installation_id": ["is", "set"]},
			pluck="github_installation_id",
		)
	)
	if given and given not in ours:
		raise frappe.PermissionError("that GitHub installation is not connected to this team")
	if not given and owner:
		# The handler would otherwise borrow the first installation any team has for this owner.
		found = frappe.get_all(
			"App Source",
			filters={"repository_owner": owner, "github_installation_id": ["is", "set"]},
			pluck="github_installation_id",
			limit=1,
		)
		if found and found[0] not in ours:
			raise frappe.PermissionError(
				f"GitHub owner {owner!r} is connected through another team; pass this team's "
				"github_installation_id"
			)


def _repository_owner(url: str) -> str:
	path = url.split("github.com/", 1)[-1].strip("/")
	return path.split("/", 1)[0] if "/" in path else ""


def _rule_list_pending(team: str, args: dict) -> None:
	if args.get("app") and args.get("release_group"):
		source = frappe.db.get_value(
			"Release Group App", {"parent": args["release_group"], "app": args["app"]}, "source"
		)
		_assert_source_usable(team, source)


def _checker(doctype: str):
	return lambda team, value: assert_in_team(team, doctype, value)


# arg name -> check that the value it names belongs to the token's team
_ARG_CHECKS = {
	**{arg: _checker("Site") for arg in _SITE_ARGS},
	**{arg: _checker("Release Group") for arg in _RG_ARGS},
	**{arg: _checker("Bench") for arg in _BENCH_ARGS},
	**{arg: _assert_candidate for arg in _CANDIDATE_ARGS},
	**{arg: _assert_source_usable for arg in _SOURCE_ARGS},
	"job_name": _assert_job,
	"release_name": _assert_release,
	"team": _assert_same_team,
}

_TOOL_RULES = {
	"site_create": _rule_remote_files,
	"site_restore": _rule_remote_files,
	"bench_set_app_branch": _rule_set_app_branch,
	"app_source_fetch_latest": _rule_fetch_latest,
	"app_release_approve": _rule_release_approve,
	"register_existing_app": _rule_register_app,
	"list_pending_releases": _rule_list_pending,
}
