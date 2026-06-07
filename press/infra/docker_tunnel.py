# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""SSH-cert tunnel to a host's docker-socket-proxy + Docker Engine HTTP call.
Opens an ssh local-forward (cert-authed when the host carries a signed key/cert)
to 127.0.0.1:<proxy_port> and issues one HTTP request. Demultiplexes Docker's
stdcopy frame stream for /logs so the caller gets clean text. Mocked in all unit
tests; verified live in Task 10."""
from __future__ import annotations

import http.client
import json
import socket
import struct
import subprocess
import time


def _free_port() -> int:
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	try:
		s.bind(("127.0.0.1", 0))
		return s.getsockname()[1]
	finally:
		s.close()


def _ident_opts(host) -> list:
	"""ssh -i / CertificateFile from the host's signed short-TTL cert when set
	(test_connection / Gate 0 populate ssh_identity + ssh_cert). Empty until then."""
	key = getattr(host, "ssh_identity", None)
	cert = getattr(host, "ssh_cert", None)
	opts = []
	if key:
		opts += ["-o", "IdentitiesOnly=yes", "-i", key]
	if cert:
		opts += ["-o", f"CertificateFile={cert}"]
	return opts


def _demux(payload: bytes) -> str:
	"""Strip Docker's 8-byte stdcopy frame headers ([stream,0,0,0, size:be32]) and
	concatenate payloads. On a truncated/invalid trailing region, keep the frames
	already parsed and best-effort decode only the remainder, instead of dumping
	the whole buffer (header bytes included). An unframed (TTY) stream with no
	valid first frame is returned as a plain decode."""
	out = []
	i, n = 0, len(payload)
	while i + 8 <= n:
		stream = payload[i]
		size = struct.unpack(">I", payload[i + 4:i + 8])[0]
		if stream not in (0, 1, 2) or i + 8 + size > n:
			if not out:
				return payload.decode("utf-8", "replace")
			return (b"".join(out) + payload[i:]).decode("utf-8", "replace")
		out.append(payload[i + 8:i + 8 + size])
		i += 8 + size
	tail = payload[i:] if i < n else b""
	return (b"".join(out) + tail).decode("utf-8", "replace")


def docker_request(host, method: str, path: str, raw: bool = False, **kw):
	"""One Docker Engine HTTP call over a short-lived cert-authed SSH local-forward."""
	local = _free_port()
	proxy = host.proxy_port or 2375
	tunnel = subprocess.Popen(
		["ssh", "-N", *_ident_opts(host),
			"-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
			"-o", "ExitOnForwardFailure=yes",
			"-p", str(host.ssh_port or 22),
			"-L", f"{local}:127.0.0.1:{proxy}",
			"--", f"{host.ssh_user}@{host.ssh_host}"],
		stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
	)
	try:
		deadline = time.monotonic() + 15
		while time.monotonic() < deadline:
			if tunnel.poll() is not None:
				err = (tunnel.stderr.read().decode("utf-8", "replace") if tunnel.stderr else "").strip()
				raise RuntimeError(f"SSH forward to {host.host_name} failed (ssh exited {tunnel.returncode}): {err[:300]}")
			try:
				with socket.create_connection(("127.0.0.1", local), timeout=0.5):
					break
			except OSError:
				time.sleep(0.1)
		else:
			raise RuntimeError(f"SSH forward to {host.host_name} did not come up within 15s")
		conn = http.client.HTTPConnection("127.0.0.1", local, timeout=15)
		try:
			conn.request(method, path)
			resp = conn.getresponse()
			body = resp.read()
		finally:
			conn.close()
		if resp.status >= 400:
			raise RuntimeError(f"Docker API {resp.status} on {path}: {body[:200]!r}")
		if raw:
			return _demux(body)
		return json.loads(body.decode("utf-8") or "[]")
	finally:
		tunnel.terminate()
		try:
			tunnel.wait(timeout=3)
		except Exception:
			tunnel.kill()
			try:
				tunnel.wait(timeout=2)
			except Exception:
				pass


def ssh_command(host, cmd: str, timeout: int = 12) -> str:
	"""Run a single FIXED command on the host over the cert-authed SSH connection
	(no -L forward). Returns stdout. Used only for the read-only host-stats probe;
	`cmd` must never include host-controlled data (no injection surface)."""
	p = subprocess.run(
		["ssh", *_ident_opts(host),
			"-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
			"-o", f"ConnectTimeout={timeout}",
			"-p", str(host.ssh_port or 22), "--", f"{host.ssh_user}@{host.ssh_host}", cmd],
		capture_output=True, text=True, timeout=timeout + 5,
	)
	return p.stdout or ""
