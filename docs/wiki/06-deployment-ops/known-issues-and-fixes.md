# Known Issues & Operational Fixes

## Active Known Issues

### u4-default agent auth (401 on scheduled jobs)
**Status:** Ongoing — Purge Binlogs fails with 401 every 30 min
**Cause:** Agent password in `config.json` on u4 doesn't match Press DB
**Fix:** See Lesson 59 — regenerate PBKDF2 hash on u4, update config.json, restart agent

### press-f1 SSL cert hostname mismatch for agent
**Status:** Ongoing — Backup jobs fail with SSL hostname mismatch
**Cause:** Agent cert on press-f1 not valid for `press-f1.sandbox.mvpstorm.com`
**Fix:** Re-issue cert or update agent Nginx config to use correct cert path

### Nginx 502 after login on tenant sites
**Status:** Known, fixed per-deploy
**Cause:** Nginx proxy buffers too small for Frappe auth headers
**Fix:** Add to each bench nginx.conf `@webserver` location:
```nginx
proxy_buffer_size 32k;
proxy_buffers 8 32k;
proxy_busy_buffers_size 64k;
```

## Cluster `public` flag resets on save
**Status:** Known Press behavior
**Impact:** New Site flow stops showing regions
**Fix after any Cluster edit:**
```sql
UPDATE `tabCluster` SET public=1 WHERE name='Default';
```

## Release Group public/private routing
| Bench state | Visible in My Benches | Visible in New Site |
|-------------|----------------------|---------------------|
| `public=0, enabled=1` | YES | NO |
| `public=1, enabled=1` | NO | YES |

**Rule:** Keep all user-managed benches `public=0`. Use bench detail page for creating sites.

## Proxy Server Domain — multi-domain setup
When adding a new root domain (e.g., `client.com`), the `after_insert` patch now auto-links it to all active Proxy Servers. If site creation still fails, verify:
```sql
SELECT name, domain, parent FROM `tabProxy Server Domain`;
```

## V16 builds require Python 3.14
**Status:** Workaround in place (syntax check skipped)
**Limitation:** No actual Python 3.14 runtime → v16 sites cannot run (only build is skipped)
**Proper fix:** Install Python 3.14 on build server, update `get_python_path()` to find it

## Dashboard shows stale content after rebuild
**Status:** Fixed — nginx no-cache headers added
**Cause:** `/dashboard` HTML had no `Cache-Control` header. Browser cached old HTML referencing old JS bundle hashes.
**Symptoms:** Features appear missing, UI elements don't render, "No plans available" etc.
**Fix (nginx):** Added `location = /dashboard` block with `Cache-Control: no-cache, no-store, must-revalidate` always.
**Quick fix for users:** Ctrl+Shift+R (hard refresh)
**Note:** `bench setup nginx` overwrites custom nginx config. Re-run `python3 scripts/fix_nginx_cache.py` after.
