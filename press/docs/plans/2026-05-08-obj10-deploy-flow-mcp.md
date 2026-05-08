# Objective 10 — Deploy / Release Workflow MCP Tools

**Date:** 2026-05-08
**Branch:** `feat/clone-bench-and-site` (PR #1, currently 62 commits)
**Status:** DRAFT — awaiting approval

> Adds the deploy/release pipeline tools that the wazin_mx-style workflow needs, so an agent can build → deploy → migrate → seed entirely via MCP without any press-ctrl SSH access.

---

## Objective

Expose Press's existing deploy/release/site-status APIs through MCP so an agent can reproduce the full wazin_mx workflow (App Release → Deploy Candidate → build → site update → bench-flip detection → seed script execution) using only the MCP HTTP endpoint with a token. **Closes the last remaining "agent must SSH to press-ctrl" gap.**

**One-sentence summary**: Ship 9 new MCP tools wrapping existing Press whitelisted methods (App Release approve, Deploy Candidate create/schedule/status, Site schedule_update + status + bench-flip polling, Agent Job listing, and a constrained `bench_run_repo_script` that fetches a Python script from a GitHub repo and executes it in a bench container).

---

## Definition of Done

### Server-side tools (all wrapping existing Press APIs)

- [ ] `app_release_approve(release_name)` — flips `App Release.status` from Draft to Approved. Risk: medium.
- [ ] `release_group_create_deploy_candidate(name, apps_to_ignore=None)` — wraps `ReleaseGroup.create_deploy_candidate()`. Returns the new candidate name. Risk: medium.
- [ ] `deploy_candidate_schedule_build(candidate_name, run_now=True)` — wraps `DeployCandidate.schedule_build_and_deploy(run_now=...)`. Returns the build job name. Risk: medium.
- [ ] `deploy_candidate_status(candidate_or_build_name)` — returns `{candidate, status, build_start, build_end, error_message}`. Accepts either a Deploy Candidate name OR a Deploy Candidate Build name. Risk: low.
- [ ] `site_schedule_update(site_name, skip_failing_patches=False, skip_backups=False)` — wraps `Site.schedule_update()` (different from existing `site_update` which uses a different code path). Returns the job name. Risk: medium.
- [ ] `site_status(site_name)` — returns `{name, bench, status, last_updated_at, pending_agent_jobs: [{name, job_type, status, creation}]}`. The pending agent jobs list is the polling primitive. Risk: low.
- [ ] `agent_job_list(site=None, status=None, since_minutes=60, limit=50)` — returns recent Agent Jobs filtered by site/status/window. Risk: low.
- [ ] `bench_run_repo_script(bench_name, repo, branch, script_path, args=None)` — fetches a Python script from a GitHub repo, copies it into the bench container, runs it. Risk: **high** (gated by `risky_tools_enabled`).
- [ ] `wait_for_bench_flip(site_name, target_candidate, timeout_seconds=600)` — polls `Site.bench` until it matches a bench whose `candidate == target_candidate`, OR timeout. Synchronous from agent perspective; uses `frappe.cache` for state. Risk: low.

### Permission + scope behavior

- [ ] All 9 tools added to `_extract_target` in `server.py` for resource-scope enforcement:
  - Site-targeted: `site_schedule_update`, `site_status`, `wait_for_bench_flip` (use `site_name` arg)
  - RG-targeted: `release_group_create_deploy_candidate`, `deploy_candidate_status` (resolve candidate → group via `frappe.db.get_value`)
  - Bench-targeted: `bench_run_repo_script` (already in the bench-targeted set pattern)
  - Other: `app_release_approve`, `deploy_candidate_schedule_build`, `agent_job_list` — no per-resource gating beyond Frappe perms
- [ ] `bench_run_repo_script` requires `risky_tools_enabled=True` (it executes arbitrary code from a remote repo).
- [ ] `app_release_approve`, `release_group_create_deploy_candidate`, `deploy_candidate_schedule_build`, `site_schedule_update` are MEDIUM risk — risky flag NOT required, but rate-limited per existing limiter.

### `bench_run_repo_script` constraints (the new high-risk tool)

- [ ] Only `https://github.com/{owner}/{repo}.git` URLs — no arbitrary git URLs.
- [ ] `script_path` must end in `.py` and not contain `..` segments.
- [ ] Repo allowlist via `Press Settings.mcp_script_repo_allowlist` (Code field, JSON list of `owner/repo` strings). If allowlist is empty, NO repos are allowed (fail-closed).
- [ ] Script execution capped at 60 seconds (configurable via Press Settings).
- [ ] Script runs as the bench's `frappe` user, not root.
- [ ] All `bench_run_repo_script` calls trigger the destructive-op notification hook (Obj 7).
- [ ] Implementation detail: clone repo to a tempdir on press-ctrl, copy the SINGLE script file (not the whole repo) into bench container under `/tmp/mcp-scripts/<uuid>.py`, run it via the existing agent `docker_execute` path, then delete the tempfile.

### Quality

- [ ] All 9 tools added to `tools.py` catalog with correct risk tags.
- [ ] `_extract_target` updated for the new tools.
- [ ] At least 12 new unit tests covering: each tool dispatches correctly, candidate→RG resolution for resource-scope, `bench_run_repo_script` rejects non-allowlisted repos, polling helper times out cleanly, agent_job_list filters work.
- [ ] No new file >300 lines.
- [ ] All existing 80+ tests still pass (no regressions).
- [ ] `bench build --app press --force` succeeds.

### Vue UI updates (minimal — the catalog change is what matters)

- [ ] `IssueTokenDialog.vue` — add the 9 new tools to `AVAILABLE_TOOLS` so agents can scope tokens to them.
- [ ] No new pages/dialogs needed; existing MCP Panel + Admin Panel surface them via the existing Recent Calls feed.

---

## Before / After

### Flow comparison

```
BEFORE — wazin_mx workflow today (your transcript above)
─────────────────────────────────────────────────────────
Agent needs:
  - SSH to press-ctrl (root@89.167.116.92)
  - `bench mariadb -e ...` (raw SQL access — no permission gating)
  - `bench --site X console` (Python REPL — full DB write access)
  - `scp` + `docker cp` (file transfer into containers)
  - Direct execution of multi-hundred-line Python scripts

Risk: anyone with the SSH key has root-equivalent access to all sites.
Audit: zero — SSH commands aren't logged in Press.


AFTER — same workflow via MCP only
──────────────────────────────────
Agent has only:
  - HTTPS endpoint + a Press MCP Token (token-scoped to specific RGs/sites)
  - Token gates: tool scope + risk level + resource allowlist + rate limit
  - Every action audited in Press MCP Call Log with hash-chain integrity

Workflow:
  1. mcp.app_release_approve(release_name="v59er8d92d")
  2. mcp.release_group_create_deploy_candidate(name="bench-0005")
        → returns candidate "deploy-0005-000046"
  3. mcp.deploy_candidate_schedule_build(candidate="deploy-0005-000046")
        → returns build job "s2h6oi14n0"
  4. Loop: mcp.deploy_candidate_status(name="s2h6oi14n0")
        → wait until status="Success"
  5. mcp.site_schedule_update(site="wazin-mx-demo.sandbox.mvpstorm.com")
  6. mcp.wait_for_bench_flip(site="...", target_candidate="deploy-0005-000046")
  7. mcp.bench_run_repo_script(
        bench="bench-0005-000046-press-f1",
        repo="accurate-systems/wazin_mx",
        branch="main",
        script_path="scripts/seed_report_data.py",
     )  # requires risky_tools_enabled token
  8. Direct HTTPS calls to /api/method/frappe.desk.query_report.run for each report
```

### Metric table

| Dimension                    | Before (SSH)                  | After (MCP)                       |
| ---------------------------- | ----------------------------- | --------------------------------- |
| Press-ctrl SSH access needed | Yes                           | No                                |
| Per-action audit             | None                          | Hash-chained log                  |
| Resource scoping             | None (full root)              | Per-RG / per-site allowlist       |
| Rate limiting                | None                          | 60 calls/min per token            |
| Time to revoke access        | Rotate SSH key (manual + slow)| Click revoke in Admin Panel       |
| Script execution origin      | Anywhere on agent's disk      | Allowlisted GitHub repos only     |
| Lines of agent SSH code      | ~50 lines for wazin_mx flow   | 0                                 |

---

## File Structure

### Created
- `press/mcp_server/deploy_flow.py` — 9 new whitelisted methods (~250 lines)
- `press/mcp_server/test_deploy_flow.py` — 12+ tests
- `press/mcp_server/script_runner.py` — git-clone + container-copy + exec helper for `bench_run_repo_script` (~120 lines)
- `press/mcp_server/test_script_runner.py` — 4 tests focused on path/URL validation

### Modified
- `press/mcp_server/tools.py` — 9 new TOOLS entries
- `press/mcp_server/server.py` — `_extract_target` extended for new tools; candidate→RG resolution helper
- `dashboard/src/components/mcp/IssueTokenDialog.vue` — 9 new tools added to `AVAILABLE_TOOLS`
- `press/doctype/press_settings/press_settings.json` — add `mcp_script_repo_allowlist` (Code, JSON list) + `mcp_script_timeout_seconds` (Int, default 60)

---

## Anchors (existing Press code we're wrapping — verified to exist)

| Wrapper | Wraps | Where |
|---|---|---|
| `app_release_approve` | `App Release.save()` after setting `status = "Approved"` | `press/doctype/app_release/app_release.py` |
| `release_group_create_deploy_candidate` | `ReleaseGroup.create_deploy_candidate(apps_to_ignore=[])` | `press/doctype/release_group/release_group.py:629` |
| `deploy_candidate_schedule_build` | `DeployCandidate.schedule_build_and_deploy(run_now)` | `press/doctype/deploy_candidate/deploy_candidate.py:240` |
| `deploy_candidate_status` | Direct query of `Deploy Candidate Build` + `Deploy Candidate` | `press/doctype/deploy_candidate_build/...` |
| `site_schedule_update` | `Site.schedule_update(skip_failing_patches, skip_backups)` | `press/doctype/site/site.py` |
| `site_status` | Direct query of `Site` + `Agent Job` | n/a |
| `agent_job_list` | Direct query of `Agent Job` | n/a |
| `bench_run_repo_script` | NEW — uses `Agent.execute_in_container` or similar primitive | needs investigation in `agent.py` |
| `wait_for_bench_flip` | Polling helper around `frappe.db.get_value("Site", x, "bench")` | n/a |

---

## Tasks (TDD-first per writing-plans skill)

### Task 1: Failing tests for `app_release_approve` + 4 simple wrappers (release_group_create_deploy_candidate, deploy_candidate_schedule_build, deploy_candidate_status, agent_job_list)
- Tests assert correct delegation + permission errors via mocks
- Run; expect ImportError; commit RED
- Implementation: 5 thin wrappers in `deploy_flow.py`
- Run; expect GREEN; commit

### Task 2: `site_schedule_update` + `site_status` + `wait_for_bench_flip`
- Tests for the polling logic (mock `frappe.db.get_value` to return changing values)
- Implementation in `deploy_flow.py`
- Verify timeout behavior

### Task 3: `bench_run_repo_script` (the high-risk one)
- Tests reject non-allowlisted repos
- Tests reject `..` in script_path
- Tests reject non-`.py` extensions
- Tests verify allowlist pulled from Press Settings
- Implementation in new `script_runner.py` module
- Mock the actual git clone + container copy steps in tests; do NOT make real network calls

### Task 4: Catalog wiring
- Add 9 entries to `tools.py` with risk tags
- Update `_extract_target` in `server.py`
- Update `IssueTokenDialog.vue` AVAILABLE_TOOLS list

### Task 5: Press Settings fields + integration test
- Add 2 fields to Press Settings doctype JSON
- Migrate
- Integration test: full happy path with all mocks (approve → create candidate → schedule build → wait status → schedule update → wait flip)

### Task 6: Push + verify in PR

---

## Risks & Mitigations

1. **`bench_run_repo_script` is RCE by design** — script content is whatever lives at `repo/script_path`. Mitigation: repo allowlist (fail-closed if empty), 60s execution cap, runs as `frappe` not root, audit log on every call, requires `risky_tools_enabled=True`.

2. **GitHub clone latency** — first clone takes seconds; subsequent calls hit a local cache. Mitigation: cache cloned repos under `/tmp/mcp-script-repos/<owner>--<repo>/` keyed by `(repo, branch)`; refresh on each call via `git pull` (idempotent).

3. **Container exec implementation** — Press's `Agent.docker_execute` exists but copying a file into a container is more involved. Two options:
   - (a) Mount a tmpdir into the container (bench setup change — invasive)
   - (b) Send the script CONTENT through `docker_execute` as a heredoc (simpler — implemented like `docker exec ... bash -c 'cat > /tmp/x.py <<EOF\n...content...\nEOF; python3 /tmp/x.py'`)
   - **Pick (b)** — matches existing patterns in `bench_dev_overview.run_python_on_site`.

4. **`wait_for_bench_flip` blocks the MCP response thread** — synchronous polling could exceed 60s timeout. Mitigation: cap poll loop at `timeout_seconds` (default 600), but require caller to re-poll. Return early with `{status: "still_pending"}` if not done within timeout.

5. **`deploy_candidate_status` returning Build OR Candidate confuses callers** — clear API: agent passes `name`, function tries `Deploy Candidate Build` first (since builds are the visible runtime entity), falls back to `Deploy Candidate` if not found.

---

## Out of scope (NOT in Obj 10)

- Press Settings UI for the script allowlist (System Manager edits via Frappe Desk for now).
- Caching of git repos beyond the simple tmpdir approach.
- Multi-step orchestration (e.g., "approve + build + wait + update" as one tool) — keep tools atomic; agents can chain.
- Agent-side script imports — script must be self-contained Python.
- Non-Python script execution (.sh, .js) — Python only for v1.

---

## Estimated effort

| Task | Hours |
|---|---|
| Task 1 (5 simple wrappers + tests) | 1.5 |
| Task 2 (site_schedule_update + status + wait_for_flip + tests) | 1.0 |
| Task 3 (bench_run_repo_script + script_runner.py + tests) | 1.5 |
| Task 4 (catalog + Vue) | 0.5 |
| Task 5 (Press Settings + integration test) | 0.5 |
| Task 6 (push + verify) | 0.25 |
| **Total** | **~5 hours** |

---

## Open questions for you (reviewer)

1. **Script repo allowlist** — should it be per-team (each team has its own allowlist) OR global (one Press-wide allowlist managed by System Users)? Plan says global; per-team is more work but better isolation.
2. **Script timeout** — 60s default, or longer (e.g., 5 min for slow seeders like the wazin_mx one which inserts 50+ docs)? Plan says 60s; bump to 300s if needed.
3. **`wait_for_bench_flip` semantics** — sync poll (blocks the MCP response) vs async (return job ID, agent polls separately)? Plan says sync with timeout. Async is more resilient but agent has to handle 2 round-trips.
4. **Should `bench_run_repo_script` be split** into `clone+copy` vs `execute` so agents can preview the script before running? Adds complexity; plan combines.
