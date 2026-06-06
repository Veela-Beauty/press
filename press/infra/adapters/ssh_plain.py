# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Plain-host adapter: read-only systemd + disk/mem/cpu over SSH.
No control in v1 (R: watch-only)."""
from __future__ import annotations

import subprocess

from frappe.utils import cint

from press.infra.adapters.base import Adapter
from press.infra import ssh_ca


class SshPlainAdapter(Adapter):
	def _ssh(self, host, remote_cmd: str) -> str:
		"""Run ONE allowlisted command on the host.

		Identity/cert wiring is deferred to Gate 0 provisioning: when the host
		carries a signed-cert path (``ssh_identity``) it is passed via ``-i``;
		until then v1 connects with the default agent identity. The remote
		forced-command validator re-checks the command server-side.
		"""
		identity = host.get("ssh_identity")  # Gate 0 fills this (ssh_ca signed cert); None in v1
		ident_opts = ["-i", identity] if identity else []
		cmd = ["ssh", *ident_opts,
			"-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes",
			"-p", str(host.ssh_port or 22), f"{host.ssh_user}@{host.ssh_host}", remote_cmd]
		r = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
		return r.stdout.strip()

	def enumerate(self, host) -> dict:
		systemctl = self._ssh(host, "systemctl list-units --type=service,timer --no-legend --plain")
		disk = self._ssh(host, "df --output=pcent / | tail -1 | tr -dc 0-9")
		mem = self._ssh(host, "free | awk '/Mem:/{printf \"%d\", $3/$2*100}'")
		cpu = self._ssh(host, "awk '{printf \"%d\", $1*25}' /proc/loadavg")
		units = []
		for line in (systemctl or "").splitlines():
			parts = line.split()
			if len(parts) < 4:
				continue
			name, active = parts[0], parts[2]
			units.append({"name": name, "kind": "systemd", "sub": "systemd",
				"state": "active" if active == "active" else "down",
				"uptime": "-", "restarts": 0, "ports": "-", "health": "-", "pid": "-"})
		return {"units": units, "metrics": {"cpu": cint(cpu), "mem": cint(mem), "disk": cint(disk), "req": 0}}
