# Press Fork Dev Log

## Working State
**Session:** Dev Actions Redesign | **Date:** 2026-04-26

### Active Task
Restructure Release Group Dev Actions panel: per-bench section, Code Server KV panel, 4 action tiles, fix password copy bug, add "Open in VS Code" Remote-SSH flow.
- [x] Plan + approved HTML prototype (`docs/prototypes/dev-actions-redesign.html`)
- [x] Backend: `get_vscode_remote_url` whitelisted method (16 tests pass)
- [x] Frontend: `VSCodeLaunchDialog.vue` (222 lines, reuses SSH cert API)
- [x] Frontend: restructure `ReleaseGroupActions.vue` (per-bench section + KV panel + 4 tiles)
- [x] Wiki: `press/docs/wiki/04-bench-management/dev-actions.md`
- [ ] User: build dashboard + smoke test on demo.mvpstorm.com (Task 5)
- [ ] User: deploy via `bench build --app press --force` + supervisorctl restart

### Key Files (current shape)
**`dashboard/src/components/group/ReleaseGroupActions.vue`** (REWRITTEN, 521 lines)
Per-bench section with bench identity, status pill (Running/Pending/Stopped), full-width Code Server KV panel (URL + masked-with-eye-toggle Password + meta footer), and 4-tile action grid (Open in VS Code, Mark as Dev Bench, Generate SSH Cert, Restart Bench). Removed old fixture-driven bottom block (was the "Open Code Server" duplication source). 16 reactive methods. `Promise.allSettled` for parallel status fetch.

**`dashboard/src/components/group/VSCodeLaunchDialog.vue`** (NEW, 222 lines)
Sibling to SSHCertificateDialog. Same SSH cert generation flow + final "Launch VS Code" step that fires `vscode://vscode-remote/ssh-remote+<bench>@<proxy>:2222/home/frappe/frappe-bench`. Reuses `releaseGroup.generateCertificate` and `getCertificate` resources. Surfaces URL-fetch errors via `<ErrorMessage>`. Disabled-key safeguards mirror SSHCertificateDialog. Async-imported in parent (`defineAsyncComponent`).

**`press/press/doctype/bench/bench_dev_overview.py`** (MODIFIED, +24 lines)
New `get_vscode_remote_url(bench_name)` whitelisted method. Validates bench name as slug (`r"[a-zA-Z0-9_.-]+"`) before URI composition. Reads `proxy_server` from the bench's `Server` doctype (NOT bench/release-group — those fields don't exist; verified). Calls `_ensure_team_access` for consistency with sibling functions.

**`press/press/doctype/bench/test_bench_dev_overview.py`** (MODIFIED, +5 tests, 16 total)
3 happy/sad-path tests for `get_vscode_remote_url` + 1 URI-injection test (bench name with `@` rejected before proxy lookup). Uses the file's existing mocked-frappe scaffold. `_bypass_team_access` helper added since `_ensure_team_access` imports `press.utils.get_current_team` which doesn't load through the mock stub.

**`press/docs/wiki/04-bench-management/dev-actions.md`** (NEW, 53 lines)
User-facing wiki page documenting the panel, password-copy UX, "Open in VS Code" first-time setup, troubleshooting.

### Decisions
- **One dialog per concern**: VSCodeLaunchDialog is a sibling of SSHCertificateDialog (not an extension). Reuses the same backend cert API. Drift comment added: "Mirrors SSHCertificateDialog.loadSshKeys — keep these two in sync."
- **Async import for VSCodeLaunchDialog**: only loaded when user clicks the tile. SSHCertificateDialog stays static (already used elsewhere).
- **`Server.proxy_server` not `Bench.proxy_server`**: plan was wrong, neither Bench nor Release Group has that field. Pattern matches `bench.py:189, 657, 663`.
- **Port 2222 hardcoded**: SSH proxy port (cert-based access, matches SSHCertificateDialog). Distinct from `22000+offset` admin port for direct bench-server SSH.
- **Confirm dialogs**: replaced native `confirm()` in `rotateCodeServerPassword` with `confirmDialog` from utils — `confirm()` is silently blocked in cross-origin iframes / sandboxed contexts.
- **Parallel status fetch**: `loadCodeServerStatuses` uses `Promise.allSettled` so N benches don't serialise.

### Next Steps
1. User: deploy and smoke-test the panel (per-bench rendering, eye toggle reveals password, copy button copies actual password not the dots, all 4 tiles fire correctly, "Open in VS Code" launches local VS Code Desktop).
2. (Tech debt) Extract `<CodeServerPanel>` sibling component to bring `ReleaseGroupActions.vue` back under the 500-line soft limit (currently 521).
3. (Tech debt) Other test files in `press/press/doctype/bench/` are broken on the same `_ensure_team_access` import path — pre-existing scaffold issue, not in scope.

### Watch Out
- `ClickToCopyField` is NOT globally registered (only `dashboard/src/components/global/*.vue` is auto-globbed by `register.js`). Components using it MUST `import ClickToCopyField from '../ClickToCopyField.vue'`. The reference `SSHCertificateDialog.vue` lacks this import — latent bug that hasn't surfaced.
- `vscode://` URI launches require VS Code Desktop installed locally. Browsers prompt the first time. Wiki documents the copy-URL fallback.
- `bench.proxy_server` and `release_group.proxy_server` do NOT exist. Use `Server.proxy_server` via `frappe.db.get_value("Server", bench.server, "proxy_server")`.

---

## Session Archive

### Session 2026-04-26: Dev Actions redesign
**What we did:** Restructured Release Group Actions panel into per-bench sections with a Code Server KV panel and 4 action tiles (Open in VS Code, Mark Dev Bench, Generate SSH Cert, Restart Bench). Fixed password copy bug — explicit eye-toggle and copy icon buttons replaced the broken `'•••••••••• copy password'` clickable label. Added "Open in VS Code" flow that mints SSH cert and fires `vscode://` Remote-SSH URI to launch local VS Code Desktop. Removed the standalone "Bench Actions" block (was the source of the "Open Code Server" duplication). 9 commits on `feat/dev-actions-redesign` off `cloudflare-dns`. Two-stage code review per task (spec compliance + code quality) — all approved. 16 backend tests pass.
**Files:** `ReleaseGroupActions.vue` (521 lines), `VSCodeLaunchDialog.vue` (NEW, 222), `bench_dev_overview.py` (+24), `test_bench_dev_overview.py` (+5 tests), `04-bench-management/dev-actions.md` (NEW), prototype + plan docs.
**Decisions:** Sibling dialog over extension; `Server.proxy_server` not bench/release-group; async import for VS Code dialog; `confirmDialog` over native `confirm()`; `Promise.allSettled` for parallel status fetch.

### Session 2026-04-03: Deploy Page + Create App + Dev Tab + Infrastructure
**What we did:** Fixed deploy page blank screen, added 7 UX enhancements (auto-refresh, stage groups, colored badges, progress bar, failure banner, retry buttons, duration comparison). Built Create New App feature. Built Dev tab local app creation + Push to GitHub. Fixed press-f1 disk full (100% → 39%, expanded 75G → 150G). Cleaned roseline_app git repo.
**Files:** DeployCandidate.vue, build_diagnostics.py, create_app.py, CreateAppDialog.vue, SiteDevTab.vue, bench_app_management.py, bench_dev_overview.py
**Decisions:** Sibling files for APIs, git -C instead of cd in docker_execute, daily cleanup cron

## Mistakes & Lessons
### 2026-04-03 - bash -c wrapping broke shell variables
**What happened:** Wrapped docker_execute commands in `bash -c '...'` to fix OCI error
**Root cause:** The agent already uses sh -c, so nesting quotes broke variable expansion
**How we fixed it:** Reverted to individual `git -C` commands per app
**Lesson:** docker_execute subshells expand on HOST. Use git -C, never cd + subshells.

### 2026-04-03 - rg.add_app() silently failed
**What happened:** Created app registered in Press but never appeared in bench
**Root cause:** `add_app()` expects `{name, title, repository_url}` but got `{app, source}`
**How we fixed it:** Passed correct keys matching the Release Group's add_app signature
**Lesson:** Press API contracts aren't always obvious — test the actual method before assuming.

### 2026-04-03 - Deploy page blank screen
**What happened:** Deploy page showed blank white screen for any build
**Root cause:** frappe-ui document resource has `.get.loading` not `.loading`. `v-if="deploy"` showed nothing when doc was null.
**How we fixed it:** Added loading state, error state, and optional chaining throughout
**Lesson:** Always add loading + error UI states. Never trust that a resource loads.
