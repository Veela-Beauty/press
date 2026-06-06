# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""SSH-cert tunnel to a host's docker-socket-proxy + Docker Engine HTTP call.
Opens an ssh local-forward (cert-authed) to 127.0.0.1:<proxy_port> and issues
one HTTP request. Demultiplexes Docker's stdcopy frame stream for /logs so the
caller gets clean text. Mocked in all unit tests; verified live in Task 10."""
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


def _demux(payload: bytes) -> str:
	"""Strip Docker's 8-byte stdcopy frame headers ([stream,0,0,0, size:be32])
	and concatenate payloads. A TTY (unframed) stream that does not line up as
	frames is returned as a plain decode."""
	out = []
	i, n = 0, len(payload)
	while i + 8 <= n:
		stream = payload[i]
		size = struct.unpack(">I", payload[i + 4:i + 8])[0]
		if stream not in (0, 1, 2) or i + 8 + size > n:
			return payload.decode("utf-8", "replace")
		out.append(payload[i + 8:i + 8 + size])
		i += 8 + size
	if i != n:
		return payload.decode("utf-8", "replace")
	return b"".join(out).decode("utf-8", "replace")


def docker_request(host, method: str, path: str, raw: bool = False, **kw):
	"""One Docker Engine HTTP call over a short-lived cert-authed SSH local-forward."""
	local = _free_port()
	proxy = host.proxy_port or 2375
	tunnel = subprocess.Popen([
		"ssh", "-N", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
		"-o", "ExitOnForwardFailure=yes",
		"-p", str(host.ssh_port or 22),
		"-L", f"{local}:127.0.0.1:{proxy}",
		f"{host.ssh_user}@{host.ssh_host}",
	])
	try:
		deadline = time.monotonic() + 5
		while time.monotonic() < deadline:
			try:
				with socket.create_connection(("127.0.0.1", local), timeout=0.5):
					break
			except OSError:
				time.sleep(0.1)
		else:
			raise RuntimeError(f"SSH forward to {host.host_name} did not come up")
		conn = http.client.HTTPConnection("127.0.0.1", local, timeout=15)
		conn.request(method, path)
		resp = conn.getresponse()
		body = resp.read()
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
