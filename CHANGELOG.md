# Changelog

This file documents changes (current commit level since, no tagged releases yet).

---


## 19-05-2026 — New-team-member permissions: 4-way fix + auto-audit to stop the recurrence

### Fixed
- **`Access not allowed for this URL` on Clone Bench / Release Group.** Clicking *Clone + Deploy* or *Clone RG only* from `CloneBenchPrompt.vue` 401'd for non-System team users because `release_group_clone.*` was never added to `ALLOWED_WILDCARD_PATHS` in `press/auth.py`. The dialog was wired up in commit `63c5a0d5fc` as the "Create a new bench" pivot inside the Clone Site flow; Marko's teammate `ahmedmowafy74@gmail.com` was the first non-System user to exercise the path.
- **`No permission for Bench Shell Log` flooding every bench Actions page.** `Bench.docker_execute()` (called by bench dev watch, bench dev overview, app management, etc.) writes an audit log via `create_bench_shell_log()` on every call. The doctype grants `create` only to System Manager; non-System team users threw `PermissionError` on each `.insert()`. The Bench Watch panel polls every 10s → users saw the error every 10s. Fix: insert with `ignore_permissions=True` — the `owner` field still captures the real session user so the audit trail stays intact, and the user can no longer be blocked from triggering a shell that they're already authorised to trigger via `_check_team_access`.
- **`Failed to get method for command ... has no attribute 'get_vscode_remote_url'`.** `VSCodeLaunchDialog.vue:311` called `press.press.doctype.bench.bench_dev_overview.get_vscode_remote_url` — but the method actually lives at `press.press.doctype.bench.bench_vscode.get_vscode_remote_url` (sibling file). Stale path from a refactor. Two-line fix: corrected the dotted path AND added `bench_vscode.*` to the auth allowlist (without both, fixing the path alone would still 401 for team users).

### Audit follow-ups (caught BY the new audit script in the same PR)
- **`press.press.ai.api.*` was missing from the allowlist** — `AiPolicyGate.vue:acknowledge_policy` and `AiTeamRules.vue:update_team_ai_rules` would have force-logged-out any non-System user who acknowledged the AI policy or edited per-team AI rules. Added preemptively before anyone hit it.

### Added
- **`scripts/audit_dashboard_allowlist.py`** — runnable audit that diffs every dotted-path caller in `dashboard/src/**/*.{vue,js,ts}` against `ALLOWED_WILDCARD_PATHS` in `press/auth.py`. Exit code 0 = all covered; 1 = missing entries listed with the files that reference them. 311 callers audited; all now covered after this PR.
- **`press/test_auth.py:TestAuthAllowlistCoverage`** — wraps the audit script in `bench run-tests` so any future PR that adds a whitelisted method without the allowlist entry fails CI. Stops the recurring trap (this is the third time we've hit it in 2 weeks: 2026-05-10 deploy_candidate_build, 2026-05-18 bench_dev_watch + bench_code_health, today's quadruple).
- **`press/press/doctype/bench_shell_log/test_bench_shell_log.py`** — regression test that calls `create_bench_shell_log` as a non-System Website User and asserts the row inserts with `owner` set to the real user. Would fail on pre-fix code (PermissionError) and passes on the new code.

### Notes
- All four fixes deployed in one commit because they affect the same user (Ahmed) trying to do his first day of work. The audit script + test are the long-term forcing function — without them we will keep hitting this trap.
- The `bench_dev_overview.*` and `bench_code_health.*` allowlist entries already existed (added in earlier sessions). Today's gaps were `release_group_clone.*`, `bench_vscode.*`, and `press.ai.api.*`.
- `Bench Shell Log` is now writeable via `ignore_permissions=True` from `create_bench_shell_log`. This is the ONLY code path that creates these rows — all callers funnel through `Bench.docker_execute(create_log=True)`. The team-access check on the parent bench remains the real authorisation gate; the audit log is now audit-complete instead of audit-blocked.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — fix(auth+bench): 4-bug perm fix for new team members + dashboard allowlist audit script


## 19-05-2026 — MCP: publish JSON Schema per tool + in-dashboard Test Tool Call form

### Fixed
- **`missing required args: ['query']` / `['site_name']` from `site_run_sql` and `site_status`.** Real call-log evidence: callers sent `{"site": "..."}` and `{"sql": "..."}` instead of the canonical `site_name` / `query`. Root cause: the MCP catalog only published `required_args` as a flat list of names — clients (Claude Code, Cursor, etc.) inferring args from the natural-language `description` field guessed the shorter natural names. No JSON Schema = no contract. Multiple users hit this (call log shows `eng.elgogary@gmail.com`, `markomaher333@gmail.com`).

### Added
- **`args_schema` (JSON Schema fragment) per tool in `press/mcp_server/tools.py`.** All 58 tools now declare `{type: "object", properties: {...}, required: [...]}` with per-arg type + description. Authored via a `_schema()` helper + shared `_ARG_FRAGMENTS` dict so common args (`site_name`, `bench_name`, etc.) have one canonical declaration reused everywhere.
- **Import-time consistency check** (`_assert_schema_covers_required_args`) fires at module load if any `required_args` entry is missing from its `args_schema.properties`. Prevents drift — every future tool added to TOOLS must keep the two in lockstep.
- **`get_tool_help()` now returns `args_schema` in the single-tool response.** MCP-compliant clients can now read the exact param names + types + descriptions without guessing.
- **Enriched dispatcher error message.** When required args are missing, the error now includes `Got: [keys you sent]. Expected: [canonical names]. For the full args_schema, call {tool: 'help', args: {tool: '<name>'}}.` so a misnamed-arg failure is self-explaining instead of "you got it wrong, figure it out".
- **In-dashboard "Test Tool Call" form** on `/dashboard/dev-tools/mcp`. Pick a token, pick a tool from a dropdown of every tool in the catalog, the form reads `args_schema` from the help endpoint and renders one input per arg (text/select for `enum`, checkbox for booleans, textarea for code/sql/objects). Required args are marked with `*`. Submit calls `press.mcp_server.server.handle` directly — same path as external clients — and shows the JSON response inline. Refreshes the Recent Calls table on completion so the user sees their test land.
- **2 new unit tests** in `test_help.py`:
  - `test_every_tool_has_args_schema_covering_required_args` — locks in the registration contract for every tool
  - `test_single_tool_detail_includes_args_schema` — locks in the `site_status` + `site_run_sql` regression specifically

### Notes
- 15/15 `test_help.py` tests pass (was 13/13; +2 new).
- Pre-existing `test_server.py` 4-test failure (SSH cert tests) is unrelated — verified by running on pre-patch tree. Tracked separately.
- The catalog mirror at `dashboard/src/components/mcp/_tool_catalog.js` still only lists tool metadata (category, risk, label, description) — it does NOT carry the schema. That's intentional: the schema source of truth is the backend; the frontend asks `help` at runtime. Avoids duplication and drift.
- `args_schema` is purely additive. External clients that only read `required_args` keep working. No breaking changes.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — feat(mcp): publish JSON Schema per tool + in-dashboard Test Tool Call form


## 19-05-2026 — Press Settings: preserve Password fields on save (stop wiping `__Auth`)

### Fixed
- **Saving Press Settings was wiping every Password field that came in falsy.** Frappe's `Document._save_passwords()` calls `remove_encrypted_password()` on any Password field whose in-memory value is falsy at save time. The desk UI shows `••••` placeholders but doesn't always re-send them — and `frappe.get_single("Press Settings").save()` from console doesn't auto-load passwords into the doc, so the in-memory value is `None` even when `__Auth` has a real encrypted value. Result: any unrelated save (via desk OR console) wiped `offsite_backups_secret_access_key`, `aws_secret_access_key`, and every other Password field on Press Settings. We hit this twice in 48h on `offsite_backups_secret_access_key` — both times the symptom was the same: Clone Site `latest_backup` mode → `Password not found for Press Settings Press Settings offsite_backups_secret_access_key`.
- **Fix: `before_save()` override on `PressSettings`.** Walks every Password field on the doctype, collects fieldnames whose in-memory value is falsy, and adds them to `self.flags.ignore_save_passwords`. Frappe's `_save_passwords()` honours that flag and skips both `remove_encrypted_password()` and `set_encrypted_password()` for those fields, leaving the existing `__Auth` rows untouched. Applies to ALL 15 Password fields on Press Settings (`offsite_backups_secret_access_key`, `aws_secret_access_key`, `twilio_api_key_secret`, `stripe_secret_key`, `razorpay_key_secret`, `remote_secret_access_key`, etc.) so the trap never bites again.

### Added
- **`test_password_preservation_on_save_without_password_resubmit`** in `test_press_settings.py`. Seeds a known secret, re-fetches the Single, changes a non-Password field, calls `.save()`, then asserts the secret is STILL decryptable. Would fail on the pre-fix code (secret wiped) and passes on the new code (secret preserved). 1/1 new test green.

### Notes
- Caveat: if a sysadmin genuinely wants to CLEAR a Press Settings password, they must now do it via `frappe.utils.password.remove_encrypted_password("Press Settings", "Press Settings", fieldname)` directly — saving Press Settings with an empty Password field will no longer wipe the row. For a system-config singleton the tradeoff is correct: cost of accidental wipe (broken offsite backups, restore by hand) >>> cost of needing a console one-liner to clear a credential.
- This is a Frappe-wide UX trap, not just Press Settings. The same risk exists on any DocType with Password fields (User, Email Account, anything with API keys). Fix is generic — copy the `before_save()` pattern to any other Single / singleton-ish doctype where field preservation matters.
- Live incident this morning: `accubuild-stg-qimma.sandbox.mvpstorm.com` clone blocked because the offsite secret got wiped between yesterday's fix and today. Restored via console (copied from `remote_secret_access_key`) — same MinIO user `pressadmin` is shared between the uploads and offsite codepaths so they share the secret.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — fix(press-settings): preserve Password fields on save so __Auth rows don't get wiped


## 19-05-2026 — Clone Site `fresh_backup` mode now actually persists

### Fixed
- **`fresh_backup` mode created the Site Backup row, then `frappe.throw()` rolled it back.** The dialog showed "Fresh backup queued for source site. Wait for it to complete, then retry…" but no Site Backup row appeared, no Agent Job ran, and the user waited forever. Symptom: clone in `fresh_backup` mode → red toast looks right → re-open in `latest_backup` mode after 10 minutes → "No usable offsite backup found". Root cause: `clone_site()` in `site_clone.py` does `source.backup(...)` (which inserts a Site Backup doc) immediately followed by `frappe.throw(...)`. Both run inside the same HTTP request's DB transaction, and `frappe.throw` rolls the whole transaction back — the insert vanishes. Fix is one line: explicit `frappe.db.commit()` between the insert and the throw. Matches the canonical pattern in `press/press/doctype/site/backups.py:357` (`schedule_logical_backups_for_sites_with_backup_time` commits between each per-site backup call).

### Added
- **Regression test `test_clone_fresh_backup_persists_site_backup_row`** in `test_site_clone.py`. Calls `clone_site(mode='fresh_backup')` against a real source (no Site.backup mock — the original test mocked it and so wouldn't catch the rollback), asserts the throw fires, then counts `Site Backup` rows with `offsite=1` for the source site to confirm exactly one new row landed. Fails on the pre-fix code path; passes after the commit is added. Locks the behaviour in.

### Notes
- 11/11 unit tests pass in `test_site_clone.py` (was 10/10 yesterday; +1 for the persistence regression).
- Live impact: `accubuild-stg-qimma.sandbox.mvpstorm.com` had this issue today. Manually triggered an offsite backup via `bench --site demo.mvpstorm.com execute press._clone_trigger.run` (one-off wrapper at `/home/frappe/frappe-bench/apps/press/press/_clone_trigger.py`) to unblock the user; backup `9547t8b5vk` is in flight against MinIO at the time of this commit.
- The original mock-based test (`test_clone_fresh_backup_triggers_backup_then_raises`) kept its place — it documents the INTENT (backup called with the right args, throw fires with right message) but doesn't exercise the transaction. The new test exercises the transaction. Both stay.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — fix(clone-site): commit fresh-backup row before throw so it actually persists


## 18-05-2026 — Dashboard pull/push UX gaps + auth allowlist audit (2 logout fixes)

### Fixed
- **Non-System users force-logged-out after clicking Launch Code Server.** Symptom: `markomaher333@gmail.com` opens `/dashboard/groups/<bench>/actions`, clicks Launch Code Server, gets bounced to `/dashboard/login` within ~10 s. Logs showed the user transitioning logged-in → Guest on `press.press.doctype.bench.bench_dev_watch.get_watch_status` (221 Guest hits in 2k log lines). Root cause: `BenchWatchStatus` Vue panel polls `bench_dev_watch.get_watch_status` every 10 s on the bench Actions page and Site Dev tab. `bench_dev_watch` was added in `2719f44c5c` but never added to `ALLOWED_WILDCARD_PATHS` in `press/auth.py`. The Press auth hook rejected every poll with HTTP 401, the Vue dashboard mapped 401 → "session expired" → force-logout. The click itself was incidental — the next poll tick is what killed the session, but users associated the logout with the click.
- **`/dashboard/code-health` would have logged out non-admin users.** Audit follow-up after fixing `bench_dev_watch`: grep'd every `@frappe.whitelist` under `press/press/doctype/bench/` and cross-referenced against Vue dashboard call sites. Found `bench_code_health.*` (10+ whitelisted methods called from `BenchCodeHealth.vue`, `CodeHealth.vue`, `HealthAdvanced.vue`) also missing from the allowlist. Same 401 → logout pattern would have fired on first visit to the Code Health page or expanding the Site Dev Health panel.
- **Dashboard "How to pull and push code" panel had 3 blocking gaps.** Real-world session (Mahmoud on `bench-0022-000015-press-f1` for `eltarek_dist_app`) showed the panel was wrong on:
  1. **Token lifetime: panel said `~60 min`, actual is `~8 hours`** (`bench-git-setup` issues 480-min tokens — Mahmoud's session showed "token valid ~479 min")
  2. **No `origin` remote check.** Fresh bench containers ship apps with only an `upstream` remote pointing at `file:///home/frappe/context/apps/<app>` — not GitHub. Panel jumped straight to `git pull` which fails with `fatal: 'origin' does not appear to be a git repository`.
  3. **No detached-HEAD check.** Fresh containers come in detached HEAD. Panel said `git pull` would just work — actually fails with `You are not currently on a branch`.
- **Misleading line in SSH tab removed.** Old copy: *"Don't run `git remote add origin` manually — the existing remote is set up by Press"*. In fresh containers there literally is no `origin` to begin with, so the advice was actively wrong.

### Added
- **`DevFlowsGuide.vue`** — Dashboard tab now has a blue Prerequisite callout up front + "If Push fails — common fixes" section covering the 3 real errors users hit (`'origin' does not appear`, detached HEAD, 403). Code Server + SSH tabs got two new steps: **3.5 Make sure `origin` points to GitHub** (with `git remote -v` + `git remote add origin`) and **3.6 Get on a real branch** (with `git status` + `git checkout`/`git switch -c`). Migrate-after-pull reminder. Shared yellow callout now differentiates `bench restart` (recycles processes — files survive) from container *rebuild* (wipes uncommitted work).
- **`ReleaseGroupActions.vue`** — Dev Bench panel ("How to use a Dev Bench") got a blue "Before you push" callout pointing devs at steps 3.5 + 3.6 in the tabs below, so they don't hit the gap blind.
- **Wiki**: `docs/wiki/06-deployment-ops/known-issues-and-fixes.md` got a new "Non-System users force-logged-out when Vue dashboard hits a 401" section — diagnostic playbook (auth.json.log tail + audit script), curl verify procedure, prevention rule, and incident history (3 incidents in 8 days).
- **Audit script** in the wiki — one-shot check that finds every dashboard-called whitelisted method NOT in the allowlist. Run before any PR that adds `@frappe.whitelist()` at a `press.press.doctype.*` path.

### Notes
- **Rule for future PRs:** every PR that adds `@frappe.whitelist()` at a `press.press.doctype.<x>.<y>.<method>` path MUST add `/api/method/press.press.doctype.<x>.<y>.` to `ALLOWED_WILDCARD_PATHS` in `press/auth.py` in the SAME commit. The audit script in the wiki enforces this — zero output = safe.
- **3 incidents in 8 days of the identical 401-allowlist bug pattern**: `cb55aebf6e` (deploy_candidate_build / site_clone / partner_payment_payout, 2026-05-10), `4b775755d0` (press.mcp_server., 2026-05-10), `cb22ec0d53` (bench_dev_watch., today), `6e18abbbfb` (bench_code_health., today audit follow-up). Adding the rule to the runbook + memory file makes this the last one.
- **Audited and confirmed safe** (no allowlist entry needed): `bench.py` controller (Vue uses `press.api.*` wrappers — already covered by `press.api.` wildcard), `bench_vscode.py` (Vue calls via `bench_dev_overview.get_vscode_remote_url` wrapper — already covered), `health_inventory.py` (the `@frappe.whitelist` text is inside a string literal, not a decorator).
- **press-ctrl `.git/objects/` permission gotcha**: during deploy, `sudo -u frappe git fetch` failed with `insufficient permission for adding an object to repository database .git/objects` because 43 object files were owned by `root:root` (someone ran git as root earlier). Fixed with `chown -R frappe:frappe .git`. Rule: ALWAYS use `sudo -u frappe git` on press-ctrl, never bare `git` as root.

### Commits
- `95827c5f48` — `docs(dashboard): close gaps in DevFlowsGuide + Dev Bench panel`
- `cb22ec0d53` — `fix(auth-hook): allowlist bench_dev_watch.* to stop force-logout on Dev pages`
- `6e18abbbfb` — `fix(auth-hook): allowlist bench_code_health.* (audit follow-up to bench_dev_watch)`



## 17-05-2026 — Clone Site dialog rewrite + offsite backups to MinIO end-to-end

### Fixed
- **`Password not found for Press Settings offsite_backups_secret_access_key`.** Offsite-backup credentials were never set on this deployment — Press's MinIO wiring existed only for the `remote_uploads` codepath (frontend file uploads). Backup uploads needed their own credentials. Fix is configuration (copy uploads creds across to the `offsite_backups_*` slots, create a `Backup Bucket` row for `press-uploads`), but the underlying code path requires `462ef02133` + agent fork `809e9c2` (next entry).
- **Agent uploaded to real AWS S3, not MinIO.** `press/agent.py:_get_offsite_backup_config()` was sending the agent only `ACCESS_KEY` / `SECRET_KEY` / `REGION` + `bucket` + `path`. Without `endpoint_url`, the agent's boto3 client defaulted to `s3.amazonaws.com` and rejected the upload with `InvalidAccessKeyId: The AWS Access Key Id you provided does not exist in our records.` Now `_get_offsite_backup_config()` passes `ENDPOINT_URL` (from `Backup Bucket.endpoint_url`) and the agent fork at `Veela-Beauty/press-agent` consumes it in `agent/site.py:upload_offsite_backup`. Same pattern `remote_file.py` already uses for downloads. Backwards compatible: empty `ENDPOINT_URL` → boto3 defaults to AWS S3, AWS users unaffected.
- **`get_backup_bucket()` didn't fetch `endpoint_url`.** Sibling fix in `press/press/doctype/site_backup/site_backup.py` — the helper was selecting only `name` and `region` so even with the agent.py fix, no endpoint would propagate. Now selects `endpoint_url` too.
- **Clone Site dialog rendered Target Bench + Data mode as plain text inputs.** The old `confirmDialog` invocation used `fieldtype: 'Select'` (Frappe casing) on the mode field — frappe-ui's FormControl expects `type: 'select'` (lowercase), so the field silently degraded to text. Target Bench had no type at all. Replaced the inline `confirmDialog` with a proper SFC `dashboard/src/components/site/CloneSiteDialog.vue`. Now: combobox bench picker (filtered to app-superset matches), proper select for mode, live subdomain availability check on blur via `press.api.site.exists`.
- **Clone Site redirect produced `/sites/[object Object]`.** `clone_site` returns `{site, job}` (it proxies through `press.api.site._new`) but the dialog templated the whole object into the URL → 404 from `press.api.client.get`. Now reads `response.site` for the route and `response.job` for the Site Job progress page, matching `NewSite.vue`'s `onSuccess` exactly. Python type hint also corrected from `-> str` to `-> dict`.

### Added
- **Clone Site dialog (`dashboard/src/components/site/CloneSiteDialog.vue`).** Replaces the old plain-text prompt. Five fields:
  - **Target Bench** — combobox of compatible benches (`source.apps ⊆ bench.apps`), team-scoped, plus `➕ Create a new bench` sentinel that pivots to `CloneBenchPrompt` against the source site's release group.
  - **New subdomain** — live availability check on blur with red/green inline feedback, regex pre-check before any network call.
  - **Site Plan** — preselected to source's plan, dropdown of enabled `Site Plan` rows. Without this, Press's `_new` silently dropped unknown plan values and left `Site.plan = None`.
  - **Disk-space banner** — when a real bench is picked, calls `check_bench_space(target_bench, required_bytes = source.current_disk_usage * 1.2)`. Public servers auto-extend so the banner short-circuits to OK. Submit is blocked on insufficient space.
  - **Data mode** — `latest_backup` (default), `fresh_backup`, `empty`, with dynamic hint paragraph.
- **`list_compatible_benches(site)`** in `site_clone.py` — returns benches whose app set ⊇ source apps. Team-scoped: team users see only their team's benches, System Users see all.
- **`get_clone_options(site)`** — single-shot fetch for the dialog. Returns `{compatible_benches, plans, source_plan, source_disk_usage}` so the frontend doesn't make three round trips.
- **`check_bench_space(target_bench, required_bytes)`** — mirrors `press.api.site.validate_restoration_space_requirements` but keyed by bench instead of pre-existing site. Returns `{server, free_bytes, required_bytes, sufficient, is_public_server}`.
- **Optional `plan` parameter** on `clone_site()` so the dashboard can pass an explicit plan (defaults to source's plan, falls back to `"Free"`).
- **Wiki**: `press/docs/wiki/02-operations/backups.md` now has full "Offsite backups to MinIO" section + Clone Site dialog reference (credentials checklist, Backup Bucket row schema, agent fork version requirement, symptom→cause table, file map).

### Notes
- 10/10 unit tests pass in `test_site_clone.py` (8 original + 2 new for `get_clone_options` and `check_bench_space`).
- Agent fork commit `809e9c2` was deployed to **press-f1 only** this round. Roll to u4 and u5 separately when ready — without it, offsite backups on those clusters will silently fail the same way ours did. Tracked as a follow-up.
- The `Backup Bucket.bucket_name` field uses `autoname: field:bucket_name` — when creating new rows programmatically, pass `bucket_name=` (NOT `name=`), otherwise Frappe throws `Bucket Name is required`. Documented in the wiki.
- Pre-existing `Site.plan = None` on `roseline-erpsys` (the test clone) was backfilled via `Site.change_plan('USD 25', ignore_card_setup=True)`. New clones via the patched dialog supply `plan` to `_new` directly so this should not recur — confirm on next clone.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `63c5a0d5fc` — Clone Site dialog with proper dropdowns + bench-clone pivot + `list_compatible_benches`
  - `462ef02133` — Send `ENDPOINT_URL` to agent so MinIO/custom-S3 offsite backups work
  - `5eb0a94f4a` — Redirect uses `response.site` not the whole dict (fixes `[object Object]` 404)
  - `cc417f2cc7` — Plan picker + disk-space pre-check + `get_clone_options` + `check_bench_space`
- Agent fork (`Veela-Beauty/press-agent` `master`):
  - `809e9c2` — Consume `auth.ENDPOINT_URL` in `upload_offsite_backup` so boto3 routes to MinIO



## 12-05-2026 — MCP token issuance: 1–90 day TTL + email-OTP password alternative

### Changed
- **MCP token TTL field switched from minutes (max 1440) to days (1–90), default 7.** Backend `TTL_MAX` in `press/mcp_server/auth.py` bumped from 1440 minutes to `60 * 24 * 90`. UI converts days → minutes before sending. Long-lived agent tokens were the stated need — minute granularity is meaningless past a few hours. The Reissue dialog in `MCPPanel.vue` was switched to days for consistency. Existing tokens are unaffected (their `expires_at` was already set at issue time).

### Added
- **Email-OTP alternative to password re-auth at token issuance.** Users on SSO / forgot-password flows could not issue MCP tokens because the dialog required typing a password. New flow: click *"Forgot password? Use email OTP instead"* → click **Send code** → a 6-digit code is mailed to `User.email`, valid 10 min, one-shot consume, hashed at rest via `passlibctx.hash`. Server-side throttle: max one OTP per username per 30s. IP brute-force gate (5 fails / 5 min → 60 min block) applies to OTP failures the same way it does to password failures. `issue_token` now accepts either `password` OR `otp` — at least one required.
- **New doctype: Press MCP Email OTP** (`press/press/doctype/press_mcp_email_otp/`). Hash-named, transient, System Manager read-only. Fields: `username`, `code_hash`, `expires_at`, `consumed`. No web/dashboard exposure.
- **New whitelisted endpoint: `press.mcp_server.auth.request_email_otp`** — guest-allowed (matches `issue_token`), uses Frappe's `sendmail` (now=True). Silently does nothing if the user doesn't exist or is disabled — never leaks user existence.
- **Wiki page**: `docs/wiki/03-integrations/mcp-server.md` — full token issuance guide (TTL range, both re-auth paths, API contract, doctype shape, operational notes, file map).

### Notes
- Email delivery depends on Press's outgoing Email Account. If `disable_mail_notifications=1` is set in `site_config.json`, turn it off before relying on OTP — the OTP path will silently degrade to "code never arrives".
- No scheduler hook ships for cleaning up consumed/expired OTP rows. They're tiny but a daily prune by `expires_at < now() - 1 day` is reasonable hygiene if rows pile up.
- Deployed to press-ctrl 2026-05-12: patch applied via `git am`, `bench migrate` installed the new doctype, `yarn build` rebuilt the dashboard, web restarted. Live at `https://autodeploypanel.mvpstorm.com/dashboard/dev-tools/mcp`.



## 06-05-2026 — Deploy logout fix + press-f1 MariaDB firewall

### Fixed
- **System Users blocked from deploying cross-team benches.** `get_bench_update()` in `bench_update.py:175` had a second team check after `@protected("Release Group")` that rejected ALL users including System Users. The decorator exempts System Users but the inner function did not — inconsistent. Added `and not is_system_user` to the check so System Users can deploy any bench (matching `@protected` behavior). 1-line fix.
- **Vue dashboard `logoutWithTeamError()` destroyed session on team PermissionError.** `waitUntilTeamLoaded()` in `router.js:712` treated all PermissionError/ValidationError from `getTeam()` as session-invalid — called `session.logout.submit()` which destroyed the Frappe session. Team error != session invalid. Replaced with `localStorage.removeItem("current_team")` + `window.location.href="/app"` — clears stale team, redirects to Desk, no session destruction. 5-second timeout fallback unchanged as safety net.
- **press-f1 MariaDB port 3306 exposed to internet.** Hetzner abuse report (CB-Report#...). MariaDB bound to `0.0.0.0:3306` with no firewall (UFW inactive, iptables empty). Could not change bind-address because Docker bench containers connect via public IP `89.167.57.21:3306`. Applied iptables rules: ACCEPT from press-ctrl, Docker bridge (172.17.0.0/16), localhost; DROP everything else. Installed `iptables-persistent`, rules saved to `/etc/iptables/rules.v4`, `netfilter-persistent.service` enabled.

### Added
- **Wiki: press-ctrl push workaround** in `docs/wiki/06-deployment-ops/press-ctrl-stability-runbook.md`. Press-ctrl deploy keys are read-only — document the bundle-to-Hetzner-dev-box push method.
- **Wiki: press-f1 MariaDB firewall recovery** in same runbook. iptables rule table, verification commands, recovery steps.



## 05-05-2026 — Team permissions: session caps, sane Press Role defaults, actionable 403 hints

### Fixed
- **`User.simultaneous_sessions = 2` evicting active dashboard tabs.** Frappe's `is_whitelisted()` raises identical wording — *"Function X is not whitelisted"* — for both the missing-decorator case AND the guest-not-allow_guest case. With a low session cap, opening a 3rd tab kicked the cookie of an older one; the next click from that tab arrived as Guest and surfaced the misleading whitelist error. New `MIN_SIMULTANEOUS_SESSIONS = 10` in `press/press/doctype/team/team_roles.py`. Patch `v0_0_5/bump_team_member_session_cap.py` backfills every existing Team Member's user.
- **Press Role with all 18 flags = 0 silently locked out members.** A freshly created Press Role started with every boolean flag at 0 — total dashboard lockout for any member assigned. `before_insert` on the Press Role doctype now pre-ticks a 7-flag Developer baseline (`allow_dashboard`, `all_release_groups`, `all_sites`, `all_servers`, `allow_apps`, `allow_bench_creation`, `allow_site_creation`); sensitive flags (`admin_access`, `allow_billing`, `allow_server_creation`, team-management, webhook) stay 0 by default.
- **`raise_not_permitted()` returned generic "Not permitted".** The dashboard 403 toast now names the missing flag — *"Ask your team admin to enable 'all_release_groups' on your Press Role (or grant access to this specific Bench via Manage Team -> Roles -> Resources)."* Driven by a new `_DOCTYPE_TO_FLAG` map (31 doctypes) in `press/api/client.py`. 6 of 7 call sites updated to pass doctype context; the 7th (unwhitelisted-method case in `check_dashboard_actions`) keeps the bare call because that's a developer config error, not a user-actionable role gap.

### Added
- **`Team Member.after_insert` → `ensure_session_cap`** — every newly invited team member gets `simultaneous_sessions = 10` automatically. Hook only raises the cap, never lowers an admin-set higher value. Idempotent.
- **`Press Role.validate` → `warn_if_zero_flag_lockout`** — orange `msgprint` warning *"Empty role — members will be locked out"* fires when a role has users assigned but every flag at 0. Not a hard block — placeholder roles still allowed.
- **Admin guide** at `docs/wiki/01-backend-development/team-roles-permissions.md` (279 lines) — explains the two parallel permission systems (`Team Member.press_role` string vs `Press Role` doctype's 18 booleans), categorizes all 18 flags, ships 5 copy-paste preset recipes (Developer / Site Admin / Ops Admin / Read-only Viewer / Full Admin), and includes a SQL recovery playbook for locked-out members.

### Notes
- Hint-aware errors land in `press.api.client` only — the highest-traffic 403 source (Vue dashboard data loads). `team_guard` decorators + per-method action throws (e.g. `Bench.deploy()`, billing methods) keep their existing wording for now. Same `_DOCTYPE_TO_FLAG` pattern is reusable when extending.
- `accurate-systems/press` is now a GitHub redirect to `Veela-Beauty/press`. press-ctrl's `upstream` remote can return stale fetch content — always use `veela` remote for canonical state.

---

## 22-04-2026 — Admin Panel: Servers tab, live stats, unified rows

### Added
- **Admin Panel sidebar entry** wired in `dashboard/src/components/NavigationItems.vue`. Was previously reachable only via direct `/dashboard/admin` URL.
- **Real Servers tab** in Admin Panel (replaces placeholder). Component at `dashboard/src/components/admin/ServerAdmin.vue`. Shows summary cards (Total / Active / Decommissioned / Effective Cost), table with edit + decommission actions per server.
- **3 Custom Fields** on `Server` DocType via `press/press/doctype/server/server_admin_setup.py`: `monthly_cost_override` (Currency), `is_decommissioned` (Check), `admin_notes` (Small Text). Idempotent setup mirrors `team_admin_setup.py` pattern.
- **3 admin APIs** in `press/api/admin_panel.py`:
  - `get_servers_admin()` — returns one row per physical machine (grouped by IP), with `roles` array
  - `update_server_admin(server, monthly_cost_override, admin_notes)` — edit cost + notes
  - `set_server_decommissioned(server, decommissioned)` — toggle the soft-archive flag
- **Live RAM/CPU/Disk stats** via SSH probe from press-ctrl (new `press/api/admin_panel_stats.py`). Single SSH call per server, cached 60s in `frappe.cache`. Returns total/used/avail RAM, CPU cores + load avg, disk size + used + percentage. Lazy-loaded per row in the UI with color thresholds (green <70%, orange 70-85%, red ≥85%).

### Changed
- **Server rows unified by physical machine.** In standalone-mode deployments where one machine runs Server + Database Server + Proxy Server records on the same IP, the table now shows **one row per machine** with multiple role badges (was: 3 separate rows = 7 total → now 3 rows). Cost / sites / benches / admin overrides are still owned by the `app` role only — no double counting.
- **`_get_server_costs()` and `_calc_team_cost()`** now skip decommissioned servers and prefer `monthly_cost_override` over the hardcoded `SERVER_COSTS` baseline. Teams tab `total_cost` updates accordingly when an admin decommissions a server or sets an override.

### Notes
- Stats collection uses the frappe user's default SSH key (`~/.ssh/id_ed25519`) which Press provisioning already deploys. No new secrets required.
- Decommission is a soft flag — no infrastructure changes are made (agent stays running, sites keep serving). Only excluded from cost rollups + UI signal.

---

## 03-02-2026

### Changed
- Introduced stricter app versioning requirements for all Frappe apps.
- All apps (Marketplace and private) must now:
  - Include a `pyproject.toml` file
  - Declare a bounded Frappe dependency under `[tool.bench.frappe-dependencies]`.
  - Support is only added for NPM based versioning, 

### Breaking Changes
- Apps without a `pyproject.toml` file will fail validation.
- Apps using unbounded Frappe version ranges (e.g. `^`, `~`, or single-sided constraints) are rejected.

### Note on version syntax

Frappe app version constraints are validated using **NPM-style semantic versioning** (`NpmSpec`), in favour of internal frappe applications such as CRM and helpdesk.

As a result:
- Version ranges must follow **NPM semver syntax**
- Python-style version specifiers (PEP 440), such as `~=`, are **not supported**

### Relevant links
https://github.com/frappe/press/issues/4809

### Example
```toml
[tool.bench.frappe-dependencies]
frappe = ">=16.0.0-dev,<17.0.0-dev"
