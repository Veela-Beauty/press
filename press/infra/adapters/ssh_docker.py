# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Docker-host adapter. Talks the Docker Engine HTTP API through a
socket-proxy reached over a short-TTL SSH-cert tunnel (R2/R3): no shell, so
no command injection, and exec/build/volumes are blocked at the proxy."""
from __future__ import annotations

import re

import frappe

from press.infra.adapters.base import Adapter

_ID_RE = re.compile(r"^[a-f0-9]{12,64}$")
_VERBS = ("start", "stop", "restart", "kill")


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
			return "heal" if "healthy" in status else "run"
		if state == "exited":
			return "exit2" if "(2)" in status else "exit0"
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
		# host metrics come from the shared host_probes (disk/mem) + /info; cpu approximated
		return {"units": units, "metrics": {"cpu": 0, "mem": 0, "disk": 0, "req": 0}}

	def _live_ids(self, host) -> set:
		return {c.get("Id") for c in (self._api(host, "GET", "/containers/json?all=1") or [])}

	def control(self, host, unit_id: str, action: str) -> dict:
		if action not in _VERBS:
			frappe.throw(f"Invalid action {action!r}; allowed: {_VERBS}", frappe.ValidationError)
		if not _ID_RE.match(unit_id or ""):
			frappe.throw("Invalid container id", frappe.ValidationError)
		if unit_id not in self._live_ids(host):
			frappe.throw("Container not found on host", frappe.ValidationError)
		self._api(host, "POST", f"/containers/{unit_id}/{action}")
		return {"ok": True, "host": host.host_name, "unit": unit_id, "action": action}

	def logs(self, host, unit_id: str, tail: int = 200) -> list:
		if not _ID_RE.match(unit_id or ""):
			frappe.throw("Invalid container id", frappe.ValidationError)
		raw = self._api(host, "GET", f"/containers/{unit_id}/logs?stdout=1&stderr=1&tail={int(tail)}", raw=True)
		return (raw or "").splitlines()
