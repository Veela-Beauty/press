# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Run a bash script (and push files) on a managed host over the SAME
cert-authed SSH connection the read-only probes use (R2/R3). The Docker-API
adapter forbids exec by design, so write-side telephony actions need this
narrow shell primitive. Files are pushed base64-encoded so a secret never
appears verbatim in the argv or the script body. Mocked in all unit tests;
verified live on press-ctrl in Task 8."""
from __future__ import annotations

import base64
import shlex
import subprocess

import frappe


def _ident_opts(host) -> list:
	key = host.get("ssh_identity")
	cert = host.get("ssh_cert")
	opts = []
	if key:
		opts += ["-o", "IdentitiesOnly=yes", "-i", key]
	if cert:
		opts += ["-o", f"CertificateFile={cert}"]
	return opts


def _file_prelude(files: dict) -> str:
	"""Emit base64-decode commands that materialise each file with a 0600 mode.
	Target paths must be absolute and free of '..' so a caller cannot escape the
	intended PBX directory."""
	lines = []
	for path, content in files.items():
		if not path.startswith("/") or ".." in path.split("/"):
			frappe.throw(frappe._("Refusing unsafe target path {0}").format(path), frappe.ValidationError)
		b64 = base64.b64encode((content or "").encode()).decode("ascii")
		q = shlex.quote(path)
		lines.append(f'mkdir -p "$(dirname {q})"')
		lines.append(f"printf %s {shlex.quote(b64)} | base64 -d > {q}")
		lines.append(f"chmod 600 {q}")
	return "\n".join(lines)


def run_host_script(host, script: str, files: dict | None = None, timeout: int = 120) -> str:
	"""Push `files` then run `script` under `bash -s` on the host. Returns stdout;
	raises RuntimeError (stderr trimmed) on a non-zero exit so the action can
	audit + surface the real reason.

	The argv ends with `user@host` (no remote command); the login shell reads the
	piped body whose first line `exec bash -s` hands off to a strict bash, so a
	secret/script never lands in argv. Files are base64-decoded host-side."""
	body = "exec bash -s <<'__OC_PBX_EOF__'\n"
	body += "set -euo pipefail\n"
	if files:
		body += _file_prelude(files) + "\n"
	body += script + "\n"
	body += "__OC_PBX_EOF__\n"
	argv = [
		"ssh", *_ident_opts(host),
		"-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
		"-o", f"ConnectTimeout={min(timeout, 30)}",
		"-p", str(host.get("ssh_port") or 22),
		"--", f"{host.get('ssh_user')}@{host.get('ssh_host')}",
	]
	p = subprocess.run(argv, input=body, capture_output=True, text=True, timeout=timeout + 10)
	if p.returncode != 0:
		raise RuntimeError(f"host script failed (exit {p.returncode}): {(p.stderr or p.stdout).strip()[:400]}")
	return p.stdout
