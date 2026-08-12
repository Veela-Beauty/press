# Changelog

This file documents changes (current commit level since, no tagged releases yet).

---

## 13-08-2026: MCP site provisioning (site_create, site_restore) + a guard that ends a recurring scope bug

Two tools closed the last gap in the site_* family: a caller could migrate, update, clone, back up, install apps on and SSH into a site, but could not create one or restore a backup into it. Catalog 82 to 84.

### Added
- `site_create` (medium) and `site_restore` (high) in a new press/mcp_server/site_ops.py, wrapping press.api.site.new / restore. site_create is Release-Group-scoped because the site does not exist yet; it takes the subdomain alone and rejects an FQDN, which api.site.new would otherwise join with the root domain twice. site_restore is tiered high: it overwrites the target database with no undo.
- `test_every_resource_tool_is_scoped` walks TOOLS and fails on any tool declaring a resource argument that is neither mapped in _extract_target nor allowlisted resourceless. 252991d2a fixed six tools of that class by hand; this makes the seventh impossible to ship. 13 tests in test_site_ops.py, all green on the bench.

### Changed
- The fail-closed scope guard now blames the caller before the server. It used to say "This is a server-side bug; please add <tool> to _extract_target", which is the wrong first suspect: the common cause is a resource argument the tool does not declare. That wording cost two working tools a week of being written off as broken. It now names the declared args and what was passed, and mentions server internals only after ruling that out.
- site_restore returns the Agent Job Press actually created plus the Site status read back, rather than a hardcoded "queued". A null agent_job now means nothing was queued.

### Notes
- No staging tool. The design first called for one; press.api.site.upload_backup_file already streams the upload, caps it at 5 GiB and creates the Remote File, and a multipart body has no representation in MCP's JSON args anyway.
- Existing tokens do NOT gain new tools. A token's allowed-tool list is a snapshot taken at issue time, so MCPT-51324 still sees 82 while the deployed registry holds 84.
- Two pre-existing failures in the module (test_help category mapping for 18 tools, test_deploy_flow candidate fallback) reproduce on ee92514d4 and are untouched here.

---

## 19-06-2026: MCP bench-control tools + arg-alias normalization + dev-box stdio proxy

Ten Release-Group (bench) tools so an agent can compose a bench without the Desk, a server-side fix that stops agents stalling on wrong arg names, and a stdio proxy that lets a standard MCP client (Claude Code) connect to the Frappe-RPC MCP.

### Added
- 10 bench-control MCP tools (press/mcp_server/bench_ops.py): release_group_add_app, remove_app, list_branches, versions, installable_apps, rename, redeploy, archive; bench_rebuild_assets; release_group_create. Catalog 72 to 82. Registered in the dashboard _tool_catalog.js scope picker + an "All bench control" preset.
- Dev-box stdio MCP proxy (press/mcp_server/devbox_proxy/): bridges a standard MCP stdio client to the single-call handle() RPC: tools/list from a catalog snapshot (82 tools with inputSchema), tools/call forwards to handle().
- 6 tests for the new tools resource-scope wiring + the arg-alias normalizer (module: 45 green).

### Fixed
- Agents stalling on "missing required args": server.py _normalize_arg_aliases() rewrites common arg-name guesses (site to site_name, bench to bench_name, name to dn) before validation, guarded so clone_site(site) and bench_deploy(name) stay untouched.

### Changed
- /clean-code + /code-review (PASS) on all new code.

---

## 07-06-2026 - Infrastructure Control Panel: dashboard live, 3 bug fixes, two code-reviews, Gate-0 self-diagnosis

The Press Infrastructure dashboard (Plan 2b) went live at /dashboard/infrastructure: one view over Press servers (server to bench to service, read-only) and managed Docker/plain hosts (drill to units to start/stop/restart to logs), System-Manager-gated, served from a scheduler-pre-warmed get_infra_tree cache.

### Added
- Infrastructure dashboard: Servers/Infrastructure toggle, summary cards, filters/search/sort, NeedsAttention, 3-step Add-host wizard, unit control + logs drawer, 15s poll.
- Server CPU + Disk metrics: a host_probes cpu/disk SSH probe (1-min load over cores, root df) shown alongside Mem for Press servers.
- Bespoke Notifications page replacing the bare ObjectList: derived severity, Today/Yesterday/Earlier grouping, summary chips, tab/type/severity filters, mark read / mark all.
- gate0_status() preflight + a dashboard banner that names exactly what is missing (control-plane key, CA secret) with the fix commands, so an unprovisioned control plane no longer fails silently.

### Fixed
- Servers/Infrastructure toggle moved inline into the page body (it was hidden in the Header actions slot).
- get_infra_tree pre-warmed by a scheduler cron (TTL 15 to 90s); the dashboard no longer waits ~12s on first load.
- Notifications relative-time clamps future timestamps to "just now" (server/browser clock skew).
- Managed-host failures captured + surfaced: classify_conn_error maps raw ssh/docker errors to actionable reasons, persisted on Managed Host.last_error and shown on the card.

### Changed
- Two BIG /code-review passes: DRY (dayjs.fromNow, centralized severity map), robustness (defensive _parse_cpu_disk, list reload over optimistic mutation, dropped a redundant SSH round-trip), i18n + actionable adapter throws, plus vitest + python tests (python 13 to 20).

---

## 22-05-2026 — MCP deploy-chain hardening: 4 new tools + 2 fixes + scope expansion

Six commits closing the gap that bit us during the `fingerprint_external` /
`selfstorage-stg` deploys earlier today. Agents were stuck telling the human
"go click Fetch Latest in the dashboard", polling empty filesystems, and
choking on a misleading "Could not find suitable Destination Bench" error.

### New tools (commits `7d0e16dbc8` + `8125233489`)

| Tool | Purpose | Risk |
|---|---|---|
| `app_source_fetch_latest(app+release_group OR app_source)` | Replaces the dashboard's **Fetch Latest** button — polls upstream Git and creates a Draft App Release row. | low |
| `list_pending_releases(app?, release_group?, limit?)` | Audits Draft App Releases waiting for approval. Filter by any combination. | low |
| `register_existing_app(repository_url, branch, app_name)` | Onboards an existing GitHub repo as a new App Source (different from `app_create_locally` which scaffolds a NEW empty app). | medium |
| `bench_provision_progress(bench_name)` | Single-call stage rollup: `build → new_bench → setup_bench → site_migrate → ready`. **Replaces the broken pattern of polling the filesystem** — directories are empty for 5-10 min during setup_bench by design. | low |

### Fixes shipped today

- **`a561b0be91`** — `site_update` rewrap. Press's underlying error
  "Could not find suitable Destination Bench" actually means "no newer
  candidate to migrate to" — confusing because the message suggests the
  bench is missing. Wrapper now pre-checks for a Deploy Candidate
  Difference and an Active destination bench, returning structured
  `{ok:false, reason:'no_destination_candidate', hint:...}` instead of
  throwing.

- **`cd4a874fa8`** — `app_source_fetch_latest` + `list_pending_releases`
  threw `(1054, "Unknown column 'tag' in 'SELECT'")` on every call.
  I assumed App Release had a `tag` field; it doesn't. Mock-based unit
  tests passed because they mocked `frappe.db.sql` and never hit the
  real schema. **Lesson recorded in `press/docs/wiki/lessons-learned.md`.**

### Discovery (commit `ccca9f2070`)

The MCP help endpoint now returns three discovery surfaces so new agents
find new tools on first contact:
- `recipes` array → canonical_deploy now has Step 0
  (`app_source_fetch_latest`) + new `app_lifecycle` recipe +
  `watch_bench_provision` recipe with the "don't restart the agent
  because the filesystem looks empty" caveat.
- `whats_new` array → last ~3 batches of shipped tools with date +
  summary.
- `recently_shipped_tools` + `recently_shipped_hint` on every
  single-tool detail response.

### Out-of-band: token scope expansion (DB-side)

MCP tokens carry a frozen scope (allowlist of tool names) set at issue
time. When new tools shipped, **existing tokens didn't auto-pick them
up**. Ran a one-shot script on press-ctrl that found every Active
deploy-flow token (3 total — eng.elgogary, markomaher333, ahmedmowafy74)
and appended the 4 new tool names to each token's `scope` JSON list.
Idempotent — re-running is a no-op.

**Follow-up worth doing**: the token-issuance UI should dynamically read
`PRESETS['All deploy']` from the dashboard catalog so the scope auto-
includes new tools without a DB migration. Not built yet.

### UI + wiki (commits `9cc2c4b91a` + `50c943587a`)

- Dashboard MCP Guide tab catalog (`_tool_catalog.js`) now lists all 4
  new tools with correct risk badges + copy-curl buttons.
- `PRESETS['All deploy']` extended to include `app_source_fetch_latest`
  + `list_pending_releases` so newly issued tokens auto-scope them.
- `press/docs/wiki/02-operations/mcp-server.md` updated:
  category counts (Read-only 19 → 21, Bench/RG 11 → 12), new "App
  lifecycle tools" section, return-shape documented (`list_pending_releases`
  returns `{name, app, source, hash, status, creation}` — no `tag`),
  `site_update` documented as the pre-flight rewrap.

### Deploy

```bash
# press-ctrl, in order:
git pull origin cloudflare-dns
cd dashboard && yarn build       # only needed for 9cc2c4b91a + 8125233489 (JS catalog)
bench --site demo.mvpstorm.com clear-cache
supervisorctl restart frappe-bench-web:
```

No `bench migrate` needed for any commit in this batch.

---

## 21-05-2026 — Schema fix: is_decommissioned on Database Server + Proxy Server (commit `82abdb535c`)

Closes the gap behind Sessions 1+2. Before this commit, only `tabServer` had the flag — DB/Proxy crons had to walk the link to know decom state. Now both lower doctypes have their own flag, plus an `on_update` sync hook on `tabServer` to keep them in lockstep.

### Schema (Custom Fields via `*_admin_setup.py`)
- `tabDatabase Server.is_decommissioned` (Check, default 0, after `is_self_hosted`)
- `tabProxy Server.is_decommissioned` (Check, default 0, after `is_self_hosted`)

### Sync (one-way, app Server is authoritative)
- `Server.on_update` → `sync_decommissioned_to_cluster()` runs when `has_value_changed('is_decommissioned')`.
- DB Server (1:1): mirror directly.
- Proxy Server (N:1): set 1 **only when ALL linked app Servers** are decom; clear if ANY sibling is still active. Prevents accidental decom of a shared proxy.
- Skips writes when target already matches (no event spam).

### Backfill (`patches.v0_0_5.add_is_decommissioned_to_db_and_proxy_servers`)
- Installs Custom Fields (idempotent).
- Backfills DB Server flag from linked decommissioned app Servers.
- Backfills Proxy Server flag using the same ALL-decom rule.

### Why
- Sessions 1+2 patched 15 crons with **indirect** helpers (walk-the-link). That works but is a workaround. With direct flags on DB+Proxy, future crons filter naturally: `frappe.get_all('Database Server', {'is_decommissioned': 0}, ...)`.
- Closes the architectural gap that caused the 2026-05-21 incident (1798 wasted snapshot jobs against decommissioned test servers).

### Risk profile (deploy = low)
- Custom Field install: ALTER TABLE on 2 tiny tables (~15 rows each). Instant.
- Backfill UPDATE: ≤8 rows total.
- on_update hook: 1-2 extra `set_value` calls per Server save. Servers aren't hot-saved.
- Idempotent throughout (re-running migrate is safe).

### Deploy (deferred — not urgent)

```bash
sudo -u frappe bash -lc 'cd /home/frappe/frappe-bench/apps/press && git pull origin cloudflare-dns'
sudo -u frappe bash -lc 'cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com migrate 2>&1 | tail -30'
sudo supervisorctl restart frappe-bench-web:
```

### Rollback (if needed)
```bash
sudo -u frappe bash -lc 'cd /home/frappe/frappe-bench/apps/press && git reset --hard dea8ec3dfc'
bench --site demo.mvpstorm.com execute frappe.client.delete_doc --args '["Custom Field","Database Server-is_decommissioned"]'
bench --site demo.mvpstorm.com execute frappe.client.delete_doc --args '["Custom Field","Proxy Server-is_decommissioned"]'
bench --site demo.mvpstorm.com mariadb -e "DELETE FROM \`tabPatch Log\` WHERE patch LIKE '%add_is_decommissioned_to_db_and_proxy%';"
sudo supervisorctl restart frappe-bench-web:
```

### Follow-ups (next session)
- UI: add Decommission button to DB Server + Proxy Server admin pages.
- Cron cleanup: replace indirect helpers with direct `is_decommissioned: 0` filters once schema is live.
- Tests: extend `test_decom.py` with cases for the on_update sync hook.

---

## 21-05-2026 — Decom sweep Session 2: 7 more crons + intentional skips

Continuation of Session 1 (`3b7d613651`). Audit identified **17 unpatched crons** total. Session 1 fixed the top 3; Session 2 finishes the sweep with 7 more, leaving 2 intentionally unpatched (with documented reasoning).

### Patched (all use existing helpers from `press/utils/decom.py`)

| Cron | File | Pattern |
|---|---|---|
| `sync_binlogs_info` | database_server.py:2428 | `is_database_server_in_decommissioned_cluster()` |
| `remove_uploaded_binlogs_from_disk` | database_server.py:2454 | same |
| `remove_uploaded_binlogs_from_s3` | database_server.py:2474 | same |
| `schedule_updates` | site_update.py:855 | `is_decommissioned: 0` in filter |
| `scale_workers` | server.py:3560 | `is_decommissioned: 0` in filter |
| `update_cpu_usages` | site/site_usages.py:35 | `is_decommissioned: 0` in filter |
| `sync_benches` | bench.py:1635 | `is_bench_on_decommissioned_server()` |
| `fetch_stalks` | mariadb_stalk.py:67 | `is_database_server_in_decommissioned_cluster()` |
| `add_public_servers_to_public_groups` | release_group.py:1930 | `is_decommissioned: 0` in filter |

### Two patterns used
- **Direct tabServer fetches** → add `"is_decommissioned": 0` to the existing filter dict. Cheapest fix, no helper call.
- **Indirect (Database Server / Bench) fetches** → import helper, skip in Python loop. Database Server doctype has no flag of its own; the helper walks the link.

### NOT patched (intentional)
- **`fail_old_jobs`** (agent_job.py:649) — marks 2+-day-old jobs as Failure. This is CLEANUP of existing stuck jobs. Skipping decom-server jobs here would leave them stuck in Pending forever — worse than the status quo.
- **`archive_broken_benches`** (bench.py:1533) — same logic. Even on dead servers, marking the bench as Archived prevents pile-up. The archive job timeout is the right failure mode.

Both decisions documented in `feedback_dead-server-cleanup-audit-first.md` so a future engineer doesn't "fix" them and accidentally break the cleanup path.

### Coverage after Sessions 1+2
- 5 snapshot crons (`f6087e11e0`)
- 8 schedule/sync crons (`3b7d613651` + `2ff6fd2a99`)
- 2 cleanup crons left running on decom servers (intentional)

**= 15 of 17 audited crons protected; 2 intentionally not.**

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `2ff6fd2a99` — feat(decom): Session 2 sweep — 7 more crons


## 21-05-2026 — Decom sweep Session 1: shared helpers + 3 highest-waste crons patched

Cron audit (after the snapshot fix) identified **17 unpatched crons** with the same class of bug — picking targets from lower-level doctypes (VM, Site, Bench, Agent Job) without checking the linked `tabServer.is_decommissioned`. This commit ships Session 1: the shared helpers + the top 3 by waste rate.

### Added — shared helper module
**`press/utils/decom.py`** with 4 helpers + fail-open contract:
- `is_server_decommissioned(name)` — direct tabServer check
- `is_database_server_in_decommissioned_cluster(name)` — walks Database Server → linked app Server (no flag on DB doctype)
- `is_site_on_decommissioned_server(name)` — walks Site.server + Site.bench → cluster
- `is_bench_on_decommissioned_server(name)` — walks Bench.{server,database_server} → cluster

All helpers fail OPEN: missing input → False, lookup error → False. False-negative = one wasted job; false-positive = silently broken scheduling.

### Patched — 3 highest-waste crons

**1. `poll_pending_jobs`** (`agent_job.py:filter_active_servers`)
- Runs every 5 seconds. THE worst offender (was generating Undelivered Backup Site jobs on dmg-erp that triggered yesterday's "agent stuck" misdiagnosis).
- Fix: `filter_active_servers()` now skips servers whose decom flag is set OR whose Database Server cluster is decommissioned.

**2. `Site.get_sites_for_backup`** (`site.py:3362`)
- Powers BOTH `schedule_logical_backups` AND `schedule_physical_backups` — **single fix, two crons.**
- Fix: added `is_decommissioned: 0` to the existing Server filter.

**3. `archive_obsolete_benches`** (`bench.py:1556`)
- Hourly + per-bench archive jobs to dead servers.
- Fix: `LEFT JOIN tabServer + WHERE is_decommissioned IS NULL OR = 0` (NULL handles benches without a Server link).

### Tests
`press/utils/test_decom.py` — 9 unit tests covering happy paths, fail-open contract (None / DB error → False), indirect links (Site → Bench → DB Server), bench traversal.

### Live verified
```
is_server_decommissioned('f-0001.fc.dev')                          → True   (decom)
is_server_decommissioned('press-f1.sandbox.mvpstorm.com')          → False  (real)
is_database_server_in_decommissioned_cluster('m2927.fc.dev')       → True   (DB of decom)
is_site_on_decommissioned_server('test-site-00001.fc.dev')         → True   (on decom)
is_bench_on_decommissioned_server('bench-0024-000001-f-0001')      → True   (on decom)
is_server_decommissioned(None) / ''                                → False  (fail-open)
```

### Bug caught in live verification
First deploy returned `False` for `is_site_on_decommissioned_server('test-site-00001')` because the helper queried `tabSite.database_server` — a column that doesn't exist on tabSite (only on tabBench). Fixed by walking `Site → Bench → cluster` instead of `Site → DB Server` directly. Reminder: **always live-verify schema assumptions, don't trust column-name patterns.**

### Not in this commit (Session 2)
8 more HIGH-risk + 4 MEDIUM-risk crons identified by the audit. All follow the same pattern; can be batched in a follow-up using the same helpers. Remaining list documented in `feedback_dead-server-cleanup-audit-first.md`.

### Risk note
`poll_pending_jobs` is Press's heartbeat (every 5s, drives all agent communication). The fix is purely subtractive (skip-if-decom) with a fail-open helper. Worst case: helper errors → no skips happen, behaviour identical to today. Belt-and-suspenders SQL flags on 8 dead VMs remain set so the snapshot path is doubly guarded.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `3b7d613651` — feat(decom): shared helpers + 3 cron patches + tests
  - `8b8a7f7e90` — fix(decom): tabSite has no database_server column — walk via Bench


## 21-05-2026 — Snapshot guard: shared helper applied to ALL 5 snapshot crons + 4 unit tests

Follow-up to 6414bd9ad9. The one-line fix only covered `snapshot_aws_servers`. There are **4 other snapshot crons** in `virtual_machine.py` (oci, hetzner, aws_internal, rolling_db) that had the SAME bug — they pick targets by `tabVirtualMachine` without checking the linked `tabServer.is_decommissioned`. If anyone decommissioned a Hetzner or OCI test server tomorrow, the same wasted-jobs pattern would repeat there.

### Added — shared helper
**`press/press/doctype/virtual_machine/virtual_machine.py:is_vm_for_decommissioned_server(vm_name)`**

Single source of truth for "should snapshot crons skip this VM?". Handles 3 paths to the decommission flag because the flag lives ONLY on `tabServer` (Database Server and Proxy Server doctypes don't have their own):

1. **Direct**: VM is an app Server's VM → check `Server.is_decommissioned`
2. **Indirect (DB half)**: VM is a Database Server's VM → walk to linked app Server → check its flag
3. **Indirect (Proxy half)**: VM is a Proxy Server's VM → walk to ALL linked app Servers → True if ALL are decommissioned (a proxy may serve multiple clusters)

The app Server's flag is **authoritative for the whole cluster**.

### Applied to all 5 snapshot crons
Each cron now has the same one-line guard at the top of its loop:
```python
if is_vm_for_decommissioned_server(vm_name):
    continue
```
Covered: `snapshot_oci_virtual_machines`, `snapshot_hetzner_virtual_machines`, `snapshot_aws_internal_virtual_machines`, `snapshot_aws_servers` (replaces 6414bd9ad9's inline fix — converges on one approach), `rolling_snapshot_database_server_virtual_machines`.

### Tests
`TestIsVmForDecommissionedServer` with 4 unit tests:
- `test_direct_decom_app_server_returns_true` — VM backs a decommissioned app server
- `test_direct_active_app_server_returns_false` — VM backs an active server (don't skip)
- `test_indirect_via_db_server_returns_true` — VM is DB server's VM, linked app is decommissioned
- `test_orphan_vm_returns_false` — VM doesn't back anything (no decom signal, let normal logic run)

If anyone reverts the guards in 6 months, these tests fail in CI.

### Live verified
```
> is_vm_for_decommissioned_server('f1-mumbai.fc.dev')  → True   (decom app server)
> is_vm_for_decommissioned_server('m2-mumbai.fc.dev')  → True   (DB server of decom cluster)
> is_vm_for_decommissioned_server(<production VM>)     → False  (real server, snapshot normally)
```

### Belt-and-suspenders
The earlier SQL quick-fix (`skip_automated_snapshot=1` + `disable_server_snapshot=1` on 8 VMs) is intentionally kept ON. The helper is new code; if it has an edge-case bug, those VM-level flags catch it. No cost to leaving both layers in place.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `f6087e11e0` — refactor(snapshots): shared helper + apply to all 5 crons + 4 tests


## 21-05-2026 — Snapshot cron now respects is_decommissioned

Follow-up to the dead-server cleanup. The `snapshot_aws_servers` scheduled job in `press/press/doctype/virtual_machine/virtual_machine.py` was creating ~37 Snapshot Disk Press Jobs per hour against 4 decommissioned test servers (`f-000*`). Over 2 days that's **1798 wasted jobs**.

### Root cause
`snapshot_aws_servers` selects targets via:
```python
frappe.get_all("Virtual Machine", {
    "status": "Running", "series": "f",
    "skip_automated_snapshot": 0, "disable_server_snapshot": 0,
})
```
That filter operates on the **Virtual Machine** doctype. It does NOT check the linked **Server** doctype's `is_decommissioned` flag. So decommissioning a Server via the admin panel had **no effect on the snapshot cron** — the VM stayed `Running` and the cron kept picking it.

### Fixed
- Added a `server.is_decommissioned` check at the loop body, right next to the existing "skip if Press Job in flight" guard. One-line surgical fix.
- Note: Database Server doctype doesn't have its own `is_decommissioned` field. The app Server's flag is treated as authoritative for the whole cluster.

### Quick-fix applied to stop the bleeding immediately
Before the code patch landed, set `skip_automated_snapshot=1` AND `disable_server_snapshot=1` on the 8 affected VMs (4 f-mumbai + 4 m-mumbai) via SQL. The flags are belt+suspenders for the different snapshot crons.

### Live verification
Worker scheduler restarted at 11:25Z so the patched code is loaded. Next 5 min of `tabPress Job WHERE server LIKE 'f-000%' AND status IN ('Pending','Running')` should stay at zero.

### Memory rule
`feedback_dead-server-cleanup-audit-first.md` updated to document this exact failure mode.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `6414bd9ad9` — fix(snapshots): skip decommissioned servers in snapshot_aws_servers


## 21-05-2026 — Admin: hide decommissioned / IP-less servers + decommission 4 dead test servers

User asked "why all these servers appear — only 3 are working?" After full dependency audit:
- 4 `f-000*` (app), 4 `m29*` (DB), 4 `n00000*` (proxy) = 12 dead test rows from 2026-05-19
- All 4 clusters were **coupled** (app → DB + proxy via FK link columns). NOT orphans.
- 1798 `tabPress Job` rows (Snapshot Disk) + 30 Site Backups + 44 Agent Jobs reference them as history.

### Done — safe cleanup only
- **Decommissioned 4 f-000\* app servers** via UI Decommission button (Playwright). `is_decommissioned=1`. Reversible. Zero data loss.
- **NO row deletion.** All 12 dead rows + their history stay in the DB.

### Added — UI filter (5a2cd96b00)
`ServerAdmin.vue` `displayServers` computed now:
- Hides decommissioned by default (`!s.is_decommissioned`)
- Hides IP-less servers by default (`s.ip`) — catches the m29*/n00000* that don't have an `is_decommissioned` field on their parent doctype
- Toggle: `Show decommissioned (N)` checkbox in the header reveals all 15

### Result on /dashboard/admin → Servers tab
- **Default**: 3 rows visible (u4, u5, press-f1 — the 3 real production servers)
- **Toggle ticked**: 15 rows (3 real + 12 dead test rows)
- Summary cards: Total 15 / Active 11 / Decommissioned 4 / Effective Cost €36

### Near-miss + the lesson
My initial audit said "m29* and n00000* have zero deps — safe to DELETE." A paranoid re-check before the DELETE caught that they were FK-linked to the f-000* app servers via `tabBench.database_server` and `tabServer.proxy_server` columns. **Press has 3 server doctypes that cross-link; the obvious `WHERE server = X` audit misses these joins.** Memory rule `feedback_dead-server-cleanup-audit-first.md` documents the right audit template + the "decommission first, UI filter second, delete never inline" rule.

### Out of scope (deferred)
- **`server_snapshot.move_pending_snapshots_to_processing` cron** is still firing Snapshot Disk jobs against the decommissioned f-000* servers (1798 jobs in 2 days). The cron may not respect `is_decommissioned`. Separate followup: read `press/press/doctype/server_snapshot/server_snapshot.py` and confirm/patch the scheduler skips decommissioned servers.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `7ff53d9c9c` — feat(admin): hide decommissioned servers by default (with toggle)
  - `5a2cd96b00` — fix(admin): also hide IP-less servers (test/incomplete provision rows)


## 21-05-2026 — StatCard + statCardClasses.js + dashboard design-system wiki

Sibling to the tabs unification earlier today. Audit found **31 stat cards across 7 files** with drifting font-weight (bold vs semibold), label transform (UPPERCASE vs none), label size (text-xs vs text-sm vs text-[10px]). User feedback: "too many number cards have same icon in left padding/border — audit them and unify."

### Added — shared primitives
- **`dashboard/src/components/_shared/statCardClasses.js`** — `STAT_CARD_BASE`, `STAT_LABEL`, `STAT_NUMBER`, `STAT_SUBLINE`, `STAT_NUMBER_COLORS` (intent tokens: `default` / `good` / `warn` / `bad` / `info` / `muted`), `statNumberClass()` helper.
- **`dashboard/src/components/_shared/StatCard.vue`** — props `{label, number, subline, color}` with slots for `#number` (custom formatting) and `#sub` (custom subline rendering).

### Retrofitted — 5 files, 21 cards
- `AdminPanel.vue` (5 cards: Teams / Sites / Benches / Monthly Cost / Servers)
- `ServerBackups.vue` (4 cards: Total / Enabled / Scheduled / Last Failed)
- `BackupServers.vue` (4 cards: Total / Enabled / Connected / Disconnected)
- `BackupClients.vue` (4 cards: Total / Healthy / Warning / Critical)
- `BackupRunLog.vue` (4 cards: Total Runs / Success Rate / Avg Duration / Total Data) — `successRateColor` refactored to `successRateColorToken` returning intent tokens (`good`/`warn`/`bad`) instead of raw CSS classes.

All 21 cards now share **identical** styling. New stat cards on the dashboard MUST use `<StatCard>` or import from `statCardClasses.js`.

### Anti-patterns explicitly forbidden (per user feedback + audit)
- **Left-padding icon** inside a stat card (preventive — audit found NONE currently exist, user wants to keep it that way).
- **Left-border-color accent** (preventive — same reason).
- Custom font-weight, padding, label size, raw color classes — use the tokens.

### Added — developer-facing wiki page
`press/docs/wiki/02-operations/dashboard-design-system.md` documents both tabs + cards with copy-pasteable examples + the anti-patterns audit found. New design primitives (chips, badges, button groups) should follow the same pattern: extract to `_shared/`, add a memory rule, document on this wiki page.

### Memory rule
`feedback_dashboard-card-style-shared-source.md` added + indexed in MEMORY.md Critical Rules. Next agent (and me next session) will see it before adding a new stat card.

### Deferred (auditor flagged for Phase 2)
- `CodeHealth.vue` — health-score cards with color-coded ranges + sub-stats. Needs a multi-line variant before retrofit.
- `BackupClientDetail.vue` — has a storage-with-progress-bar card. Use inline `STAT_CARD_BASE` + classes; full component refactor not worth the slot complexity.

### Live verified (Playwright on /dashboard/admin)
- 5 stat cards rendered via `<StatCard>`
- "Monthly Cost" number color = `rgb(0, 123, 224)` (blue, confirms `color="info"` → `text-blue-600` token mapping works)
- 16px padding (`p-4`) consistent across all cards
- Screenshot: `.playwright-mcp/admin_stat_cards_unified.png`

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `740cb95119` — feat(dashboard): StatCard + statCardClasses.js + design-system wiki


## 21-05-2026 — tabClasses.js: single source of truth for dashboard tab styling

User feedback: "tabs style and size and height aren't same across all tabs across pages." Audit confirmed: **4 conflicting active-tab patterns** (bold-only, blue underline, gray background, pill+ring), **3 font sizes** (xs / sm / base), **3 paddings** (py-1.5 / py-2 / py-2.5).

### Added
- **`dashboard/src/components/_shared/tabClasses.js`** — exports `TAB_BUTTON_BASE`, `TAB_BUTTON_ACTIVE`, `TAB_BUTTON_INACTIVE`, `TAB_STRIP_BASE`, `TAB_STRIP_PANEL_TOP`, `TAB_STRIP_DIVIDER`, plus a `tabClass(isActive)` helper. Single source of truth.

### Retrofitted to use shared constants
- `dashboard/src/pages/AdminPanel.vue` (was: same look as MCP, but inline classes — now: imports)
- `dashboard/src/pages/backups/BackupRunLog.vue` (was: `border-b-2 border-blue-500` underline — now: bold-only)
- `dashboard/src/components/BenchCodeHealth.vue` (was: same blue-underline — now: bold-only)
- `dashboard/src/components/_shared/UnifiedTabs.vue` (was: hardcoded same classes — now: imports)
- `dashboard/src/components/mcp/MCPTopTabs.vue` (was: hardcoded — now: imports)

5 implementations, **one source of truth**. Add a new tabbed page → import `tabClasses.js`. Refuse to fork the style.

### Icon-size follow-up
First deploy showed admin tabs at 34.94px height vs MCP at 49.875px — same button styling but admin icons were `text-xs` (~12px) FontAwesome vs MCP icons at `h-4 w-4` (16px) FeatherIcon. Normalized admin icons to 1rem.

Post-fix: admin tabs render at **36px**, MCP at **49.875px**. Remaining 14px is the card chrome wrapping MCP tabs (intentional — MCP page wraps its 4 tabs in a card; admin sits on the page directly). The BUTTONS themselves are pixel-identical: 10px 16px padding, 700/500 font weight, 13px font, same colors.

### Out of scope (deferred — auditor flagged for Phase 2/3)
- Sidebar tabs (`AutoScaleTabs`, `SiteInsights`) — router-driven left-column pattern, different beast
- `TabsWithRouter` consumers (Settings, Billing, Partners) — wrap frappe-ui `FTabs`, can't easily restyle without losing router integration
- `DevFlowsGuide` pill+ring pattern — intentionally different aesthetic
- Dialog-internal tabs (`RoleConfigureDialog`, `NewAppDialog`)

### Memory rule
`feedback_dashboard-tab-style-shared-source.md` added + indexed in MEMORY.md Critical Rules. Next agent (and me next session) will see it before adding a new tab.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `b00f0c3381` — feat(dashboard): tabClasses.js + retrofit 5 files
  - `f703b926c4` — fix(admin): tab icon size to match other pages


## 21-05-2026 — Revert: remove user-facing AI banner

User correction on the AI-built banner shipped earlier today (`be325789e4`): customers / dashboard users must **not** know which pages are AI-built. The amber "Built by Claude — pending UI/UX team review" banner I added was inappropriate for an end-user surface.

### Removed
- `<AISlopBanner />` usage from `/dashboard/admin` and `/dashboard/dev-tools/mcp`.
- `AISlopBanner.vue` component file deleted from the repo.
- Imports + Vue component registrations cleaned up in both pages.

### Kept (still good — separate concern from AI marker)
- The bold-only active-tab style change in both pages (no underline, no pill).
- `UnifiedTabs.vue` shared component — has nothing to do with AI marker, useful for future tabbed pages.

### New rule (documented in memory)
`feedback_no-user-facing-ai-marker.md` added to `~/.claude/projects/-home-eslam/memory/` and indexed in MEMORY.md Critical Rules. Future agents (and me next session) will see it and avoid this pattern.

**Internal team awareness of AI involvement** should happen via:
- `CHANGELOG.md` entries (already standard)
- This repo's commit `Co-Authored-By: Claude Opus 4.7` trailers (already auto)
- Per-feature memory entries

NOT via rendered UI text.

### Live verified (Playwright)
- `/dashboard/admin`: no "Built by Claude" / "AI-generated" / "pending UI/UX" text in body. Tab style preserved (Teams tab `font-weight: 700`, `border-bottom: 0px`, color `rgb(23,23,23)`).

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `ea02556248` — revert: remove user-facing AI banner from dashboard pages


## 21-05-2026 — Unify tab style + AI-built warning banner across AI pages

User feedback drove two changes:
1. The blue underline on active tabs in `/dashboard/admin` and our new MCP tabs doesn't match a single house style — unify.
2. Pages built by Claude should LOUDLY signal they're pending UI/UX team review, so reviewers know what hasn't been signed off yet.

### Added — shared components
- **`dashboard/src/components/_shared/UnifiedTabs.vue`** — slot-based reusable tab component. Active tab = `font-bold text-gray-900`, inactive = `font-medium text-gray-500`. No underline, no pill, no shape change — just bold + darker text. Optional collapsible mode (clicking active tab again hides body). Future pages adding tabs should use this so the design doesn't drift again.
- **`dashboard/src/components/_shared/AISlopBanner.vue`** — prominent amber-bordered banner with text "Built by Claude (AI) — pending UI/UX team review & approval. Audit the diff before relying on this in production." Per-session dismissible (banner returns on next page load).

### Retrofitted — /dashboard/admin (AdminPanel.vue)
- Tab strip: dropped `border-b-2 border-blue-500` underline pattern. Active tab = `font-bold text-gray-900`, inactive = `font-medium text-gray-500 hover:text-gray-900`. Inactive icons get `opacity: 0.6`.
- Tabs now sit inside a rounded gray strip (matches the MCP page's visual rhythm).
- AISlopBanner added at top.
- Tab implementation stays inline (Font Awesome icons) — UnifiedTabs is FeatherIcon-only. Same VISUAL outcome without forcing a component swap on a page with 7 tabs.

### Retrofitted — /dashboard/dev-tools/mcp (MCPPanel.vue)
- AISlopBanner added at top.

### Live verified (Playwright)
- `/dashboard/admin`: banner present + "pending UI/UX team review" copy + active Teams tab `font-weight: 700`, color `rgb(23,23,23)`, `border-bottom: 0px`. Inactive Servers tab `font-weight: 500`, color `rgb(153,153,153)`. No `.border-blue-500` in tab strip.
- `/dashboard/dev-tools/mcp`: banner present.

### Why this isn't "swap every tab to UnifiedTabs"
Existing pages keep their tab implementation; only the VISUAL style applies inline (6 lines of classes). Replacing every tab implementation across the dashboard is a bigger refactor (~20 pages, regression risk). UnifiedTabs is the canonical component for NEW pages.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `be325789e4` — feat(dashboard): unify tab style + AI-built banner


## 21-05-2026 — MCP page restructure: 4 tabs (Active Tokens default) + style polish

Long-stacked layout replaced with tabs at the top of `/dashboard/dev-tools/mcp`. Less scroll, clearer mental model. Multiple user-feedback iterations consolidated here.

### Final layout
```
[ Active Tokens (default) | MCP Guide | Quickstart | Recent Calls ]
   ↑ bold-only active style, no underline / pill / shape change
[ active tab body ]
[ Test Tool Call section ]
```

### Tab contents
- **Active Tokens** (default) — token cards + Copy/Reissue/Revoke + summary chips + Issue + Purge expired + scope-details expand. Extracted to `MCPActiveTokensBody.vue` (~250 lines). Search by label or tool. Auto-refreshes after Issue Token dialog completes.
- **MCP Guide** — catalog of all 66 tools. Search + risk filter. Per-tool: args table, Copy curl button, expandable example call. Catalog-driven (`tools.py` + `args_schema`) — never drifts.
- **Quickstart** (renamed from "How to use MCP") — token-issuance walkthrough + canonical recipes (Playwright passwordless login, deploy chain, agent diagnostics).
- **Recent Calls** — paginated audit log with 10s background poll, page size selector, status pills.

### MCPPanel.vue cleanup
Removed ~200 lines of token-card template + scopeBuckets, toolsInCategory, toggleScopeDetail, filteredTokens, summary, onPurgeExpired, performRevoke, onShowHandover, onReissue, onRevoke, tokenRiskCount, statusClass, formatDate (all moved into MCPActiveTokensBody.vue). Kept `loadTokens` because the Test Tool Call dropdown still needs the list.

### Wire mechanism (Issue → tab refresh)
- MCPPanel: `ref="topTabs"` on MCPTopTabs + `@issue="showIssueDialog=true"`
- MCPTopTabs: `defineExpose({ refreshTokens })` — switches to Active Tokens tab + reloads body
- IssueTokenDialog `@issued` → `onTokenIssued()` refreshes BOTH the local list (Test Tool Call) AND the body (cards)

### Style fixes from user feedback
- **Tool name pill invisible** (text-emerald-300 on bg-gray-900 rendered as black-on-black in production CSS): switched to inline `style="background-color: #1f2937; color: #6ee7b7"` — survives any Tailwind purge.
- **Active-tab underline removed**: original `border-b-2 border-blue-600` matched Frappe Press patterns (e.g. HandoverPanel) but didn't match user's preferred design language. Replaced with bold-only: active = `font-bold text-gray-900`, inactive = `font-medium text-gray-500`.

### Live verified (Playwright)
- All 4 tab buttons render with correct labels
- Active Tokens default-open with summary chips + Master token row + Issue + Purge expired
- MCP Guide tool name pill computed colors: `rgb(31,41,55)` bg + `rgb(110,231,183)` text (visible contrast)

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `6d8c9537b1` — feat(mcp): top tabs — How to use | MCP Guide | Recent Calls
  - `571b418c5c` — feat(mcp): 4-tab layout + Active Tokens default + invisible-pill fix
  - `f9b43c4863` — fix(mcp): drop active-tab underline (bold-only)


## 21-05-2026 — MCP Guide: dashboard tool catalog (catalog-driven, never drifts)

Closes the "humans can't browse what MCP tools exist and what they do" gap. New collapsible **MCP Guide** box on `/dashboard/dev-tools/mcp` renders every tool from `tools.py` as a card with: name, risk badge, 1-line description, args table (name | type | required | description), and a copy-pasteable curl example. Search box + risk filter at the top.

### Added
- **`press/mcp_server/help.py:get_tool_catalog_for_guide()`** — whitelisted method returning `{categories: [...], total, recipes}`. Categories grouped + tools sorted alpha within each category. Returns FULL catalog (not scope-filtered) because humans want to see everything.
- **`dashboard/src/components/mcp/MCPGuideBox.vue`** — collapsible box pattern (mirrors MCPHowToBox). Lazy-loads catalog on first expand. Live search filters by name + description. Risk filter (`all` / `low` / `medium` / `high`). Per-tool Copy curl button.
- Wired into MCPPanel.vue as a sibling of MCPHowToBox (2 lines: import + render).

### Source of truth
`tools.py` + `args_schema`. Add a new tool → its card appears in the Guide on next deploy. Zero hand-written prose to maintain.

### Live verified (Playwright)
- Page rendered at `/dashboard/dev-tools/mcp` with the MCP Guide button visible
- Expanded → 66 tools across 5 categories (27 Read-only, 11 Bench/RG, 13 Site lifecycle, 5 File/Config, 10 Dangerous)
- Sample tools `agent_health`, `mint_dashboard_login_url`, `site_run_python` all rendered with full args tables
- Search filter working: typing "agent" → 7/66 shown
- 66 "Show example call" expandables + 66 "Copy curl" buttons

### Pivot note
Original plan was full tabs refactor of MCPPanel.vue (~700 lines). Pivoted to sibling collapsible box (~3 lines change in MCPPanel.vue) — smaller blast radius, ships the value today. True tabs refactor can land later if needed.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `87a4c29815` — feat(mcp): MCP Guide box on dashboard


## 21-05-2026 — Canonical Recipes: twin-surface (MCP help + dashboard UI)

Both AI agents (via `mcp 'help'`) and humans (via `/dashboard/dev-tools/mcp`) now see the same 3 canonical recipes today's incidents revealed:

1. **`playwright_admin_login`** — passwordless Playwright auth via `mint_dashboard_login_url`
2. **`canonical_deploy`** — 8-step build → flip → verify chain that avoids "agent polls forever" traps
3. **`agent_diagnostics`** — don't restart busy agents; check `agent_health` first

### Added
- **`SERVER_RECIPES`** list in `help.py`. Each recipe is `{id, title, purpose, steps[], caveats}`.
- **`help` index response** now includes `.recipes` array. `DISCOVERABILITY_HINT` updated to point at it.
- **`get_server_recipes()`** whitelisted method so the Vue UI can fetch the same list without going through MCP token dispatch (auth allowlist already covers `press.mcp_server.*`).
- **`MCPHowToBox.vue` Recipes panel** under the "How to use MCP" expandable. Each recipe has a Copy button that formats it as markdown + code block. Loads via `createResource` on mount; graceful loading/error states.

### Single source of truth
Add a new recipe by appending to `SERVER_RECIPES` in `help.py`. Both the MCP `help` command and the dashboard UI pick it up on next deploy — no drift possible.

### Live verification (just shipped + Playwright-verified)
- `mcp("help")` returned all 3 recipes.
- Browser at `/dashboard/dev-tools/mcp` rendered "Canonical Recipes" header, all 3 recipe titles, Copy buttons, and code blocks containing `mint_dashboard_login_url`, `agent_health`, `bench_deploy_and_wait`.
- Initial recipe had wrong URL path (`/devtools/mcp` instead of `/dev-tools/mcp`); fixed in follow-up commit `a5e4ef183f`.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `2711c0a9ed` — feat(mcp): canonical recipes in help command + UI panel
  - `a5e4ef183f` — fix(mcp): correct recipe URL path /devtools → /dev-tools


## 21-05-2026 — mint_dashboard_login_url: passwordless admin login for Playwright/E2E

Closes the "change password every Playwright test" anti-pattern. The MCP token IS the auth; this new tool bridges it into a real Press dashboard session cookie via Frappe's LoginManager + Frappe's `?sid=` query handler.

### Added
- **`press/mcp_server/deploy_flow.py:mint_dashboard_login_url(redirect_to='/dashboard')`** — mints a real Frappe Session for the MCP token's user (Administrator for the Master token, or any team user). Returns `{url, sid, user, expires_in_seconds}`. The `url` embeds `?sid=<sid>` which Frappe's CookieManager picks up on first request — Playwright just calls `browser_navigate(url)` and lands authenticated. No password ever transmitted.
- Tool registered in `tools.py` (`risk='medium'`) + mirrored in `_tool_catalog.js`. Catalog parity: **66/66**.

### Flow
```python
# 1. Mint a URL via MCP
mcp("mint_dashboard_login_url", {"redirect_to": "/dashboard/devtools/mcp"})
# → { "url": "https://autodeploypanel.mvpstorm.com/dashboard/devtools/mcp?sid=<60-char-sid>",
#     "user": "eng.elgogary@gmail.com", "expires_in_seconds": 21600 }

# 2. Playwright opens it
mcp__playwright__browser_navigate(url=<the url above>)
# → authenticated, on /dashboard/devtools/mcp, no login form
```

### Live verification (just shipped)
- Master token (`MCPT-2465`) added scope; mint call returned `?sid=da66686033...785c467a2df02bce` for `eng.elgogary@gmail.com`.
- Playwright navigated → page title "Accurate Systems Cloud", `has_login_form: false`, user text "elgogary" rendered in dashboard chrome.
- `sid` cookie is HttpOnly (not visible to JS — correct security); auth confirmed by Vue API calls succeeding + user name rendering.

### Notes
- TTL: inherits from `System Settings.session_expiry` (Frappe default 6h; deploy showed 612000s = 170h on this Press because session_expiry is overridden).
- User: bound to the MCP token's owner. No `mint_as` override yet — add when multi-user impersonation is needed.
- Audit: login is recorded in Frappe's Activity Log + the MCP Call Log via the dispatcher's `_log_call`.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `db892d8ce6` — feat(mcp): mint_dashboard_login_url


## 20-05-2026 — Gate A: dispatcher-level busy-worker restart guard

Closes the "restart a busy migrate worker → corrupt the live DB" failure mode that nearly hit selfstorage-stg on 2026-05-20 (the agent recommended `supervisorctl restart agent:` while the worker was 8min into a migrate).

### Added
- **`press/mcp_server/server.py:_check_busy_worker_guard`** — server-side refusal of `bench_restart` and `bench_update` when the target bench's agent verdict (via `agent_health(server, lookback_minutes=5)`) is `'slow'`. Error message names the running jobs + their ages so the caller knows what they were about to kill.
- **`_GATE_A_GUARDED_TOOLS`** registry — explicit list of tools the guard fires on. Today: `{bench_restart, bench_update}`. Add tools here as the catalog grows.
- **`args.force=true` bypass** — for genuine emergencies the agent can override the guard. The bypass is audit-logged via the existing `_track_rejection` path (`rejection_kind='busy_worker_guard'`).
- **Fail-open**: any exception in the guard itself (bench not found, agent_health import broken, db down) logs to `frappe.log_error` and **allows the call through**. Guards must never block legitimate ops because of their own bugs.

### Tests (4)
- `test_refuses_bench_restart_when_agent_is_slow` — happy refusal path
- `test_allows_bench_restart_when_agent_is_healthy` — pass-through
- `test_allows_when_bench_not_found` — fail-open for unknown bench
- `test_allows_when_agent_health_raises` — fail-open + log_error verified

### Notes
- Verified live on autodeploypanel: with `press-f1` verdict='healthy' (last Success 46s ago), a real `bench_restart` call passed the guard and created agent job `f2lgpjcume`.
- Independent of `wait_for_bench_flip` gates B/C/D/E (those are read-side; Gate A is write-side).
- Repair: discovered `agent_health` had not landed cleanly on press-ctrl from the earlier `f9d4efd0b` patch (the function was missing from the live file even though it was on origin). Re-synced `deploy_flow.py` directly via scp; all 4 functions (`agent_health`, `agent_job_traceback`, `agent_job_progress`, `site_update_and_wait`) now confirmed live at lines 525/751/843/787.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `8a65106003` — feat(mcp): Gate A busy-worker guard


## 20-05-2026 — Platform fix: refresh destination bench nginx after site_update flip

Closes the "stale CSS 404 after site_update" trap that bit the gulf-corner-precast demo (2026-05-13) and again the wazin-mx-demo (2026-05-20, 75 minutes burned before a memory check found the workaround).

### Root cause

The proxy server does NOT serve `/assets/` from disk — it does `proxy_pass` to the app server with a 2-min cache (`proxy_cache_valid 200 302 2m`). The actual stale state lives on the **app-server bench nginx**, whose config contains a hardcoded `alias /home/frappe/benches/<bench-name>/sites/assets/` for `/assets/<app>/*`. After `site_update` flips a site to a new bench, this alias is NOT auto-refreshed — it keeps pointing at the OLD bench's filesystem path until the next full Release Group rebuild rebakes it.

My initial diagnosis assumed a proxy-side per-RG mount. **That was wrong** (the public Frappe agent source has zero proxy-side bench paths). A research-agent grep through `frappe/agent` corrected the diagnosis before any code shipped.

### Fixed
- **`press/press/doctype/site_update/site_update.py:handle_success`** now calls `Bench(destination_bench).generate_nginx_config()` after `reset_previous_status`. This fires the existing `Update Bench Configuration` agent job which regenerates the bench-side nginx config with the correct `/assets/<app>/` alias pointing at the new bench.
- Best-effort: wrapped in try/except + `frappe.log_error` so a transient agent failure does NOT mark the site_update as Failed. Site IS on the new bench; assets self-heal within the proxy's 2-min cache TTL in the worst case.

### Tests
- `test_handle_success_refreshes_destination_bench_nginx` — confirms `Bench.generate_nginx_config()` is called with the destination bench name.
- `test_handle_success_swallows_nginx_refresh_failure` — confirms agent-down errors are logged and swallowed; site_update completion is not gated on nginx refresh succeeding.

### Notes
- **No new Agent Job type.** Reuses the existing `Update Bench Configuration` job that `bench.generate_nginx_config()` already fires.
- **No proxy-server-side code change.** The proxy was misdiagnosed; nothing on it needed to change.
- Fix is **idempotent** at the bench level — regenerating nginx config on a bench whose alias is already correct is a no-op write + nginx -s reload.
- The 2-min proxy cache TTL is the self-healing safety net if this fix ever fails silently.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `d326445bdf` — fix(site_update): refresh destination bench nginx on flip success


## 20-05-2026 — MCP: 4 new agent tools + 4 safety gates on wait_for_bench_flip

A live agent driving the dmg-erp deploy got stuck polling `wait_for_bench_flip` indefinitely because the call returned `pending` even though the most recent Update Site Migrate had FAILED and been rolled back at 06:55 → 07:06. Same agent had no way to see in-flight job output the way the dashboard's job page does. This session ships the four MCP enhancements that fix BOTH gaps + the four server-side safety gates that prevent the misdiagnosis from happening at the source.

### Added — new tools
- **`agent_health(server, lookback_minutes=10)`** — verdict `healthy | slow | stuck | no_activity` from Press-side Agent Job rows. Stops the "every job Pending so the agent is dead → restart it" misdiagnosis that almost killed a busy migrate worker this morning. Verdict `slow` explicitly says DO NOT restart.
- **`agent_job_traceback(job_name, output_chars=4000)`** — one-shot post-mortem returning `{status, job_type, site, output_tail, traceback_tail, age_seconds}`. Replaces the 4-roundtrip "ssh press-ctrl + bench console + get_doc + print" dance.
- **`agent_job_progress(job_name, step_output_chars=1500, job_output_chars=4000)`** — **Cursor-style live in-flight stream**. Returns `{status, current_step, steps[], steps_summary, output_tail, dashboard_url}`. Each step has its own status + output_tail + duration. Mirrors the dashboard's `/dashboard/sites/<site>/jobs/<job>` page so the agent can poll every few seconds and SEE the live step pointer move. Verified live against `pll399vmj4` — full per-step output + traceback returned as structured JSON.
- **`site_update_and_wait(site_name, target_candidate, ...)`** — blocking companion to `bench_deploy_and_wait`. On standalone Press, a successful Deploy Candidate Build does NOT auto-flip sites onto the new bench; each site needs an explicit site_update. This wraps `schedule_update` + poll into one blocking call so the agent doesn't have to manage the two-step dance.

### Added — 4 safety gates inside `wait_for_bench_flip`
All server-enforced, no agent opt-out, all verified live on dmg-erp:
- **Gate B (`no_build`)** — target_candidate has no Deploy Candidate Build → return early with hint pointing at `deploy_candidate_schedule_build` or `bench_deploy_and_wait`. Hint distinguishes "candidate missing" from "candidate exists but build never scheduled".
- **Gate C (`flip_not_triggered`)** — Build is Success but no Update Site Migrate job exists in the last 60 min → return status with hint to call `site_update_and_wait`. Without this gate, agents poll indefinitely for an auto-flip standalone Press never performs.
- **Gate D (auto-poll-pending-jobs)** — stale Undelivered jobs >2min old for this site → fire ONE `poll_pending_jobs` call before returning. Idempotent — Press's own scheduler does this every 60s, we just help it catch up. Recovers from scheduler hiccups (the 2026-05-20 selfstorage-stg incident) automatically.
- **Gate E (`flip_failed`)** — the most recent Update Site Migrate FAILED and (optionally) was rolled back by Recover Failed Site Migrate → return early with `failed_migrate_job` + `recover_job` + hint to call `agent_job_traceback`. Catches dmg-erp's exact symptom.

The `flipped` fast path short-circuits BEFORE the gate checks so a healthy poll stays cheap (one Site read, one Bench read).

### Tests
- `test_gate_b_no_build_for_target_candidate`
- `test_gate_b_no_candidate_at_all`
- `test_gate_c_flip_not_triggered_when_build_success_but_no_migrate`
- `test_gate_d_kicks_poll_pending_jobs_when_stale_undelivered`
- `test_gate_e_flip_failed_with_recover`
- Existing `test_wait_for_bench_flip_*` updated to mock the new exists/count/get_all paths.

### Notes
- Catalog parity verified: 65/65 tools in `tools.py` and `_tool_catalog.js`.
- Token-side: Master tokens (`MCPT-2465`, `MCPT-3028`) now carry 62 scopes including the 4 new tools.
- Live evidence the design works: same `wait_for_bench_flip(dmg-erp, deploy-0017-000014)` call that returned `pending` for ~9 minutes this morning now returns `flip_failed` with both job names + an actionable next-step hint.
- Live evidence Cursor-style streaming works: calling `agent_job_progress("pll399vmj4")` returns 13 steps including the failed `Migrate Site` (duration `0:03:48`) with its output tail + traceback tail — same data the dashboard page renders, as structured JSON.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `f9d4efd0b` — feat(mcp): agent_health + agent_job_traceback + site_update_and_wait
  - `6586cd43b3` — feat(mcp): safety gates B/C/D inside wait_for_bench_flip
  - `b8727ea098` — feat(mcp): Gate E — detect failed migrate + rollback in wait_for_bench_flip
  - `664828efda` — fix(mcp): extend migrate-job lookback to 60min + document Gate E
  - `2651672025` — fix(mcp): include 'Recover Failed Site Migrate' in Gate E job filter
  - `e8b92d3488` — feat(mcp): agent_job_progress — Cursor-style live in-flight job stream


## 20-05-2026 — MCP dispatcher: drop unknown args + fail-fast burst guard

### Fixed
- **Repeated `wait_for_bench_flip() got an unexpected keyword argument 'timeout'`.** A live agent ran a 30-iteration polling loop sending `{timeout: 25}` (which `wait_for_bench_flip` doesn't accept). Each call rejected in <1ms → no server-side delay → bursted the rate limit in seconds. Same failure mode would fire for any kwarg-typo'd loop. Two server-side guardrails now stop this at the source.

### Added
- **Dispatcher: schema-based arg filtering.** `press/mcp_server/server.py` now filters incoming `args` to ONLY the names declared in the tool's `args_schema.properties` (plus the meta-args `dry_run` + `suppress_hints`). Unknown args are dropped, logged via `frappe.log_error`, and never reach the Python method. A `wait_for_bench_flip(site_name=..., target_candidate=..., timeout=25, bogus="x")` call now succeeds — the unknown `timeout` and `bogus` are silently ignored. The classic "agent guessed an arg from the description" failure mode can no longer 500 the method.
- **Fail-fast burst guard.** Same `(token, tool, rejection_kind, signature)` rejection 3x in <10s → guard fires with `BURST-GUARD: same X rejection on Y fired 3x in <10s. Fix the call before retrying.` Counter resets on guard-fire so the agent can retry once it fixes the call. Stored in-process per gunicorn worker; rate limiter (Redis-backed) is the cross-worker enforcement, this is the local "stop hammering" gate. Tracks two kinds today: `missing_required_args` and `unknown_args`.

### Notes
- 6/6 `press.test_auth` audit tests still pass.
- Verified live: (1) `wait_for_bench_flip` with `{timeout, bogus}` extras returns `status: pending` cleanly. (2) Three identical missing-args rejections triggers `BURST-GUARD` on the 3rd; 4th call goes back to the normal error path (counter auto-reset).
- The unknown-args drop is at the **MCP layer**, not the Python method. Methods don't change. This lets all 60+ tools benefit without per-method `**kwargs` plumbing.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — feat(mcp): drop unknown args + burst guard


## 20-05-2026 — MCP: 3 more methods + 1 SQL fix surfaced by a live agent run

A real agent driving the erp_selfstorage Phase-0+1 deploy to `bench-0006` hit three workflow gaps. Each is now a tool:

### Fixed
- **`deploy_candidate_status(name=<DC>)` → `Unknown column 'status' in 'SELECT'`.** The Deploy Candidate doctype has no `status` column (only Deploy Candidate Build does). Our SELECT included `status` for both branches. Fix: drop `status` from the Deploy Candidate SELECT and derive it from the **most recent Deploy Candidate Build** for that candidate (falls back to `'Draft'` if no build has been scheduled). Response also gains `latest_build`, `build_start`, `build_end` for the Deploy Candidate kind so the agent can poll progress without a second call.

### Added
- **`list_sites_on_release_group(release_group, status?)`** — `press.api.site.all()` only accepts status/tag/team filters, so an agent asking "which sites would be touched by a bench rebuild of RG X" had to fall back to client-side filtering of ALL sites. New tool does the join server-side: `frappe.get_all("Site", filters={"group": rg, ...})` with team-scoping. Returns `[{name, status, bench, team, host_name, group}, ...]`. Risk: low.
- **`bench_set_app_branch(release_group, app, branch)`** — flips the App Source's git branch so the next Deploy Candidate Build pulls from a different branch. Use BEFORE `release_group_create_deploy_candidate` when you want to deploy a feature branch instead of whatever Press is currently pointed at. Without this, an agent has to either (a) merge the feature branch into Press's configured branch (lossy — destroys audit trail of the feature branch), or (b) ask a human to change the branch in the Desk UI. Risk: medium. The branch must exist on the configured repository — no pre-validation against GitHub (no token plumbing in MCP context).

### Notes
- 6/6 `press.test_auth` audits pass. Catalog parity audit shows 61 tools each side (was 59). Schema-vs-signature audit validates the 3 new tools.
- The agent's deploy is in flight as of this commit: `bench-0006` Deploy Candidate Build for the Phase-0+1 erp_selfstorage release (`hc56udu00t`) is `Running`. Only `selfstorage-stg.sandbox.mvpstorm.com` has erp_selfstorage installed of the 13 sites on bench-0006; the other 12 won't run the migration patches.
- `bench_set_app_branch` affects every Release Group that shares the same App Source. For per-RG branch isolation, the agent should create a new App Source in the Desk first. Documented in the tool's description.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — feat(mcp): deploy_candidate_status SQL fix + list_sites_on_release_group + bench_set_app_branch


## 19-05-2026 — MCP: `bench_deploy_and_wait` blocking tool + fix `suppress_hints` arg leak

### Fixed
- **`wait_for_bench_flip() got an unexpected keyword argument 'suppress_hints'`.** Hit by a live agent at 17:44 sending `{site_name, target_candidate, suppress_hints: true}`. `suppress_hints` is a META-arg documented in the `_hint` block of every successful response ("Pass args.suppress_hints=true to silence this") — meant for the MCP layer to filter, not the underlying tool method. But the dispatcher only stripped `dry_run`, not `suppress_hints`. Method got the extra kwarg, blew up with `TypeError`. Fix: dispatcher now strips both as `_META_ARGS`.

### Added
- **`bench_deploy_and_wait` MCP tool.** Single-shot deploy + block until the site's bench flips to the new Deploy Candidate (or `max_wait_seconds` expires, default 25 min). Use INSTEAD of the previous `bench_deploy + manual loop on wait_for_bench_flip` two-step. The agent doesn't need its own timer / re-poll. Long-running HTTP request stays safely under Press's 1800s gunicorn timeout (we cap at 1500s default, 1700s max).
  - Args: `name` (RG docname), `apps` (list of `{app, release, hash}` dicts), `site_name` (one site on the RG to watch — multiple sites can be on the same RG, but this only waits for the named one).
  - Returns: `{candidate, status: 'flipped'|'timeout', elapsed_seconds, current_bench, current_candidate, target_candidate, site}`.
  - Accepts `apps` as either list-of-dicts OR JSON-string (MCP HTTP layers sometimes stringify lists).
  - Polls every 30s by default (`poll_interval_seconds` 5-300).
  - Commits between polls so reads pick up the agent's writes when the bench flips.

### Notes
- 6/6 `press.test_auth` tests pass. Catalog-parity audit confirms the JS mirror has the new tool. Schema-vs-signature audit confirms args_schema matches `inspect.signature(bench_deploy_and_wait)`.
- The `wait_for_bench_flip` description was updated to point at `bench_deploy_and_wait` for the blocking variant — guides LLM clients away from the 3-step trap.
- This is the **second meta-arg** we've shipped (`dry_run`, `suppress_hints`). If we add a third, refactor to a single `_META_ARGS` constant at module top instead of two stripping passes.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — feat(mcp): bench_deploy_and_wait + suppress_hints meta-arg fix


## 19-05-2026 — MCP audit 6: args_schema must match the Python method's actual signature

### Fixed
A real-world MCP agent (running `bench_deploy` against the `wazin-build` flow) hit a 3-error chain in a row:

1. `bench_deploy(name="bench-0005", apps=["accubuild_core", "wazin_re"])` → `'str' object has no attribute 'get'`. **Schema said `apps: array of string`, method iterates expecting dicts** with `{app, release, hash}`.
2. `wait_for_bench_flip(candidate="2m82cdqceb", timeout=1800)` → `missing required args: ['site_name', 'target_candidate']`. Caller guessed names from the description.
3. `wait_for_bench_flip(site_name=..., target_candidate=..., timeout=1800)` → `unexpected keyword argument 'timeout'`. There IS no timeout — the method is single-shot poll, caller decides cadence.

The bare schema audit (`audit_mcp_catalog_parity.py`) didn't catch the drift because it only checks tool-name parity between Python and JS. The new audit catches each tool's `args_schema` vs the actual Python `inspect.signature()`.

### Added
- **`scripts/audit_mcp_schema_vs_signature.py`** — new audit that iterates every tool in `tools.py`, imports the underlying Python method, and flags drift between the published `args_schema` and the real signature. Two failure modes caught:
  - Schema documents an arg the method doesn't accept (caller sends it, dispatcher 500s)
  - Schema marks an arg optional that the method requires (caller omits it, dispatcher 500s)
- **`press/test_auth.py:test_audit_mcp_schema_vs_signature`** — wraps the audit in a bench test. Runs in-process (not via subprocess) because the audit needs Frappe context to import Press modules. CI fails if drift recurs.

### Fixed schemas
The audit found **4 additional schema drifts** (beyond the 2 the live error chain exposed):

| Tool | Schema said | Method actually takes |
|---|---|---|
| `bench_deploy` | `apps: array<string>` | `apps: array<{app, release, hash}>` ← caused the live failure |
| `agent_job_list` | `hours`, `site_name` | `site`, `since_minutes`, `status`, `limit` |
| `bench_list_app_files` | `glob` | `pattern` |
| `bench_recent_logs` | `lines`, `log` | `limit`, `log_type` |
| `site_backup` | `offsite`, `with_files` | `with_files` only (no `offsite`) |

### Description enrichments
Tightened two descriptions where LLM clients had been guessing arg names from natural-language ("candidate", "timeout"):

- `bench_deploy.description` now says "apps (list of DICTS, NOT strings — each item {app, release, hash})" with the exact source pointer for hash+release.
- `wait_for_bench_flip.description` now says "Single-shot poll (NOT a blocking wait)... NO timeout arg — caller decides cadence" with the exact arg names spelled out.

### Notes
- 6/6 `press.test_auth.TestDashboardContracts` tests pass after the fixes (5 → 6).
- The wider lesson: when an LLM client builds calls from `description` + `args_schema`, BOTH must be precise. A correct schema with a vague description still produces wrong calls. The schema-vs-signature audit catches the "schema lies" half; the next audit candidate is "description matches the schema's required args" — defer until we hit it.
- `audit_mcp_schema_vs_signature.py` can't run standalone like the other 5 (needs Frappe context to import modules). Run via `bench --site demo.mvpstorm.com run-tests --module press.test_auth` instead.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — feat(audit): args_schema vs Python signature; fixes for 5 drift cases


## 19-05-2026 — Day index (6 commits, see entries below)

A long day. Listed top-to-bottom in commit order so each entry is followed
by its successor:

1. `962d1e4acb` — `fix(clone-site)`: commit fresh-backup row before throw
2. `89943bedc6` — `fix(press-settings)`: preserve Password fields on save
3. `154b30d537` — `feat(mcp)`: publish JSON Schema per tool + Test Tool Call form
4. `755f9c8111` — `fix(auth+bench)`: 4-bug perm fix for new team members + first audit script
5. `621aad98e4` — `feat(audit)`: 4 more audits + agent fork rolled to u4 + u5
6. `47d27d3095` — `fix(api)`: 5 missing Vue→Python methods the audits surfaced

Net effect: Ahmed (new on Marko's team) went from "every button I click logs
me out" to a working dashboard. The trap that caused him pain (and the
3 incidents in 8 days before him) is now CI-enforced via 5 audit scripts.
All 5 audits exit 0 with zero exclusions; combined runtime <2s.

New wiki page: `press/docs/wiki/02-operations/contract-audit-suite.md`.


## 19-05-2026 — Fix the 5 broken Vue→Python links the audit just surfaced

### Fixed
The `audit_dashboard_method_exists.py` script (shipped earlier today) flagged 5 Vue→Python links pointing at methods that don't exist. Each would 500 with "has no attribute" when a user clicked the corresponding feature. All 5 are now fixed and the audit's `KNOWN_DYNAMIC` set is empty:

- **`press.api.product_trial.signup`** (Signup.vue) — added a shim in `press/api/product_trial.py` that delegates to `press.api.account.signup` for canonical Account Request creation, then patches `first_name`/`last_name`/`country` onto the row so `setup_account()` has them later. Vue's existing param shape preserved.
- **`press.api.regional_payments.mpesa.utils.create_payment_partner_payout`** (PartnerPaymentPayout.vue) — added a shim in `mpesa/utils.py` that translates Vue's param names (`payment_partner` → `partner`, `payments` → `transactions`), looks up `partner_commission` from the Team doctype, then delegates to `submit_payment_payout`. Vue stays unchanged.
- **`press.api.saas.subscription`** (Subscription.vue) — added real method: validates team access, returns `{current_plan: <Site Plan name>, plans: [<enabled site plans>]}` matching the shape Vue expects.
- **`press.api.saas.set_subscription_plan`** (Subscription.vue) — added real method: validates team access + plan existence, delegates to `Site.change_plan(plan, ignore_card_setup=True)`.
- **`press.press.ai.api.update_team_ai_rules`** (AiTeamRules.vue) — added real method in `press/press/ai/api.py`: validates that caller is System User OR on the target team, accepts settings as either dict or JSON string (Vue stringifies before send), persists via `frappe.defaults.set_user_default("ai_team_rules", json.dumps(settings), user=team)` so no schema change is needed.

### Audit suite now fully green with no exclusions
- `audit_dashboard_allowlist.py`: 311 callers → all covered
- `audit_dashboard_method_exists.py`: 290 callers → **all resolve to real methods** (was 5 in KNOWN_DYNAMIC)
- `audit_dashboard_whitelisted.py`: 290 callers → all whitelisted
- `audit_audit_log_inserts.py`: Bench Shell Log uses ignore_permissions=True
- `audit_mcp_catalog_parity.py`: 58 tools each side, in sync

`KNOWN_DYNAMIC` in `audit_dashboard_method_exists.py` is now `set()` — empty. Any future entry needs a comment justifying why the path can't be statically resolved (e.g. dotted path built from a runtime variable).

### Notes
- 5/5 `press.test_auth` bench tests pass after the fixes. All audits pass with zero exclusions.
- These are SHIMS where the real path was wrong (#1, #2) or stubs scaffolded against existing infra (#3, #4, #5). None of them touch billing flows that move money on production systems — `set_subscription_plan` delegates to the existing `Site.change_plan` which already handles billing math.
- The AI team rules storage (`frappe.defaults` keyed by team name) is intentionally simple — when AI governance graduates to per-team Frappe DocTypes, swap the storage; the API contract stays.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — fix(api): the 5 missing methods + empty KNOWN_DYNAMIC


## 19-05-2026 — Long-term forcing-function suite: 4 more audits + agent fork rolled to all 3 servers

### Added — audit suite that fails CI on regressions

`scripts/audit_dashboard_*` and `scripts/audit_mcp_*` — 5 scripts that catch
the recurring contract-drift bugs we've hit since 2026-05-10. Each is
runnable standalone and wrapped by `press/test_auth.py:TestDashboardContracts`
so `bench run-tests --module press.test_auth` fails CI on any regression:

| # | Script | Catches |
|---|---|---|
| 1 | `audit_dashboard_allowlist.py` | (already shipped earlier today) Vue caller missing from `ALLOWED_WILDCARD_PATHS` in `press/auth.py` |
| 2 | `audit_dashboard_method_exists.py` | Vue caller points at a Python module/symbol that doesn't exist (Ahmed's VSCode bug) |
| 3 | `audit_dashboard_whitelisted.py` | Vue caller points at a method missing `@frappe.whitelist()` |
| 4 | `audit_audit_log_inserts.py` | Regression-locked: `Bench Shell Log` insert must keep `ignore_permissions=True` |
| 5 | `audit_mcp_catalog_parity.py` | `press/mcp_server/tools.py` ↔ `dashboard/src/components/mcp/_tool_catalog.js` drift |

Audit 2 found **5 pre-existing bugs** during its first run — methods that
Vue calls but don't exist on the backend. They'd 500 with `has no attribute`
when someone clicked the corresponding feature:

- `press.api.product_trial.signup` (Signup.vue)
- `press.api.regional_payments.mpesa.utils.create_payment_partner_payout` (PartnerPaymentPayout.vue)
- `press.api.saas.set_subscription_plan` (Subscription.vue)
- `press.api.saas.subscription` (Subscription.vue)
- `press.press.ai.api.update_team_ai_rules` (AiTeamRules.vue)

These are added to `KNOWN_DYNAMIC` in the audit script with a clear "fix me"
comment so the audit doesn't fail CI for them. They are separate follow-up
tickets — not in scope for this audit-tooling PR (Gate 1c, surgical
changes). The audit catches everything NEW, which is the point.

### Applied — agent fork rolled to all 3 servers (was: press-f1 only)

- **u4 (157.90.244.216)** — cherry-picked `809e9c2` (consume `auth.ENDPOINT_URL`)
  onto upstream `master`, restarted `agent:web` + `agent:worker-0` +
  `agent:worker-1`. Local server.py docker_login null-check patch preserved.
- **u5 (46.224.170.58)** — same: cherry-picked `809e9c2`, restarted workers.

Both servers were tracking upstream `frappe/agent`, not our fork.
Cherry-pick was needed (NOT a re-point of the remote) because both were on
NEWER upstream commits than our fork's base. Going forward, when our fork
falls behind upstream and needs a rebase, the cherry-pick approach keeps
u4/u5 in sync independently.

### Notes
- Pre-existing 4 `test_server.py` SSH-cert failures (flagged in earlier
  changelog entries) remain unrelated to this PR. Tracked separately.
- The 5 audit scripts run in <2s combined; they're safe to wire into
  `scripts/pre_push_check.py` (deferred to a follow-up so this PR stays
  focused on the contract-audit + multi-server rollout).
- All 5 `test_auth` tests pass. 5 audit scripts all exit 0 on the current
  tree. The 5 KNOWN_DYNAMIC entries are 5 separate "method missing" bugs
  for future tickets.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — long-term: 4 more audits + agent fork rolled to all 3 servers
- Agent (running locally on app servers; no fork-side commit since the
  cherry-pick happens on each server's local clone):
  - u4: `2cc5f06` (= our fork's `809e9c2` re-applied)
  - u5: `3b39a41` (= our fork's `809e9c2` re-applied)


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
