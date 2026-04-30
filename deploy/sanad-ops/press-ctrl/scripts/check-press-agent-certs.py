#!/usr/bin/env python3
"""check-press-agent-certs.py — daily audit of every Press agent's TLS cert.

Probes each server with strict SSL via Python's stdlib ssl. Alerts (stdout +
log file) on any deviation from a current Let's Encrypt cert. Designed to
run as a cron job on press-ctrl. Phase 3 (later) will wire alerts to
Telegram / email.

Exit codes:
  0 = all servers OK
  1 = at least one server has an issue (alert fired)
"""

from __future__ import annotations

import datetime as dt
import math
import socket
import ssl
import sys
from pathlib import Path

LOG_PATH = Path("/var/log/press-cert-audit.log")

# (display_name, port443_hostname)
SERVERS = [
    ("press-ctrl", "autodeploypanel.mvpstorm.com"),
    ("press-f1",   "press-f1.sandbox.mvpstorm.com"),
    ("u4",         "u4.sandbox.mvpstorm.com"),
    ("u5",         "u5.sandbox.mvpstorm.com"),
]

EXPIRY_WARN_DAYS = 14
LE_ORG_NAME = "Let's Encrypt"


def log(msg: str) -> None:
    line = f"[{dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M:%S} UTC] {msg}"
    print(line)
    try:
        with LOG_PATH.open("a") as f:
            f.write(line + "\n")
    except PermissionError:
        pass  # cron writes to /var/log; manual runs may not


def probe_cert(host: str, port: int = 443, timeout: int = 5) -> dict:
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            return ssock.getpeercert()


def issues_for(name: str, host: str) -> list[str]:
    findings: list[str] = []
    try:
        cert = probe_cert(host)
    except ssl.SSLCertVerificationError as e:
        return [f"{name} ({host}): SSL VERIFY FAILED — {e}"]
    except OSError as e:
        return [f"{name} ({host}): connection error — {e}"]

    issuer = dict(x[0] for x in cert.get("issuer", []))
    if LE_ORG_NAME not in issuer.get("organizationName", ""):
        findings.append(
            f"{name} ({host}): issuer is NOT Let's Encrypt — {issuer}"
        )

    not_after_str = cert.get("notAfter")
    if not not_after_str:
        findings.append(f"{name} ({host}): cert missing notAfter field")
        return findings
    not_after = dt.datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt.timezone.utc)
    days_left = math.ceil((not_after - dt.datetime.now(dt.timezone.utc)).total_seconds() / 86400)
    if days_left < 0:
        findings.append(f"{name} ({host}): cert EXPIRED {-days_left} days ago")
    elif days_left < EXPIRY_WARN_DAYS:
        findings.append(
            f"{name} ({host}): cert expires in {days_left} days ({not_after:%Y-%m-%d})"
        )

    return findings


def main() -> int:
    log(f"=== audit start ({len(SERVERS)} servers) ===")
    all_findings: list[str] = []
    for name, host in SERVERS:
        findings = issues_for(name, host)
        if findings:
            for f in findings:
                log(f"ALERT: {f}")
            all_findings.extend(findings)
        else:
            log(f"OK: {name} ({host})")
    log(f"=== audit end — {len(all_findings)} alerts ===")
    return 1 if all_findings else 0


if __name__ == "__main__":
    sys.exit(main())
