# Infra Control Panel: Plan 1, Backend Data Layer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend API that powers a live Press control panel: one aggregator that returns a `server -> bench -> service` health tree, a safe per-service start/stop/restart action, and a host-probe adapter (disk/memory/agent/ssh/docker) returning JSON.

**Architecture:** Reuse Press primitives wherever possible (`get_processes` for supervisor status, `get_dev_overview_benches` for the bench list, `host_memory_pressure`/`get_storage_usage` for host metrics). Add one new module `press/api/infra_board.py` (aggregator + probes) and one new whitelisted action in `press/api/bench.py` (per-service supervisorctl). Everything is System-Manager-gated, read paths are Redis-cached ~15s, and the per-service action validates the program name against live `get_processes` output. See `docs/infra-board/2026-06-05-capability-audit.md` for the full reuse map.

**Tech Stack:** Frappe (Python), `frappe.tests.utils.FrappeTestCase`, `unittest.mock`, MariaDB, Redis (frappe cache). Tests run with `bench --site demo.mvpstorm.com run-tests`.

**Scope note:** This is Plan 1 of 2. Plan 2 (the Vue `InfraBoard.vue` page + service log drawer, built from the approved prototype `docs/infra-board/press-control-panel.prototype.html`) is authored after this API contract is proven.

---

## File structure

| File | Responsibility |
|---|---|
| `press/api/bench.py` (modify) | Add `_service_action` (pure helper) + `service_action` (whitelisted, `@protected("Bench")`) for per-service start/stop/restart |
| `press/api/infra_board.py` (create) | `host_probes(server)` adapter + `get_infra_tree()` aggregator (System-Manager-gated, cached) |
| `press/api/tests/test_infra_board.py` (create) | Unit tests for all three with mocked underlying calls |

---

## Task 1: Per-service control action (`service_action`)

**Files:**
- Modify: `press/api/bench.py` (add helper + whitelisted wrapper near `get_processes`, around line 666)
- Test: `press/api/tests/test_infra_board.py` (create)

- [ ] **Step 1: Write the failing test**

Create `press/api/tests/test_infra_board.py`:

```python
# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.api.bench import _service_action


class TestServiceAction(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_rejects_invalid_action(self):
		with self.assertRaises(frappe.ValidationError):
			_service_action("bench-X-001-press-f1", "redis-queue", "delete")

	def test_rejects_unknown_program(self):
		with patch("press.api.bench.get_processes", return_value=[{"program": "redis-queue"}]):
			with self.assertRaises(frappe.ValidationError):
				_service_action("bench-X-001-press-f1", "ghost-program", "restart")

	def test_calls_supervisorctl_for_valid_program(self):
		fake_bench = MagicMock()
		with patch("press.api.bench.get_processes", return_value=[{"program": "redis-queue"}, {"program": "frappe-web"}]), patch(
			"press.api.bench.frappe.get_doc", return_value=fake_bench
		):
			result = _service_action("bench-X-001-press-f1", "redis-queue", "restart")
		fake_bench.supervisorctl.assert_called_once_with("restart", programs=["redis-queue"])
		self.assertTrue(result["ok"])
		self.assertEqual(result["action"], "restart")
		self.assertEqual(result["program"], "redis-queue")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site demo.mvpstorm.com run-tests --module press.api.tests.test_infra_board --test test_rejects_invalid_action`
Expected: FAIL with `ImportError: cannot import name '_service_action' from 'press.api.bench'`

- [ ] **Step 3: Write minimal implementation**

In `press/api/bench.py`, immediately AFTER the `get_processes` function (after line ~666 block), add:

```python
def _service_action(bench_name: str, program: str, action: str) -> dict:
	"""Start/stop/restart ONE supervisor program on a bench.

	Pure helper (no permission decorator) so it is unit-testable. The
	whitelisted `service_action` wrapper applies @protected('Bench'). The
	program name is validated against live get_processes output so a caller
	can only act on programs that actually exist on this bench (no free-form
	command injection into supervisorctl).
	"""
	if action not in ("start", "stop", "restart"):
		frappe.throw(
			f"Invalid action {action!r}; allowed: start, stop, restart",
			frappe.ValidationError,
		)
	valid_programs = {p["program"] for p in get_processes(bench_name)}
	if program not in valid_programs:
		frappe.throw(
			f"Unknown program {program!r} on bench {bench_name!r}",
			frappe.ValidationError,
		)
	frappe.get_doc("Bench", bench_name).supervisorctl(action, programs=[program])
	return {"bench": bench_name, "program": program, "action": action, "ok": True}


@frappe.whitelist()
@protected("Bench")
def service_action(name: str, program: str, action: str) -> dict:
	"""Dashboard-callable per-service control. `name` is the Bench docname
	(team/permission enforced by @protected). Restricts action to
	start/stop/restart and validates the program against get_processes.
	"""
	return _service_action(name, program, action)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bench --site demo.mvpstorm.com run-tests --module press.api.tests.test_infra_board`
Expected: PASS (3 tests in TestServiceAction)

- [ ] **Step 5: Commit**

```bash
git add press/api/bench.py press/api/tests/test_infra_board.py
git commit -m "feat(infra-board): per-service supervisorctl action (start/stop/restart)"
```

---

## Task 2: Host-probe adapter (`host_probes`)

Returns a per-server JSON dict of disk/memory/agent/ssh status by reusing existing Press + Watch Tower probes. Watch Tower helpers are soft-imported so Press still works if `frappe_theme_switcher` is absent.

**Files:**
- Create: `press/api/infra_board.py`
- Test: `press/api/tests/test_infra_board.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `press/api/tests/test_infra_board.py`:

```python
class TestHostProbes(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_host_probes_normalizes_memory_and_agent(self):
		from press.api import infra_board

		mem = {"verdict": "ok", "memory_available_mb": 12940, "memory_total_mb": 23458}
		agent = {"verdict": "healthy"}
		with patch.object(infra_board, "_memory", return_value=mem), patch.object(
			infra_board, "_agent", return_value=agent
		), patch.object(infra_board, "_ssh_ok", return_value=True):
			out = infra_board.host_probes("press-f1.sandbox.mvpstorm.com")

		self.assertEqual(out["memory"]["verdict"], "ok")
		self.assertEqual(out["memory"]["used_pct"], 45)  # (23458-12940)/23458 rounded
		self.assertEqual(out["agent"]["verdict"], "healthy")
		self.assertTrue(out["ssh"]["ok"])

	def test_host_probes_survives_failing_probe(self):
		from press.api import infra_board

		with patch.object(infra_board, "_memory", side_effect=Exception("boom")), patch.object(
			infra_board, "_agent", return_value={"verdict": "healthy"}
		), patch.object(infra_board, "_ssh_ok", return_value=True):
			out = infra_board.host_probes("press-f1.sandbox.mvpstorm.com")

		self.assertIsNone(out["memory"])  # failed probe degrades to None, never raises
		self.assertEqual(out["agent"]["verdict"], "healthy")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site demo.mvpstorm.com run-tests --module press.api.tests.test_infra_board --test test_host_probes_normalizes_memory_and_agent`
Expected: FAIL with `ModuleNotFoundError: No module named 'press.api.infra_board'`

- [ ] **Step 3: Write minimal implementation**

Create `press/api/infra_board.py`:

```python
# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Infra Control Panel backend: host probes + the server->bench->service tree.

Read-only, System-Manager-gated, Redis-cached. Reuses existing Press
primitives (get_processes, get_dev_overview_benches, host_memory_pressure,
get_storage_usage, agent_health) and soft-imports Watch Tower's ssh_cmd for
the ssh reachability probe. See docs/infra-board/2026-06-05-capability-audit.md.
"""
from __future__ import annotations

import frappe


def _memory(server: str):
	from press.mcp_server.deploy_flow import host_memory_pressure

	return host_memory_pressure(server=server)


def _agent(server: str):
	from press.mcp_server.deploy_flow import agent_health

	return agent_health(server=server, lookback_minutes=10)


def _ssh_ok(server: str) -> bool:
	"""Reachability via Watch Tower's ssh_cmd if available, else None-safe False."""
	try:
		from frappe_theme_switcher.watch_tower.alerts._helpers import ssh_cmd

		ip = frappe.db.get_value("Server", server, "ip") or server
		ok, _out, _err = ssh_cmd(ip, "echo OK", timeout=8)
		return bool(ok)
	except Exception:
		return False


def _safe(fn, *args):
	try:
		return fn(*args)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"infra_board probe failed: {fn.__name__}")
		return None


def host_probes(server: str) -> dict:
	"""Per-server health dict. Every probe is best-effort: a failing probe
	degrades to None and never breaks the whole payload.
	"""
	mem = _safe(_memory, server)
	mem_norm = None
	if mem:
		total = mem.get("memory_total_mb") or 0
		avail = mem.get("memory_available_mb") or 0
		used_pct = round((total - avail) / total * 100) if total else 0
		mem_norm = {"verdict": mem.get("verdict"), "used_pct": used_pct,
			"available_mb": avail, "total_mb": total}

	agent = _safe(_agent, server)
	return {
		"server": server,
		"memory": mem_norm,
		"agent": {"verdict": agent.get("verdict")} if agent else None,
		"ssh": {"ok": _safe(_ssh_ok, server) or False},
	}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bench --site demo.mvpstorm.com run-tests --module press.api.tests.test_infra_board`
Expected: PASS (TestServiceAction 3 + TestHostProbes 2)

- [ ] **Step 5: Commit**

```bash
git add press/api/infra_board.py press/api/tests/test_infra_board.py
git commit -m "feat(infra-board): host-probe adapter (memory/agent/ssh -> JSON)"
```

---

## Task 3: The aggregator (`get_infra_tree`)

Fans out servers -> benches -> services into one normalized payload, cached to a short Redis TTL. System-Manager-gated.

**Files:**
- Modify: `press/api/infra_board.py` (add `get_infra_tree` + `_build_tree`)
- Test: `press/api/tests/test_infra_board.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `press/api/tests/test_infra_board.py`:

```python
class TestInfraTree(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_build_tree_groups_benches_by_server_with_services(self):
		from press.api import infra_board

		benches = [
			{"name": "bench-A", "server": "press-f1", "group": "g1", "status": "Active", "site_count": 1},
			{"name": "bench-B", "server": "u4", "group": "g2", "status": "Active", "site_count": 2},
		]
		procs = {
			"bench-A": [{"program": "frappe-web", "status": "Running"}, {"program": "redis-queue", "status": "Stopped"}],
			"bench-B": [{"program": "frappe-web", "status": "Running"}],
		}
		with patch.object(infra_board, "_all_servers", return_value=["press-f1", "u4"]), patch.object(
			infra_board, "_all_benches", return_value=benches
		), patch.object(infra_board, "_bench_services", side_effect=lambda b: procs[b]), patch.object(
			infra_board, "host_probes", side_effect=lambda s: {"server": s, "memory": None, "agent": None, "ssh": {"ok": True}}
		):
			tree = infra_board._build_tree()

		f1 = next(s for s in tree["servers"] if s["name"] == "press-f1")
		self.assertEqual(len(f1["benches"]), 1)
		bench_a = f1["benches"][0]
		self.assertEqual(bench_a["name"], "bench-A")
		self.assertEqual(bench_a["services_down"], 1)  # redis-queue Stopped
		self.assertEqual(bench_a["health"], "down")    # any down -> bench down

	def test_get_infra_tree_uses_cache_on_second_call(self):
		from press.api import infra_board

		frappe.cache().delete_value(infra_board.CACHE_KEY)
		calls = {"n": 0}

		def fake_build():
			calls["n"] += 1
			return {"servers": [], "built": calls["n"]}

		with patch("press.api.infra_board.frappe.only_for"), patch.object(
			infra_board, "_build_tree", side_effect=fake_build
		):
			first = infra_board.get_infra_tree()
			second = infra_board.get_infra_tree()

		self.assertEqual(calls["n"], 1)            # built once
		self.assertEqual(first["built"], second["built"])
		frappe.cache().delete_value(infra_board.CACHE_KEY)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site demo.mvpstorm.com run-tests --module press.api.tests.test_infra_board --test test_build_tree_groups_benches_by_server_with_services`
Expected: FAIL with `AttributeError: module 'press.api.infra_board' has no attribute '_build_tree'`

- [ ] **Step 3: Write minimal implementation**

Append to `press/api/infra_board.py`:

```python
import json

CACHE_KEY = "infra_board:tree"
CACHE_TTL = 15  # seconds


def _all_servers() -> list[str]:
	rows = frappe.get_all("Server", filters={"status": "Active"}, pluck="name")
	return rows


def _all_benches() -> list[dict]:
	from press.press.doctype.bench.bench_dev_overview import get_dev_overview_benches

	return get_dev_overview_benches()


def _bench_services(bench_name: str) -> list[dict]:
	from press.api.bench import get_processes

	try:
		return get_processes(bench_name) or []
	except Exception:
		return []


def _service_state(status: str) -> str:
	return "run" if status == "Running" else "down"


def _build_tree() -> dict:
	benches = _all_benches()
	by_server: dict[str, list] = {}
	for b in benches:
		services = _bench_services(b["name"])
		down = sum(1 for s in services if s.get("status") != "Running")
		node = {
			"name": b["name"],
			"group": b.get("group"),
			"status": b.get("status"),
			"site_count": b.get("site_count", 0),
			"services": [
				{"program": s.get("program"), "state": _service_state(s.get("status")), "status": s.get("status")}
				for s in services
			],
			"services_up": len(services) - down,
			"services_down": down,
			"health": "down" if down else "up",
		}
		by_server.setdefault(b.get("server"), []).append(node)

	servers = []
	for name in _all_servers():
		bs = by_server.get(name, [])
		any_down = any(x["health"] == "down" for x in bs)
		servers.append({
			"name": name,
			"benches": bs,
			"host": host_probes(name),
			"health": "down" if any_down else "up",
		})
	return {"servers": servers}


@frappe.whitelist()
def get_infra_tree() -> dict:
	"""System-Manager-gated, Redis-cached server->bench->service tree."""
	frappe.only_for("System Manager")
	cached = frappe.cache().get_value(CACHE_KEY)
	if cached:
		return json.loads(cached) if isinstance(cached, str) else cached
	tree = _build_tree()
	frappe.cache().set_value(CACHE_KEY, json.dumps(tree), expires_in_sec=CACHE_TTL)
	return tree
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bench --site demo.mvpstorm.com run-tests --module press.api.tests.test_infra_board`
Expected: PASS (all classes: 3 + 2 + 2 = 7 tests)

- [ ] **Step 5: Commit**

```bash
git add press/api/infra_board.py press/api/tests/test_infra_board.py
git commit -m "feat(infra-board): get_infra_tree aggregator (server->bench->service, cached)"
```

---

## Task 4: Live smoke test against real data + dashboard allowlist

Confirm the aggregator runs end-to-end on the live site and is reachable by the dashboard client.

**Files:**
- Modify: `press/auth.py` ONLY IF the dashboard calls it via a path not already covered by `@frappe.whitelist` (verify first; `get_infra_tree` is a plain whitelist so usually no change needed)
- Test: manual live verification

- [ ] **Step 1: Live run the aggregator as Administrator**

Run:
```bash
bench --site demo.mvpstorm.com execute press.api.infra_board.get_infra_tree
```
Expected: a JSON dict with a `servers` array; each server has `benches` and `host`. No traceback. (Confirms get_dev_overview_benches + get_processes + host_memory_pressure wire together live.)

- [ ] **Step 2: Verify dashboard-callability**

Run:
```bash
grep -n "get_infra_tree\|infra_board" press/auth.py
```
Expected: If the Vue dashboard's `call()` requires an explicit allowlist entry (pattern: methods under `press.api.*` already allowed), no change. If a 403 appears from the dashboard in Plan 2, add `press.api.infra_board.get_infra_tree` to `ALLOWED_WILDCARD_PATHS` in `press/auth.py` in the same commit (see `docs/infra-board/2026-06-05-capability-audit.md` permission notes).

- [ ] **Step 3: Confirm cache behavior live**

Run:
```bash
bench --site demo.mvpstorm.com execute press.api.infra_board.get_infra_tree
bench --site demo.mvpstorm.com mariadb -e "SELECT 1"  # noop spacer
bench --site demo.mvpstorm.com execute frappe.client.get_value --kwargs "{'doctype':'DocType','filters':{'name':'Bench'},'fieldname':'name'}"
```
Then verify the cache key exists:
```bash
bench --site demo.mvpstorm.com console <<'PYEOF'
import frappe
from press.api.infra_board import CACHE_KEY
print("CACHED:", bool(frappe.cache().get_value(CACHE_KEY)))
PYEOF
```
Expected: `CACHED: True` after a call.

- [ ] **Step 4: Commit (only if auth.py changed)**

```bash
git add press/auth.py
git commit -m "feat(infra-board): allow dashboard to call get_infra_tree"
```

---

## Definition of Done (Plan 1)

- [ ] `service_action` rejects invalid actions + unknown programs, calls `supervisorctl([program])` for valid ones (3 tests green)
- [ ] `host_probes` returns normalized memory/agent/ssh and never raises on a failing probe (2 tests green)
- [ ] `get_infra_tree` returns a server->bench->service tree, groups correctly, marks bench `down` on any stopped service, and caches to Redis ~15s (2 tests green)
- [ ] Live `bench execute press.api.infra_board.get_infra_tree` returns real data with no traceback
- [ ] All committed and pushed to `Veela-Beauty/press` `cloudflare-dns`

## Self-review notes (author)

- Spec coverage: covers the audit's three "build_new"/"reuse_with_wrapper" backend gaps (aggregator, per-service restart, host probes). Watch-Tower docker/microservice JSON adapter is deferred to Plan 1b (only memory/agent/ssh host probes here) to keep this plan shippable; disk via `get_storage_usage` is added in Plan 1b alongside docker.
- No placeholders: every step has runnable code + exact commands.
- Type consistency: `_service_action(bench_name, program, action)`, `host_probes(server)`, `get_infra_tree()`, `CACHE_KEY` used consistently across tasks and tests.
