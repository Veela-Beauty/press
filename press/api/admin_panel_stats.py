"""SSH-based server live stats — RAM/CPU/disk for the Admin Panel Servers tab.

Runs from press-ctrl. Uses the frappe user's default SSH key to reach app
servers (Press provisioning sets up key auth as root). Cached 60s in
frappe.cache to avoid SSH on every page load.
"""
import re
import shlex
import subprocess

import frappe

CACHE_KEY_PREFIX = "admin_panel_server_stats:"
CACHE_TTL = 60  # seconds
SSH_TIMEOUT = 8  # seconds end-to-end (incl. connect)
SSH_CONNECT_TIMEOUT = 5

# One-shot probe — five blocks separated by blank lines, parsed below.
PROBE_CMD = (
    "head -5 /proc/meminfo; "
    "echo ---; "
    "echo CPUS=$(nproc); "
    "echo ---; "
    "uptime; "
    "echo ---; "
    "df -B1G --output=size,used,avail / | tail -1"
)


def _ssh_run(host, port=22):
    """Run PROBE_CMD over SSH. Returns stdout or None on failure."""
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "BatchMode=yes",
                "-o", f"ConnectTimeout={SSH_CONNECT_TIMEOUT}",
                "-p", str(port),
                f"root@{host}",
                PROBE_CMD,
            ],
            capture_output=True, text=True, timeout=SSH_TIMEOUT,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except Exception:
        return None


def _parse_meminfo(text):
    """Return (mem_total_mb, mem_avail_mb, mem_used_mb, mem_pct)."""
    fields = {}
    for line in text.splitlines():
        m = re.match(r"^(\w+):\s+(\d+)\s*kB", line)
        if m:
            fields[m.group(1)] = int(m.group(2))
    total = fields.get("MemTotal", 0) // 1024
    avail = fields.get("MemAvailable", fields.get("MemFree", 0)) // 1024
    used = total - avail
    pct = round(used / total * 100, 1) if total else 0
    return total, avail, used, pct


def _parse_cpus(text):
    m = re.search(r"CPUS=(\d+)", text)
    return int(m.group(1)) if m else 1


def _parse_uptime(text):
    """Return (load1, load5, load15, uptime_human)."""
    m = re.search(r"load average[s]?:\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)", text)
    loads = [float(m.group(i)) for i in (1, 2, 3)] if m else [0.0, 0.0, 0.0]
    up_m = re.search(r"up\s+([^,]+(?:,\s*\d+\s+min)?)", text)
    uptime_str = up_m.group(1).strip() if up_m else ""
    return loads[0], loads[1], loads[2], uptime_str


def _parse_df(text):
    """Return (size_gb, used_gb, avail_gb, used_pct)."""
    parts = text.split()
    if len(parts) < 3:
        return 0, 0, 0, 0
    try:
        size = int(parts[0])
        used = int(parts[1])
        avail = int(parts[2])
        pct = round(used / size * 100, 1) if size else 0
        return size, used, avail, pct
    except ValueError:
        return 0, 0, 0, 0


def _parse_probe(stdout):
    """Split probe output into 4 sections by '---' and parse each."""
    sections = stdout.split("---")
    if len(sections) < 4:
        return None
    mem_text, cpus_text, uptime_text, df_text = sections[:4]
    total, avail, used, pct = _parse_meminfo(mem_text)
    cpus = _parse_cpus(cpus_text)
    load1, load5, load15, uptime_str = _parse_uptime(uptime_text)
    disk_size, disk_used, disk_avail, disk_pct = _parse_df(df_text)
    return {
        "ram_total_mb": total,
        "ram_used_mb": used,
        "ram_pct": pct,
        "cpus": cpus,
        "load1": load1,
        "load5": load5,
        "load15": load15,
        "load_pct": round(load1 / cpus * 100, 1) if cpus else 0,
        "uptime": uptime_str,
        "disk_size_gb": disk_size,
        "disk_used_gb": disk_used,
        "disk_pct": disk_pct,
    }


def collect_stats(server_name, ip):
    """Return live stats for a server. Uses host (FQDN) when ip is empty.
    Cached 60s. Caller is responsible for permission check."""
    cache_key = f"{CACHE_KEY_PREFIX}{server_name}"
    cached = frappe.cache().get_value(cache_key)
    if cached is not None:
        return cached

    target = ip or server_name
    stdout = _ssh_run(target)
    if stdout is None:
        result = {"error": "ssh_failed", "target": target}
    else:
        parsed = _parse_probe(stdout)
        if parsed is None:
            result = {"error": "parse_failed", "raw": stdout[:200]}
        else:
            result = parsed

    frappe.cache().set_value(cache_key, result, expires_in_sec=CACHE_TTL)
    return result
