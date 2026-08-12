# Press Fork Dev Log

### Session 10 - 2026-08-13: MCP site provisioning + the scope-guard message that misled us

**What we did:**
1. Added site_create + site_restore (press/mcp_server/site_ops.py, new) so a caller can seed a throwaway site from a backup without the dashboard. Catalog 82 to 84. Both registered in tools.py / help.py and scoped in server.py _extract_target.
2. Wrote test_every_resource_tool_is_scoped: walks TOOLS and fails on any tool carrying a resource arg that _extract_target does not map. 252991d2a had fixed six of that class by hand and missed two, which is what set us off down a wrong path today.
3. Corrected the guard's error message. It told you to patch the server; the usual cause is passing an arg the tool does not declare. app_git_status and bench_provision_progress were fine all along (already mapped at lines 564/576) and work when called with bench_name instead of release_group.
4. site_restore now reads the Agent Job and Site status back instead of returning a hardcoded "queued".
5. Used the pair (via the APIs they wrap, since the token predates them) to restore a 440 MB prod Lipton backup onto lipton-yp.sandbox.mvpstorm.com. Verified row-for-row against prod.

**Files:** press/mcp_server/site_ops.py (new, 183), test_site_ops.py (new, 227, 13 green), tools.py (+2 entries), server.py (scoping + message), help.py (+2), docs/superpowers/specs/2026-08-12-mcp-site-create-restore-design.md (new)

**Mistakes worth keeping:**
- Claimed two tools were broken because the error message said so. They were not. Read the mapping before trusting a message that blames the server.
- Wrote the guard test with a blanket exists()/DB stub, so it reported 18 false positives on the bench and one test asserted the wrong error entirely. Running it on the bench, not parsing it locally, is what found both.
- api.site.new cannot place a site on a chosen Release Group on this install: all three Site Plans have private_bench_support=1, so it always takes the private-bench branch. The route that lands on an existing bench is the dedicated-server branch (pass `server`), and that branch ignores `files` -- so create-then-restore is two calls here, not one.
- site_config_set still reports status:set while writing nothing (confirmed again today). All 130 Scheduled Job Types were stopped in the DB instead, which is what actually holds.

---

### Session 9 - 2026-06-19: MCP bench-control tools + arg-alias fix + dev-box proxy

**What we did:**
1. Added 10 Release-Group bench-control MCP tools (bench_ops.py) so an agent composes a bench (add/remove/switch app, versions, branches, rename, redeploy, archive, rebuild, create) without the Desk. Catalog 72 to 82.
2. Fixed the recurring "missing required args" agent stall: _normalize_arg_aliases() in server.py rewrites site/bench/name to the canonical arg before validation, guarded so clone_site/bench_deploy stay untouched.
3. Registered all 10 in the dashboard _tool_catalog.js + rebuilt the Vue dashboard (yarn build).
4. Wrote a dev-box stdio proxy (devbox_proxy/) so Claude Code (type:stdio) can call the Frappe-RPC MCP; wired as "press-cloud" in ~/.claude.json (token MCPT-2465 via get_password). 6 tests added (module 45 green).

**Files:** press/mcp_server/bench_ops.py (new), server.py (alias norm + scoping), tools.py (10 entries + fragments), dashboard/src/components/mcp/_tool_catalog.js, press/mcp_server/test_server.py, press/mcp_server/devbox_proxy/ (new)

**Decisions:**
- Arg aliases fixed server-side, not in agent guidance: a guide cannot stop agents guessing; normalization makes the natural name work.
- Press MCP is a Frappe single-call RPC, not MCP-protocol, so a stdio proxy bridges it (type:http cannot talk to it directly).
- token_plaintext is a Password field: read with doc.get_password(), not db.get_value (returns the encrypted value and fails auth).

**Commits:** bb72c6ee0, 475ad4196, 9de191ad9, 9ee6d764f.

**Lesson:** Frappe Password fields return the ENCRYPTED value via db.get_value; use get_password() to read the usable plaintext.



### Session 8 - 2026-06-07: Infrastructure dashboard polish, two code-reviews, Gate-0 self-diagnosis

**What we did:**
1. Shipped the Plan-2b Infrastructure dashboard live, then fixed 3 hand-test bugs: Servers/Infrastructure toggle moved inline, server CPU/Disk probes added to host_probes, and a bespoke Notifications page replacing the bare ObjectList.
2. Two BIG /code-review passes (dashboard + managed-host backend); implemented the approved DRY/robustness/test fixes (python tests 13 to 20, vitest 35).
3. Gate-0 long-term fix: the control plane no longer fails silently. classify_conn_error + Managed Host.last_error + a gate0_status() banner name exactly what is missing to connect a managed host.
4. Proved the managed-host adapter/tunnel/control/logs cycle on real Docker via a throwaway CA-free sidecar, then tore it down (press-ctrl restored, 0 managed hosts).

**Files:** `press/api/infra_board.py`, `press/infra/adapters/ssh_docker.py`, `press/press/doctype/managed_host/`, `dashboard/src/pages/infrastructure/*`, `dashboard/src/pages/notifications/*`, `docs/infra-board/2026-06-06-plan-2b-*.md`

**Decisions:**
- CA-free demo sidecar (frappe default key, `_attach_cert` fails open) to prove the cycle without provisioning Gate 0; a real registration still needs Gate 0 (CA + control-plane key + socket-proxy).
- Surface failures over silent best-effort: every connection error now carries an actionable reason.

**Commits:** 1c4013b6, a8ad60db, 5cdd7cfa, ba0955b5, 12416b35, c04bc3ef, 20a00cf0 (+ docs). HEAD 8d6201606.

**Lesson:** alpine `adduser -D` leaves the account password-locked (`!`), which sshd reports as "invalid user" even for pubkey auth. Fix the shadow field `!` to `*`.

### Session 7 — 2026-05-06: get_bench_update double team-check + router.js defensive redirect + press-f1 MariaDB firewall

**What we did:**
1. Diagnosed and fixed deploy-button logout bug — two-part root cause
2. Responded to Hetzner abuse report — secured press-f1 MariaDB port 3306

**Fix 1 — bench_update.py:175**: Added System User bypass to second team check in `get_bench_update()`. The `@protected("Release Group")` decorator exempts System Users, but the inner function had its own team check that blocked everyone. 1-line fix.

**Fix 2 — router.js:712-717**: Replaced `logoutWithTeamError()` (which calls `session.logout.submit()` and destroys the session) with `localStorage.removeItem("current_team")` + `window.location.href="/app"`. Team PermissionError != session invalid.

**Fix 3 — press-f1 firewall**: MariaDB port 3306 was open to internet. Added iptables rules: ACCEPT from press-ctrl, Docker bridge (172.17.0.0/16), localhost; DROP everything else. Installed iptables-persistent. bind-address unchanged (bench containers connect via public IP).

**Files:** `bench_update.py`, `router.js`, `DEVLOG.md`, `team-roles-permissions.md`, `press-ctrl-stability-runbook.md`

**Decisions:**
- Fix 1 is architectural (aligns two inconsistent permission checks)
- Fix 2 is defense-in-depth (team error should never destroy session)
- Fix 3: firewall-level fix (can't change MariaDB bind-address without breaking Docker bench containers)
- Kept 5-second timeout → logout fallback as safety net
- Pushed via Hetzner dev box (press-ctrl deploy keys are read-only)

---

## Session Archive

### Session 6 — 2026-05-05: Vue auto-logout root cause (bare frappe.throw → ValidationError)
**What we did:** Changed `Team.get_doc` throw to explicit `PermissionError` + Vue one-shot fallback reset to `window.default_team`. Built and shipped.
**Files:** `press/api/team.py`, `dashboard/src/router.js`
**Decisions:** Bare `frappe.throw(string)` defaults to `ValidationError` — always pass explicit exception type in dashboard-reachable code paths.

### Session 5 — 2026-05-05: Disable simultaneous_sessions cap entirely
**What we did:** Set cap to 0 (unlimited), renamed constant, backfilled all team-member users. Cap and auto-logout were fighting each other.
**Files:** `team_roles.py`, patch `disable_team_member_session_cap`
**Decisions:** The cap loses against a frontend auto-logout loop. Right fix is the loop, not the cap value.

### Session 4 — 2026-05-05: simultaneous_sessions cap raised to 50
**What we did:** Bumped from 10 to 50. Still wasn't enough — led to Session 5.
**Files:** `team_roles.py`
**Decisions:** Underestimated the dashboard's session creation rate.

### **Session:** Press Role + simultaneous_sessions + actionable 403 messages | **Date:** 2026-05-05
**What we did:** Diagnosed and fixed Vue auto-logout loop caused by bare frappe.throw defaulting to ValidationError. Changed Team.get_doc to explicit PermissionError + added one-shot localStorage fallback.
**Files:** `press/api/team.py`, `dashboard/src/router.js`
**Decisions:** Bare frappe.throw(string) defaults to ValidationError — always pass explicit exception type in dashboard-reachable code paths.


## Session Archive

### Session 2026-05-05: Press Role + simultaneous_sessions + actionable 403 messages
**What we did:** Shipped 3 commits (`ce99c03c2d`, `639335ef2b`, `020eb9892c`) diagnosing two related permission failures + 4 long-term guards. Marco's "Function … is not whitelisted" was `simultaneous_sessions=2` evicting his older browser tabs (NOT a missing decorator — Frappe's `is_whitelisted` raises identical wording for both causes). His Deploy 403 was the OptiFlowERP Developer Press Role having all 18 booleans = 0 — a silent lockout from a half-configured role. Bumped 5 affected users to 10 + added `ensure_session_cap` after_insert hook on Team Member so future invites are safe. Press Role now pre-ticks a 7-flag Developer baseline via `before_insert` + warns on zero-flag lockouts via `validate`. Vue dashboard 403s now name the missing flag — *"Ask your team admin to enable 'all_release_groups' on your Press Role."* New 279-line admin wiki guide explains the two parallel permission systems, all 18 Press Role flags, 5 preset recipes, and a SQL recovery playbook.
**Files:** press/press/doctype/team/team_roles.py, press/press/doctype/press_role/press_role.py, press/api/client.py, press/patches/v0_0_5/bump_team_member_session_cap.py, press/patches.txt, docs/wiki/01-backend-development/team-roles-permissions.md, DEVLOG.md, CHANGELOG.md.
**Decisions:** `simultaneous_sessions` cap = 10 (generous enough for normal multi-tab use, tight enough that one leaked cookie can't run unbounded); Press Role default = Developer baseline (7 of 18 flags); empty-role warning is `msgprint` not `throw` (placeholder roles still allowed); hint-aware errors in `press.api.client` only — extension to `team_guard` decorators deferred.

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

### 2026-05-05 - "is not whitelisted" 403 misdiagnosed as missing decorator
**What happened:** Marco/Mahmoud reported `Function press.press.doctype.bench.bench_dev_overview.restart_code_server is not whitelisted` toast on the dashboard. The function IS `@frappe.whitelist()`-decorated and IS in `frappe.whitelisted` (verified by importing the module fresh in `bench console`). Yet 401/403 alternated with 200 for the same user in the same minute.
**Root cause:** `User.simultaneous_sessions = 2` (Frappe default) evicted Marco's older browser tabs every time he opened a 3rd. The kicked tab's next request went through with a Guest cookie. `frappe.is_whitelisted()` (frappe/__init__.py:866) raises identical wording — *"You are not permitted to access this resource. Login to access. Function X is not whitelisted."* — for BOTH the missing-decorator case AND the guest-not-allow_guest case.
**How we fixed it:** Bumped affected users 2 → 10 directly. Added `MIN_SIMULTANEOUS_SESSIONS = 10` + `ensure_session_cap` `after_insert` hook on Team Member so future invites can't trip on this. Patch v0_0_5/bump_team_member_session_cap backfilled existing users.
**Lesson:** When you see "is not whitelisted" but the source has the decorator, run `frappe.whitelisted` introspection in `bench console` to confirm registration. If registered but the error persists, the user is Guest at the moment of the call — investigate session limits, cookie state, or auto-logout flows. Same wording for two different bugs.

### 2026-05-05 - Press has TWO permission systems and they are easy to confuse
**What happened:** Admin granted Marco "all team role permissions" via the Team Member dropdown. Marco still got 403 on Deploy. Spent 20 minutes hunting the wrong bug (whitelist registration, team header, CSRF) before finding the real cause.
**Root cause:** Press has **two parallel permission systems**:
- `Team Member.press_role` STRING field (Owner / Platform Admin / DevOps Admin / DevOps User / Developer / Implementor / Viewer) — gates `DEFAULT_FEATURES` (Code Server, SSH Access, Dev Tools — feature visibility).
- Separate `Press Role` doctype with 18 boolean flags (`allow_bench_creation`, `all_release_groups`, etc.) — gates per-resource access (Bench, Site, Server, Deploy, Billing).

Granting role A does NOT grant role B. A new Press Role created via the dashboard's Manage Team → Roles UI starts with **every flag = 0** — total lockout for any member assigned to it.
**How we fixed it:** Flipped all 18 flags = 1 on both team Press Role rows. Added `before_insert` to pre-tick a Developer baseline on new roles. Added `validate` warning when a role with users assigned has every flag at 0. Wrote 279-line wiki guide explaining the two systems, all 18 flags, 5 preset recipes, and a SQL recovery playbook.
**Lesson:** Never assume "I gave them a role" means "they have access." In Press that involves at least 5 different doctypes/fields. The wiki guide at `docs/wiki/01-backend-development/team-roles-permissions.md` is now the source of truth — reference it whenever debugging "Not permitted" toasts.

### 2026-05-05 - GitHub repo redirect makes `git fetch upstream` silently stale
**What happened:** After pushing my commit to `accurate-systems/press cloudflare-dns` from a local clone, `git fetch upstream` on press-ctrl returned STALE content (no error, no warning). `git reset --hard upstream/cloudflare-dns` rolled HEAD BACKWARDS by 2 commits.
**Root cause:** `accurate-systems/press` is now a GitHub redirect to `Veela-Beauty/press`. The redirect does respect pushes (with a deprecation note in stderr) but the fetch refspec doesn't follow it cleanly — old fetch metadata can get served. press-ctrl already has both `upstream` (= accurate-systems) and `veela` (= Veela-Beauty) remotes; only `veela` is canonical.
**How we fixed it:** `git fetch veela cloudflare-dns` returned the right SHA. Reset to `veela/cloudflare-dns` to recover.
**Lesson:** When a GitHub repo moves, deploy boxes still have the old remote name. Prefer the canonical new-location remote (`veela` here) for `git reset` operations. Eventually update the `upstream` URL or remove it to avoid future confusion.


### 2026-05-05 - simultaneous_sessions=10 not enough — eviction loop continued
**What happened:** Bumped the cap from 2 to 10 globally + added after_insert hook for new invites. Problem appeared "fixed." 1-2 hours later Marco was at 12 active sessions, Mahmoud at 34 — both above 10. Vue dashboard kept showing 403/INVALID_TEAM redirects. `clear_old_sessions` on each fresh login was still evicting the OLDEST excess SIDs, which were the cookies of legitimately active browser tabs.
**Root cause:** Underlying Vue dashboard bug auto-logs the user out whenever `getTeam()` errors with ValidationError, which fires on intermittent transient conditions. Each auto-logout triggers a fresh login, which creates a new session and evicts an old one. Cap=10 gave only 8 evictions of buffer before a freshly-evicted SID belonged to a tab the user actively had open. The death spiral continued because the dashboard kept feeding fresh sessions in.
**How we fixed it (workaround):** Bumped cap to 50 in `MIN_SIMULTANEOUS_SESSIONS`. Marco/Mahmoud manually at 100 for extra headroom while we investigate the Vue auto-logout. Commit `14c47ad604`.
**Lesson:** Capping `simultaneous_sessions` only WORKS if the dashboard isn't continuously creating fresh sessions. When there's an auto-logout loop in the frontend, the cap just delays the death spiral by N evictions. The real fix is upstream — find and stop whatever makes `getTeam()` return ValidationError. Tech debt item logged as P0 for next session.


### 2026-05-05 - cap=50 was also not enough — disable simultaneous_sessions entirely
**What happened:** After bumping cap from 10 → 50 (commit `14c47ad604`), the eviction loop *still* fired. The Vue dashboard's auto-logout creates fresh sessions every time it triggers; cap=50 just delays the cliff. With ~10-15 fresh sessions per active user per day plus a 7-day session_expiry, anyone using the dashboard heavily would hit any reasonable cap within a week.
**Root cause:** Same Vue `getTeam()` ValidationError → `logoutWithTeamError()` that started this whole investigation. The cap and the auto-logout fight each other; the cap loses.
**How we fixed it:** Disable the cap. `simultaneous_sessions = 0` makes Frappe's `clear_old_sessions` return early — no eviction. Sessions still expire after `session_expiry` (170h / ~7d), so we don't accumulate forever. New constant `TEAM_MEMBER_SESSION_CAP = 0` (renamed from `MIN_SIMULTANEOUS_SESSIONS` to make "always set" semantics clear). New patch `disable_team_member_session_cap` backfills all team-member users. Commit `64db47fcd8`.
**Lesson:** When a user-facing knob fights an underlying broken loop, the knob loses. The right fix is the loop, not the knob's value. We picked a workaround (disable the cap) because the root cause investigation is non-trivial — but logged as P0 so we don't forget. For internal admin instances with small teams, disabling caps like this is also fine on its own merits — the security argument for capping is thin when the dashboard is not internet-facing public SaaS.


### 2026-05-05 - Vue dashboard auto-logout root cause: Team.get_doc bare frappe.throw → ValidationError
**What happened:** Press dashboard repeatedly bounced users to `/dashboard/login?reason=INVALID_TEAM`. The router's `waitUntilTeamLoaded()` checks `team.get.error.exc_type === 'ValidationError'` and fires `logoutWithTeamError()`. We thought it was the simultaneous_sessions cap (lesson #127); cap removal helped but didn't stop the loop.
**Root cause:** `Team.get_doc()` had `frappe.throw("You are not allowed to access this document")` with no explicit exception type. Frappe's default for bare `frappe.throw(string)` is `ValidationError`. The throw fires when session.user isn't in the team's `team_members` — most commonly stale `localStorage.current_team` (user removed from a previously-belonged team, or shared browser).
**How we fixed it (commit `1b057047f9`):**
1. Backend: changed `Team.get_doc` throw to explicit `frappe.PermissionError` with a helpful message ("Use the team selector to switch to one of your teams"). Vue router specifically checks for ValidationError, so PermissionError no longer triggers logout.
2. Vue (`dashboard/src/router.js` `waitUntilTeamLoaded`): on team-resource error, try a one-shot fallback — reset `localStorage.current_team` to `window.default_team` and reload the page. Fresh boot creates a new resource for the right team and recovers without re-login. Only logs out if fallback already attempted OR no default_team available. Added 5-second polling cap as safety net.
3. `bench build --app press` to ship the JS change.
**Lesson:** Bare `frappe.throw(message)` defaults to `ValidationError` — a foot-gun anywhere a frontend branches on `exc_type`. Always pass an explicit exception type matching the semantic meaning: `PermissionError` for "not allowed", `DoesNotExistError` for "missing", `ValidationError` for "invalid input". Going forward, never use bare `frappe.throw(string)` in code paths reachable by the dashboard.

