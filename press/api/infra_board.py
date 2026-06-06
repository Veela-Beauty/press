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


import json

CACHE_KEY = "infra_board:tree"
CACHE_TTL = 15  # seconds


def _all_servers() -> list[str]:
	return frappe.get_all("Server", filters={"status": "Active"}, pluck="name")


def _all_benches() -> list[dict]:
	from press.press.doctype.bench.bench_dev_overview import get_dev_overview_benches

	return get_dev_overview_benches()


def _bench_services(bench_name: str) -> list[dict]:
	from press.api.bench import get_processes

	try:
		return get_processes(bench_name) or []
	except Exception:
		return []


def _service_state(status: str) -> str:
	return "run" if status == "Running" else "down"


def _press_servers() -> list:
	benches = _all_benches()
	by_server: dict[str, list] = {}
	for b in benches:
		services = _bench_services(b["name"])
		down = sum(1 for s in services if s.get("status") != "Running")
		node = {
			"name": b["name"],
			"group": b.get("group"),
			"status": b.get("status"),
			"site_count": b.get("site_count", 0),
			"services": [
				{"program": s.get("program"), "state": _service_state(s.get("status")), "status": s.get("status")}
				for s in services
			],
			"services_up": len(services) - down,
			"services_down": down,
			# No services found means the supervisor probe failed / bench
			# unreachable: report 'unknown', never a false-green 'up'.
			"health": ("unknown" if not services else "down" if down else "up"),
		}
		by_server.setdefault(b.get("server"), []).append(node)

	servers = []
	for name in _all_servers():
		bs = by_server.get(name, [])
		any_bad = any(x["health"] != "up" for x in bs)
		servers.append({
			"name": name,
			"benches": bs,
			"host": host_probes(name),
			"health": "down" if any_bad else "up",
		})
	return servers


def _managed_hosts() -> list:
	return frappe.get_all(
		"Managed Host", filters={"status": ["!=", "Pending"]},
		fields=["name as host_name", "server_type", "ssh_host", "ssh_port", "ssh_user", "proxy_port", "status"],
	)


def _enumerate_managed(host) -> dict:
	from press.infra.adapters.base import get_adapter

	try:
		out = get_adapter(host).enumerate(host)
		out.setdefault("reach", "ok")
		return out
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"infra enumerate failed: {host.host_name}")
		return {"units": [], "metrics": {"cpu": 0, "mem": 0, "disk": 0, "req": 0}, "reach": "fail"}


def _overload(m: dict):
	hi = max(m.get("cpu", 0), m.get("mem", 0), m.get("disk", 0))
	return "crit" if hi >= 90 else "high" if hi >= 80 else None


def _build_tree() -> dict:
	servers = _press_servers()
	for h in _managed_hosts():
		en = _enumerate_managed(h)
		units = en["units"]
		down = sum(1 for u in units if u.get("state") in ("stop", "exit2", "down"))
		overload = _overload(en["metrics"])
		servers.append({
			"name": h.host_name, "kind": "managed", "server_type": h.server_type,
			"benches": [],
			"units": units, "metrics": en["metrics"], "overload": overload,
			"host": {"server": h.host_name},
			"health": ("unknown" if (h.status == "Unreachable" or en.get("reach") == "fail") else "down" if (down or overload == "crit") else "up"),
		})
	return {"servers": servers}


@frappe.whitelist()
def get_infra_tree() -> dict:
	"""System-Manager-gated, Redis-cached server->bench->service tree."""
	frappe.only_for("System Manager")
	# Cache the tree for CACHE_TTL so a live polling board does not re-run a
	# synchronous supervisorctl-status exec per bench every tick. Keys set with
	# expires_in_sec live in Redis only, so the read MUST pass expires=True to
	# force a Redis GET (frappe.local.cache is stale for expiring keys).
	cached = frappe.cache().get_value(CACHE_KEY, expires=True)
	if cached is not None:
		if isinstance(cached, bytes):
			cached = cached.decode("utf-8")
		return json.loads(cached) if isinstance(cached, str) else cached
	tree = _build_tree()
	frappe.cache().set_value(CACHE_KEY, json.dumps(tree), expires_in_sec=CACHE_TTL)
	return tree
