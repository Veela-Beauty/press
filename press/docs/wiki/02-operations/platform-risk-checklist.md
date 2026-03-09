# Platform Risk Checklist

This is a cloud hosting platform serving multiple users across multiple servers. Every operational change
has a blast radius. This checklist is mandatory before and after any task.

---

## Why This Matters

| What breaks | Who is affected |
|-------------|-----------------|
| Scheduler stops | ALL users — no status updates, no backups, no auto-operations |
| Agent auth fails on server X | ALL sites on server X go dark — jobs queue up, never complete |
| SSL cert mismatch on server X | ALL operations on server X fail — agent unreachable from Press |
| Docker registry down | ALL builds fail for ALL users |
| Press DB down | Entire platform down |
| Disk full on app server | All sites on that server fail (DB, backups, bench) |
| Wrong team assignment | Specific user's resources invisible or inaccessible |
| DNS propagation delay | New sites unreachable until TTL expires |

Never fix one thing without checking whether the same issue exists on other servers.

---

## Pre-Task Risk Assessment

Before starting any operational change, answer these:

1. **What is the blast radius if this goes wrong?**
   - One user's site? One server? All servers? All users?

2. **Is this reversible?**
   - Can you undo in under 5 minutes? If not — take a backup first.

3. **Does this affect a shared resource?**
   - Scheduler, Docker registry, Press Settings, Root Domain → affects everyone
   - Agent config on server X → affects all sites on X

4. **Is this being done during active user hours?**
   - Agent restart = 10-30 seconds downtime for jobs in flight
   - nginx reload = near-zero downtime (graceful)
   - Supervisor restart = brief downtime for that process

5. **Does the same issue exist on other servers?**
   - If one server has a misconfigured agent, the others likely do too

---

## Post-Task Verification (Run After Every Fix)

### 1. Scheduler Health

```bash
bench --site demo.mvpstorm.com execute frappe.client.get_list \
  --kwargs '{"doctype": "Scheduled Job Type", "filters": {"name": "agent_job.poll_pending_jobs"}, "fields": ["name", "last_execution", "stopped"]}'
```

- `stopped` must be `0`
- `last_execution` must be within the last 30 seconds

### 2. Agent Health — All Servers

Run from each server (must be tested from inside the server — agent binds to 127.0.0.1):

```bash
# On press-f1 (89.167.57.21)
ssh press-f1 "curl -s -o /dev/null -w '%{http_code}' -u 'press-f1.demo.mvpstorm.com:PASSWORD' http://127.0.0.1:25052/ping"
# Expected: 200

# On u4 (157.90.244.216)
ssh u4 "curl -s -o /dev/null -w '%{http_code}' -u 'u4-default.sandbox.mvpstorm.com:PASSWORD' http://127.0.0.1:25052/ping"
# Expected: 200
```

Any non-200 = agent auth broken = all sites on that server are down.

### 3. SSL Certificate Health — All Servers

```bash
# press-f1 — must match *.demo.mvpstorm.com
openssl s_client -connect 89.167.57.21:443 -servername press-f1.demo.mvpstorm.com 2>/dev/null \
  | openssl x509 -noout -subject -dates
# Look for: "Verify return code: 0 (ok)"

# u4 — must match *.sandbox.mvpstorm.com
openssl s_client -connect 157.90.244.216:443 -servername u4-default.sandbox.mvpstorm.com 2>/dev/null \
  | openssl x509 -noout -subject -dates
```

### 4. Docker Registry

```bash
# From press-ctrl
curl -s http://89.167.116.92:5000/v2/_catalog
# Expected: {"repositories": [...]}

# From press-f1 (must reach registry for builds)
ssh press-f1 "curl -s http://89.167.116.92:5000/v2/_catalog | head -c 100"
```

### 5. Disk Space — All Servers

```bash
# press-ctrl
ssh press-ctrl "df -h / | tail -1"

# press-f1
ssh press-f1 "df -h / | tail -1"

# u4
ssh u4 "df -h / | tail -1"
```

Flag anything over 70% used. At 85%+ builds will fail. At 95%+ sites will go down.

### 6. Recent Job Failures

```bash
bench --site demo.mvpstorm.com execute frappe.client.get_list \
  --kwargs '{"doctype": "Agent Job", "filters": {"status": "Failure", "modified": [">", "1 hour ago"]}, "fields": ["name", "job_type", "server", "creation", "output"], "order_by": "creation desc", "limit_page_length": 10}'
```

Any failures from the server you just modified = your change caused a regression.

---

## Risk Levels and Response

### P0 — Platform Down (All Users)
**Symptoms:** Scheduler stopped, Press DB unreachable, Docker registry down

Immediate actions:
1. Check supervisorctl on press-ctrl (`supervisorctl status`)
2. Check frappe-web process is running
3. Check mariadb is running on press-ctrl
4. Check Docker registry: `docker ps | grep registry`

```bash
# Full service check on press-ctrl
supervisorctl status
systemctl status mariadb nginx
docker ps | grep registry
```

### P1 — Server Down (All Sites on Server X)
**Symptoms:** Agent jobs failing, 401 errors, SSL errors for one server

Immediate actions:
1. SSH to the affected server
2. Check agent: `supervisorctl status agent:web`
3. Test /ping from inside: `curl -u 'name:pass' http://127.0.0.1:25052/ping`
4. Check nginx: `nginx -t && systemctl status nginx`
5. Check SSL cert subject matches server hostname

### P2 — Operations Broken (Builds/Creates Failing)
**Symptoms:** New sites fail, builds fail, specific job types fail

Diagnosis path:
1. Check the Agent Job for output/traceback
2. Check the affected server's disk space
3. Check if the issue is only for one Frappe version or all
4. Check if Docker registry is reachable from that server

### P3 — Single User Issue
**Symptoms:** One user can't see their sites, one site stuck

Diagnosis:
1. Check team assignment on the user's resources
2. Check if their site has a running Bench
3. Check site status and Agent Job history for their site

---

## Server Inventory (Current State)

| Server | Role | IP | Agent Hostname | Cert Domain |
|--------|------|----|----------------|-------------|
| press-ctrl | Press controller | 89.167.116.92 | N/A | *.demo.mvpstorm.com |
| press-f1 | App server (standalone) | 89.167.57.21 | press-f1.demo.mvpstorm.com | *.demo.mvpstorm.com |
| u4 | App server (standalone) | 157.90.244.216 | u4-default.sandbox.mvpstorm.com | *.sandbox.mvpstorm.com |

**Cert scope rules:**
- `*.demo.mvpstorm.com` covers: `press-f1.demo.mvpstorm.com`, `*.demo.mvpstorm.com`
- `*.sandbox.mvpstorm.com` covers: `u4-default.sandbox.mvpstorm.com`, `*.sandbox.mvpstorm.com`
- These are SEPARATE wildcard certs — one does NOT cover the other

---

## After Adding a New Server (Use the Script)

**Do not do this manually.** Use `scripts/provision-server.sh` — it runs all 13 steps and verifies each one:

```bash
# From press-ctrl (after Ansible setup_server + setup_standalone)
./scripts/provision-server.sh \
  --ip NEW_SERVER_IP \
  --hostname press-uX.subdomain.mvpstorm.com \
  --cert-domain subdomain.mvpstorm.com \
  --press-site demo.mvpstorm.com \
  --registry 89.167.116.92:5000 \
  --team TEAM_HASH
```

After the script completes, verify manually:

- [ ] `supervisorctl status` on new server — all processes RUNNING
- [ ] `curl -u 'hostname:password' http://127.0.0.1:25052/ping` from inside server → 200
- [ ] `openssl s_client -connect IP:443 -servername HOSTNAME` → Verify return code: 0
- [ ] `df -h /` on new server → <70% used
- [ ] Create a test site from dashboard — reaches Active status
- [ ] Add server to Server Inventory table below

---

## Automation Scripts (Reference)

| Script | Run On | Purpose |
|--------|--------|---------|
| `scripts/provision-server.sh` | press-ctrl | All 13 PER-SERVER steps for a new server |
| `scripts/setup-build-worker.sh` | press-ctrl | Add dedicated build queue worker (run once) |
| `scripts/hooks/fix-letsencrypt-permissions.sh` | `/etc/letsencrypt/renewal-hooks/post/` | Restore chmod 755 after every cert renewal |
| `scripts/hooks/sync-press-tls-records.sh` | `/etc/letsencrypt/renewal-hooks/deploy/` | Update Press TLS Certificate DB records on renewal |
| `scripts/hooks/docker-cleanup.sh` | `/etc/cron.daily/` on each app server | Daily prune of stopped containers |

---

## Recurring Health Check (Run Weekly)

Run all steps in "Post-Task Verification" above proactively, even when nothing changed.

Certbot autorenewal check:
```bash
# Dry run to verify renewal would succeed AND all hooks are valid
# NOTE: If dry-run fails with "DNS TXT records not verified", increase propagation time:
# for conf in /etc/letsencrypt/renewal/*.conf; do
#   grep -q 'dns_cloudflare_propagation_seconds' "$conf" || \
#     sed -i '/\[renewalparams\]/a dns_cloudflare_propagation_seconds = 30' "$conf"
# done
certbot renew --dry-run
```

Log review:
```bash
# Any agent errors in the last 24h?
bench --site demo.mvpstorm.com execute frappe.client.get_list \
  --kwargs '{"doctype": "Agent Job", "filters": {"status": "Failure", "modified": [">", "24 hours ago"]}, "fields": ["job_type", "server", "creation"], "order_by": "creation desc", "limit_page_length": 20}'
```
