# Site Dev Tab v2 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade SiteDevTab.vue to show per-app git status (ahead/dirty), VS Code button, and Restart Bench button — matching prototype `docs/prototypes/site_dev_tab_v2.html`.

**Architecture:** Two new `@frappe.whitelist()` methods in `bench_dev_overview.py`. Vue component rewritten to consume them. All new Python tested with TDD before implementation.

**Tech Stack:** Python (Frappe), Vue 2 Options API, frappe-ui `call()`, Tailwind CSS.

---

## Task 1: Failing tests for `get_app_git_status()`

**Files:**
- Create: `press/press/doctype/bench/test_bench_dev_git_status.py`

**Step 1: Write the failing test file**

```python
"""
Unit tests for get_app_git_status() in bench_dev_overview.py

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_bench_dev_git_status -v
"""
import sys, types, unittest
from unittest.mock import MagicMock, patch

_frappe_stub = types.ModuleType("frappe")
_frappe_stub._ = lambda s: s
_frappe_stub.whitelist = lambda fn=None, **kw: (lambda f: f) if fn is None else fn
_frappe_stub.only_for = lambda role: None
_frappe_stub.get_all = MagicMock()
_frappe_stub.get_doc = MagicMock()
_frappe_stub.session = MagicMock()
_frappe_stub.session.user = "admin@test.com"
_frappe_stub.db = MagicMock()
_frappe_stub.logger = lambda: MagicMock()
sys.modules.setdefault("frappe", _frappe_stub)

import press.press.doctype.bench.bench_dev_overview as _bdo

PATCH = "press.press.doctype.bench.bench_dev_overview.frappe"


def _app_entry(app, hash_="abc123"):
    ae = MagicMock(); ae.app = app; ae.hash = hash_
    return ae


def _bench_doc(name, apps):
    doc = MagicMock(); doc.name = name
    doc.apps = apps
    return doc


def _docker_result(output, returncode=0):
    return {"status": "Success", "output": output, "returncode": returncode}


class TestGetAppGitStatus(unittest.TestCase):

    @patch(PATCH)
    def test_requires_system_manager(self, mf):
        mf.only_for.side_effect = Exception("Not permitted")
        with self.assertRaises(Exception):
            _bdo.get_app_git_status("bench-001")

    @patch(PATCH)
    def test_returns_list_of_apps(self, mf):
        bench = _bench_doc("bench-001", [_app_entry("frappe"), _app_entry("erpnext")])
        mf.get_doc.return_value = bench
        bench.docker_execute.return_value = _docker_result("version-15:0:0:fix: cleanup")
        result = _bdo.get_app_git_status("bench-001")
        self.assertEqual(len(result), 2)

    @patch(PATCH)
    def test_result_has_required_keys(self, mf):
        bench = _bench_doc("bench-001", [_app_entry("frappe")])
        mf.get_doc.return_value = bench
        bench.docker_execute.return_value = _docker_result("version-15:3:2:feat: new")
        result = _bdo.get_app_git_status("bench-001")
        for key in ("app", "branch", "ahead", "dirty", "last_msg"):
            self.assertIn(key, result[0])

    @patch(PATCH)
    def test_parses_ahead_and_dirty_counts(self, mf):
        bench = _bench_doc("bench-001", [_app_entry("erpnext")])
        mf.get_doc.return_value = bench
        bench.docker_execute.return_value = _docker_result("version-15:4:7:fix: tax")
        result = _bdo.get_app_git_status("bench-001")
        self.assertEqual(result[0]["ahead"], 4)
        self.assertEqual(result[0]["dirty"], 7)
        self.assertEqual(result[0]["branch"], "version-15")

    @patch(PATCH)
    def test_last_msg_captured(self, mf):
        bench = _bench_doc("bench-001", [_app_entry("press")])
        mf.get_doc.return_value = bench
        bench.docker_execute.return_value = _docker_result("main:0:0:feat: add git status")
        result = _bdo.get_app_git_status("bench-001")
        self.assertEqual(result[0]["last_msg"], "feat: add git status")

    @patch(PATCH)
    def test_docker_execute_called_with_subdir(self, mf):
        bench = _bench_doc("bench-001", [_app_entry("press")])
        mf.get_doc.return_value = bench
        bench.docker_execute.return_value = _docker_result("main:0:0:")
        _bdo.get_app_git_status("bench-001")
        call_kwargs = bench.docker_execute.call_args[1]
        self.assertEqual(call_kwargs.get("subdir"), "apps/press")

    @patch(PATCH)
    def test_docker_execute_no_log(self, mf):
        """git status polls should not flood the bench shell log."""
        bench = _bench_doc("bench-001", [_app_entry("frappe")])
        mf.get_doc.return_value = bench
        bench.docker_execute.return_value = _docker_result("v15:0:0:")
        _bdo.get_app_git_status("bench-001")
        call_kwargs = bench.docker_execute.call_args[1]
        self.assertFalse(call_kwargs.get("create_log", True))

    @patch(PATCH)
    def test_docker_failure_returns_safe_defaults(self, mf):
        bench = _bench_doc("bench-001", [_app_entry("frappe")])
        mf.get_doc.return_value = bench
        bench.docker_execute.side_effect = Exception("container not found")
        result = _bdo.get_app_git_status("bench-001")
        self.assertEqual(result[0]["ahead"], 0)
        self.assertEqual(result[0]["dirty"], 0)
        self.assertEqual(result[0]["branch"], "?")

    @patch(PATCH)
    def test_empty_bench_returns_empty_list(self, mf):
        bench = _bench_doc("bench-001", [])
        mf.get_doc.return_value = bench
        result = _bdo.get_app_git_status("bench-001")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

**Step 2: Run test — confirm ALL FAIL (ImportError or AttributeError on missing function)**

```bash
cd /home/eslam/data/erpnext-app-repos/press_local
python3 -m unittest press.press.doctype.bench.test_bench_dev_git_status -v 2>&1 | tail -15
```

Expected: `AttributeError: module ... has no attribute 'get_app_git_status'`

**Step 3: Commit failing tests**

```bash
git add press/press/doctype/bench/test_bench_dev_git_status.py
git commit -m "test(tdd): failing tests for get_app_git_status()"
```

---

## Task 2: Implement `get_app_git_status()`

**Files:**
- Modify: `press/press/doctype/bench/bench_dev_overview.py`

**Step 1: Add the function** (append after `push_app_to_github`):

```python
@frappe.whitelist()
def get_app_git_status(bench_name):
    """
    Return per-app git status for a bench: branch, commits ahead of remote,
    dirty file count, and last commit message.
    Calls docker_execute per app — no shell log created (polling-safe).
    """
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)
    results = []
    for ae in bench.apps:
        if not ae.app:
            continue
        cmd = (
            "branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?');"
            "ahead=$(git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0);"
            "dirty=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ');"
            "msg=$(git log -1 --format='%s' 2>/dev/null | cut -c1-60);"
            'echo "$branch:$ahead:$dirty:$msg"'
        )
        try:
            raw = bench.docker_execute(
                cmd,
                subdir=f"apps/{ae.app}",
                save_output=False,
                create_log=False,
            )
            output = (raw.get("output") or "").strip()
            parts = output.split(":", 3)
            results.append({
                "app": ae.app,
                "branch": parts[0] if len(parts) > 0 else "?",
                "ahead": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0,
                "dirty": int(parts[2]) if len(parts) > 2 and parts[2].strip().isdigit() else 0,
                "last_msg": parts[3].strip() if len(parts) > 3 else "",
            })
        except Exception:
            results.append({"app": ae.app, "branch": "?", "ahead": 0, "dirty": 0, "last_msg": ""})
    return results
```

**Step 2: Run tests — confirm all pass**

```bash
python3 -m unittest press.press.doctype.bench.test_bench_dev_git_status -v 2>&1 | tail -15
```

Expected: `Ran 9 tests ... OK`

**Step 3: Syntax check**

```bash
python3 -c "import ast; ast.parse(open('press/press/doctype/bench/bench_dev_overview.py').read()); print('OK')"
```

**Step 4: Commit**

```bash
git add press/press/doctype/bench/bench_dev_overview.py
git commit -m "feat(api): add get_app_git_status() — per-app branch/ahead/dirty via docker_execute"
```

---

## Task 3: Failing tests for `restart_bench_for_site()`

**Files:**
- Modify: `press/press/doctype/bench/test_bench_dev_actions.py` (append new class)

**Step 1: Append to test_bench_dev_actions.py**

```python
class TestRestartBenchForSite(unittest.TestCase):
    """Tests for restart_bench_for_site() in bench_dev_overview.py"""

    def setUp(self):
        self.mf = MagicMock()
        _bdo.frappe = self.mf

    def tearDown(self):
        _bdo.frappe = _frappe_stub

    def test_requires_system_manager(self):
        self.mf.get_doc.return_value = MagicMock()
        _bdo.restart_bench_for_site("bench-001")
        self.mf.only_for.assert_called_once_with("System Manager")

    def test_fetches_bench_by_name(self):
        bench = MagicMock()
        self.mf.get_doc.return_value = bench
        _bdo.restart_bench_for_site("bench-001")
        self.mf.get_doc.assert_called_with("Bench", "bench-001")

    def test_calls_restart_bench(self):
        bench = MagicMock()
        self.mf.get_doc.return_value = bench
        _bdo.restart_bench_for_site("bench-001")
        bench.restart_bench.assert_called_once()
```

**Step 2: Run — confirm 3 new tests FAIL**

```bash
python3 -m unittest press.press.doctype.bench.test_bench_dev_actions -v 2>&1 | tail -10
```

Expected: `AttributeError: ... has no attribute 'restart_bench_for_site'`

**Step 3: Commit**

```bash
git add press/press/doctype/bench/test_bench_dev_actions.py
git commit -m "test(tdd): failing tests for restart_bench_for_site()"
```

---

## Task 4: Implement `restart_bench_for_site()`

**Files:**
- Modify: `press/press/doctype/bench/bench_dev_overview.py`

**Step 1: Append after `get_app_git_status`**

```python
@frappe.whitelist()
def restart_bench_for_site(bench_name):
    """Restart bench supervisor processes via the bench doc method."""
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)
    bench.restart_bench()
```

**Step 2: Run tests — all pass**

```bash
python3 -m unittest press.press.doctype.bench.test_bench_dev_actions -v 2>&1 | tail -10
```

Expected: `Ran 18 tests ... OK`

**Step 3: Run all bench dev tests together**

```bash
python3 -m unittest \
  press.press.doctype.bench.test_bench_dev_overview \
  press.press.doctype.bench.test_bench_dev_panel \
  press.press.doctype.bench.test_bench_dev_actions \
  press.press.doctype.bench.test_bench_dev_git_status -v 2>&1 | tail -5
```

Expected: `Ran 51 tests ... OK`

**Step 4: Syntax check + commit**

```bash
python3 -c "import ast; ast.parse(open('press/press/doctype/bench/bench_dev_overview.py').read()); print('OK')"
git add press/press/doctype/bench/bench_dev_overview.py
git commit -m "feat(api): add restart_bench_for_site() standalone wrapper"
```

---

## Task 5: Rewrite SiteDevTab.vue

**Files:**
- Modify: `dashboard/src/components/SiteDevTab.vue`

**Full replacement** — matches prototype v2 layout:

```vue
<template>
  <div class="mx-auto max-w-4xl space-y-4 p-4">

    <!-- Status Cards -->
    <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">

      <!-- Developer Mode -->
      <div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-gray-500">Developer Mode</p>
          <div class="mt-1 flex items-center gap-1.5">
            <span :class="devModeOn ? 'bg-green-500' : 'bg-gray-300'" class="inline-block h-2 w-2 rounded-full"></span>
            <span class="text-sm font-medium">{{ devModeOn ? 'Enabled' : 'Disabled' }}</span>
          </div>
        </div>
        <Button class="mt-3 w-full" size="sm" :variant="devModeOn ? 'outline' : 'solid'"
          :loading="devModeLoading" @click="toggleDevMode">
          {{ devModeOn ? 'Disable Dev Mode' : 'Enable Dev Mode' }}
        </Button>
      </div>

      <!-- Scheduler -->
      <div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-gray-500">Scheduler</p>
          <div class="mt-1 flex items-center gap-1.5">
            <span :class="schedulerEnabled ? 'bg-green-500' : 'bg-yellow-400'" class="inline-block h-2 w-2 rounded-full"></span>
            <span class="text-sm font-medium">{{ statusLoading ? '…' : (schedulerEnabled ? 'Running' : 'Paused') }}</span>
          </div>
        </div>
        <p class="mt-3 text-xs text-gray-400">Read-only</p>
      </div>

      <!-- Migration -->
      <div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-gray-500">Migration</p>
          <p class="mt-1 text-sm font-medium">{{ statusLoading ? '…' : migrationLabel }}</p>
        </div>
        <Button class="mt-3 w-full" size="sm" variant="outline" :loading="migrateLoading" @click="triggerMigrate">
          Migrate Now
        </Button>
      </div>

      <!-- Cache -->
      <div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-gray-500">Cache</p>
          <p class="mt-1 text-sm text-gray-400">Clears Redis + assets</p>
        </div>
        <Button class="mt-3 w-full" size="sm" variant="outline" :loading="clearCacheLoading" @click="triggerClearCache">
          Clear Cache
        </Button>
      </div>

    </div>

    <!-- Quick Actions row -->
    <div class="flex flex-wrap gap-3">

      <!-- VS Code -->
      <a href="https://code.sandbox.mvpstorm.com" target="_blank"
        class="flex flex-1 items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-sm hover:border-blue-400 hover:text-blue-600 transition-colors min-w-[180px]">
        <svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
          <path d="M16.5 3L21 7.5 9 19.5 3 15l13.5-12z"/><path d="M12 7.5L16.5 12"/><path d="M3 15l4.5-4.5"/>
        </svg>
        <span>
          <span class="block text-sm font-semibold">Open VS Code</span>
          <span class="block text-xs text-gray-400">code.sandbox.mvpstorm.com</span>
        </span>
        <svg class="ml-auto h-3.5 w-3.5 text-gray-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
        </svg>
      </a>

      <!-- Restart Bench -->
      <button @click="restartBench"
        class="flex flex-1 items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-sm hover:border-orange-400 hover:text-orange-600 transition-colors min-w-[180px]"
        :class="{ 'opacity-60 cursor-not-allowed': restartLoading }">
        <svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
          <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
          <path d="M3 3v5h5"/>
        </svg>
        <span>
          <span class="block text-sm font-semibold">{{ restartLoading ? 'Restarting…' : 'Restart Bench' }}</span>
          <span class="block text-xs text-gray-400">Restart all bench workers</span>
        </span>
      </button>

    </div>

    <!-- App Git Status -->
    <div class="rounded-lg border border-gray-200 bg-white shadow-sm">
      <div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
        <div class="flex items-center gap-2">
          <p class="text-sm font-semibold">App Status</p>
          <span v-if="appsNeedingPush > 0"
            class="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700">
            {{ appsNeedingPush }} need push
          </span>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xs text-gray-400">{{ gitStatusAge }}</span>
          <Button size="sm" variant="ghost" :loading="gitStatusLoading" @click="loadGitStatus">Refresh</Button>
        </div>
      </div>

      <!-- Loading skeleton -->
      <div v-if="gitStatusLoading && !appGitStatus.length" class="space-y-2 p-4">
        <div v-for="i in 3" :key="i" class="h-9 animate-pulse rounded bg-gray-100"></div>
      </div>

      <!-- Empty -->
      <div v-else-if="!appGitStatus.length" class="p-4 text-center text-sm text-gray-400">
        No apps found or bench unavailable
      </div>

      <!-- Table -->
      <table v-else class="w-full text-sm">
        <thead class="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
          <tr>
            <th class="px-4 py-2 text-left">App</th>
            <th class="px-4 py-2 text-left">Branch</th>
            <th class="px-4 py-2 text-left">Status</th>
            <th class="px-4 py-2 text-left">Last Commit</th>
            <th class="px-4 py-2 text-right"></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="item in appGitStatus" :key="item.app">
            <tr :class="{ 'bg-blue-50': openPushApp === item.app }" class="border-b border-gray-50 last:border-0">
              <td class="px-4 py-2.5 font-medium">{{ item.app }}</td>
              <td class="px-4 py-2.5">
                <code class="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">{{ item.branch }}</code>
              </td>
              <td class="px-4 py-2.5">
                <div class="flex flex-wrap gap-1">
                  <span v-if="item.ahead > 0"
                    class="inline-flex items-center gap-1 rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-semibold text-yellow-700">
                    ↑ {{ item.ahead }} ahead
                  </span>
                  <span v-if="item.dirty > 0"
                    class="inline-flex items-center gap-1 rounded-full bg-orange-100 px-2 py-0.5 text-xs font-semibold text-orange-600">
                    ● {{ item.dirty }} dirty
                  </span>
                  <span v-if="item.ahead === 0 && item.dirty === 0"
                    class="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
                    ✓ Clean
                  </span>
                </div>
              </td>
              <td class="max-w-[180px] truncate px-4 py-2.5 text-xs text-gray-500">{{ item.last_msg }}</td>
              <td class="px-4 py-2.5 text-right">
                <Button v-if="item.ahead > 0 || item.dirty > 0" size="sm" variant="outline"
                  @click="togglePushRow(item.app)">
                  {{ openPushApp === item.app ? 'Cancel' : 'Push ↓' }}
                </Button>
              </td>
            </tr>
            <!-- Inline push form -->
            <tr v-if="openPushApp === item.app" :key="item.app + '-push'">
              <td colspan="5" class="border-b border-blue-100 bg-blue-50 px-4 py-3">
                <div class="flex items-end gap-2">
                  <div class="min-w-0 flex-1">
                    <label class="mb-1 block text-xs font-medium text-gray-600">Commit message</label>
                    <input v-model="pushMessages[item.app]" type="text" placeholder="WIP"
                      class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none" />
                  </div>
                  <Button size="sm" variant="solid" :loading="pushingApp === item.app" @click="doPush(item.app)">
                    Push to GitHub
                  </Button>
                </div>
                <pre v-if="pushOutputs[item.app]"
                  class="mt-2 whitespace-pre-wrap rounded bg-gray-900 p-2 text-xs leading-relaxed text-green-300">{{ pushOutputs[item.app] }}</pre>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <!-- Recent Errors -->
    <div class="rounded-lg border border-gray-200">
      <div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
        <p class="text-sm font-semibold">Recent Errors</p>
        <Button size="sm" variant="ghost" @click="loadErrors">Refresh</Button>
      </div>
      <div v-if="errorsLoading" class="p-4 text-center text-sm text-gray-400">Loading…</div>
      <div v-else-if="!errorList.length" class="p-4 text-center text-sm text-gray-400">No recent errors</div>
      <table v-else class="w-full text-sm">
        <thead class="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
          <tr>
            <th class="px-4 py-2 text-left">Time</th>
            <th class="px-4 py-2 text-left">Job Type</th>
            <th class="px-4 py-2 text-left"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="err in errorList" :key="err.name" class="border-b border-gray-50 last:border-0">
            <td class="px-4 py-2 text-gray-500">{{ relativeTime(err.creation) }}</td>
            <td class="px-4 py-2">{{ err.job_type }}</td>
            <td class="px-4 py-2">
              <a :href="`/dashboard/sites/${site}/jobs/${err.name}`" class="text-blue-600 hover:underline">View</a>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
</template>

<script>
import { call, getCachedDocumentResource } from 'frappe-ui';
import { toast } from 'vue-sonner';

export default {
  name: 'SiteDevTab',
  props: {
    site: { type: String, required: true },
  },
  data() {
    return {
      devModeLoading: false,
      migrateLoading: false,
      clearCacheLoading: false,
      restartLoading: false,
      statusLoading: false,
      errorsLoading: false,
      gitStatusLoading: false,
      schedulerEnabled: true,
      migrationData: null,
      errorList: [],
      appGitStatus: [],
      gitStatusAge: '',
      openPushApp: null,
      pushMessages: {},
      pushOutputs: {},
      pushingApp: null,
    };
  },
  computed: {
    $site() {
      return getCachedDocumentResource('Site', this.site);
    },
    devModeOn() {
      return !!this.$site?.doc?.is_development_site;
    },
    migrationLabel() {
      if (!this.migrationData?.last_run) return 'Never';
      return 'Last: ' + this.relativeTime(this.migrationData.last_run);
    },
    appsNeedingPush() {
      return this.appGitStatus.filter(a => a.ahead > 0 || a.dirty > 0).length;
    },
  },
  watch: {
    '$site.doc.bench': {
      immediate: true,
      handler(benchName) {
        if (benchName) this.loadGitStatus();
      },
    },
  },
  mounted() {
    this.loadStatus();
    this.loadErrors();
  },
  methods: {
    async loadStatus() {
      this.statusLoading = true;
      try {
        const [sched, migr] = await Promise.all([
          this.$site.getSchedulerStatus.submit(),
          this.$site.getMigrationStatus.submit(),
        ]);
        this.schedulerEnabled = sched?.enabled !== false;
        this.migrationData = migr;
      } catch (e) {
        // Fail silently
      } finally {
        this.statusLoading = false;
      }
    },
    async loadErrors() {
      this.errorsLoading = true;
      try {
        const res = await this.$site.getRecentErrors.submit({ limit: 10 });
        this.errorList = res?.errors || [];
      } catch (e) {
        this.errorList = [];
      } finally {
        this.errorsLoading = false;
      }
    },
    async loadGitStatus() {
      const benchName = this.$site?.doc?.bench;
      if (!benchName) return;
      this.gitStatusLoading = true;
      try {
        const result = await call(
          'press.press.doctype.bench.bench_dev_overview.get_app_git_status',
          { bench_name: benchName },
        );
        this.appGitStatus = Array.isArray(result) ? result : [];
        this.gitStatusAge = 'Updated just now';
        // Pre-fill push messages
        this.appGitStatus.forEach(a => {
          if (!this.pushMessages[a.app]) this.pushMessages[a.app] = 'WIP';
        });
      } catch (e) {
        this.appGitStatus = [];
      } finally {
        this.gitStatusLoading = false;
      }
    },
    togglePushRow(app) {
      this.openPushApp = this.openPushApp === app ? null : app;
      this.pushOutputs = { ...this.pushOutputs, [app]: '' };
    },
    async toggleDevMode() {
      const enabling = !this.devModeOn;
      this.devModeLoading = true;
      try {
        await this.$site.setDevelopmentMode.submit({ enable: enabling ? 1 : 0 });
        toast.success(enabling ? 'Developer mode enabled' : 'Developer mode disabled');
        this.$site.reload();
      } catch (e) {
        toast.error(e?.messages?.join(', ') || 'Failed');
      } finally {
        this.devModeLoading = false;
      }
    },
    async triggerMigrate() {
      this.migrateLoading = true;
      try {
        await this.$site.migrate.submit();
        toast.success('Migration started');
        this.loadStatus();
      } catch (e) {
        toast.error(e?.messages?.join(', ') || 'Failed to start migration');
      } finally {
        this.migrateLoading = false;
      }
    },
    async triggerClearCache() {
      this.clearCacheLoading = true;
      try {
        await this.$site.clearSiteCache.submit();
        toast.success('Cache cleared');
      } catch (e) {
        toast.error(e?.messages?.join(', ') || 'Failed to clear cache');
      } finally {
        this.clearCacheLoading = false;
      }
    },
    async restartBench() {
      const benchName = this.$site?.doc?.bench;
      if (!benchName || this.restartLoading) return;
      this.restartLoading = true;
      try {
        await call(
          'press.press.doctype.bench.bench_dev_overview.restart_bench_for_site',
          { bench_name: benchName },
        );
        toast.success('Bench restarted');
      } catch (e) {
        toast.error(e?.messages?.join(', ') || 'Failed to restart bench');
      } finally {
        this.restartLoading = false;
      }
    },
    async doPush(app) {
      const benchName = this.$site?.doc?.bench;
      if (!benchName) return;
      this.pushingApp = app;
      this.pushOutputs = { ...this.pushOutputs, [app]: '' };
      try {
        const result = await call(
          'press.press.doctype.bench.bench_dev_overview.push_app_to_github',
          { bench_name: benchName, app, message: this.pushMessages[app] || 'WIP' },
        );
        this.pushOutputs = { ...this.pushOutputs, [app]: result?.output || 'Done' };
        toast.success('Pushed to GitHub');
        this.loadGitStatus();
      } catch (e) {
        toast.error(e?.messages?.join(', ') || 'Push failed');
      } finally {
        this.pushingApp = null;
      }
    },
    relativeTime(ts) {
      if (!ts) return '';
      const diffMin = Math.floor((new Date() - new Date(ts)) / 60000);
      if (diffMin < 1) return 'just now';
      if (diffMin < 60) return `${diffMin}m ago`;
      const h = Math.floor(diffMin / 60);
      return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`;
    },
  },
};
</script>
```

**Step: Verify no lint errors (check imports are correct)**

```bash
grep -n "import" dashboard/src/components/SiteDevTab.vue
```

Expected: only `frappe-ui` and `vue-sonner` imports.

**Step: Commit**

```bash
git add dashboard/src/components/SiteDevTab.vue
git commit -m "feat(ui): Site Dev Tab v2 — app git status table, per-app push, VS Code, restart bench"
```

---

## Task 6: Deploy to press-ctrl

**Step 1: Create bundle and SCP**

```bash
cd /home/eslam/data/erpnext-app-repos/press_local
git bundle create /tmp/press-devtab-v2.bundle HEAD~4..HEAD
scp /tmp/press-devtab-v2.bundle press-ctrl:/tmp/
```

**Step 2: Apply on press-ctrl**

```bash
ssh press-ctrl "cd /home/frappe/frappe-bench/apps/press && \
  git fetch /tmp/press-devtab-v2.bundle HEAD:refs/remotes/bundle/devtab-v2 && \
  git merge --ff-only refs/remotes/bundle/devtab-v2 && echo MERGE_OK"
```

**Step 3: Build + restart**

```bash
ssh press-ctrl "sudo -u frappe bash -c 'cd /home/frappe/frappe-bench && \
  bench build --app press 2>&1 | tail -3 && \
  bench --site demo.mvpstorm.com clear-cache && echo CACHE_CLEARED'"
ssh press-ctrl "supervisorctl restart frappe-bench-web:frappe-bench-frappe-web && \
  sleep 2 && supervisorctl status frappe-bench-web:frappe-bench-frappe-web"
```

---

## Task 7: Prototype match checklist

After implementation produce a table comparing every visible element in the prototype vs the live implementation.
