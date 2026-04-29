"""
Background `bench watch` lifecycle for Dev Benches.

When a bench is marked as Development Bench, we start `bench watch` inside the
Docker container so JS/CSS edits in any app auto-rebuild on save. When the bench
is unmarked, the watch is stopped.

PID is tracked in /tmp/bench-watch.pid; logs in /tmp/bench-watch.log.
nohup-style spawn — survives the docker_execute session ending, but NOT a
container restart. After a container restart, the UI shows status=stopped and
offers a one-click Restart.
"""

import frappe

from press.utils import ensure_team_access

WATCH_PID_FILE = "/tmp/bench-watch.pid"
WATCH_LOG_FILE = "/tmp/bench-watch.log"


def _is_watch_running(bench_doc) -> bool:
	"""Return True if a tracked watch PID is alive in the bench container."""
	check = bench_doc.docker_execute(
		f"bash -c 'pid=$(cat {WATCH_PID_FILE} 2>/dev/null); "
		f'[ -n "$pid" ] && kill -0 $pid 2>/dev/null && echo running || echo stopped\''
	)
	return "running" in (check.get("output") or "")


def start_watch(bench_doc) -> dict:
	"""Idempotently start `bench watch` in the bench container.
	Safe to call multiple times — only spawns if not already running."""
	if _is_watch_running(bench_doc):
		return {"started": False, "reason": "already_running"}

	cmd = (
		"bash -c 'cd /home/frappe/frappe-bench && "
		f"nohup bench watch > {WATCH_LOG_FILE} 2>&1 < /dev/null & "
		f"echo $! > {WATCH_PID_FILE}'"
	)
	bench_doc.docker_execute(cmd)
	return {"started": True}


def stop_watch(bench_doc) -> dict:
	"""Kill the tracked watch process if running, clean up PID file."""
	cmd = (
		f"bash -c 'pid=$(cat {WATCH_PID_FILE} 2>/dev/null); "
		f'[ -n "$pid" ] && kill "$pid" 2>/dev/null; '
		f"rm -f {WATCH_PID_FILE}'"
	)
	bench_doc.docker_execute(cmd)
	return {"stopped": True}


@frappe.whitelist()
def get_watch_status(bench_name: str) -> dict:
	"""Watch status for the dashboard: running flag, PID, last log lines.
	Returns is_dev_bench=False when bench isn't a dev bench (UI hides the panel)."""
	ensure_team_access(bench_name=bench_name)
	# Cheap single-column read for the gate; only fetch the full doc if needed
	# for docker_execute below (saves a full Bench doc fetch on every poll).
	if not frappe.db.get_value("Bench", bench_name, "is_development_bench"):
		return {"running": False, "is_dev_bench": False}

	bench = frappe.get_doc("Bench", bench_name)
	check = bench.docker_execute(
		f"bash -c 'pid=$(cat {WATCH_PID_FILE} 2>/dev/null); "
		f'if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then '
		f'  echo "running:$pid"; tail -5 {WATCH_LOG_FILE} 2>/dev/null; '
		f"else echo stopped; fi'"
	)
	output = (check.get("output") or "").strip()
	lines = output.splitlines()
	first = lines[0] if lines else "stopped"
	if first.startswith("running:"):
		try:
			pid = int(first.split(":", 1)[1])
		except (ValueError, IndexError):
			pid = 0
		return {
			"running": True,
			"is_dev_bench": True,
			"pid": pid,
			"log_tail": "\n".join(lines[1:]),
		}
	return {"running": False, "is_dev_bench": True, "log_tail": ""}


@frappe.whitelist()
def restart_watch(bench_name: str) -> dict:
	"""User-triggered restart — for when watch died after a container restart."""
	ensure_team_access(bench_name=bench_name)
	if not frappe.db.get_value("Bench", bench_name, "is_development_bench"):
		frappe.throw("Bench is not a Development Bench")
	bench = frappe.get_doc("Bench", bench_name)
	stop_watch(bench)
	return start_watch(bench)
