# Lessons Learned: 2026-10-30: a hooks.py change was deployed but Frappe kept the old hooks

> 0.7.4 added Bench Shell Log (30 days) and Agent Job (90 days) to
> `default_log_clearing_doctypes` in `press/hooks.py`. The deploy step that registers them in
> Log Settings (`add_default_logtypes()`) printed `[]`: nothing was added, so the daily log
> clean-up would never have run for either table (13 GB at the time).

**Second time.** The same trap was written down on 2026-09-08
([Lesson 5](2026-09-08-stranded-server-freezes-every-job.md#lesson-5--bench-clear-cache-does-not-clear-app_hooks):
a new `scheduler_events` entry stayed invisible through a restart and `clear-cache`), with the
same fix. It hit again because the deploy procedure had no step for it; it has one now.

## Lesson 1: the `app_hooks` cache can outlive `clear-cache`

### What it is

`frappe.get_hooks()` reads the merged hooks of every app from the Redis key
`<db_name>|app_hooks` (`cache.get_value("app_hooks", _load_app_hooks)` in
`frappe/__init__.py`, Frappe 15.101.5). The key is rebuilt from disk only when it is missing.

### How it bit us

After the 0.7.4 merge, in a fresh Python process on press-ctrl:

| Read | Bench Shell Log / Agent Job |
|---|---|
| `importlib.import_module("press.hooks").default_log_clearing_doctypes` | present |
| `frappe._load_app_hooks()` (uncached) | present |
| `frappe.get_hooks("default_log_clearing_doctypes")` (cached) | **missing** |

`bench --site demo.mvpstorm.com clear-cache` (which does delete `app_hooks` in
`clear_global_cache`) and a graceful restart of all 10 workers did not fix it on their own:
the cached value still lacked the new entries right after both. No bench process older than
the change was running. Deleting the key by hand (`redis-cli -p 13000 DEL
'_97ba09b8275e29ad|app_hooks'`) did: within a second the `frappe schedule` process rewrote it
from disk with the new entries, and `add_default_logtypes()` then added both rows (Log Settings
12 -> 14 rows). Which process put the old value back after `clear-cache` was not proven.

### How to spot it

After any deploy that changes `hooks.py`, compare cached and uncached hooks in a fresh process:

```python
frappe.get_hooks("<hook>")                 # what every process uses
frappe._load_app_hooks().get("<hook>")     # what is on disk
```

If they differ, delete `<db_name>|app_hooks` in the site's cache Redis and read again.

### Prevention

The press deploy procedure ([deployment guide](../06-deployment-ops/deployment-guide.md#deploying-the-press-app-to-press-ctrl))
now says to run that check whenever `hooks.py` changed. Once a doctype is in Log Settings, the
daily clean-up reads the Log Settings rows, not the hook, so the cache only matters for the
registration step.

## Lesson 2: press-ctrl's database clock is 3 hours behind the stored times

`NOW()` in a MariaDB session on press-ctrl returns UTC, while Frappe stores `creation` /
`modified` in the site time zone (Asia/Riyadh, +3). A query like
`WHERE creation > NOW() - INTERVAL 10 MINUTE` therefore covers the last 3 h 10 min. It made a
steady 41 rows a minute look like 713 a minute. For "last N minutes", compute the cutoff on the
server side in the site time zone, or group by time slot and read the shape.
