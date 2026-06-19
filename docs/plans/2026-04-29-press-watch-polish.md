# Press Watch Polish + UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply 9 code-review fixes (race protection, DRY, polling lifecycle, perf), add a "what is this and why" UX layer to the dashboard guide cards, and tailor Site Dev tab guide separately from Bench Actions.

**Architecture:** Backend fixes are localized refactors and tests in `press/press/doctype/bench/`. Frontend changes split into structural moves (component relocation), behavioral fixes (polling lifecycle), and content additions (UX intros). UI content is split per surface (Site Dev vs Bench Actions) using a `surface` prop on `DevFlowsGuide.vue` so each tells the user what that surface specifically does — no component duplication.

**Tech Stack:** Frappe v15, Vue 3 (frappe-ui dashboard), Python 3.11, pytest, esbuild

---

## Objective

Polish the just-shipped Watch panel + Dev Flows Guide work to production quality: eliminate the polling leak, lock in regression tests, and add user-facing context that explains what each panel is and what it actually does.

**Summary:** harden the runtime, prevent today's bug from reappearing, and explain each surface in-context.

## Definition of Done

- [ ] **Race-free `start_watch`** — concurrent calls produce ≤1 process (verified by test that fires 2 starts in parallel)
- [ ] **DRY** — `_ensure_team_access` lives in `press.utils`; `bench_dev_watch.py` and `bench_app_management.py` both import it
- [ ] **No polling leak** — `BenchWatchStatus` clears its `setInterval` after `is_dev_bench === false` is observed once
- [ ] **Visibility-aware polling** — pauses when `document.visibilityState !== 'visible'`, resumes on focus
- [ ] **Component relocated** — `BenchWatchStatus.vue` lives in `dashboard/src/components/` (top level), both mount points updated
- [ ] **Lighter doc fetch** — `get_watch_status` reads `is_development_bench` via `frappe.db.get_value` (no full doc)
- [ ] **Unit tests pass** — `test_bench_dev_watch.py` covers idempotent start, clean stop, dead-PID, restart, non-dev short-circuit
- [ ] **Hook test passes** — `set_development_bench(1)` calls `start_watch`; `(0)` calls `stop_watch`; watch failure does not break the toggle
- [ ] **Regression test passes** — `is_development_bench` appears in `press.api.client.get_list` Bench response
- [ ] **UX intro on guides** — both guide cards (How to use a Dev Bench, How to pull and push code) have a 1-line "What is this and why" leader visible without expanding
- [ ] **Watch panel explains itself** — header shows what auto-rebuild does + when it runs in plain language
- [ ] **Surface-aware copy** — Site Dev tab guide focuses on "this site's bench"; Bench Actions guide focuses on "this release group's bench". Same component, different prop value.
- [ ] **Build clean** — `yarn build` produces dashboard bundle without errors
- [ ] **All tests pass** — `bench --site demo.mvpstorm.com run-tests --module press.press.doctype.bench`
- [ ] **Live verification** — Playwright check on autodeploypanel.mvpstorm.com confirms Watch panel + new copy renders on bench-0011

## Before / After

**Before (state at start of this plan):**

```
9 review issues open  |  polling continues forever  |  same generic guide on both surfaces
                         on non-dev benches and       no explanation of WHAT each panel
                         when tab is hidden           does or WHY it's there
─────────────────────────────────────────────────
0 unit tests for bench_dev_watch.py
0 regression test for the dashboard_fields bug we just fixed
DRY violation: _ensure_team_access duplicated in 2 files
get_doc() instead of cheap get_value() for single-flag reads
```

**After (state when DoD is met):**

```
9 fixes shipped       |  polling auto-stops on       |  Site Dev: "your site's bench"
+ ~15 unit tests         non-dev / hidden tab           Bench Actions: "this group's bench"
─────────────────────────────────────────────────
test_bench_dev_watch.py — 6 tests covering full lifecycle
test_bench_methods.py — hook integration test
test_bench.py — dashboard_fields contract test (locks today's bug shut)
press.utils.ensure_bench_team_access — single source
get_value() for single-column reads
Each guide card opens with a "what & why" leader paragraph
Watch panel header explains what auto-rebuild does in 1 sentence
```

| Metric | Before | After |
|---|---|---|
| Open review findings (medium+) | 9 | 0 |
| Polling lifecycle bugs | 1 (silent leak) | 0 |
| Unit tests covering the new code | 0 | 8+ |
| `_ensure_team_access` copies | 2 | 1 |
| Surface-tailored copy | 0 surfaces | 2 surfaces |
| Bench doc fetches per status poll | 1 full doc | 1 single column |
| User-visible "what is this" intros | 0 | 3 (Watch + 2 guides) |
| Days until dashboard_fields bug returns | unbounded | regression-locked |

---

## File Structure

| Action | File | Purpose |
|---|---|---|
| MODIFY | `press/press/utils/__init__.py` | Add `ensure_bench_team_access(bench_name)` next to `get_current_team` |
| MODIFY | `press/press/press/doctype/bench/bench_dev_watch.py` | Remove `_ensure_team_access`; use shell `flock`; use `get_value` |
| MODIFY | `press/press/press/doctype/bench/bench_app_management.py` | Replace local `_ensure_team_access` with import from utils |
| MODIFY | `press/press/press/doctype/bench/bench.py` | (no functional change in this plan — the existing try/except stays per Code-3C decision) |
| CREATE | `press/press/press/doctype/bench/test_bench_dev_watch.py` | Unit tests for watch lifecycle |
| MODIFY | `press/press/press/doctype/bench/test_bench_methods.py` | Add hook integration test |
| MODIFY | `press/press/press/doctype/bench/test_bench.py` | Add dashboard_fields regression test |
| MOVE | `dashboard/src/components/group/BenchWatchStatus.vue` → `dashboard/src/components/BenchWatchStatus.vue` | Top-level shared component |
| MODIFY | `dashboard/src/components/BenchWatchStatus.vue` | Polling lifecycle fix + visibility pause + UX intro |
| MODIFY | `dashboard/src/components/SiteDevTab.vue` | Update import path; pass `surface="site"` to DevFlowsGuide |
| MODIFY | `dashboard/src/components/group/ReleaseGroupActions.vue` | Update import path; pass `surface="bench"` to DevFlowsGuide |
| MODIFY | `dashboard/src/components/DevFlowsGuide.vue` | Add `surface` prop; surface-specific copy in each tab |

---

## Tasks

### Task 1: Extract `ensure_bench_team_access` to `press.utils`

**Files:**
- Modify: `press/press/utils/__init__.py`
- Modify: `press/press/press/doctype/bench/bench_app_management.py:13-29`
- Modify: `press/press/press/doctype/bench/bench_dev_watch.py:24-32`

- [ ] **Step 1.1: Add the helper to `press.utils`**

Append to `press/press/utils/__init__.py`:

```python
def ensure_bench_team_access(bench_name: str) -> None:
	"""Permission check shared by bench-side helpers.

	Allows System Manager + the bench/release-group team. Raises
	frappe.PermissionError otherwise.
	"""
	if frappe.session.data and frappe.session.data.user_type == "System User":
		return
	if "System Manager" in frappe.get_roles(frappe.session.user):
		return
	target = frappe.db.get_value("Bench", bench_name, "team") or frappe.db.get_value(
		"Release Group", frappe.db.get_value("Bench", bench_name, "group"), "team"
	)
	if target != get_current_team():
		frappe.throw("Not allowed", frappe.PermissionError)
```

- [ ] **Step 1.2: Replace local copy in `bench_dev_watch.py`**

Remove the local `_ensure_team_access` definition (lines 24-32). Replace import block at top:

```python
import frappe

from press.utils import ensure_bench_team_access

WATCH_PID_FILE = "/tmp/bench-watch.pid"
WATCH_LOG_FILE = "/tmp/bench-watch.log"
```

Replace each `_ensure_team_access(bench_name)` call site with `ensure_bench_team_access(bench_name)`.

- [ ] **Step 1.3: Replace local copy in `bench_app_management.py`**

Remove `_ensure_team_access` definition (lines 13-29). Add import:

```python
from press.utils import ensure_bench_team_access, get_current_team
```

Replace each `_ensure_team_access(bench_name=...)` call with `ensure_bench_team_access(bench_name)`. Note the **signature simplification** — old version accepted `site_name` too. Audit callers: any `_ensure_team_access(site_name=…)` callers must remain on a separate site-side helper. Grep first:

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "cd /home/frappe/frappe-bench/apps/press && grep -n '_ensure_team_access(site_name' press/press/press/doctype/bench/"
```

If no site_name callers exist, the simpler signature is safe.

- [ ] **Step 1.4: Run lint + import check**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com console <<<'from press.utils import ensure_bench_team_access; print(\"OK\")'"
```

Expected: `OK`. Any ImportError → fix.

- [ ] **Step 1.5: Commit**

```bash
git add press/press/utils/__init__.py \
        press/press/press/doctype/bench/bench_dev_watch.py \
        press/press/press/doctype/bench/bench_app_management.py
git commit -m "refactor(press.utils): extract ensure_bench_team_access (DRY)"
```

---

### Task 2: Replace `get_doc` with `get_value` in `get_watch_status`

**Files:**
- Modify: `press/press/press/doctype/bench/bench_dev_watch.py` (the `get_watch_status` and `restart_watch` functions)

- [ ] **Step 2.1: Update `get_watch_status` to use `get_value` for the flag**

Replace this block:

```python
@frappe.whitelist()
def get_watch_status(bench_name: str) -> dict:
	ensure_bench_team_access(bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	if not bench.is_development_bench:
		return {"running": False, "is_dev_bench": False}

	check = bench.docker_execute(...)
```

With:

```python
@frappe.whitelist()
def get_watch_status(bench_name: str) -> dict:
	ensure_bench_team_access(bench_name)
	if not frappe.db.get_value("Bench", bench_name, "is_development_bench"):
		return {"running": False, "is_dev_bench": False}

	bench = frappe.get_doc("Bench", bench_name)  # only fetched if dev — needed for docker_execute
	check = bench.docker_execute(...)
```

Rationale: poll for non-dev benches now does a single column read instead of full doc fetch. Dev benches still need the full doc (it has the `docker_execute` method).

- [ ] **Step 2.2: Update `restart_watch` similarly**

```python
@frappe.whitelist()
def restart_watch(bench_name: str) -> dict:
	ensure_bench_team_access(bench_name)
	if not frappe.db.get_value("Bench", bench_name, "is_development_bench"):
		frappe.throw("Bench is not a Development Bench")
	bench = frappe.get_doc("Bench", bench_name)
	stop_watch(bench)
	return start_watch(bench)
```

- [ ] **Step 2.3: Quick smoke test in console**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com console <<'PY'
from press.press.doctype.bench.bench_dev_watch import get_watch_status
print(get_watch_status('bench-0011-000110-press-f1'))  # currently dev — expect running:True
print(get_watch_status('bench-0011-000086-press-f1'))  # not dev — expect is_dev_bench:False
PY"
```

Expected: first prints `{'running': True, ...}`, second prints `{'running': False, 'is_dev_bench': False}`.

- [ ] **Step 2.4: Commit**

```bash
git add press/press/press/doctype/bench/bench_dev_watch.py
git commit -m "perf(bench-watch): use frappe.db.get_value for is_development_bench flag check"
```

---

### Task 3: Add shell `flock` for race-free `start_watch`

**Files:**
- Modify: `press/press/press/doctype/bench/bench_dev_watch.py` (the `start_watch` function)

- [ ] **Step 3.1: Replace the `start_watch` body with flock-protected spawn**

```python
WATCH_LOCK_FILE = "/tmp/bench-watch.lock"  # add this constant near the others

def start_watch(bench_doc) -> dict:
	"""Idempotently start `bench watch` in the bench container.
	Uses shell-level flock so concurrent callers can't both spawn."""
	if _is_watch_running(bench_doc):
		return {"started": False, "reason": "already_running"}

	# flock is atomic. If another process holds the lock, our exec exits 0 silently
	# (still safe — _is_watch_running will pick up the other start's PID next poll).
	cmd = (
		"bash -c '"
		f"exec 9>{WATCH_LOCK_FILE}; "
		'flock -n 9 || exit 0; '
		f"if [ -s {WATCH_PID_FILE} ] && kill -0 $(cat {WATCH_PID_FILE}) 2>/dev/null; then exit 0; fi; "
		"cd /home/frappe/frappe-bench && "
		f"nohup bench watch > {WATCH_LOG_FILE} 2>&1 < /dev/null & "
		f"echo $! > {WATCH_PID_FILE}'"
	)
	bench_doc.docker_execute(cmd)
	return {"started": True}
```

Notes:
- `exec 9>file` opens fd 9 for writing
- `flock -n 9` non-blockingly acquires the lock; `|| exit 0` if held → silently no-op (the other caller is doing the work)
- Inner re-check of PID file prevents the rare case where the lock is released between contended attempts but the watch is already up

- [ ] **Step 3.2: Smoke test concurrent starts**

Will be covered by Task 6 unit test. Skip immediate manual test.

- [ ] **Step 3.3: Commit**

```bash
git add press/press/press/doctype/bench/bench_dev_watch.py
git commit -m "fix(bench-watch): atomic start with shell flock to prevent double-spawn"
```

---

### Task 4: Move `BenchWatchStatus.vue` to top-level `components/` + update imports

**Files:**
- Move: `dashboard/src/components/group/BenchWatchStatus.vue` → `dashboard/src/components/BenchWatchStatus.vue`
- Modify: `dashboard/src/components/SiteDevTab.vue`
- Modify: `dashboard/src/components/group/ReleaseGroupActions.vue`

- [ ] **Step 4.1: git mv the file**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "cd /home/frappe/frappe-bench/apps/press && \
   git mv dashboard/src/components/group/BenchWatchStatus.vue dashboard/src/components/BenchWatchStatus.vue"
```

- [ ] **Step 4.2: Update SiteDevTab.vue import**

Old:
```js
import BenchWatchStatus from './group/BenchWatchStatus.vue';
```

New:
```js
import BenchWatchStatus from './BenchWatchStatus.vue';
```

- [ ] **Step 4.3: Update ReleaseGroupActions.vue import**

Old:
```js
import BenchWatchStatus from './BenchWatchStatus.vue';
```

New:
```js
import BenchWatchStatus from '../BenchWatchStatus.vue';
```

- [ ] **Step 4.4: Commit (no build yet — defer to Task 5)**

```bash
git add -A
git commit -m "refactor(dashboard): move BenchWatchStatus to top-level components/ (shared between Site Dev and Bench Actions)"
```

---

### Task 5: Polling lifecycle — clear timer on non-dev + visibility-aware pause + UX intro

**Files:**
- Modify: `dashboard/src/components/BenchWatchStatus.vue`

- [ ] **Step 5.1: Add UX intro line at the top of the panel**

Just under the badge in the header row, add a short explanatory line. Update the `<template>` header:

```vue
<div class="overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
	<div class="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-2.5">
		<div class="flex flex-col">
			<div class="flex items-center gap-2">
				<span class="text-xs font-semibold text-gray-900">Auto-Rebuild (bench watch)</span>
				<span class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium" :class="badgeClass">
					<span class="h-1.5 w-1.5 rounded-full" :class="dotClass"></span>
					{{ badgeLabel }}
				</span>
			</div>
			<div class="text-[11px] text-gray-500">
				Watches JS/CSS in every app on this bench and rebuilds bundles ~1 s after you save.
				Hard-reload your browser to see changes.
			</div>
		</div>
		<div class="flex items-center gap-1.5">
			...existing buttons...
		</div>
	</div>
```

- [ ] **Step 5.2: Clear setInterval permanently when bench is non-dev**

In the `refresh` method, after the API call resolves and we know `is_dev_bench === false`, kill the timer:

```js
async refresh({ silent = false } = {}) {
	if (!silent) this.loading = true;
	try {
		const res = await call('press.press.doctype.bench.bench_dev_watch.get_watch_status',
			{ bench_name: this.benchName });
		this.status = res || res?.message || null;

		// PERF: if this bench isn't a dev bench, stop polling forever
		if (this.status && this.status.is_dev_bench === false && this.pollTimer) {
			clearInterval(this.pollTimer);
			this.pollTimer = null;
		}
	} catch (e) {
		if (!silent) toast.error('Could not fetch watch status');
	} finally {
		this.loading = false;
	}
}
```

- [ ] **Step 5.3: Pause polling when tab is hidden, resume on focus**

Add a `data()` field `visibilityHandler: null` and update `mounted/beforeUnmount`:

```js
mounted() {
	this.refresh();
	this.startPolling();
	this.visibilityHandler = () => {
		if (document.visibilityState === 'visible') {
			this.refresh({ silent: true });
			this.startPolling();
		} else {
			this.stopPolling();
		}
	};
	document.addEventListener('visibilitychange', this.visibilityHandler);
},
beforeUnmount() {
	this.stopPolling();
	if (this.visibilityHandler) {
		document.removeEventListener('visibilitychange', this.visibilityHandler);
	}
},
methods: {
	startPolling() {
		if (this.pollTimer || (this.status && this.status.is_dev_bench === false)) return;
		this.pollTimer = setInterval(() => this.refresh({ silent: true }), POLL_MS);
	},
	stopPolling() {
		if (this.pollTimer) {
			clearInterval(this.pollTimer);
			this.pollTimer = null;
		}
	},
	...
}
```

- [ ] **Step 5.4: Build dashboard**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "cd /home/frappe/frappe-bench/apps/press/dashboard && yarn build 2>&1 | tail -3"
```

Expected: `built in ~40s` and no errors.

- [ ] **Step 5.5: Verify in browser via Playwright**

Navigate to bench-0011 actions, confirm Watch panel renders with new intro line and badge.

- [ ] **Step 5.6: Commit**

```bash
git add dashboard/src/components/BenchWatchStatus.vue
git commit -m "feat(dashboard): BenchWatchStatus visibility-aware polling + clear timer on non-dev + UX intro"
```

---

### Task 6: Tests for `bench_dev_watch.py`

**Files:**
- Create: `press/press/press/doctype/bench/test_bench_dev_watch.py`

- [ ] **Step 6.1: Write the test file**

```python
"""Unit tests for press.press.doctype.bench.bench_dev_watch.

Mocks Bench.docker_execute so tests run without a live container.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.press.doctype.bench.bench_dev_watch import (
	WATCH_PID_FILE,
	_is_watch_running,
	get_watch_status,
	restart_watch,
	start_watch,
	stop_watch,
)


class FakeBench:
	"""Minimal Bench stand-in with a mockable docker_execute."""

	def __init__(self, name="test-bench-0001-press-f1", outputs=None):
		self.name = name
		self.is_development_bench = 1
		self.docker_execute = MagicMock(side_effect=outputs or [])


class TestBenchDevWatch(FrappeTestCase):
	def test_start_watch_idempotent_when_running(self):
		"""start_watch must not spawn a second process if one is already alive."""
		bench = FakeBench(outputs=[{"output": "running\n", "returncode": 0}])
		result = start_watch(bench)
		self.assertEqual(result, {"started": False, "reason": "already_running"})
		# Only the running-check should have hit docker_execute, not the spawn
		self.assertEqual(bench.docker_execute.call_count, 1)

	def test_start_watch_spawns_when_stopped(self):
		"""start_watch spawns when no live PID is tracked."""
		bench = FakeBench(outputs=[
			{"output": "stopped\n", "returncode": 0},  # _is_watch_running
			{"output": "", "returncode": 0},           # the spawn
		])
		result = start_watch(bench)
		self.assertEqual(result, {"started": True})
		self.assertEqual(bench.docker_execute.call_count, 2)
		# Verify the spawn call actually invokes flock + bench watch
		spawn_cmd = bench.docker_execute.call_args_list[1][0][0]
		self.assertIn("flock", spawn_cmd)
		self.assertIn("bench watch", spawn_cmd)
		self.assertIn(WATCH_PID_FILE, spawn_cmd)

	def test_stop_watch_cleans_up(self):
		bench = FakeBench(outputs=[{"output": "", "returncode": 0}])
		result = stop_watch(bench)
		self.assertEqual(result, {"stopped": True})
		stop_cmd = bench.docker_execute.call_args[0][0]
		self.assertIn("kill", stop_cmd)
		self.assertIn(WATCH_PID_FILE, stop_cmd)

	def test_is_watch_running_returns_false_for_dead_pid(self):
		bench = FakeBench(outputs=[{"output": "stopped\n", "returncode": 0}])
		self.assertFalse(_is_watch_running(bench))

	def test_is_watch_running_returns_true_for_live_pid(self):
		bench = FakeBench(outputs=[{"output": "running\n", "returncode": 0}])
		self.assertTrue(_is_watch_running(bench))

	@patch("press.press.doctype.bench.bench_dev_watch.frappe.db.get_value")
	@patch("press.press.doctype.bench.bench_dev_watch.ensure_bench_team_access")
	def test_get_watch_status_short_circuits_for_non_dev(self, _access, get_value):
		"""Non-dev benches must NOT trigger a docker_execute (perf protection)."""
		get_value.return_value = 0
		result = get_watch_status("any-bench-name")
		self.assertEqual(result, {"running": False, "is_dev_bench": False})
		# Single-column read, never opened the doc, never executed in container
		get_value.assert_called_once_with("Bench", "any-bench-name", "is_development_bench")

	@patch("press.press.doctype.bench.bench_dev_watch.frappe.get_doc")
	@patch("press.press.doctype.bench.bench_dev_watch.frappe.db.get_value")
	@patch("press.press.doctype.bench.bench_dev_watch.ensure_bench_team_access")
	def test_get_watch_status_returns_running_for_live_dev_bench(self, _a, get_value, get_doc):
		get_value.return_value = 1
		bench = FakeBench(outputs=[{"output": "running:12345\nbuild line 1\nbuild line 2", "returncode": 0}])
		get_doc.return_value = bench
		result = get_watch_status("test-bench")
		self.assertTrue(result["running"])
		self.assertEqual(result["pid"], 12345)
		self.assertIn("build line 1", result["log_tail"])

	@patch("press.press.doctype.bench.bench_dev_watch.frappe.get_doc")
	@patch("press.press.doctype.bench.bench_dev_watch.frappe.db.get_value")
	@patch("press.press.doctype.bench.bench_dev_watch.ensure_bench_team_access")
	def test_restart_watch_calls_stop_then_start(self, _a, get_value, get_doc):
		get_value.return_value = 1
		bench = FakeBench(outputs=[
			{"output": "", "returncode": 0},          # stop
			{"output": "stopped\n", "returncode": 0},  # _is_watch_running inside start
			{"output": "", "returncode": 0},          # spawn
		])
		get_doc.return_value = bench
		result = restart_watch("test-bench")
		self.assertEqual(result, {"started": True})
		# stop + is_running + spawn = 3 calls
		self.assertEqual(bench.docker_execute.call_count, 3)
```

- [ ] **Step 6.2: Run the new tests**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com run-tests \
     --module press.press.doctype.bench.test_bench_dev_watch 2>&1 | tail -20"
```

Expected: `OK` and 8 tests pass.

- [ ] **Step 6.3: Commit**

```bash
git add press/press/press/doctype/bench/test_bench_dev_watch.py
git commit -m "test(bench-watch): unit tests for start/stop/status/restart lifecycle"
```

---

### Task 7: Test for `set_development_bench` watch hook integration

**Files:**
- Modify: `press/press/press/doctype/bench/test_bench_methods.py`

- [ ] **Step 7.1: Append a new test class to `test_bench_methods.py`**

Open the file and add at the bottom:

```python
class TestSetDevelopmentBenchWatchHook(FrappeTestCase):
	"""Verify set_development_bench triggers start_watch / stop_watch as a side-effect."""

	def setUp(self):
		# Use first existing bench for type checks; we mock the doc methods so no DB writes
		self.bench_name = "test-hook-bench"

	@patch("press.press.doctype.bench.bench_dev_watch.start_watch")
	@patch("press.press.doctype.bench.bench_dev_watch.stop_watch")
	def test_enable_calls_start_watch(self, mock_stop, mock_start):
		bench = MagicMock()
		bench.is_development_bench = 0
		bench.save = MagicMock()
		# Bind the real method to the mock so it executes the production code path
		from press.press.doctype.bench.bench import Bench
		Bench.set_development_bench(bench, enable=1)
		mock_start.assert_called_once_with(bench)
		mock_stop.assert_not_called()

	@patch("press.press.doctype.bench.bench_dev_watch.start_watch")
	@patch("press.press.doctype.bench.bench_dev_watch.stop_watch")
	def test_disable_calls_stop_watch(self, mock_stop, mock_start):
		bench = MagicMock()
		bench.is_development_bench = 1
		bench.save = MagicMock()
		from press.press.doctype.bench.bench import Bench
		Bench.set_development_bench(bench, enable=0)
		mock_stop.assert_called_once_with(bench)
		mock_start.assert_not_called()

	@patch("press.press.doctype.bench.bench_dev_watch.start_watch", side_effect=Exception("watch failed"))
	def test_watch_failure_does_not_break_toggle(self, _start):
		"""set_development_bench must succeed even if start_watch raises."""
		bench = MagicMock()
		bench.is_development_bench = 0
		bench.save = MagicMock()
		from press.press.doctype.bench.bench import Bench
		# Should not raise
		Bench.set_development_bench(bench, enable=1)
		bench.save.assert_called_once()
```

Add imports if missing at top:

```python
from unittest.mock import MagicMock, patch
```

- [ ] **Step 7.2: Run new tests**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com run-tests \
     --module press.press.doctype.bench.test_bench_methods 2>&1 | tail -10"
```

Expected: all tests pass including 3 new ones.

- [ ] **Step 7.3: Commit**

```bash
git add press/press/press/doctype/bench/test_bench_methods.py
git commit -m "test(bench): set_development_bench triggers start_watch/stop_watch side-effects"
```

---

### Task 8: Regression test for `is_development_bench` in `dashboard_fields`

**Files:**
- Modify: `press/press/press/doctype/bench/test_bench.py`

- [ ] **Step 8.1: Add a regression test class**

Append to `test_bench.py`:

```python
class TestBenchDashboardFields(FrappeTestCase):
	"""Regression tests for the dashboard_fields whitelist on Bench.

	Background: on 2026-04-29 the Watch panel + 'Mark as Dev Bench' button
	silently broke because is_development_bench was missing from this tuple.
	This test locks in the contract.
	"""

	def test_is_development_bench_in_dashboard_fields(self):
		from press.press.doctype.bench.bench import Bench
		self.assertIn(
			"is_development_bench",
			Bench.dashboard_fields,
			"is_development_bench MUST be in Bench.dashboard_fields — the dashboard "
			"depends on it for the Mark/Unset Dev Bench toggle and the Auto-Rebuild "
			"watch panel. Removing it silently breaks both surfaces.",
		)
```

- [ ] **Step 8.2: Run the regression test**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com run-tests \
     --module press.press.doctype.bench.test_bench 2>&1 | tail -10"
```

Expected: test passes. To verify it actually catches the bug: temporarily remove the field, confirm test fails, restore.

- [ ] **Step 8.3: Commit**

```bash
git add press/press/press/doctype/bench/test_bench.py
git commit -m "test(bench): regression for is_development_bench in dashboard_fields"
```

---

### Task 9: Add `surface` prop to DevFlowsGuide + tailor copy per surface

**Files:**
- Modify: `dashboard/src/components/DevFlowsGuide.vue`
- Modify: `dashboard/src/components/SiteDevTab.vue`
- Modify: `dashboard/src/components/group/ReleaseGroupActions.vue`

- [ ] **Step 9.1: Add `surface` prop and a `surfaceIntro` computed**

In `DevFlowsGuide.vue` `<script>`:

```js
props: {
	defaultFlow: { type: String, default: 'dashboard',
		validator: v => ['dashboard','code-server','ssh'].includes(v) },
	surface: { type: String, default: 'bench',
		validator: v => ['bench', 'site'].includes(v) },
},
computed: {
	surfaceIntro() {
		if (this.surface === 'site') {
			return 'These are the three ways to push code that affects THIS site. ' +
				'Pick the one that matches how you edit: from the dashboard, from Code Server in the browser, or from a real SSH terminal. ' +
				'Whichever you choose, the change lands in the same bench container that powers this site.';
		}
		// surface === 'bench'
		return 'Three ways to push code from a bench in this group. ' +
			'These flows apply to every site running on the bench you choose. ' +
			'Use Dashboard for the easiest path, Code Server for browser-based editing, or SSH if you want your own terminal.';
	},
},
```

- [ ] **Step 9.2: Render the intro inside the open panel header**

Right after the tabs row in the template, add:

```vue
<div v-if="open" class="border-b border-gray-200 bg-gray-50 px-4 py-2 text-[11.5px] leading-relaxed text-gray-600">
	{{ surfaceIntro }}
</div>
```

- [ ] **Step 9.3: Wire `surface="site"` from `SiteDevTab.vue`**

Update the existing mount:
```vue
<DevFlowsGuide default-flow="dashboard" surface="site" />
```

- [ ] **Step 9.4: Wire `surface="bench"` from `ReleaseGroupActions.vue`**

Update the existing mount:
```vue
<DevFlowsGuide default-flow="code-server" surface="bench" />
```

- [ ] **Step 9.5: Build dashboard**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "cd /home/frappe/frappe-bench/apps/press/dashboard && yarn build 2>&1 | tail -3"
```

- [ ] **Step 9.6: Verify both surfaces render distinct copy via Playwright**

Navigate to:
- `/dashboard/sites/<site>/dev` → confirm intro starts "These are the three ways to push code that affects THIS site"
- `/dashboard/groups/bench-0011/actions` → confirm intro starts "Three ways to push code from a bench in this group"

- [ ] **Step 9.7: Commit**

```bash
git add dashboard/src/components/DevFlowsGuide.vue \
        dashboard/src/components/SiteDevTab.vue \
        dashboard/src/components/group/ReleaseGroupActions.vue
git commit -m "feat(dashboard): surface-aware DevFlowsGuide intros (Site Dev vs Bench Actions)"
```

---

### Task 10: Add "What is this and why" leader to "How to use a Dev Bench" guide

**Files:**
- Modify: `dashboard/src/components/group/ReleaseGroupActions.vue`

- [ ] **Step 10.1: Insert a 1-line leader directly under the collapsed-card header**

Locate the existing "How to use a Dev Bench" collapsible. After the button row but inside the `v-if="showWorkflow"` panel, ensure the first content is a leader paragraph (already exists per current code at line 27-29 — verify and tighten):

```vue
<p class="text-xs leading-relaxed text-gray-600">
	A <strong>Dev Bench</strong> is a bench you've flagged for development.
	Press flips on developer mode (Python edits hot-reload) and the
	<strong>Auto-Rebuild</strong> process inside the container, which watches your
	JS/CSS files and rebuilds bundles automatically. Use it for quick edits;
	push to GitHub from the Site Dev tab when ready.
</p>
```

This replaces the current less-explanatory leader. Goal: in 4 lines explain WHAT a Dev Bench is + WHAT the side-effects are + WHERE to push.

- [ ] **Step 10.2: Build + verify in Playwright**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "cd /home/frappe/frappe-bench/apps/press/dashboard && yarn build 2>&1 | tail -3"
```

Expand "How to use a Dev Bench" on the page, confirm new leader is visible.

- [ ] **Step 10.3: Commit**

```bash
git add dashboard/src/components/group/ReleaseGroupActions.vue
git commit -m "docs(dashboard): clearer leader paragraph on 'How to use a Dev Bench'"
```

---

### Task 11: Final integration — full test run + Playwright verification + relay-push to GitHub

**Files:** none new

- [ ] **Step 11.1: Run all bench tests**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com run-tests \
     --module press.press.doctype.bench 2>&1 | tail -20"
```

Expected: All tests pass (existing + new 11+).

- [ ] **Step 11.2: Visual verification on autodeploypanel via Playwright**

Open these URLs and visually confirm:
1. `/dashboard/groups/bench-0011/actions` →
   - "How to use a Dev Bench" leader explains Dev Bench in plain language
   - "How to pull and push code" intro starts "Three ways to push code from a bench in this group"
   - bench-0011-000110 tile shows "This bench is marked as a development bench" + Watch panel running
2. `/dashboard/sites/roseline-stg.sandbox.mvpstorm.com/dev` →
   - "How to pull and push code" intro starts "These are the three ways to push code that affects THIS site"
   - Auto-Rebuild panel renders with new intro line "Watches JS/CSS in every app on this bench…"

- [ ] **Step 11.3: Relay-push the entire batch to GitHub**

```bash
# On press-ctrl: bundle commits made during this plan
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "cd /home/frappe/frappe-bench/apps/press && \
   git bundle create /tmp/watch-polish.bundle 8dc8ab3c6d..cloudflare-dns"

# On Hetzner box: fetch + ff + push via elgogary key
scp -i ~/.ssh/id_ed25519_old root@89.167.116.92:/tmp/watch-polish.bundle /tmp/watch-polish.bundle
cd /home/eslam/data/erpnext-app-repos/press_local/press
git fetch /tmp/watch-polish.bundle 'refs/heads/cloudflare-dns:refs/remotes/press-bundle/cloudflare-dns3'
git merge --ff-only press-bundle/cloudflare-dns3
git push accurate-systems cloudflare-dns
```

Expected: push succeeds, all commits land on `accurate-systems/press` cloudflare-dns.

- [ ] **Step 11.4: Final summary commit (optional — only if any leftover docs)**

If any markdown docs were touched, commit them. Otherwise skip.

---

### Task 12: Recover ghost-pending sites + add detection

**Background:** Discovered during this session — `stlube-stg.sandbox.mvpstorm.com` and `prime-textile.sandbox.mvpstorm.com` have `status='Pending'` even though they've been fully functional for 16 days (daily backups + migrations all green). The original `New Site` agent job failed on 2026-04-13 → status never advanced to `Active` → dashboard UI hides plan/usage display + install-app dialog gates on `status='Active'`. This is a recurring class of bug: a failed initial provisioning leaves the site in a permanently-stuck state with no auto-recovery.

**Files:**
- Modify: `press/press/press/doctype/site/site.py` — add `recover_ghost_pending_sites` scheduler function
- Modify: `press/hooks.py` — register the scheduler entry
- Create: `press/press/press/doctype/site/test_site_recovery.py` — tests for the detector
- Data: one-shot fix for the 2 currently-stuck sites

- [ ] **Step 12.1: One-shot data fix for the 2 known stuck sites**

This is a manual data correction. Both sites currently have an Update Site Migrate Running — wait for those to complete first.

```bash
# Poll until both migrate jobs are done
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com console <<'PY'
import frappe
running = frappe.db.sql('SELECT name, site, status FROM \`tabAgent Job\` WHERE site IN (%s, %s) AND status IN (\"Running\",\"Pending\")', ('stlube-stg.sandbox.mvpstorm.com','prime-textile.sandbox.mvpstorm.com'), as_dict=True)
print('STILL RUNNING:', running)
PY"
```

When both report no in-flight jobs:

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com console <<'PY'
import frappe
for name in ['stlube-stg.sandbox.mvpstorm.com','prime-textile.sandbox.mvpstorm.com']:
    cur = frappe.db.get_value('Site', name, 'status')
    if cur == 'Pending':
        frappe.db.set_value('Site', name, 'status', 'Active')
        print(f'{name}: flipped Pending -> Active')
    else:
        print(f'{name}: status is {cur}, skipping')
frappe.db.commit()
PY"
```

- [ ] **Step 12.2: Add scheduler function `recover_ghost_pending_sites` in site.py**

Append to `press/press/press/doctype/site/site.py`:

```python
def recover_ghost_pending_sites():
	"""Detect and recover sites stuck in Pending status despite being functional.

	A 'ghost-pending' site has:
	  - status='Pending'
	  - setup_wizard_complete=1
	  - At least one successful Backup Site agent job in the last 7 days
	  - No in-flight provisioning jobs

	The most common cause is an early 'New Site' agent job failure that left
	status='Pending' even though all subsequent jobs (migrations, backups,
	upstream registration) succeeded. This function recovers them automatically.
	"""
	candidates = frappe.db.sql(
		"""
		SELECT s.name FROM `tabSite` s
		WHERE s.status = 'Pending'
		  AND s.setup_wizard_complete = 1
		  AND EXISTS (
			SELECT 1 FROM `tabAgent Job` j
			WHERE j.site = s.name
			  AND j.job_type = 'Backup Site'
			  AND j.status = 'Success'
			  AND j.creation > NOW() - INTERVAL 7 DAY
		  )
		  AND NOT EXISTS (
			SELECT 1 FROM `tabAgent Job` j2
			WHERE j2.site = s.name
			  AND j2.status IN ('Pending','Running')
			  AND j2.job_type IN ('New Site','New Site from Backup','Migrate Site',
			                     'Update Site Migrate','Update Site Pull')
		  )
		""",
		as_dict=True,
	)
	for row in candidates:
		try:
			frappe.db.set_value("Site", row["name"], "status", "Active")
			frappe.logger().info(
				f"recover_ghost_pending_sites: {row['name']} flipped Pending -> Active "
				f"(had successful backups + setup complete)"
			)
		except Exception as e:
			frappe.logger().error(
				f"recover_ghost_pending_sites: failed to fix {row['name']}: {e}"
			)
	frappe.db.commit()
```

- [ ] **Step 12.3: Register the scheduler in hooks.py**

In `press/hooks.py`, find the `daily` scheduler list and append:

```python
"daily": [
	# ... existing entries ...
	"press.press.doctype.site.site.recover_ghost_pending_sites",
],
```

Why daily, not hourly: this is a recovery for a rare edge case. Daily is plenty.

- [ ] **Step 12.4: Write tests**

Create `press/press/press/doctype/site/test_site_recovery.py`:

```python
"""Tests for ghost-pending site recovery."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.press.doctype.site.site import recover_ghost_pending_sites


class TestRecoverGhostPendingSites(FrappeTestCase):
	@patch("press.press.doctype.site.site.frappe.db.set_value")
	@patch("press.press.doctype.site.site.frappe.db.sql")
	def test_recovers_eligible_site(self, mock_sql, mock_set):
		mock_sql.return_value = [{"name": "ghost-site.example.com"}]
		recover_ghost_pending_sites()
		mock_set.assert_called_once_with("Site", "ghost-site.example.com", "status", "Active")

	@patch("press.press.doctype.site.site.frappe.db.set_value")
	@patch("press.press.doctype.site.site.frappe.db.sql")
	def test_no_op_when_no_candidates(self, mock_sql, mock_set):
		mock_sql.return_value = []
		recover_ghost_pending_sites()
		mock_set.assert_not_called()

	@patch("press.press.doctype.site.site.frappe.logger")
	@patch("press.press.doctype.site.site.frappe.db.set_value", side_effect=Exception("boom"))
	@patch("press.press.doctype.site.site.frappe.db.sql")
	def test_continues_on_individual_failure(self, mock_sql, mock_set, mock_logger):
		"""If one site recovery fails, others should still be attempted."""
		mock_sql.return_value = [
			{"name": "ghost-1.example.com"},
			{"name": "ghost-2.example.com"},
		]
		recover_ghost_pending_sites()
		# both attempted despite first one raising
		self.assertEqual(mock_set.call_count, 2)
		# error logged
		self.assertTrue(mock_logger.return_value.error.called)
```

- [ ] **Step 12.5: Run new tests**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com run-tests \
     --module press.press.doctype.site.test_site_recovery 2>&1 | tail -10"
```

Expected: 3 tests pass.

- [ ] **Step 12.6: Verify scheduler registration**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com console <<'PY'
from frappe.utils.scheduler import get_scheduler_status
import frappe
hooks = frappe.get_hooks('scheduler_events')
daily = hooks.get('daily', [])
assert any('recover_ghost_pending_sites' in h for h in daily), 'scheduler entry missing'
print('OK: recover_ghost_pending_sites registered for daily')
PY"
```

- [ ] **Step 12.7: Commit**

```bash
git add press/press/press/doctype/site/site.py \
        press/hooks.py \
        press/press/press/doctype/site/test_site_recovery.py
git commit -m "fix(site): recover ghost-pending sites that survived a failed New Site job

Sites whose initial 'New Site' agent job fails sometimes never advance from
status='Pending' to 'Active', even though all subsequent jobs (backups,
migrations) succeed. The dashboard hides plan + install-app on Pending sites,
making them look broken to users.

Discovered: stlube-stg and prime-textile were stuck like this for 16 days.

This adds a daily scheduler that detects ghost-pending sites and flips them
to Active. Conservative criteria: setup_wizard_complete=1, recent successful
backup, no in-flight provisioning jobs.

3 unit tests cover: detection, no-op, partial-failure resilience."
```

---

## NOTE: BI AI install visibility

Separate from this plan — the user must trigger a deploy of `bench-0006` so the latest Docker image includes `sanad_business_intelligence_ai` (it's in the release group manifest but not in the active bench image `bench-0006-000022`). Press cannot automate this safely on a multi-site production bench.

Action: user clicks **Update Available** on `/dashboard/groups/bench-0006/apps` for `sanad_business_intelligence_ai`. Press creates a new Deploy Candidate that includes all group apps. After deploy completes (~5–35 min), BI AI appears in the install dialog on every site in bench-0006.

---

## Completion Checklist

After Task 12 finishes, mark these confirmed:

- [ ] Backend: 8+ unit tests pass
- [ ] Backend: race protection test passes
- [ ] Backend: dashboard_fields regression test passes
- [ ] Backend: ghost-pending recovery scheduler registered + tested
- [ ] Frontend: dashboard builds without errors
- [ ] Frontend: BenchWatchStatus lives in `components/`
- [ ] Frontend: polling stops on non-dev benches (verified via Playwright network tab)
- [ ] Frontend: polling pauses when tab is hidden (verified via Playwright)
- [ ] Frontend: Site Dev tab shows site-context intro
- [ ] Frontend: Bench Actions tab shows bench-context intro
- [ ] Frontend: Watch panel header explains what auto-rebuild does
- [ ] Data: stlube-stg + prime-textile flipped to Active (one-shot fix)
- [ ] All commits pushed to GitHub `accurate-systems/press` cloudflare-dns
