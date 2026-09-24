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
_REMOTE_FILE_FIELDS = ("remote_database_file", "remote_public_file", "remote_private_file", "remote_config_file")
# Placement tools may put new things on a public server or a public (shared) bench, as the
# dashboard's default new-site flow does; tools that read or change them may not.
PLACEMENT_TOOLS = frozenset({"release_group_create", "site_create"})
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
			check(team, args[arg], tool)
	_assert_server(team, args.get("server"), allow_public=tool in PLACEMENT_TOOLS)
	_assert_nested(team, args)
	_TOOL_RULES.get(tool, _no_rule)(team, args)
	if tool in _IN_CONTAINER_TOOLS:
		for bench in _benches_of_call(args):
			_assert_bench_single_tenant(team, bench)


def assert_release_group(team: str, name: str, tool: str | None = None) -> None:
	"""A public, enabled bench is shared by design, but only for placing a new site on it."""
	if tool in PLACEMENT_TOOLS and frappe.db.get_value("Release Group", {"name": name, "public": 1, "enabled": 1}):
		return
	assert_in_team(team, "Release Group", name)


def _no_rule(team: str, args: dict) -> None:
	pass


def _check_site(team: str, value: str, tool: str) -> None:
	assert_in_team(team, "Site", value)
	_assert_allowlisted("Site", value)


def _check_release_group(team: str, value: str, tool: str) -> None:
	assert_release_group(team, value, tool)
	_assert_allowlisted("Release Group", value)


def _check_bench(team: str, value: str, tool: str) -> None:
	# Bench.team is copied from its group only on a full save, so after a Release Group
	# changes team it can still name the old one. The group is authoritative.
	group = frappe.db.get_value("Bench", value, "group")
	if not group:
		raise frappe.PermissionError(not_visible("Bench", value))
	assert_in_team(team, "Release Group", group)
	_assert_allowlisted("Release Group", group)


def _assert_allowlisted(doctype: str, name: str) -> None:
	"""A token's own allowlists apply to every site/bench it names, not only the first."""
	allowed = getattr(frappe.local, "mcp_token_allowed", None) or {}
	sites, groups = allowed.get("Site") or [], allowed.get("Release Group") or []
	if doctype == "Site":
		if sites and name not in sites:
			raise frappe.PermissionError(f"token does not allow Site {name!r}")
		name, doctype = frappe.db.get_value("Site", name, "group"), "Release Group"
	if doctype == "Release Group" and groups and name not in groups:
		raise frappe.PermissionError(f"token does not allow Release Group {name!r}")


def _assert_same_team(team: str, value: str, tool: str | None = None) -> None:
	if value != team:
		raise frappe.PermissionError("a token can only act for its own team")


def _rows(args: dict, arg: str) -> list[dict]:
	"""Read a list arg the way the handler will: some handlers accept it as a JSON string."""
	value = args.get(arg)
	if value in (None, "", []):
		return []
	if isinstance(value, str):
		try:
			value = frappe.parse_json(value)
		except Exception:
			raise frappe.PermissionError(f"{arg!r} must be a list of objects") from None
	if not isinstance(value, list) or not all(isinstance(r, dict) for r in value):
		raise frappe.PermissionError(f"{arg!r} must be a list of objects")
	return value


def _assert_nested(team: str, args: dict) -> None:
	for row in _rows(args, "new_apps"):
		_assert_source_usable(team, row.get("source"))
	for row in _rows(args, "apps"):
		_assert_release(team, row.get("release"))


def _rule_remote_files(team: str, args: dict) -> None:
	for arg in _REMOTE_FILE_ARGS:
		_assert_remote_file(team, args.get(arg))


def _assert_candidate(team: str, name: str | None, tool: str | None = None) -> None:
	if not name:
		return
	rg = _candidate_to_release_group(name)
	if not rg or frappe.db.get_value("Release Group", rg, "team") != team:
		# One message for missing and foreign, as everywhere else.
		raise frappe.PermissionError(not_visible("Deploy Candidate", name))


def _assert_source_usable(team: str, name: str | None, tool: str | None = None) -> None:
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


def _assert_job(team: str, name: str | None, tool: str | None = None) -> None:
	if not name:
		return
	row = frappe.db.get_value("Agent Job", name, ["site", "bench", "server"], as_dict=True)
	if not row or job_team(row) != team:
		raise frappe.PermissionError(not_visible("Agent Job", name))


def job_team(row) -> str | None:
	if row.get("site"):
		return frappe.db.get_value("Site", row["site"], "team")
	if row.get("bench"):
		group = frappe.db.get_value("Bench", row["bench"], "group")
		return frappe.db.get_value("Release Group", group, "team") if group else None
	if row.get("server"):
		return frappe.db.get_value("Server", row["server"], "team")
	return None


def _assert_release(team: str, name: str | None, tool: str | None = None) -> None:
	if not name:
		return
	row = frappe.db.get_value("App Release", name, ["source", "public"], as_dict=True)
	if not row:
		raise frappe.PermissionError(not_visible("App Release", name))
	_assert_source_usable(team, row.source)


def _assert_remote_file(team: str, name: str | None) -> None:
	"""A backup file belongs to the team whose site it came from or was restored into.

	An upload not yet used by any site is attributed to its uploader, who must belong
	to the token's team.
	"""
	if not name:
		return
	row = frappe.db.get_value("Remote File", name, ["site", "owner"], as_dict=True)
	if not row:
		raise frappe.PermissionError(not_visible("Remote File", name))
	sites = {row.site} if row.site else set()
	for field in _REMOTE_FILE_FIELDS:
		sites.update(frappe.get_all("Site Backup", filters={field: name}, pluck="site"))
		sites.update(frappe.get_all("Site", filters={field: name}, pluck="name"))
	if sites:
		if any(frappe.db.get_value("Site", s, "team") != team for s in sites):
			raise frappe.PermissionError(not_visible("Remote File", name))
		return
	if not frappe.db.exists("Team Member", {"parent": team, "parenttype": "Team", "user": row.owner}):
		raise frappe.PermissionError(not_visible("Remote File", name))


def _benches_of_call(args: dict) -> set[str]:
	"""Every bench the call can reach: a tool may take a site and a bench that differ."""
	benches = {frappe.db.get_value("Site", args[a], "bench") for a in ("site_name", "site") if args.get(a)}
	if args.get("bench_name"):
		benches.add(args["bench_name"])
	return {b for b in benches if b}


def _assert_bench_single_tenant(team: str, bench: str) -> None:
	"""Code or file access inside a bench container reaches every site on that bench.

	Archived sites count too: their folders can stay in the container.
	"""
	if frappe.db.count("Site", {"bench": bench, "team": ["!=", team]}):
		raise frappe.PermissionError(
			f"bench {bench!r} also hosts another team's sites, so in-container access is refused"
		)


def _source_of(release_group: str | None, app: str | None) -> str | None:
	if not (release_group and app):
		return None
	return frappe.db.get_value("Release Group App", {"parent": release_group, "app": app}, "source")


def _rule_set_app_branch(team: str, args: dict) -> None:
	_assert_source_owned(team, _source_of(args.get("release_group"), args.get("app")))


def _rule_fetch_latest(team: str, args: dict) -> None:
	if args.get("release_group") and args.get("app") and not args.get("app_source"):
		# Same as the dashboard's "Fetch latest" on one of the team's own benches (the
		# release group itself was already checked). Any source attached there is fine.
		if not _source_of(args["release_group"], args["app"]):
			raise frappe.PermissionError(f"app {args['app']!r} is not on {args['release_group']!r}")
		return
	if not args.get("app_source"):
		raise frappe.PermissionError("pass app_source, or app together with release_group")
	# Fetching creates a release, and auto-deploy then rebuilds every bench on this source.
	_assert_source_owned(team, args["app_source"])


def _rule_release_approve(team: str, args: dict) -> None:
	source = frappe.db.get_value("App Release", args.get("release_name"), "source")
	if not source:
		raise frappe.PermissionError(not_visible("App Release", args.get("release_name")))
	_assert_source_owned(team, source)


def _rule_register_app(team: str, args: dict) -> None:
	owner = repository_owner(args.get("repository_url") or "")
	given = args.get("github_installation_id")
	ours = set(
		frappe.get_all(
			"App Source",
			filters={"team": team, "github_installation_id": ["is", "set"]},
			pluck="github_installation_id",
		)
	)
	if given:
		# A new installation is fine; one already proven for another team is not ours to use.
		if given not in ours and frappe.db.exists(
			"App Source", {"github_installation_id": given, "team": ["!=", team]}
		):
			raise frappe.PermissionError("that GitHub installation belongs to another team")
		return
	if owner:
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


def repository_owner(repository_url: str) -> str:
	"""Parse the owner exactly as register_existing_app does, so both read the same one."""
	url = repository_url.strip().rstrip("/")
	if url.startswith("https://github.com/"):
		owner_repo = url[len("https://github.com/") :]
	elif url.startswith("git@github.com:"):
		owner_repo = url[len("git@github.com:") :]
	else:
		owner_repo = url
	if owner_repo.endswith(".git"):
		owner_repo = owner_repo[:-4]
	parts = owner_repo.split("/")
	return parts[0] if len(parts) == 2 and all(parts) else ""


def _rule_list_pending(team: str, args: dict) -> None:
	_assert_source_usable(team, _source_of(args.get("release_group"), args.get("app")))


# arg name -> check that the value it names belongs to the token's team
_ARG_CHECKS = {
	**{arg: _check_site for arg in _SITE_ARGS},
	**{arg: _check_release_group for arg in _RG_ARGS},
	**{arg: _check_bench for arg in _BENCH_ARGS},
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
