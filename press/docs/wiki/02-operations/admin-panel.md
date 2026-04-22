# Admin Panel

The Admin Panel is the platform-level control surface for Press administrators — team quotas, server cost & lifecycle, AI governance, and policy. Lives at `/dashboard/admin`.

**Audience:** users with `User.user_type = "System User"` (a.k.a. desk users).
The sidebar entry only appears when `Team.is_desk_user` is true; the API additionally enforces System User check via `_require_admin()` so non-admins can't reach it by URL.

## How to access

1. Sign in to the dashboard as a System User (e.g. `Administrator` or any team member with `is_desk_user=1`).
2. Click **Admin Panel** in the left sidebar (last item, ShieldCheck icon). Or navigate directly: `/dashboard/admin`.

Press standalone hosts: bench site is `demo.mvpstorm.com`, served via the dashboard domain (e.g. `autodeploypanel.mvpstorm.com`).

## Tabs

| Tab | Purpose |
|---|---|
| **Teams** | All teams with site / bench quotas, member counts, monthly cost, block / unblock |
| **Servers** | Per-physical-machine admin: cost overrides, decommission, live RAM/CPU/disk |
| **AI Governance** | Global rules + role-level AI limits (read-only summary) |
| **Escalations** | AI action escalation queue (open / approved / denied) |
| **Usage & Cost** | AI token usage by user + period selector |
| **Policy** | AI Usage Policy text + agreement gate |

## Servers tab — what to look at

Each row is **one physical machine**, even when it runs multiple Press roles (Server + Database Server + Proxy Server). The Kind column shows the active roles as colored badges (`app` blue, `db` purple, `proxy` green).

### Reading the stats

Three columns load asynchronously via SSH from press-ctrl, cached 60 s in `frappe.cache`:

- **RAM** — `used / total` GB and `used %`
- **CPU Load** — `load1 / cores` and `load1 / cores %` (1-minute average)
- **Disk** — `used / total` GB and `used %` for the root mount

Color thresholds:

- 🟢 **Green** `< 70 %` — healthy
- 🟠 **Orange** `70 – 85 %` — investigate
- 🔴 **Red** `≥ 85 %` — upsize candidate

If SSH fails (firewall, key missing, host down), the cell shows `err` with the reason on hover. Non-`app` rows and decommissioned rows show `—`.

### Editing a server

Click **Edit** on a row to open the dialog. Fields:

- **Monthly Cost Override (€)** — overrides the hardcoded `SERVER_COSTS` baseline in `press/api/admin_panel.py`. Set `0` to use the baseline. Useful when Hetzner pricing changes mid-month or when the server has add-ons (extra disk, dedicated IP) not reflected in the plan name.
- **Admin Notes** — free-form text. Use for contract end dates, vendor ticket numbers, ops context.

Saved values write to `Server.monthly_cost_override` and `Server.admin_notes` (Custom Fields installed via `setup_server_admin_fields()`).

### Decommissioning a server

Click **Decommission** → confirmation dialog → **Decommission**.

What happens:

- `Server.is_decommissioned` flag set to 1
- Row visually muted (orange background, line-through cost)
- Excluded from **Effective Cost / mo** summary card
- Excluded from `_get_server_costs()` (Teams tab Server Costs table) and `_calc_team_cost()` (per-team cost)
- **No infrastructure change** — the agent keeps running, sites keep serving, no migration is triggered

Decommission is a soft flag. To physically retire the server, you still need to:

1. Migrate sites off (drag & drop or `move_to_bench` / `move_to_server`)
2. Stop the agent
3. Remove DNS A records
4. Delete the Hetzner VM

Reactivate any time by clicking **Reactivate** on the same row.

## Teams tab — quota management

Each team row shows: status, members, sites used / max, benches used / max, monthly cost (proportional), Block / Unblock action.

Click a row to expand the per-team detail (Quotas & Features / Members / Sites / Benches sub-tabs). Edit `max_sites`, `max_benches`, `max_disk_gb`, allowed site types, and per-feature toggles. `0` for any quota means unlimited.

## Common ops tasks

### Raise a team's site quota

1. Open Admin Panel → Teams tab
2. Click the team row → Quotas & Features
3. Edit **Max Sites** → Save
4. Or via desk: `https://demo.mvpstorm.com/app/team/<team-name>` → Admin Controls section

### Override a server's monthly cost

1. Open Admin Panel → Servers tab
2. Click **Edit** on the row → enter override € → Save
3. Teams tab Monthly Cost summary refreshes after page reload

### Spot a server that needs upsizing

1. Open Admin Panel → Servers tab
2. Look at the **RAM** and **Disk** columns — anything orange or red is a candidate
3. Cross-check Sites + Benches counts to see which team is driving the load
4. Plan the move (migrate, then upsize via Hetzner Cloud console, then resync)

## Architecture notes

- **Custom Fields, not new DocTypes.** `monthly_cost_override`, `is_decommissioned`, `admin_notes` are added to upstream `Server` via `Custom Field` records — keeps the upstream JSON untouched, idempotent on re-deploys, and survives `bench update --reset`.
- **Stats source.** Single SSH probe per machine running `head /proc/meminfo; nproc; uptime; df`. Parsed in `press/api/admin_panel_stats.py`. 8 s end-to-end timeout, 5 s connect timeout, BatchMode=yes (won't hang on prompts). Cached 60 s via `frappe.cache().set_value(..., expires_in_sec=60)`.
- **Cost double-counting.** When a single machine has Server + Database Server + Proxy Server records, only the `app` role contributes baseline cost in `get_servers_admin()` so the same physical machine isn't billed three times.
- **`get_admin_data` total_cost** sums `_get_server_costs()` (which already filters decommissioned) instead of iterating `SERVER_COSTS` directly — keeps Teams tab summary in agreement with the Servers tab.

## Files

| File | Role |
|---|---|
| `dashboard/src/pages/AdminPanel.vue` | Tab orchestrator |
| `dashboard/src/components/admin/ServerAdmin.vue` | Servers tab UI |
| `dashboard/src/components/admin/TeamDetail.vue` | Per-team detail |
| `dashboard/src/components/NavigationItems.vue` | Sidebar entry (Admin Panel) |
| `press/api/admin_panel.py` | Backend APIs (admin-guarded) |
| `press/api/admin_panel_stats.py` | SSH stats collector |
| `press/press/doctype/team/team_admin_setup.py` | Team Custom Fields installer |
| `press/press/doctype/server/server_admin_setup.py` | Server Custom Fields installer |

## Initial setup (per site)

After deploying the admin panel for the first time on a new bench, run the Custom Field installers:

```python
# bench --site <site> console
from press.press.doctype.team.team_admin_setup import setup_admin_fields
from press.press.doctype.server.server_admin_setup import setup_server_admin_fields
setup_admin_fields()
setup_server_admin_fields()
```

Both are idempotent — re-running has no effect if fields already exist.
