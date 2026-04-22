# Changelog

This file documents changes (current commit level since, no tagged releases yet).

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
