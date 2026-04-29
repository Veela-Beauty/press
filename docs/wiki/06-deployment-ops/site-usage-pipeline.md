# Site Usage Data Pipeline

> Tracks how the Site Overview's Compute / Storage / Database panels get their numbers.

## TL;DR

```
agent on bench → bench.sync_info() → site.sync_info() → tabSite Usage
                                                              ↓
                                                   update_disk_usages
                                                              ↓
                                       Site.current_{database,disk,cpu}_usage
                                                              ↓
                                                  Site Overview panel
```

Two independent schedulers keep it fresh. If they stop, panels drift to 0.

## Schedulers

| Cron | Function | What it does | Failure mode |
|---|---|---|---|
| `hourly_long` | `press.press.doctype.bench.bench.sync_benches` | Enqueues `sync_bench` per active bench → calls `bench.sync_info()` → iterates sites → `site.sync_info()` → inserts a `Site Usage` record per site (database/public/private MB from agent report) | Wraps `bench.sync_info()` in try/except + `log_error`. **Silent failure** if agent unreachable or rate-limited. |
| `15,45 * * * *` | `press.press.doctype.site.site_usages.update_disk_usages` | Reads latest Site Usage record per site, computes `% of plan`, writes to `Site.current_database_usage` / `current_disk_usage` | Wraps each site update in try/except + `log_error`. Skips sites without a Subscription/Plan. |
| `15,45 * * * *` | `press.press.doctype.site.site_usages.update_cpu_usages` | Queries ES `filebeat-*` for latest `request.counter` per site → writes to `Site.current_cpu_usage` | Skips sites without `log_server` configured or `Plan`. |
| Daily (`daily_long`) | `press.press.doctype.bench.bench.sync_analytics` | Different — pulls request analytics for the Insights page (per-route counts / durations). Does NOT touch Site Usage. | Independent. |

So **every hour Site Usage refreshes**, **every 30 min the Site doc fields refresh**, and the dashboard reads from the Site doc.

## Data shape

`tabSite Usage` rows (one per site per hour):
```
site             database   public  private  database_free
roseline-stg     2628       1500    23       400         (all in MB)
```

`update_disk_usages` converts to % of plan:
```python
latest_database_usage = CAST(usage.database / plan.max_database_usage * 100 AS INT)
latest_disk_usage     = CAST((usage.public + usage.private) / plan.max_storage_usage * 100 AS INT)
```

So `Site.current_database_usage = 86` means 86% of the plan's database limit.

The Vue panel converts back to bytes for display:
```vue
{{ formatBytes(currentUsage.database) }} of {{ formatBytes(currentPlan.max_database_usage) }}
```

## What populates `tabSite Usage` immediately

- After every successful **Site Backup** — `site_backup.py:200` calls `site.sync_info()` if the site lacks `database_name`. Most sites already have it, so this rarely triggers a sync.
- After **manual UI action**: Site detail page → `Sync Info` button calls the whitelisted `Site.sync_info()`.
- After **bench-level sync**: Bench detail page → `Sync Sites Info` button.
- **`sync_benches` hourly_long scheduler** — the one we rely on for steady state.

## How to verify it's working

```bash
ssh root@press-ctrl "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com console <<'PY'
import frappe
total = frappe.db.count('Site Usage')
recent = frappe.db.sql('SELECT site, MAX(creation) FROM \`tabSite Usage\` GROUP BY site ORDER BY MAX(creation) DESC LIMIT 5', as_dict=True)
print('Total Site Usage records:', total)
print('Most recent per site:')
for r in recent: print(' ', r)
PY"
```

Healthy: `total >= active_sites_count`, most recent per site is < 2 hours old.
Stale: any site's most recent record is > 4 hours old → run the manual backfill (see runbook).

## What broke once on 2026-04-29

`tabSite Usage` was completely empty install-wide despite `sync_benches` being scheduled. Caused by silent agent failures over weeks of running. Manual backfill (`for site in active_sites: site.sync_info()`) populated all 26 sites in one shot. Documented in `docs/runbook/log-server.md` under "Site Storage / Database panels show 0".

## Defensive monitor

A daily scheduler `audit_site_usage_freshness` (added in commit TBD) checks every active site's most-recent `Site Usage` record. If any site's record is >24 hours old, it logs a warning to `Error Log`. Use to catch silent agent failures early.

## Related

- Compute panel data flow: `docs/architecture/log-server.md` (ES + Filebeat for `request.counter`)
- Slow Queries follow-up: `docs/plans/2026-04-29-press-mariadb-slowlog-followup.md`
- Lessons from 2026-04-29 session: `docs/wiki/08-lessons/2026-04-29-bench-watch-and-log-server.md`
