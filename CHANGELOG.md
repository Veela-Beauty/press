# Changelog

This file documents changes (current commit level since, no tagged releases yet).

---


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
