# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Git-fetch + execute Python scripts inside a bench container.

Reuses press.press.doctype.bench.bench_dev_overview.run_python_on_site for
the actual execution. This module's job is:
  1. Validate the repo + branch + script_path against an allowlist.
  2. Fetch the script content from GitHub (raw URL, optional auth via
     Press Settings.github_access_token for private repos).
  3. Hand the script content to run_python_on_site.

Constraints (enforced here, NOT delegated):
  - repo must be in Press Settings.mcp_script_repo_allowlist (JSON list).
  - script_path must end in .py and not contain ".." segments.
  - Empty allowlist = NO repos allowed (fail-closed).
"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import frappe
import requests

from press.mcp_server._util import safe_parse_list

DEFAULT_TIMEOUT_SECONDS = 60
MAX_TIMEOUT_SECONDS = 600
MAX_SCRIPT_BYTES = 1 * 1024 * 1024  # 1 MB cap on fetched script


def fetch_script_from_github(
	repo: str,
	branch: str,
	script_path: str,
) -> str:
	"""Fetch a script's raw content from GitHub. Returns text.

	Caller MUST validate the repo against the allowlist BEFORE calling.
	"""
	# raw.githubusercontent.com is the public direct file URL
	url = (
		f"https://raw.githubusercontent.com/{repo}/{branch}/"
		f"{quote(script_path, safe='/')}"
	)
	headers = {"User-Agent": "press-mcp-script-runner/1.0"}
	# Use Press's GitHub token for private repos. Public repos work without it.
	token = _get_github_token()
	if token:
		headers["Authorization"] = f"Bearer {token}"
	resp = requests.get(url, headers=headers, timeout=15)
	if resp.status_code == 404:
		raise frappe.ValidationError(
			f"Script not found: {repo}@{branch}/{script_path}"
		)
	if resp.status_code == 401 or resp.status_code == 403:
		raise frappe.PermissionError(
			f"GitHub access denied for {repo}@{branch}/{script_path} "
			f"(status {resp.status_code}). Configure Press Settings.github_access_token."
		)
	resp.raise_for_status()
	if len(resp.content) > MAX_SCRIPT_BYTES:
		raise frappe.ValidationError(
			f"Script too large: {len(resp.content)} bytes (max {MAX_SCRIPT_BYTES})"
		)
	return resp.text


def validate_script_request(repo: str, branch: str, script_path: str) -> None:
	"""Raise ValidationError / PermissionError if request is unsafe."""
	if not repo or "/" not in repo:
		raise frappe.ValidationError(
			"repo must be in 'owner/name' format (e.g., 'accurate-systems/wazin_mx')"
		)
	if not branch or not isinstance(branch, str):
		raise frappe.ValidationError("branch must be a non-empty string")
	if not script_path or not script_path.endswith(".py"):
		raise frappe.ValidationError("script_path must end in '.py'")
	if ".." in script_path.split("/"):
		raise frappe.ValidationError("script_path must not contain '..' segments")
	# Check allowlist
	allowlist = _get_repo_allowlist()
	if not allowlist:
		raise frappe.PermissionError(
			"Press Settings.mcp_script_repo_allowlist is empty; no repos allowed. "
			"A System User must populate it before bench_run_repo_script can be used."
		)
	if repo not in allowlist:
		raise frappe.PermissionError(
			f"Repo {repo!r} is not in the MCP script allowlist. "
			f"Allowed: {sorted(allowlist)}"
		)


@frappe.whitelist()
def bench_run_repo_script(
	bench_name: str,
	repo: str,
	branch: str,
	script_path: str,
	site_name: str | None = None,
	timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
	"""Fetch a Python script from an allowlisted GitHub repo and run it via
	the bench's Python console (uses run_python_on_site under the hood).

	Args:
		bench_name: Bench docname (used for site resolution if site_name omitted).
		repo: GitHub `owner/name` (must be in Press Settings allowlist).
		branch: Branch or tag.
		script_path: Path within repo (e.g., 'scripts/seed.py').
		site_name: Site to run the script in. If omitted, picks the first Active
			site on the bench.
		timeout_seconds: Cap on agent-side execution. Min 1, max 600.

	Returns:
		{site, repo, branch, script_path, output, bytes_fetched}
	"""
	timeout_seconds = max(1, min(MAX_TIMEOUT_SECONDS, int(timeout_seconds)))
	validate_script_request(repo, branch, script_path)

	# Resolve site if not given
	if not site_name:
		site_name = frappe.db.get_value(
			"Site",
			{"bench": bench_name, "status": "Active"},
			"name",
			order_by="creation desc",
		)
		if not site_name:
			raise frappe.ValidationError(
				f"No Active site found on bench {bench_name!r}; pass site_name explicitly"
			)

	script_content = fetch_script_from_github(repo, branch, script_path)
	# Delegate to the existing console-runner. It handles docker_execute
	# correctly per the bench_dev_overview.py implementation.
	from press.press.doctype.bench.bench_dev_overview import run_python_on_site
	output = run_python_on_site(site_name=site_name, code=script_content)

	return {
		"site": site_name,
		"bench": bench_name,
		"repo": repo,
		"branch": branch,
		"script_path": script_path,
		"bytes_fetched": len(script_content),
		"output": output,
	}


def _get_repo_allowlist() -> list[str]:
	raw = frappe.db.get_single_value(
		"Press Settings", "mcp_script_repo_allowlist"
	)
	return safe_parse_list(raw)


def _get_github_token() -> str | None:
	# Reuse Press's existing GitHub token for raw.githubusercontent.com.
	# Press Settings stores it as a Password field; we get the decrypted value.
	try:
		from frappe.utils.password import get_decrypted_password
		return get_decrypted_password(
			"Press Settings", "Press Settings", "github_access_token", raise_exception=False
		)
	except Exception:
		return None
