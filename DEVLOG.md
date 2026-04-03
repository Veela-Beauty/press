# Press Fork Dev Log

## Working State
**Session:** Deploy Page + Create App + Dev Tab | **Date:** 2026-04-03

### Active Task
Dev tab local app creation + infrastructure fixes
- [x] Deploy page blank screen fix
- [x] Deploy page 7 UX enhancements + code review (all 7 fixes applied)
- [x] Create New App feature (GitHub-first, from bench Apps tab)
- [x] Dev tab: Create App Locally + Push to GitHub
- [x] press-f1 disk cleanup (100% → 39%) + expand (75G → 150G)
- [x] Daily cleanup cron on press-f1
- [x] roseline_app git cleanup (removed baked-in database dumps)
- [ ] "Add to other benches" picker after GitHub push

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
