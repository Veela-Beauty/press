# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""The Telephony view of the infra tree: PBX hosts + per-host telemetry.

`build_pbx_tree` assembles the EXACT host shape the Vue page binds to (see
dashboard/src/pages/telephony/tele-derive.js + its test fixtures):
  { name, ip, status, container, listener, active_calls, cpu_pct, uptime,
    instances:[{instance, site, trunk, did, reg}] }
plus a roll-up `summary` and a `generated` ISO timestamp. Every per-host probe
is best-effort (reuses infra_telephony.telephony_status), so one unreachable
host degrades to status='down'/'unknown' and never breaks the whole payload.
Pure helpers (`_host_status`, `_reg`, `_roll_up`) are unit-tested directly."""
from __future__ import annotations

import frappe


def _reg(active: bool) -> str:
	return "reg" if active else "unreg"


def _host_status(reach_ok: bool, listener_connected: bool, any_unreg: bool) -> str:
	"""Map raw per-host booleans to the dashboard status token. Pure + tested.
	unreachable -> 'unknown'; a not-connected listener or an unregistered trunk
	is a 'warn'; otherwise 'up'. (A hard 'down' is set by the caller when the
	host itself is Unreachable.)"""
	if not reach_ok:
		return "unknown"
	if not listener_connected or any_unreg:
		return "warn"
	return "up"


def _container_word(reach_ok: bool, listener_connected: bool) -> str:
	if not reach_ok:
		return "missing"
	# The oc-asterisk container is the PBX; if the listener AMI-connected to it,
	# the container is necessarily running. Without a connected listener we still
	# report 'running' on a reachable host (the probe confirmed reachability) and
	# surface the listener state separately.
	return "running"


def _pbx_rows_by_host() -> dict[str, list[dict]]:
	"""Active Telephony PBX rows grouped by host. Parameterized ORM read only."""
	rows = frappe.get_all(
		"Telephony PBX",
		filters={"status": "Active"},
		fields=["host", "instance", "site_url", "public_ip"],
	)
	by_host: dict[str, list[dict]] = {}
	for r in rows:
		by_host.setdefault(r["host"], []).append(r)
	return by_host


def _instance_meta(instance: str) -> dict:
	"""Best-effort trunk/DID metadata for an instance from the co-hosted
	frappe_omnichannel OC Channel Instance. NEVER reads trunk_password. Returns
	empty strings when the doctype is absent (control-plane-only Press site)."""
	try:
		meta = frappe.db.get_value(
			"OC Channel Instance", instance,
			["trunk_server", "did_number", "company"], as_dict=True,
		)
	except Exception:
		meta = None
	if not meta:
		return {"trunk": "", "did": ""}
	# trunk label: prefer the company (human) then the trunk_server (host).
	return {"trunk": meta.get("company") or meta.get("trunk_server") or "", "did": meta.get("did_number") or ""}


def _build_host(host_name: str, pbx_rows: list[dict]) -> dict:
	"""One PBX host node in the page's shape. Probes telemetry through the same
	cert SSH channel the describe read uses; a probe failure degrades the host to
	status='unknown' rather than raising."""
	from press.api.infra_telephony import _managed_doc, telephony_status

	public_ip = (pbx_rows[0].get("public_ip") if pbx_rows else "") or ""
	reach_ok = True
	tele = {"trunk_registered": False, "active_calls": 0, "listener_connected": False}
	try:
		tele = telephony_status(_managed_doc(host_name))
	except Exception:
		reach_ok = False

	listener_connected = bool(tele.get("listener_connected"))
	# One Asterisk serves several companies; the probe gives a single trunk-reg
	# boolean for the host, so every served instance reflects that host-level
	# registration. (Per-instance registration is a future probe refinement.)
	trunk_registered = bool(tele.get("trunk_registered"))
	instances = []
	for r in pbx_rows:
		m = _instance_meta(r["instance"])
		instances.append({
			"instance": r["instance"],
			"site": (r.get("site_url") or "").replace("https://", "").replace("http://", "").rstrip("/"),
			"trunk": m["trunk"],
			"did": m["did"],
			"reg": _reg(trunk_registered),
		})

	any_unreg = any(i["reg"] == "unreg" for i in instances)
	return {
		"name": host_name,
		"ip": public_ip,
		"status": _host_status(reach_ok, listener_connected, any_unreg),
		"container": _container_word(reach_ok, listener_connected),
		"listener": "connected" if listener_connected else ("disconnected" if reach_ok else "unknown"),
		"active_calls": int(tele.get("active_calls") or 0),
		"cpu_pct": tele.get("cpu_pct"),
		"uptime": tele.get("uptime") or "",
		"instances": instances,
	}


def _roll_up(hosts: list[dict]) -> dict:
	"""Server-side summary mirroring tele-derive.summary so the page and the API
	agree even before the client recomputes. Pure + tested."""
	trunks = registered = trunk_down = active_calls = listeners_up = 0
	for h in hosts:
		insts = h.get("instances") or []
		trunks += len(insts)
		registered += sum(1 for i in insts if i.get("reg") == "reg")
		trunk_down += sum(1 for i in insts if i.get("reg") == "unreg")
		active_calls += h.get("active_calls") or 0
		if h.get("listener") == "connected":
			listeners_up += 1
	return {
		"hosts": len(hosts), "trunks": trunks, "registered": registered,
		"trunkDown": trunk_down, "activeCalls": active_calls, "listenersUp": listeners_up,
	}


def build_pbx_tree() -> dict:
	"""Assemble { hosts, summary, generated } for the Telephony page. Iterates the
	Active Telephony PBX rows grouped by host so a host with no PBX record simply
	does not appear (the Telephony view is PBX-scoped, unlike the full infra tree)."""
	by_host = _pbx_rows_by_host()
	hosts = [_build_host(name, rows) for name, rows in by_host.items()]
	return {
		"hosts": hosts,
		"summary": _roll_up(hosts),
		"generated": frappe.utils.now(),
	}
