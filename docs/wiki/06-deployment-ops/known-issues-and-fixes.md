# Known Issues & Operational Fixes

## Active Known Issues

### Tenant site hangs (TLS OK, body times out) — wrong upstream IP
**Status:** Recurring — `charity.sandbox.mvpstorm.com` hit it 2026-05-02 (silent for hours; surfaced via Watch Tower alert)
**Symptom:** Site is `Active` in Press DB, bench is `Active`, gunicorn is healthy, OTHER sites in the same bench respond fine — but ONE site times out. nginx access log on the proxy shows `499 ... 7.9s` (client gave up); nginx error log has no upstream errors.
**Cause:** Press's agent stores per-site upstream membership at `/home/frappe/agent/nginx/upstreams/<IP>/<site>` files. The `<IP>` directory name is hashed via `sha512(upstream)[:16]` to produce the `upstream <hash>` block in `proxy.conf`. If a site file is misplaced under the **private IP** of the bench's server (e.g. `10.1.9.105` instead of `46.224.170.58`) and the proxy server has no private network to that IP, every request to that site hangs at `proxy_connect_timeout` (10s). Other sites under the correct public-IP directory work normally.
**Diagnostic:**
```bash
# 1. Compare upstream hashes across sites in the same bench
ssh press-f1 'sudo nginx -T 2>/dev/null | grep -E "<site>|<bench-mate>" | head -10'

# 2. Find the IP behind the broken upstream hash
ssh press-f1 'sudo grep -A1 "upstream <hash> {" /home/frappe/agent/nginx/proxy.conf'

# 3. Confirm upstream is healthy when reached via the right IP
ssh press-f1 'curl -sk --max-time 8 -o /dev/null -w "%{http_code} %{time_total}s\n" \
   --resolve <site>:443:<good_public_ip> https://<site>/api/method/ping'
# 200 in <1s = upstream is fine, routing is the bug
```
**Fix (permanent — also do this even after a hot patch):**
```bash
# Move site to the correct upstream directory
ssh press-f1 'sudo mv /home/frappe/agent/nginx/upstreams/<wrong_ip>/<site> \
                       /home/frappe/agent/nginx/upstreams/<right_ip>/<site> && \
              sudo chown frappe:frappe /home/frappe/agent/nginx/upstreams/<right_ip>/<site>'

# Remove now-empty wrong-ip directory so the dead upstream block disappears
ssh press-f1 'sudo rmdir /home/frappe/agent/nginx/upstreams/<wrong_ip> 2>/dev/null'

# Regenerate proxy.conf via the agent (NOT a manual rewrite — agent overwrites on every operation)
ssh press-f1 'sudo -u frappe bash -c "cd /home/frappe/agent && source env/bin/activate && \
   python -c \"from agent.proxy import Proxy; Proxy()._generate_proxy_config()\""'

# Reload nginx (agent's _reload_nginx() refuses to run outside a job context — use plain nginx)
ssh press-f1 'sudo nginx -t && sudo nginx -s reload'

# Verify zero references to the dead upstream hash
ssh press-f1 'sudo grep -c "<dead_hash>" /home/frappe/agent/nginx/proxy.conf'  # expect 0
```
**Hot patch (only if you must restore service in seconds — the permanent fix above must follow immediately):**
```bash
ssh press-f1 'sudo sed -i "/upstream <dead_hash> {/,/^}/{ s|<wrong_ip>:80|<right_ip>:80| }" \
              /home/frappe/agent/nginx/proxy.conf && sudo nginx -s reload'
```
The agent regenerates `proxy.conf` from the directory tree on every Press operation that touches a site (deploy, archive, rename, …) — so a hot patch is overwritten silently.

### u4-default agent auth (401 on scheduled jobs)
**Status:** Ongoing — Purge Binlogs fails with 401 every 30 min
**Cause:** Agent password in `config.json` on u4 doesn't match Press DB
**Fix:** See Lesson 59 — regenerate PBKDF2 hash on u4, update config.json, restart agent

### press-f1 SSL cert hostname mismatch for agent (RESOLVED)
**Status:** RESOLVED — Self-signed cert added to certifi CA bundle on press-ctrl
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


## Cross-server site routing (proxy hostnames;)
**Status:** Fixed — template patched + post-merge hook installed
**Cause:** Agent Jinja template for proxy.conf `map $host $actual_host` block missing `hostnames;` directive. Nginx treats wildcards as literals without it.
**Symptoms:** Sites on u4 (157.90.244.216) return 307 redirect to `demo.mvpstorm.com/dashboard/#/sites/new`. Login as Administrator shows Internal Server Error. `X-Proxy-Upstream: http://site_not_found` in response headers.
**Architecture:**
- DNS `*.sandbox.mvpstorm.com` → press-f1 (89.167.57.21, proxy server)
- press-f1 proxy.conf maps hostnames to upstream servers (press-f1 local or u4)
- Sites on press-f1 work regardless (bench nginx.conf has exact `server_name`)
- Only cross-server sites (u4) are affected
**Fix:** `hostnames;` in template + live proxy.conf. Post-merge hook auto-reapplies.
**Debug:** `curl -sI https://SITE | grep X-Proxy-Upstream` — if it says `site_not_found`, check `hostnames;` in proxy.conf.

## NEVER run `supervisorctl restart all`
**Status:** Permanent rule
**Impact:** Kills SSH — server becomes unreachable remotely
**Cause:** `supervisorctl restart all` restarts every supervised process. If SSH or networking services are managed by supervisor, they go down and can't be recovered without Hetzner Console.
**Rule:** Always restart specific process groups:
```bash
# GOOD
supervisorctl restart frappe-bench-workers:
supervisorctl restart frappe-bench-web:

# BAD — kills SSH
supervisorctl restart all
```
**Recovery:** Reboot from Hetzner Cloud Console.

## Agent patches survive git pull
**Status:** Automated via post-merge hook
**Location:** `/home/frappe/agent/repo/.git/hooks/post-merge` on press-f1
**What it fixes:** `hostnames;` directive (template + live proxy.conf)
**Log:** `/var/log/agent-post-merge.log`
**Note:** Docker login patch (server.py) is NOT in the hook — must be reapplied manually if agent is updated.

### Non-System users force-logged-out when Vue dashboard hits a 401
**Status:** Recurring — 3 incidents in 8 days (2026-05-10 × 2, 2026-05-18 × 2). Mandatory check on every PR that adds a whitelisted method.
**Symptom:** A non-System user (Website User / Team Member) clicks something on the dashboard (Launch Code Server, Deploy, Open Code Health, etc.) and the next page load bounces them to `/dashboard/login`. Sometimes the click is incidental — a background poll firing right after is the real trigger.
**Cause:** Press has its own auth hook at `apps/press/press/auth.py` that runs BEFORE Frappe's whitelist check. It rejects any URL not in `ALLOWED_PATHS` (exact) or `ALLOWED_WILDCARD_PATHS` (prefix). System Users short-circuit on line 107; everyone else must match. When a whitelisted method is called via its dotted Python path (`press.press.doctype.<x>.<y>.<method>`) but that path is not in the allowlist, the request returns HTTP 401. The Vue dashboard (`router.js` → `waitUntilTeamLoaded`) maps any 401 to "session expired", clears `localStorage.current_team`, and force-redirects to login.
**Diagnostic:**
```bash
# 1. Tail the auth log on press-ctrl
ssh press-ctrl
sudo -u frappe tail -F /home/frappe/frappe-bench/logs/press.auth.json.log

# 2. Look for transitions: same email -> Guest on a repeating endpoint
#    e.g. user "marco@x.com" appears, then 10s later "user": "Guest"
#    The path field is the missing allowlist entry.

# 3. Audit script — find every dashboard-called whitelisted method NOT in the allowlist
cd ~/data/erpnext-app-repos/press_local
for f in $(grep -rl "@frappe.whitelist" press/press/doctype/ --include="*.py" | grep -v test_); do
  module=$(echo "$f" | sed 's|press/press/doctype/||; s|\.py$||; s|/|.|g')
  prefix="press.press.doctype.$module."
  if grep -qrE "$(echo "$prefix" | sed 's/\./\\./g')" dashboard/src/ 2>/dev/null; then
    if ! grep -q "$prefix" press/auth.py; then
      echo "MISSING: $prefix"
    fi
  fi
done
```
**Fix:** add one line to `ALLOWED_WILDCARD_PATHS` in `press/auth.py`:
```python
"/api/method/press.press.doctype.<x>.<y>.",   # trailing dot mandatory
```
Then on press-ctrl: cherry-pick + `supervisorctl restart frappe-bench-web:` (no rebuild needed — pure Python).
**Verify the fix is live:**
```bash
ssh press-ctrl 'curl -k -X POST "https://demo.mvpstorm.com/api/method/press.press.doctype.<x>.<y>.<method>" --data "x=y"'
# Expect: "PermissionError: ... is not whitelisted" (auth_hook PASSED, hit whitelist gate)
# Before fix: "AuthenticationError: Access not allowed for this URL" (auth_hook BLOCKED)
```
**Prevention:** every PR that adds `@frappe.whitelist()` at a `press.press.doctype.*` path MUST add the matching allowlist entry in the SAME commit. Run the audit script above before merging.
**Incident history:**
- 2026-05-10 `cb55aebf6e` — `deploy_candidate_build.` + `site_clone.` + `partner_payment_payout.`
- 2026-05-10 `4b775755d0` — `press.mcp_server.`
- 2026-05-18 `cb22ec0d53` — `bench_dev_watch.` (BenchWatchStatus poll every 10s logged users out within seconds)
- 2026-05-18 `6e18abbbfb` — `bench_code_health.` (audit follow-up — would have logged out anyone visiting `/dashboard/code-health`)
