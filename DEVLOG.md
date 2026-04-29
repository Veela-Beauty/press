# Press Fork Dev Log

## Working State
**Session:** Bench-watch polish + Site Overview usage panels + Log Server (ES) end-to-end | **Date:** 2026-04-29

### Active Task
Make the dashboard usage panels show real numbers AND polish the bench-watch
panel that landed in the previous session. Then deploy ElasticSearch + Filebeat
end-to-end so Compute hours shows real CPU time.

- [x] DevFlowsGuide 3-tab guide on Site Dev + Bench Actions tabs
- [x] bench-git-setup auto-rewrite SSH→HTTPS
- [x] BenchWatchStatus panel: lifecycle + visibility-pause + UX intro
- [x] dashboard_fields whitelist: added `is_development_bench`, `current_*_usage`
- [x] bench_dev_watch.py: extracted `ensure_team_access` (DRY across 3 files), flock for race, get_value over get_doc
- [x] Tests: 33 unit tests added, all green
- [x] Ghost-pending site recovery scheduler (recover_ghost_pending_sites)
- [x] Log Server: ES + Kibana + nginx HTTPS deployed on press-ctrl
- [x] Filebeat on press-f1 reconfigured + monitor/nginx ingest pipelines installed
- [x] Compute panel verified: tradeingdemov15 shows 0.00082 hours (real CPU time)
- [x] Both guide cards unified styling (rounded, shadow, font-semibold)
- [x] sales_force_server_app cleaned (removed Windows-built node_modules-backup, 619 files)
- [ ] Bench-side filebeat: older Frappe sites don't emit `request.counter` — needs Frappe upgrade for compute tracking

### Key Files (current shape)
**`press/utils/__init__.py`** (MODIFIED, +27 lines) — `ensure_team_access(bench_name, site_name)` extracted from 3 duplicate copies; both args supported for back-compat.

**`press/press/doctype/bench/bench_dev_watch.py`** (NEW since 2719f44, ~165 lines) — start_watch / stop_watch / get_watch_status / restart_watch. flock-protected spawn, get_value gate, runs `bench watch` inside the bench Docker container.

**`dashboard/src/components/BenchWatchStatus.vue`** (NEW, 176 lines) — self-contained polling panel. Visibility-aware (pauses on hidden tab). Clears `setInterval` permanently when bench is non-dev. UX intro line. Mounted on Site Dev + Bench Actions tabs.

**`dashboard/src/components/DevFlowsGuide.vue`** (NEW since dbbf97e, 232 lines) — 3-tab guide with surface-aware intros (`surface=site` vs `surface=bench`).

**`docs/runbook/log-server.md`** (NEW, 200+ lines) — Operations manual for the ES + Kibana + Filebeat stack on press-ctrl. Includes 5 setup gotchas discovered during install.

**`/opt/log-server/`** on press-ctrl (NEW infra) — Docker Compose stack with ES 7.17.20 + Kibana 7.17.20. Nginx vhost at `logs.sandbox.mvpstorm.com` with HTTP Basic auth. Press queries via `https://logs.sandbox.mvpstorm.com/elasticsearch/filebeat-*/_search`.

### Decisions
- **No new VM for Log Server** — user vetoed Press's Ansible-based dedicated-server log_server. Deployed ES + Kibana as Docker Compose on press-ctrl instead. Saves ~€7/mo, fits 30G RAM headroom on press-ctrl.
- **Skip Press's ILM template setup** — Filebeat's PUT-to-date-math URLs hit nginx 405. `setup.ilm.enabled: false` + `setup.template.enabled: false` is the simpler workaround. Indices roll daily by suffix (`filebeat-7.17.29-YYYY.MM.DD`); manual cleanup cron later.
- **Two cards unified style** — rounded card chrome with shadow at the same hierarchy level inside the parent Dev Actions card.
- **Don't unmark user's bench-0011-000110 from Dev** — bench-watch keeps running, harmless to user, easy to undo.
- **Bundle-relay push pattern** — every commit goes through Hetzner's `elgogary` GitHub key via git bundle (press-ctrl deploy keys are read-only).

### Next Steps
1. (Tech debt) Bench-side filebeat: log shipping works for newer Frappe (request.counter present); older Frappe sites stay 0. Either upgrade Frappe per-site OR modify Press analytics to fall back to nginx.access.duration field.
2. (Tech debt) Storage / Database panels: depend on `tabSite Usage` populated by `update_disk_usages` scheduler. Should naturally fill within 1 hour of next 15/45 tick now that sites are Active.
3. (Tech debt) Add weekly cron to delete filebeat indices >90d old (no ILM = manual cleanup).
4. (Tech debt) Watch process on dev benches doesn't survive container restart — supervisord-managed program is the proper fix; UI Restart button is the workaround.

### Watch Out
- Press's `dashboard_fields` whitelist on each Doctype is a silent failure mode — fields not in the tuple are filtered from API responses. This bit us 3 times in this session: `is_development_bench` on Bench, `current_*_usage` on Site, and (likely) others on other doctypes. Always check this when a UI panel inexplicably shows 0/null/false.
- Press's `get_current_cpu_usage` catches all exceptions and returns 0. If your ES auth/URL is wrong, you get 0 with NO error visible to the user. Always verify with raw curl first.
- `frappe.utils.password.get_decrypted_password` decrypts whatever's stored. If the doc was inserted with a different password than what nginx expects, drift is silent. Cross-check the prefix.

---
---

## Session Archive

### Session 2026-04-29: Bench-watch polish + Log Server end-to-end
**What we did:** Shipped 22 commits across 3 areas. Fixed dashboard_fields whitelist class of bug on Bench + Site (3 missing fields). Built BenchWatchStatus polling panel + DevFlowsGuide 3-tab guide. Patched bench-git-setup to auto-rewrite SSH origin → HTTPS. Cleaned sales_force_server_app's Windows-built node_modules-backup. Wrote ghost-pending site recovery scheduler. Stood up ElasticSearch + Kibana + Filebeat on press-ctrl: tradeingdemov15.sandbox.mvpstorm.com Compute panel now shows real 0.00082 hours from indexed Frappe request logs. Unified the two guide cards' styling. Added 33 unit tests across 4 modules. Wrote runbook for log-server ops + 5 setup gotchas.
**Files:** bench_dev_watch.py + tests, BenchWatchStatus.vue, DevFlowsGuide.vue, ReleaseGroupActions.vue, SiteDevTab.vue, ensure_team_access in press.utils, recover_ghost_pending_sites in site.py, /opt/log-server/ Docker stack on press-ctrl, /etc/filebeat/filebeat.yml on press-f1, Log Server doctype record + Press Settings.log_server, docs/runbook/log-server.md, docs/plans/{2026-04-29-press-watch-polish.md, 2026-04-29-press-log-server-setup.md}
**Decisions:** Self-host ES on press-ctrl (no new VM); ILM disabled (workaround for nginx 405); both guide cards now rounded; bench-watch lives only in tmpfs (no supervisord yet); Frappe-version skew on `request.counter` is documented not patched.

### Session 2026-04-26: Dev Actions synthesis (merge of two parallel implementations)

### Active Task
Synthesize merged Dev Actions panel: take ours's UI shell + theirs's working Code Server backend + theirs's RG actions card. User decisions: Q1=B (keep RG actions card), Q2=B (proxy:2222 cert path), Q3=C (hybrid cert flow), Q4=B (any-key cert lookup). Hard rule: don't touch Code Server flow.
- [x] Safety preservation: 5 stashes + cloudflare-dns tip + 8.9MB untracked tar pushed to Veela-Beauty `safety/*` branches
- [x] Q4 fix: `get_ssh_certificate` iterates all enabled SSH keys
- [x] `log_error` bug fixed in `restart_code_server` (was NameError)
- [x] `get_vscode_remote_url` in sibling `bench_vscode.py` (file-size budget compliant)
- [x] `ReleaseGroupActions.vue` synthesized: ours's UI + theirs's bottom RG-actions card + `can_use` gate
- [x] `VSCodeLaunchDialog.vue` Q3=C hybrid: 4 cert states (no_key / valid_cert / one_key_no_cert / multi_key_no_cert)
- [x] Wiki page + plan + prototypes ported
- [ ] User: push to GitHub remotes
- [ ] User: build + restart on press-ctrl

### Key Files (current shape)
**`dashboard/src/components/group/ReleaseGroupActions.vue`** (SYNTHESIZED, 579 lines)
Per-bench section + status pill + Code Server KV panel (eye-toggle + copy buttons) + 4-tile action grid + bottom Release Group Actions card. Code Server panel collapses to "not enabled on team plan" when `can_use === false`. `Promise.allSettled` parallel status fetch with fail-open `can_use:true` on errors.

**`dashboard/src/components/group/VSCodeLaunchDialog.vue`** (NEW, 366 lines)
Q3=C hybrid cert flow. `certState` computed picks one of 4 branches: no_key (link to Settings), valid_cert (compact panel + Launch button + renew link), one_key_no_cert (single Generate-and-Launch button), multi_key_no_cert (full multi-step flow with key picker). Calls theirs's `get_ssh_certificate` and `generate_ssh_certificate` APIs.

**`press/press/doctype/bench/bench_dev_overview.py`** (MODIFIED, 816 lines — net -9 from 825)
`get_ssh_certificate` now iterates all enabled SSH keys, returns first valid cert (default wins ties). `restart_code_server`'s `log_error` references replaced with `frappe.log_error(title=..., message=str(e))`. All other Code Server methods byte-for-byte unchanged from production tip `57024889be`.

**`press/press/doctype/bench/bench_vscode.py`** (NEW, 32 lines)
Sibling file housing `get_vscode_remote_url` — placed outside `bench_dev_overview.py` because that file is over the 700-line hard limit. Returns `vscode://vscode-remote/ssh-remote+<bench>@<proxy>:2222/home/frappe/frappe-bench`. Reuses `_ensure_team_access`, validates bench name regex, i18n via `_(...)`.

**`press/press/doctype/bench/test_bench_vscode.py`** + new tests in `test_bench_dev_overview.py` (20 tests, all pass via `python3 -m unittest`)

### Decisions
- **Don't touch Code Server flow** — every method except the bug-fix in `restart_code_server` is byte-identical to production.
- **Sibling file for `get_vscode_remote_url`** — `bench_dev_overview.py` is at 825/816 lines (over 700 hard limit), so adding new code went into `bench_vscode.py`. Same pattern as the team has used elsewhere ("Sibling files over editing upstream").
- **Port 2222 / proxy / cert** for VS Code Remote-SSH (Q2=B) — matches the canonical SSH cert flow `SSHCertificateDialog.vue` documents. Theirs's deployed `frappe@server:22000+offset` direct path bypasses certs and is harder to audit.
- **Q3=C hybrid** — one-click cert mint for default-key users, full multi-step dialog for multi-key power users. Single line of code change between branches.
- **Q4 — any-key cert lookup** — iterates `User SSH Key` records, prefers default; previously only checked `is_default=1` (broke for users who minted certs for non-default keys via the picker).
- **Bottom RG-actions card kept** — these are real Release Group doctype actions (deploy / update / clone), not duplicates. Re-added per Q1=B.

### Next Steps
1. User: `git push` to whichever remote(s) they want (Veela-Beauty fork + accurate-systems upstream).
2. User: deploy on press-ctrl: `git -C apps/press fetch + checkout feat/dev-actions-merged + bench build --app press --force + supervisorctl restart`.
3. (Tech debt) `bench_dev_overview.py` is at 816 lines — over the 700-line hard limit. Should be split into smaller modules: `bench_ssh.py`, `bench_console.py`, `bench_codeserver.py`, etc. Out of scope here.
4. (Tech debt) `ReleaseGroupActions.vue` at 579 lines — over the 500-line soft limit. Future: extract `<CodeServerPanel>` and `<DevActionTiles>` siblings.
5. (Pre-existing) Other test files in `press/press/doctype/bench/` (`test_bench_dev_panel.py`, etc.) fail at import-time due to `_ensure_team_access` transitively importing `frappe.utils`. Pre-existing scaffold issue, not in scope.

### Watch Out
- `bench_dev_overview.py` is OVER the 700 hard limit. Any future feature MUST go in a sibling file or split this one first.
- VS Code Desktop must be installed locally for the `vscode://` URL to work. Browser asks the first time. Wiki documents the copy-URL fallback.
- `ClickToCopyField` is NOT globally registered (per `dashboard/src/components/global/register.js` which only globs `global/*.vue`). Components using it MUST `import ClickToCopyField from '../ClickToCopyField.vue'`. The reference `SSHCertificateDialog.vue` lacks this import — latent bug that hasn't surfaced.
- 5 git stashes that were on press-ctrl have been preserved as `safety/stash-*` branches on Veela-Beauty/press. Don't lose them.

---

## Session Archive

### Session 2026-04-26 (afternoon): Dev Actions synthesis
**What we did:** Discovered another agent had built parallel "Local VS Code" feature on `cloudflare-dns` (commits `f76f2c6b65` + `57024889be`) over the past 3 days while we were doing the brainstorm + prototype + plan + implementation flow on a separate branch. Stopped before deploy. Compared both implementations feature-by-feature in `/tmp/synthesis-report.md`. User picked merged path: ours's UI shell + theirs's `can_use` gating + theirs's bottom RG-actions card + ours's `proxy:2222` cert path + Q3=C hybrid cert flow + Q4 any-key fix. Created `feat/dev-actions-merged` off theirs's tip and synthesized in 8 commits. Preserved theirs's 5 uncommitted stashes + 8.9MB untracked files as safety branches on Veela-Beauty.
**Files:** ReleaseGroupActions.vue (synthesized 579), VSCodeLaunchDialog.vue (NEW Q3=C hybrid 366), bench_dev_overview.py (Q4 fix + log_error fix, -9 lines), bench_vscode.py (NEW sibling 32), test files (+8 tests, 20 pass total), wiki + plan + prototype docs ported.
**Decisions:** Use sibling file when host file is over 700 lines. Don't touch working Code Server backend. Synthesis branch off theirs's tip rather than rebase ours onto theirs (less conflict risk). Safety branches BEFORE any merge work.

### Session 2026-04-26 (morning): Dev Actions redesign (now superseded by afternoon synthesis)
**What we did:** Original brainstorm + prototype + 8-task subagent-driven implementation on `feat/dev-actions-redesign`. Approved prototype, two-stage code reviews per task, 16-test backend, 521-line restructured component. Pushed to Veela-Beauty before discovering the parallel work — see afternoon session for resolution.
**Files:** Same files; superseded by `feat/dev-actions-merged`. Branch retained as `feat/dev-actions-redesign` for reference.

### Session 2026-04-03: Deploy Page + Create App + Dev Tab + Infrastructure
**What we did:** Fixed deploy page blank screen, added 7 UX enhancements (auto-refresh, stage groups, colored badges, progress bar, failure banner, retry buttons, duration comparison). Built Create New App feature. Built Dev tab local app creation + Push to GitHub. Fixed press-f1 disk full (100% → 39%, expanded 75G → 150G). Cleaned roseline_app git repo.
**Files:** DeployCandidate.vue, build_diagnostics.py, create_app.py, CreateAppDialog.vue, SiteDevTab.vue, bench_app_management.py, bench_dev_overview.py
**Decisions:** Sibling files for APIs, git -C instead of cd in docker_execute, daily cleanup cron

### Key Files (current shape)
**`dashboard/src/pages/DeployCandidate.vue`** (MODIFIED, 685 lines)
Enhanced deploy build page: loading state, failure banner with step details, colored badges,
stage-grouped collapsible steps, auto-refresh, progress bar with estimate, retry/cancel/force buttons.

**`press/press/doctype/bench/bench_app_management.py`** (NEW, 148 lines)
Local app creation + GitHub push APIs. create_app_locally runs bench new-app inside container.
init_github_for_app creates repo, pushes, registers in Press.

**`press/api/create_app.py`** (NEW, 195 lines)
GitHub-first app creation. Scaffold → create repo → push → register → auto-add to bench.
GitHub account selector (user + orgs). Team token with global fallback.

**`press/press/doctype/deploy_candidate_build/build_diagnostics.py`** (NEW, 37 lines)
get_failure_details API — returns failed step, stage, output, progress.

**`dashboard/src/components/SiteDevTab.vue`** (MODIFIED, 612 lines)
Dev tab: New App button (dev benches only), Create App dialog, Push to GitHub dialog,
git status filtered by site apps, GitHub account selector.

### Decisions
- **Sibling files over editing upstream**: All new APIs in separate .py files to avoid merge conflicts
- **git -C over cd**: docker_execute doesn't expand $() subshells — use git -C per app
- **Daily cleanup cron**: press-f1 at 3 AM — prune images >72h, build cache, /tmp, journals
- **Docker logs weekly**: Truncate Sunday only (kept for debugging)
- **Global GitHub token fallback**: OK for self-hosted with trusted teams

### Next Steps
1. "Add to other benches" picker after GitHub push
2. Stabilize docker_execute for compound commands (investigate agent shell handling)
3. Split bench_dev_overview.py if it approaches 600 lines

### Watch Out
- docker_execute $() subshells expand on HOST not container — never use subshells
- Press benches use detached HEAD (commit hash) not branches — `has_remote` is false for all
- `rg.add_app()` expects `{name, title, repository_url, branch}` not `{app, source}`

---

## Session Archive

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

### 2026-04-29 - dashboard_fields whitelist silently drops fields
**What happened:** "Mark/Unset Dev Bench" toggle text never reflected reality; Watch panel never appeared even after marking dev; Site Overview Storage/Database stayed at 0 despite real data in DB.
**Root cause:** `Bench.dashboard_fields` and `Site.dashboard_fields` are class-level tuples that Press's `press.api.client.get*` methods use as filter whitelists. Fields requested by the dashboard but missing from the tuple are silently stripped from the response. No error, no warning.
**How we fixed it:** Added `is_development_bench` to `Bench.dashboard_fields` and `current_cpu_usage` / `current_database_usage` / `current_disk_usage` to `Site.dashboard_fields`. Wrote regression tests asserting both fields stay in the tuple.
**Lesson:** When a Frappe Press dashboard panel shows 0/null/false despite the DB having a value, FIRST check the doctype's `dashboard_fields` whitelist before debugging anywhere else. Same class of bug bit 3 different fields in one session.

### 2026-04-29 - Log Server kibana_password drift = silent 401
**What happened:** Compute panel showed 0 hours even after ES + Filebeat were shipping real data and indices had thousands of `transaction_type=request` docs.
**Root cause:** When I created the Log Server doc via `frappe.get_doc({...}).insert()`, the heredoc env var didn't expand cleanly on one path — the kibana_password ended up as a different random hash than what nginx's htpasswd file expected. Press's `get_current_cpu_usage` posts to ES with `auth=("frappe", get_decrypted_password(...))`. Got 401. The function catches all exceptions and returns 0. No error visible to user.
**How we fixed it:** Verified htpasswd password prefix matched stored kibana_password prefix. They didn't. Updated the Log Server doc with the correct password.
**Lesson:** When ES infra is in place but Press still shows 0, do `requests.post` directly with the password Press would use — see if you get 200 or 401. Don't trust silent failures.

### 2026-04-29 - Filebeat ILM PUT 405 through nginx proxy
**What happened:** Filebeat connected to ES but kept retrying with errors, never indexed anything for monitor.json.log.
**Root cause:** Filebeat 7.x tries to PUT to a date-math URL like `<filebeat-7.17.29-{now/d}-000001>` during ILM (Index Lifecycle Management) setup. ES expects POST for these and returns 405 Method Not Allowed when receiving PUT. Through our nginx reverse proxy this was unrecoverable.
**How we fixed it:** Added `setup.ilm.enabled: false` + `setup.template.enabled: false` to `/etc/filebeat/filebeat.yml`. Filebeat falls back to creating daily indices by date suffix (e.g. `filebeat-7.17.29-2026.04.29`) without ILM rollover.
**Lesson:** When Filebeat → ES errors with 405, check ILM setup first. ILM via reverse proxy needs nginx to either accept PUT on those URLs or be disabled at filebeat level.

### 2026-04-29 - Older Frappe sites don't emit request.counter
**What happened:** Some sites' Compute panels showed 0 even with real traffic in ES.
**Root cause:** Frappe's `monitor.json.log` includes `request.counter` (CPU microseconds per request) only on newer versions (v15+). Older sites log `request.{ip,method,path,status_code}` without counter. Press's `get_current_cpu_usage` reads `hits[0]["_source"]["json"]["request"]["counter"]` — None gets `.get(..., 0)` → 0.
**How we fixed it:** Documented as known limitation. Sites need Frappe upgrade for compute tracking.
**Lesson:** Press features that depend on log shape are coupled to Frappe versions. Test on a representative site, not just one.

### 2026-04-29 - Windows-built node_modules in Linux Docker build
**What happened:** Bench builds for bench-0011 failed repeatedly (~5 fails/hour). Each failure ~4 min wasted before user could see the error.
**Root cause:** sales_force_server_app's `main` branch had `node_modules-backup/` (619 files) committed by a developer who ran `npm install playwright` on Windows. The package.json files inside referenced `C:/Users/VICTUS/AppData/Roaming/npm/...` paths. yarn on Linux scanned these on `bench get-app` and failed immediately. Rename `node_modules/` → `node_modules-backup/` didn't help — yarn still scans subdirs.
**How we fixed it:** Removed all `*-backup/` dirs and `*-backup` files. Added entries to `.gitignore`. Committed.
**Lesson:** Apps in any build pipeline must add `node_modules/`, `node_modules-*/`, `*-backup/`, `playwright-report*/`, `test-results*/` to `.gitignore` from day 1. Once Windows artifacts get committed, even renamed they'll break Linux builds.
**Lesson:** Always add loading + error UI states. Never trust that a resource loads.
