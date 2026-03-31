# Site Dev Tab Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand `SiteDevTab.vue` with 4 status-action cards, a Push to GitHub dialog, and a recent errors table. Add the `push_app_to_github` backend method with full TDD.

**Architecture:** New whitelisted method in `bench_dev_overview.py` uses `bench.docker_execute()` to run git commands inside the bench container. Vue component uses three `createResource` calls for scheduler status, migration status, and recent errors, all `auto: true` on mount.

**Design doc:** `docs/plans/2026-04-01-site-dev-tab-design.md`

---

## Task 1: Backend — `push_app_to_github`

**Files:**
- Modify: `press/press/doctype/bench/bench_dev_overview.py`
- Modify: `press/press/doctype/bench/test_bench_dev_overview.py`

### Step 1: Write the failing tests

Add a new test class `TestPushAppToGithub` to the bottom of `test_bench_dev_overview.py`:

```python
class TestPushAppToGithub(unittest.TestCase):
    """Tests for push_app_to_github() in bench_dev_overview.py"""

    def setUp(self):
        self.mf = MagicMock()
        _bdo.frappe = self.mf
        self.mf.session.user = "admin@example.com"

    def _bench_with_apps(self, apps):
        """Return a mock bench doc with given app names."""
        bench = MagicMock()
        bench.name = "bench-0001"
        bench.status = "Active"
        bench.docker_execute.return_value = {
            "status": "Success",
            "output": "Everything up-to-date",
            "returncode": 0,
        }
        return bench

    def test_requires_system_manager(self):
        """push_app_to_github must call frappe.only_for('System Manager')."""
        self.mf.get_doc.return_value = self._bench_with_apps(["frappe"])
        _bdo.push_app_to_github("bench-0001", "frappe", "WIP")
        self.mf.only_for.assert_called_once_with("System Manager")

    def test_calls_docker_execute_with_git_commands(self):
        """docker_execute must be called with the composed git command."""
        bench = self._bench_with_apps(["frappe"])
        self.mf.get_doc.return_value = bench
        _bdo.push_app_to_github("bench-0001", "frappe", "WIP")
        bench.docker_execute.assert_called_once()
        cmd_arg = bench.docker_execute.call_args[0][0]
        assert "git add -A" in cmd_arg
        assert "git commit" in cmd_arg
        assert "git push" in cmd_arg

    def test_passes_app_as_subdir(self):
        """subdir must be 'apps/<app>' so git runs in the right directory."""
        bench = self._bench_with_apps(["erpnext"])
        self.mf.get_doc.return_value = bench
        _bdo.push_app_to_github("bench-0001", "erpnext", "fix")
        kwargs = bench.docker_execute.call_args[1]
        assert kwargs.get("subdir") == "apps/erpnext"

    def test_message_included_in_commit(self):
        """Commit message must appear in the git commit command."""
        bench = self._bench_with_apps(["frappe"])
        self.mf.get_doc.return_value = bench
        _bdo.push_app_to_github("bench-0001", "frappe", "my feature")
        cmd_arg = bench.docker_execute.call_args[0][0]
        assert "my feature" in cmd_arg

    def test_returns_execute_result(self):
        """Must return the ExecuteResult dict from docker_execute."""
        bench = self._bench_with_apps(["frappe"])
        self.mf.get_doc.return_value = bench
        result = _bdo.push_app_to_github("bench-0001", "frappe", "WIP")
        assert result["status"] == "Success"
        assert result["returncode"] == 0

    def test_fetches_bench_by_name(self):
        """frappe.get_doc must be called with ('Bench', bench_name)."""
        bench = self._bench_with_apps(["frappe"])
        self.mf.get_doc.return_value = bench
        _bdo.push_app_to_github("bench-0001", "frappe", "WIP")
        self.mf.get_doc.assert_called_with("Bench", "bench-0001")
```

### Step 2: Run tests to verify they fail

```bash
cd /home/eslam/data/erpnext-app-repos/press_local
python -m pytest press/press/doctype/bench/test_bench_dev_overview.py::TestPushAppToGithub -v 2>&1 | head -40
```

Expected: `AttributeError: module 'press.press.doctype.bench.bench_dev_overview' has no attribute 'push_app_to_github'`

### Step 3: Implement `push_app_to_github` in bench_dev_overview.py

Add after the `get_dev_panel_data` function:

```python
@frappe.whitelist()
def push_app_to_github(bench_name, app, message):
    """
    Run git add -A && git commit -m <message> && git push inside the bench container
    for the given app. Uses bench.docker_execute() — requires the bench to be Active
    and the container to have SSH keys configured for GitHub.
    """
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)
    # Escape single quotes in message to prevent shell injection
    safe_message = message.replace("'", "'\\''")
    cmd = f"git add -A && git commit -m '{safe_message}' && git push"
    return bench.docker_execute(cmd, subdir=f"apps/{app}")
```

### Step 4: Run tests to verify they pass

```bash
python -m pytest press/press/doctype/bench/test_bench_dev_overview.py::TestPushAppToGithub -v 2>&1 | head -40
```

Expected: 6 tests PASSED.

### Step 5: Run full test file to ensure no regressions

```bash
python -m pytest press/press/doctype/bench/test_bench_dev_overview.py -v 2>&1 | tail -20
```

Expected: All tests pass.

### Step 6: Syntax check

```bash
python3 -c "import ast; ast.parse(open('press/press/doctype/bench/bench_dev_overview.py').read()); print('OK')"
```

### Step 7: Commit

```bash
cd /home/eslam/data/erpnext-app-repos/press_local
git add press/press/doctype/bench/bench_dev_overview.py \
        press/press/doctype/bench/test_bench_dev_overview.py \
        docs/plans/
git commit -m "feat(dev-tab): add push_app_to_github backend method + tests"
```

---

## Task 2: Frontend — SiteDevTab.vue full rewrite

**Files:**
- Modify: `dashboard/src/components/SiteDevTab.vue` (full rewrite)

This is a UI component — no frontend test framework is set up in press, so no TDD here.

### Step 1: Read the current file

Read `dashboard/src/components/SiteDevTab.vue` to confirm current state (100 lines, minimal dev mode only).

### Step 2: Write the new SiteDevTab.vue

Full rewrite. Key structure:
- Options API (matches existing codebase style — see `ReleaseGroupActions.vue`)
- Three `createResource` calls: `schedulerStatus`, `migrationStatus`, `recentErrors`
- Four cards in a responsive grid
- Push to GitHub button that opens an inline dialog (no extra component file)
- Errors table at the bottom

```vue
<template>
  <div class="mx-auto max-w-4xl space-y-4 p-4">

    <!-- Status-Action Cards -->
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
        <Button
          class="mt-3 w-full"
          size="sm"
          :variant="devModeOn ? 'outline' : 'solid'"
          :loading="devModeLoading"
          @click="toggleDevMode"
        >
          {{ devModeOn ? 'Disable Dev Mode' : 'Enable Dev Mode' }}
        </Button>
      </div>

      <!-- Scheduler -->
      <div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-gray-500">Scheduler</p>
          <div class="mt-1 flex items-center gap-1.5">
            <span
              :class="schedulerRunning ? 'bg-green-500' : 'bg-yellow-400'"
              class="inline-block h-2 w-2 rounded-full"
            ></span>
            <span class="text-sm font-medium">
              {{ schedulerStatus.loading ? '…' : (schedulerRunning ? 'Running' : 'Paused') }}
            </span>
          </div>
        </div>
        <p class="mt-3 text-xs text-gray-400">Read-only</p>
      </div>

      <!-- Migration -->
      <div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-gray-500">Migration</p>
          <p class="mt-1 text-sm font-medium">
            {{ migrationStatus.loading ? '…' : (migrationLabel || 'Never') }}
          </p>
        </div>
        <Button
          class="mt-3 w-full"
          size="sm"
          variant="outline"
          :loading="migrateLoading"
          @click="triggerMigrate"
        >
          Migrate Now
        </Button>
      </div>

      <!-- Cache -->
      <div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-gray-500">Cache</p>
          <p class="mt-1 text-sm text-gray-400">—</p>
        </div>
        <Button
          class="mt-3 w-full"
          size="sm"
          variant="outline"
          :loading="clearCacheLoading"
          @click="triggerClearCache"
        >
          Clear Cache
        </Button>
      </div>

    </div>

    <!-- Push to GitHub -->
    <div class="rounded-lg border border-gray-200 p-4">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm font-medium">Push to GitHub</p>
          <p class="text-xs text-gray-500 mt-0.5">Commit and push uncommitted changes in a bench app to GitHub</p>
        </div>
        <Button size="sm" variant="outline" @click="showPushDialog = true">
          Push to GitHub
        </Button>
      </div>

      <!-- Inline push dialog -->
      <div v-if="showPushDialog" class="mt-4 space-y-3 rounded-lg bg-gray-50 p-4">
        <div>
          <label class="mb-1 block text-xs font-medium text-gray-700">App</label>
          <select
            v-model="pushApp"
            class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          >
            <option value="">— Select app —</option>
            <option v-for="app in benchApps" :key="app" :value="app">{{ app }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-gray-700">Commit message</label>
          <input
            v-model="pushMessage"
            type="text"
            class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
            placeholder="WIP"
          />
        </div>
        <div class="flex gap-2">
          <Button size="sm" variant="solid" :loading="pushLoading" :disabled="!pushApp" @click="doPush">
            Push
          </Button>
          <Button size="sm" variant="ghost" @click="showPushDialog = false">Cancel</Button>
        </div>
        <pre v-if="pushOutput" class="mt-2 rounded bg-gray-100 p-2 text-xs text-gray-700 whitespace-pre-wrap">{{ pushOutput }}</pre>
      </div>
    </div>

    <!-- Recent Errors -->
    <div class="rounded-lg border border-gray-200">
      <div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
        <p class="text-sm font-semibold">Recent Errors</p>
        <Button size="sm" variant="ghost" @click="recentErrors.reload()">Refresh</Button>
      </div>
      <div v-if="recentErrors.loading" class="p-4 text-center text-sm text-gray-400">Loading…</div>
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
              <a
                :href="`/dashboard/sites/${site}/jobs/${err.name}`"
                class="text-blue-600 hover:underline"
              >View</a>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
</template>

<script>
import { call, createResource, getCachedDocumentResource } from 'frappe-ui';
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
      showPushDialog: false,
      pushApp: '',
      pushMessage: 'WIP',
      pushLoading: false,
      pushOutput: '',
      schedulerStatus: createResource({
        url: 'press.api.site.get_scheduler_status',
        params: { name: this.site },
        auto: true,
      }),
      migrationStatus: createResource({
        url: 'press.api.site.get_migration_status',
        params: { name: this.site },
        auto: true,
      }),
      recentErrors: createResource({
        url: 'press.api.site.get_recent_errors',
        params: { name: this.site },
        auto: true,
      }),
      benchAppsResource: createResource({
        url: 'frappe.client.get_list',
        params: {
          doctype: 'Bench App',
          filters: [['parent', '=', this.benchName]],
          fields: ['app'],
          limit: 50,
        },
        auto: false,
      }),
    };
  },
  computed: {
    $site() {
      return getCachedDocumentResource('Site', this.site);
    },
    benchName() {
      return this.$site?.doc?.bench || '';
    },
    devModeOn() {
      return !!this.$site?.doc?.is_development_site;
    },
    schedulerRunning() {
      const status = this.schedulerStatus.data;
      if (!status) return true;
      return status.status === 'Active';
    },
    migrationLabel() {
      const data = this.migrationStatus.data;
      if (!data || !data.last_migrate) return '';
      return this.relativeTime(data.last_migrate);
    },
    errorList() {
      return this.recentErrors.data || [];
    },
    benchApps() {
      const res = this.benchAppsResource.data;
      if (!res) return [];
      return res.map(r => r.app);
    },
  },
  watch: {
    benchName(val) {
      if (val) {
        this.benchAppsResource.params = {
          doctype: 'Bench App',
          filters: [['parent', '=', val]],
          fields: ['app'],
          limit: 50,
        };
        this.benchAppsResource.reload();
      }
    },
  },
  methods: {
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
        await call('press.api.site.migrate', { name: this.site });
        toast.success('Migration started');
        this.migrationStatus.reload();
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
    async doPush() {
      if (!this.pushApp) return;
      this.pushLoading = true;
      this.pushOutput = '';
      try {
        const result = await call(
          'press.press.doctype.bench.bench_dev_overview.push_app_to_github',
          {
            bench_name: this.benchName,
            app: this.pushApp,
            message: this.pushMessage || 'WIP',
          },
        );
        this.pushOutput = result?.output || 'Done';
        toast.success('Pushed to GitHub');
        this.recentErrors.reload();
      } catch (e) {
        toast.error(e?.messages?.join(', ') || 'Push failed');
      } finally {
        this.pushLoading = false;
      }
    },
    relativeTime(ts) {
      if (!ts) return '';
      const now = new Date();
      const then = new Date(ts);
      const diffMs = now - then;
      const diffMin = Math.floor(diffMs / 60000);
      if (diffMin < 1) return 'just now';
      if (diffMin < 60) return `${diffMin}m ago`;
      const diffH = Math.floor(diffMin / 60);
      if (diffH < 24) return `${diffH}h ago`;
      return `${Math.floor(diffH / 24)}d ago`;
    },
  },
};
</script>
```

### Step 3: Verify no import errors

```bash
cd /home/eslam/data/erpnext-app-repos/press_local
node --input-type=module < /dev/null 2>&1 || true
# Check that the dashboard build doesn't fail:
grep -n "from 'frappe-ui'" dashboard/src/components/SiteDevTab.vue
grep -n "import" dashboard/src/components/SiteDevTab.vue
```

Expected: `call`, `createResource`, `getCachedDocumentResource` all imported from `frappe-ui`. `toast` from `vue-sonner`.

### Step 4: Verify `get_recent_errors` API signature

Check that `press.api.site.get_recent_errors` accepts `name` as param:

```bash
grep -n "def get_recent_errors\|def get_scheduler_status\|def get_migration_status" \
  /home/eslam/data/erpnext-app-repos/press_local/press/api/site.py | head -10
```

If any method name or param is different, adjust the `createResource` URLs/params accordingly before committing.

### Step 5: Commit

```bash
cd /home/eslam/data/erpnext-app-repos/press_local
git add dashboard/src/components/SiteDevTab.vue
git commit -m "feat(dev-tab): rewrite SiteDevTab.vue with status cards + push to GitHub + errors table"
```

---

## Task 3: Deploy to press-ctrl

### Step 1: Syntax-check Python

```bash
python3 -c "
import ast
ast.parse(open('press/press/doctype/bench/bench_dev_overview.py').read())
print('Python OK')
"
```

### Step 2: Build and deploy

```bash
# On press-ctrl — standard deploy pipeline
sudo -u frappe bash -c 'cd /home/frappe/frappe-bench && bench build --app press && bench --site demo.mvpstorm.com clear-cache'
supervisorctl restart frappe-bench-web:frappe-bench-frappe-web
```

See CLAUDE.md deploy commands for the full SCP → fetch → merge → build pipeline.

### Step 3: Smoke test in browser

Open: `https://demo.mvpstorm.com/dashboard/sites/<any-active-site>/dev`

Check:
- [ ] 4 cards render with correct status badges
- [ ] Dev Mode button toggles correctly
- [ ] Migrate Now triggers migration toast
- [ ] Clear Cache triggers toast
- [ ] "Push to GitHub" reveals inline dialog
- [ ] App dropdown populates from bench apps
- [ ] Push triggers toast (success or error depending on SSH key availability)
- [ ] Recent Errors table shows last 10 failures (or "No recent errors")

---

## Notes

- **`docker_execute` requires Active bench**: If bench is Pending/Archived, it throws. The Push button is inside the Dev tab which only shows when site status !== 'Archived', but the bench could still be non-Active. The backend already guards: `if self.status not in ["Active", "Broken"]: raise Exception(...)`.
- **SSH keys for push**: The bench container must have SSH keys configured to push to GitHub. This is environment-specific — the button will return an error if keys aren't set up. The output is shown in the UI so the user sees the git error.
- **Migration status API**: If `get_migration_status` returns a different shape than expected (e.g., `last_migrate` field name), adjust `migrationLabel` computed property accordingly after checking the actual API response.
