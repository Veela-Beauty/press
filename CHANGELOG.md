# Changelog

This file documents changes (current commit level since, no tagged releases yet).

---


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
