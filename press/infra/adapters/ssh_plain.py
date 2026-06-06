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
		identity = host.get("ssh_identity")  # test_connection / Gate 0 sets the signed key
		cert = host.get("ssh_cert")
		ident_opts = []
		if identity:
			ident_opts += ["-o", "IdentitiesOnly=yes", "-i", identity]
		if cert:
			ident_opts += ["-o", f"CertificateFile={cert}"]
		# ControlMaster multiplexing: a 15s-polled tree re-uses one connection
		# per host for 30s instead of a fresh handshake on every probe.
		ctl = f"/tmp/sanad-infra-{host.ssh_user}@{host.ssh_host}:{host.ssh_port or 22}.sock"
		cmd = ["ssh", *ident_opts,
			"-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes",
			"-o", "ControlMaster=auto", "-o", f"ControlPath={ctl}", "-o", "ControlPersist=30s",
			"-p", str(host.ssh_port or 22), "--", f"{host.ssh_user}@{host.ssh_host}", remote_cmd]
		r = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
		return r.stdout.strip()

	def enumerate(self, host) -> dict:
		# ONE round-trip: systemd units + disk%/mem%/cpu split on a marker.
		# The marker is single-quoted so the shell echoes it literally (a bare
		# echo ##B## would treat ## as a comment).
		probe = (
			"systemctl list-units --type=service,timer --no-legend --plain; echo '##B##'; "
			"df --output=pcent / | tail -1 | tr -dc 0-9; echo '##B##'; "
			"free | awk '/Mem:/{printf \"%d\", $3/$2*100}'; echo '##B##'; "
			"awk '{printf \"%d\", $1*25}' /proc/loadavg"
		)
		parts = (self._ssh(host, probe) or "").split("##B##")
		systemctl = parts[0] if len(parts) > 0 else ""
		disk = parts[1].strip() if len(parts) > 1 else ""
		mem = parts[2].strip() if len(parts) > 2 else ""
		cpu = parts[3].strip() if len(parts) > 3 else ""
		units = []
		for line in systemctl.splitlines():
			cols = line.split()
			if len(cols) < 4:
				continue
			name, active = cols[0], cols[2]
			units.append({"name": name, "kind": "systemd", "sub": "systemd",
				"state": "active" if active == "active" else "down",
				"uptime": "-", "restarts": 0, "ports": "-", "health": "-", "pid": "-"})
		return {"units": units, "metrics": {"cpu": cint(cpu), "mem": cint(mem), "disk": cint(disk), "req": 0}}
