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


def _parse_cpu_disk(out: str):
	"""Parse the `CPU=<load>:<cores> DISK=<pct>` line from the host-stats probe
	into normalized metrics. Pure + side-effect free so it is unit-tested
	directly. Returns None on any missing or malformed field.
	"""
	if not out or "CPU=" not in out or "DISK=" not in out:
		return None
	try:
		cpu_field = out.split("CPU=", 1)[1].split()[0]   # "0.42:4"
		disk_field = out.split("DISK=", 1)[1].split()[0]  # "53"
		load_s, cores_s = cpu_field.split(":")
		load = float(load_s)
		cores = int(cores_s) or 1
		disk_pct = int(disk_field)
	except (ValueError, IndexError):
		return None
	return {
		"cpu": {"used_pct": min(100, round(load / cores * 100)), "load": load, "cores": cores},
		"disk": {"used_pct": disk_pct},
	}


def _cpu_disk(server: str):
	"""1-min load average + root-disk usage in one SSH round-trip via the same
	Ansible ad-hoc pattern as _memory. Cached 60s per server (the round-trip is
	3-10s). CPU% is load-average / cores (a cheap proxy that needs no sampling),
	capped at 100. Disk% is root filesystem usage. Returning data also doubles as
	the server's reachability signal (see host_probes), so there is no separate
	ssh probe.
	"""
	cache_key = f"infra_board:cpu_disk:{server}"
	cached = frappe.cache().get_value(cache_key)
	if cached:
		return cached

	from press.press.doctype.ansible_console.ansible_console import AnsibleAdHoc

	adhoc = AnsibleAdHoc(sources=f"{server},")
	cmd = "echo CPU=$(awk '{print $1}' /proc/loadavg):$(nproc) DISK=$(df -P / | awk 'NR==2{print $5}' | tr -d %)"
	out = ""
	for host_result in adhoc.run(cmd, raw_params=True) or []:
		out = host_result.get("output") or host_result.get("stdout") or ""
		if "CPU=" in out:
			break

	data = _parse_cpu_disk(out)
	if data is None:
		frappe.log_error(f"unparseable cpu/disk output for {server}: {out!r}", "infra_board cpu/disk parse")
		return None
	frappe.cache().set_value(cache_key, data, expires_in_sec=60)
	return data


def _safe(fn, *args):
	try:
		return fn(*args)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"infra_board probe failed: {getattr(fn, '__name__', repr(fn))}")
		return None


def host_probes(server: str) -> dict:
	"""Per-server health dict. Every probe is best-effort: a failing probe
	degrades to None and never breaks the whole payload. `ssh.ok` is derived
	from the cpu/disk probe succeeding (one fewer SSH round-trip than a
	dedicated reachability ping).
	"""
	mem = _safe(_memory, server)
	mem_norm = None
	if mem:
		total = mem.get("memory_total_mb") or 0
		avail = mem.get("memory_available_mb") or 0
		used_pct = round((total - avail) / total * 100) if total else 0
		mem_norm = {"verdict": mem.get("verdict"), "used_pct": used_pct,
			"available_mb": avail, "total_mb": total}

	stats = _safe(_cpu_disk, server)
	agent = _safe(_agent, server)
	return {
		"server": server,
		"memory": mem_norm,
		"cpu": (stats or {}).get("cpu"),
		"disk": (stats or {}).get("disk"),
		"agent": {"verdict": agent.get("verdict")} if agent else None,
		"ssh": {"ok": bool(stats)},
	}


import json

CACHE_KEY = "infra_board:tree"
CACHE_TTL = 90  # seconds


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
		fields=["name as host_name", "server_type", "ssh_host", "ssh_port", "ssh_user", "proxy_port", "status", "last_error"],
	)


def _telephony_for(host_name: str):
	"""Telephony telemetry for a managed host that carries a Telephony PBX record,
	else None. Soft + best-effort: a probe failure or a missing module never
	breaks the tree build."""
	if not frappe.db.exists("Telephony PBX", {"host": host_name, "status": "Active"}):
		return None
	try:
		from press.api.infra_telephony import _managed_doc, telephony_status

		return telephony_status(_managed_doc(host_name))
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"telephony_status failed: {host_name}")
		return None


def _enumerate_managed(host) -> dict:
	from press.infra.adapters.base import get_adapter

	try:
		_attach_cert(host)
		out = get_adapter(host).enumerate(host)
		out.setdefault("reach", "ok")
		_set_last_error(host.host_name, "")
		return out
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), f"infra enumerate failed: {host.host_name}")
		reason = getattr(host, "_provision_error", None) or classify_conn_error(str(getattr(e, "message", "") or str(e)))
		_set_last_error(host.host_name, reason)
		return {"units": [], "metrics": {"cpu": 0, "mem": 0, "disk": 0, "req": 0}, "reach": "fail", "reason": reason}


def _overload(m: dict):
	# metrics may be None when host stats are not collected; treat None as 0.
	hi = max(m.get("cpu") or 0, m.get("mem") or 0, m.get("disk") or 0)
	return "crit" if hi >= 90 else "high" if hi >= 80 else None


def _build_tree() -> dict:
	servers = _press_servers()
	for h in _managed_hosts():
		en = _enumerate_managed(h)
		units = en["units"]
		down = sum(1 for u in units if u.get("state") in ("stop", "exit2", "down"))
		overload = _overload(en["metrics"])
		node = {
			"name": h.host_name, "kind": "managed", "server_type": h.server_type,
			"benches": [],
			"units": units, "metrics": en["metrics"], "overload": overload,
			"host": {"server": h.host_name},
			"last_error": en.get("reason") or h.get("last_error") or None,
			"health": ("unknown" if (h.status == "Unreachable" or en.get("reach") == "fail") else "down" if (down or overload == "crit") else "up"),
		}
		tele = _telephony_for(h.host_name)
		if tele is not None:
			node["telephony"] = tele
		servers.append(node)
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


def warm_infra_tree():
	"""Scheduled: rebuild + cache the infra tree so the dashboard always reads a
	warm cache. The build does a supervisorctl probe per bench + host probes (~10s),
	so we pay that cost here in the background, not on the user's first page load."""
	tree = _build_tree()
	frappe.cache().set_value(CACHE_KEY, json.dumps(tree), expires_in_sec=CACHE_TTL)


def _managed_doc(host_name: str):
	return _attach_cert(frappe.get_doc("Managed Host", host_name))


@frappe.whitelist()
def host_unit_action(host: str, unit_id: str, action: str) -> dict:
	"""Start/stop/restart/kill a unit on a managed host. System-Manager only;
	the adapter validates the action allowlist + the unit against live state;
	every call is audited (R5/R6)."""
	frappe.only_for("System Manager")
	from press.infra.adapters.base import get_adapter, log_infra_action

	try:
		doc = _managed_doc(host)
		res = get_adapter(doc).control(doc, unit_id, action)
		log_infra_action(host=host, unit=unit_id, action=action, outcome="success")
		return res
	except Exception as e:
		log_infra_action(host=host, unit=unit_id, action=action, outcome="error", detail=str(e))
		raise


@frappe.whitelist()
def get_host_log(host: str, unit_id: str, tail: int = 200) -> list:
	"""Tail a unit's log on a managed host (docker logs / journalctl)."""
	frappe.only_for("System Manager")
	from press.infra.adapters.base import get_adapter, log_infra_action

	try:
		doc = _managed_doc(host)
		lines = get_adapter(doc).logs(doc, unit_id, tail=tail)
		log_infra_action(host=host, unit=unit_id, action="logs", outcome="read")
		return lines
	except Exception as e:
		log_infra_action(host=host, unit=unit_id, action="logs", outcome="error", detail=str(e))
		raise


def classify_conn_error(text: str) -> str:
	"""Map a raw SSH/Docker connection error into a short, actionable operator
	reason (what failed + what to check). Pure + unit-tested; falls back to the
	trimmed raw text so nothing is ever fully swallowed."""
	t = (text or "").lower()
	if "not provisioned" in t or "gate 0" in t or "gate0" in t:
		return ("Gate 0 not provisioned: the SSH CA secret is missing. Set "
			"SANAD_SSH_CA_PRIVATE_PATH (or store infra/ssh_ca_private) and restart the bench.")
	if "permission denied" in t or "publickey" in t:
		return ("Control-plane cert rejected. Check Gate 0: the CA, the control-plane key, "
			"and the host's TrustedUserCAKeys trust for this principal.")
	if "forward" in t and ("fail" in t or "did not come up" in t):
		return ("Socket-proxy not reachable through the tunnel. Confirm the docker-socket-proxy "
			"listens on 127.0.0.1:<proxy_port> on the host.")
	if "timed out" in t or "timeout" in t:
		return "Host did not respond in time (network, sshd, or socket-proxy down)."
	if "connection refused" in t:
		return "Connection refused: no sshd listening on the configured ssh_port."
	if "docker api" in t:
		return "Reached the host, but the Docker API returned an error (check the socket-proxy allowlist)."
	return (text or "Unknown connection error").strip()[:300]


def _set_last_error(host_name: str, reason: str) -> None:
	"""Persist the latest connection reason on a Managed Host, only when it
	changed, so the steady-state warm cron does not write on every poll."""
	if not host_name:
		return
	current = frappe.db.get_value("Managed Host", host_name, "last_error")
	if (current or "") != (reason or ""):
		frappe.db.set_value("Managed Host", host_name, "last_error", reason or "", update_modified=False)


# Gate-0 provisions a dedicated control-plane keypair at this path; test_connection
# signs its pubkey with the CA to mint a short-TTL cert. Until provisioned, sign_cert
# fails and test_connection honestly reports the host Unreachable.
INFRA_KEY = "/home/frappe/.ssh/sanad-infra"


def _attach_cert(host):
	"""Attach a valid short-TTL SSH cert (control-plane key, principal = ssh_user)
	to `host` so the adapter can authenticate. The cert is cached per ssh_user and
	re-signed well before its 8h TTL. Best-effort: if signing fails (Gate 0 not yet
	provisioned) the host is returned without a cert and the adapter call surfaces
	the auth failure honestly."""
	import os

	from press.infra import ssh_ca

	user = host.get("ssh_user")
	if not user:
		return host
	ck = f"infra_board:cert:{user}"
	cert = frappe.cache().get_value(ck, expires=True)
	if cert and not os.path.exists(cert):
		cert = None  # cached cert file was deleted/rotated -> re-sign instead of serving a dead path
	if not cert:
		try:
			cert = ssh_ca.sign_cert(principal=user, pubkey_path=f"{INFRA_KEY}.pub")
			frappe.cache().set_value(ck, cert, expires_in_sec=6 * 3600)
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "infra cert sign failed")
			host._provision_error = classify_conn_error(str(getattr(e, "message", "") or str(e)))
			return host
	host.ssh_identity = INFRA_KEY
	host.ssh_cert = cert
	return host


@frappe.whitelist()
def add_managed_host(host_name, server_type, ssh_host, ssh_user="sanad", ssh_port=22, proxy_port=2375, tags=None, notes=None):
	"""Register a managed host (System-Manager). Starts Pending until test_connection verifies it."""
	frappe.only_for("System Manager")
	from frappe.utils import cint
	from press.infra.adapters.base import log_infra_action

	doc = frappe.get_doc({
		"doctype": "Managed Host",
		"host_name": host_name,
		"server_type": server_type,
		"ssh_host": ssh_host,
		"ssh_user": ssh_user,
		"ssh_port": cint(ssh_port) or 22,
		"proxy_port": cint(proxy_port) or 2375,
		"status": "Pending",
		"tags": tags,
		"notes": notes,
	}).insert()
	log_infra_action(host=doc.name, unit="-", action="add_host", outcome="created",
		detail=f"{ssh_user}@{ssh_host}:{cint(ssh_port) or 22} type={server_type}")
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def test_connection(host) -> dict:
	"""Sign a short-TTL cert, SSH-probe, and (docker) hit the Docker API via the
	socket-proxy tunnel. Flips status to Active on success. System-Manager only."""
	frappe.only_for("System Manager")
	from press.infra.adapters.base import get_adapter, log_infra_action

	doc = _managed_doc(host)  # attaches a fresh short-TTL cert
	out = {"ssh_ok": False, "docker_ok": False, "containers": 0}
	try:
		# reach the host through its adapter (SSH for plain, socket-proxy tunnel for docker).
		en = get_adapter(doc).enumerate(doc)
		out["ssh_ok"] = True
		if doc.server_type == "docker":
			out["docker_ok"] = True
			out["containers"] = sum(1 for u in en.get("units", []) if u.get("kind") == "container")
		frappe.db.set_value("Managed Host", host, {"status": "Active", "last_seen": frappe.utils.now_datetime(), "last_error": ""})
		log_infra_action(host=host, unit="-", action="test_connection", outcome="success", detail=str(out))
		return out
	except Exception as e:
		reason = getattr(doc, "_provision_error", None) or classify_conn_error(str(getattr(e, "message", "") or str(e)))
		frappe.db.set_value("Managed Host", host, {"status": "Unreachable", "last_error": reason})
		log_infra_action(host=host, unit="-", action="test_connection", outcome="error", detail=str(e))
		frappe.throw(reason)


def _gate0_ca_probe():
	"""5-min cached, read-only probe that the CA secret resolves AND is a valid SSH
	key (`ssh-keygen -y`, which produces no cert and opens no tunnel). Returns
	(ok, hint)."""
	ck = "infra_board:gate0_ca_ok"
	cached = frappe.cache().get_value(ck, expires=True)
	if cached is not None:
		try:
			d = json.loads(cached) if isinstance(cached, (str, bytes)) else cached
			return bool(d.get("ok")), d.get("hint", "")
		except (ValueError, TypeError, AttributeError):
			pass
	import subprocess

	from press.infra.secrets import get_infisical_secret

	try:
		ca_path = get_infisical_secret("infra/ssh_ca_private")
		r = subprocess.run(["ssh-keygen", "-y", "-f", ca_path], capture_output=True, text=True, timeout=10)
		ok = r.returncode == 0
		hint = "" if ok else "CA key is unreadable or not a valid SSH private key."
	except Exception as e:
		ok = False
		hint = classify_conn_error(str(getattr(e, "message", "") or str(e)))
	# Cache the hint, not just the flag, so polled (cached) calls keep the specific reason.
	frappe.cache().set_value(ck, json.dumps({"ok": ok, "hint": hint}), expires_in_sec=300)
	return ok, hint


def _control_key_present() -> bool:
	import os

	return os.path.exists(INFRA_KEY) and os.path.exists(f"{INFRA_KEY}.pub")


@frappe.whitelist()
def gate0_status() -> dict:
	"""Preflight for the managed-host control plane: is it provisioned enough to
	reach hosts? Cheap local checks + the cached CA probe; never opens an SSH
	tunnel. System-Manager only. Drives the dashboard's Gate-0 banner so an
	operator sees what is missing instead of an unexplained 'Unreachable'."""
	frappe.only_for("System Manager")

	key_ok = _control_key_present()
	ca_ok, ca_hint = _gate0_ca_probe()
	checks = [
		{"name": "Control-plane key", "ok": key_ok,
			"hint": "" if key_ok else f"Generate it: ssh-keygen -t ed25519 -f {INFRA_KEY} -N ''"},
		{"name": "SSH CA secret", "ok": ca_ok, "hint": ca_hint},
	]
	return {"ready": all(c["ok"] for c in checks), "checks": checks}
