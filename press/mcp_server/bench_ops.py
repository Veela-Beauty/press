# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""MCP bench-control wrappers — Release Group composition + lifecycle.

Thin wrappers over `press.api.bench` whitelisted methods so an MCP agent can
fully manage a Release Group (a "Bench" in the dashboard) without falling back
to the Desk: add/remove apps, switch sources, list branches/versions, rename,
redeploy, archive, rebuild assets, and create a fresh group.

Each wrapper runs inside the dispatcher's `_as_user()` context, so the
underlying `@protected("Release Group")` team checks still apply. Returns are
JSON-safe dicts/lists. Mutating wrappers `frappe.db.commit()` explicitly — the
MCP request context does NOT auto-commit (same gotcha as site_run_python), so
without it the change would silently roll back when the request ends.
"""
from __future__ import annotations

from typing import Any

import frappe

from press.api import bench as bench_api


def _assert_rg(name: str) -> None:
	if not frappe.db.exists("Release Group", name):
		frappe.throw(f"Release Group {name!r} not found", frappe.DoesNotExistError)


def release_group_add_app(name: str, source: str, app: str) -> dict[str, Any]:
	_assert_rg(name)
	if not frappe.db.exists("App Source", source):
		frappe.throw(f"App Source {source!r} not found", frappe.DoesNotExistError)
	bench_api.add_app(name, source, app)
	frappe.db.commit()
	return {
		"release_group": name,
		"app": app,
		"source": source,
		"added": True,
		"note": "Trigger release_group_create_deploy_candidate + deploy to apply.",
	}


def release_group_remove_app(name: str, app: str) -> dict[str, Any]:
	_assert_rg(name)
	bench_api.remove_app(name, app)
	frappe.db.commit()
	return {
		"release_group": name,
		"app": app,
		"removed": True,
		"note": "App stays on running benches until the next deploy — create a "
		"deploy candidate + deploy to drop it.",
	}


def release_group_list_branches(name: str, app: str) -> dict[str, Any]:
	_assert_rg(name)
	branches = bench_api.branch_list(name, app)
	return {"release_group": name, "app": app, "branches": branches}


def release_group_versions(name: str) -> list[dict]:
	_assert_rg(name)
	return bench_api.versions(name)


def release_group_installable_apps(name: str) -> Any:
	_assert_rg(name)
	return bench_api.installable_apps(name)


def release_group_rename(name: str, title: str) -> dict[str, Any]:
	_assert_rg(name)
	bench_api.rename(name, title)
	frappe.db.commit()
	return {"release_group": name, "title": title, "renamed": True}


def release_group_redeploy(name: str, dc_name: str) -> dict[str, Any]:
	_assert_rg(name)
	new_candidate = bench_api.redeploy(name, dc_name)
	frappe.db.commit()
	return {"release_group": name, "from_candidate": dc_name, "new_candidate": new_candidate}


def release_group_archive(name: str) -> dict[str, Any]:
	_assert_rg(name)
	bench_api.archive(name)
	frappe.db.commit()
	return {"release_group": name, "archived": True}


def bench_rebuild_assets(name: str) -> dict[str, Any]:
	if not frappe.db.exists("Bench", name):
		frappe.throw(f"Bench {name!r} not found", frappe.DoesNotExistError)
	bench_api.rebuild(name)
	frappe.db.commit()
	return {"bench": name, "rebuild_enqueued": True}


def release_group_create(
	title: str,
	version: str,
	new_apps: list[dict],
	cluster: str,
	server: str = "",
	saas_app: str = "",
) -> dict[str, Any]:
	if bench_api.exists(title):
		frappe.throw(f"A Release Group titled {title!r} already exists")
	bench = {
		"title": title,
		"version": version,
		"apps": new_apps,
		"cluster": cluster,
		"server": server or "",
		"saas_app": saas_app or "",
	}
	rg_name = bench_api.new(bench)
	frappe.db.commit()
	return {"release_group": rg_name, "title": title, "version": version, "created": True}
