# Press Fork Dev Log

## Working State
**Session:** Dev Actions synthesis (merge of two parallel implementations) | **Date:** 2026-04-26

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
**Lesson:** Always add loading + error UI states. Never trust that a resource loads.
