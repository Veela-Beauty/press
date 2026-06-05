# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Infra Control Panel backend: host probes + the server->bench->service tree.

Read-only, System-Manager-gated, Redis-cached. Reuses existing Press
primitives (get_processes, get_dev_overview_benches, host_memory_pressure,
agent_health) and soft-imports Watch Tower's ssh_cmd for the ssh probe.
"""
from __future__ import annotations

import frappe


def _memory(server: str):
	from press.mcp_server.deploy_flow import host_memory_pressure

	return host_memory_pressure(server=server)


def _agent(server: str):
	from press.mcp_server.deploy_flow import agent_health

	return agent_health(server=server, lookback_minutes=10)


def _ssh_ok(server: str) -> bool:
	try:
		from frappe_theme_switcher.watch_tower.alerts._helpers import ssh_cmd

		ip = frappe.db.get_value("Server", server, "ip") or server
		ok, _out, _err = ssh_cmd(ip, "echo OK", timeout=8)
		return bool(ok)
	except Exception:
		return False


def _safe(fn, *args):
	try:
		return fn(*args)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"infra_board probe failed: {getattr(fn, '__name__', repr(fn))}")
		return None


def host_probes(server: str) -> dict:
	"""Per-server health dict. Every probe is best-effort: a failing probe
	degrades to None and never breaks the whole payload.
	"""
	mem = _safe(_memory, server)
	mem_norm = None
	if mem:
		total = mem.get("memory_total_mb") or 0
		avail = mem.get("memory_available_mb") or 0
		used_pct = round((total - avail) / total * 100) if total else 0
		mem_norm = {"verdict": mem.get("verdict"), "used_pct": used_pct,
			"available_mb": avail, "total_mb": total}

	agent = _safe(_agent, server)
	return {
		"server": server,
		"memory": mem_norm,
		"agent": {"verdict": agent.get("verdict")} if agent else None,
		"ssh": {"ok": _safe(_ssh_ok, server) or False},
	}
