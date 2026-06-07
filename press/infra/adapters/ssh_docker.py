# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Docker-host adapter. Talks the Docker Engine HTTP API through a
socket-proxy reached over a short-TTL SSH-cert tunnel (R2/R3): no shell, so
no command injection, and exec/build/volumes are blocked at the proxy."""
from __future__ import annotations

import re

import frappe

from press.infra.adapters.base import Adapter

_ID_RE = re.compile(r"\A[a-f0-9]{12,64}\Z")
_VERBS = ("start", "stop", "restart", "kill")

# Read-only host-stats probe (a FIXED command, no host-controlled data -> no
# injection). Reads the host /proc + root fs the sidecar mounts read-only.
# Output: "CPU=<load>:<cores> MEM=<pct> DISK=<pct>".
_HOST_STATS_CMD = (
	"echo CPU=$(awk '{print $1}' /host/proc/loadavg):$(nproc) "
	"MEM=$(awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{if(t)printf \"%d\",(t-a)*100/t}' /host/proc/meminfo) "
	"DISK=$(df -P /host/root 2>/dev/null | awk 'NR==2{print $5}' | tr -d %)"
)


def _int_after(out: str, key: str):
	try:
		return int(out.split(key, 1)[1].split()[0])
	except (ValueError, IndexError):
		return None


def parse_host_stats(out: str) -> dict:
	"""Parse the host-stats probe line into {cpu, mem, disk} percentages, each None
	on a missing/malformed field. Pure + unit-tested."""
	if not out or "CPU=" not in out:
		return {"cpu": None, "mem": None, "disk": None, "req": 0}
	try:
		load_s, cores_s = out.split("CPU=", 1)[1].split()[0].split(":")
		cpu = min(100, round(float(load_s) / (int(cores_s) or 1) * 100))
	except (ValueError, IndexError):
		cpu = None
	return {"cpu": cpu, "mem": _int_after(out, "MEM="), "disk": _int_after(out, "DISK="), "req": 0}


class SshDockerAdapter(Adapter):
	def _api(self, host, method: str, path: str, **kw):
		"""Open the SSH-cert tunnel to 127.0.0.1:proxy_port and call the Docker API.
		Implemented with an SSH local-forward + an HTTP request; the tunnel and
		cert handling live in press.infra.docker_tunnel (created at onboarding).
		In tests this method is fully mocked."""
		from press.infra.docker_tunnel import docker_request

		return docker_request(host, method, path, **kw)

	def _container_state(self, c: dict) -> str:
		state = (c.get("State") or "").lower()
		status = c.get("Status") or ""
		if state == "running":
			if "(unhealthy)" in status:
				return "unhealth"
			if "(healthy)" in status:
				return "heal"
			return "run"
		if state == "exited":
			m = re.search(r"Exited \((\d+)\)", status)
			code = int(m.group(1)) if m else 0
			return "exit0" if code == 0 else "exit2"
		if state == "restarting":
			return "restart"
		if state == "dead":
			return "dead"
		if state == "paused":
			return "pause"
		return "stop"

	def enumerate(self, host) -> dict:
		containers = self._api(host, "GET", "/containers/json?all=1") or []
		units = []
		for c in containers:
			name = (c.get("Names") or ["/?"])[0].lstrip("/")
			units.append({
				"name": name, "kind": "container", "sub": c.get("Image", "-"),
				"state": self._container_state(c), "uptime": c.get("Status", "-"),
				"restarts": 0, "ports": "-", "health": "-", "pid": "-", "_id": c.get("Id"),
			})
		return {"units": units, "metrics": self._host_metrics(host)}

	def _host_metrics(self, host) -> dict:
		"""Live host CPU/Mem/Disk via the read-only stats probe; degrades to None
		(rendered 'n/a') if the sidecar lacks the host mounts or the probe fails."""
		from press.infra.docker_tunnel import ssh_command

		try:
			return parse_host_stats(ssh_command(host, _HOST_STATS_CMD))
		except Exception:
			return {"cpu": None, "mem": None, "disk": None, "req": 0}

	def _live_ids(self, host) -> set:
		return {c.get("Id") for c in (self._api(host, "GET", "/containers/json?all=1") or [])}

	def control(self, host, unit_id: str, action: str) -> dict:
		if action not in _VERBS:
			frappe.throw(frappe._("Unknown action {0}. Allowed actions: {1}.").format(action, ", ".join(_VERBS)), frappe.ValidationError)
		if not _ID_RE.match(unit_id or ""):
			frappe.throw(frappe._("That container id is not valid (expected a 12-64 character hex id)."), frappe.ValidationError)
		if unit_id not in self._live_ids(host):
			frappe.throw(frappe._("Container {0} is no longer on {1}; refresh the host.").format((unit_id or "")[:12], host.host_name), frappe.ValidationError)
		self._api(host, "POST", f"/containers/{unit_id}/{action}")
		return {"ok": True, "host": host.host_name, "unit": unit_id, "action": action}

	def logs(self, host, unit_id: str, tail: int = 200) -> list:
		if not _ID_RE.match(unit_id or ""):
			frappe.throw(frappe._("That container id is not valid (expected a 12-64 character hex id)."), frappe.ValidationError)
		if unit_id not in self._live_ids(host):
			frappe.throw(frappe._("Container {0} is no longer on {1}; refresh the host.").format((unit_id or "")[:12], host.host_name), frappe.ValidationError)
		try:
			tail_n = max(1, min(int(tail or 200), 5000))
		except (TypeError, ValueError):
			frappe.throw(frappe._("Invalid tail value; use a number of lines (1-5000)."), frappe.ValidationError)
		raw = self._api(host, "GET", f"/containers/{unit_id}/logs?stdout=1&stderr=1&tail={tail_n}", raw=True)
		return (raw or "").splitlines()
