# Press-Ctrl Stability Runbook

**Server:** press-ctrl @ `89.167.116.92` (autodeploypanel.mvpstorm.com)
**Authoritative on the box:** `/etc/sanad/press-ctrl-rules.md`
**Snapshots:** `/home/frappe/snapshots/`
**Scripts:** `/home/frappe/scripts/`
**Last incident:** 2026-04-29 — `pydantic`/`pydantic_core` mismatch → 10h hidden outage

---

## TL;DR

For everyday ops:
```bash
sudo -u frappe bench-update-safe                              # safe update (preflight + update + postflight + safe restart + smoke + auto-rollback)
sudo -u frappe bench-update-safe --dry-run                    # preview only
sudo -u frappe bench-update-safe --skip-update --no-restart   # validate env health only (no disruption)
sudo -u frappe /home/frappe/scripts/rollback.sh               # emergency rollback to latest snapshot
```

**Never run `bench update` directly on press-ctrl. Always use `bench-update-safe`.**

---

## Why This Runbook Exists — The 2026-04-29 Incident

A bare `bench update` upgraded `pydantic` to 2.12.5 but the matching `pydantic_core` wheel never installed (partial install — no module, no dist-info left in venv). Frappe imports pydantic at module load, so every Python supervisor process FATAL'd at boot. The defect stayed hidden for ~10 hours because gunicorn workers in memory don't re-import on update — failure surfaced only at the next worker recycle.

Result: site fully down for ~10h. All scheduled jobs stopped. Background queue stalled. No alerting. Discovered by manual check.

The wrapper described below makes this category of failure impossible:
- **Snapshot before** → instant rollback target
- **Boot test BEFORE restart** → catches broken env without taking the site down
- **Auto-rollback** → restores from snapshot if anything fails post-update
- **Safe restart** → timeouts + force-kill stragglers, no more hung supervisorctl

---

## The Iron Rules

These five rules are mirrored on the box at `/etc/sanad/press-ctrl-rules.md`. They are non-negotiable for press-ctrl operators.

### 1. NEVER `sudo pip install` or `pip install` as root

Files installed as root pollute the venv. Next `bench update` (run as `frappe`) hits `Permission denied` and breaks halfway. We had **7,153 root-owned files** in the venv from past mistakes — silently waiting to break the next update.

```bash
# WRONG — pollutes venv with root-owned files
sudo pip install <pkg>
# WRONG — same problem
pip install <pkg>          # if your shell happens to be root

# RIGHT
sudo -u frappe /home/frappe/frappe-bench/env/bin/pip install <pkg>
sudo -u frappe bench setup requirements --python   # respects pyproject pins
```

If you find pollution: `chown -R frappe:frappe /home/frappe/frappe-bench/env/`.

### 2. NEVER bare `bench update` on production

No pre-flight check, no rollback path. The 2026-04-29 incident is proof. Use `bench-update-safe` instead — it does the same thing but with safety nets.

### 3. Updates only happen in a maintenance window

Default windows:
- Weekdays 02:00 — 04:00 Cairo
- Sundays 22:00 — 24:00 Cairo

For ad-hoc updates: ping the team in `#press-ops` channel first.

### 4. NEVER force-push to `cloudflare-dns`

It's the primary deploy branch of our white-label fork. Force-push deletes other engineers' commits. Always merge or rebase locally, then push (no force).

### 5. Server changes are reversible by default

```bash
# Frappe site backup before risky DB ops
sudo -u frappe bench --site all backup --with-files

# pip freeze before pip changes
sudo -u frappe /home/frappe/frappe-bench/env/bin/pip freeze \
  > /home/frappe/snapshots/<context>-$(date +%Y%m%d-%H%M%S).txt

# git tag before risky merges
cd /home/frappe/frappe-bench/apps/press && git tag pre-<change>-$(date +%Y%m%d)
```

---

## bench-update-safe — The Wrapper

### Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ /usr/local/bin/bench-update-safe                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ [1/7] PRE-FLIGHT                                                │
│   - venv ownership check (0 non-frappe files required)          │
│   - pip check (warning, not fatal — boot test is the gate)      │
│   - import all 5 apps in subprocess                             │
│   - supervisor: 8/8 RUNNING expected                            │
│   - save pip freeze → /home/frappe/snapshots/pre-update-<ts>.txt│
│                                                                 │
│ [2/7] UPDATE                                                    │
│   - bench update --pull --requirements --no-backup              │
│                                                                 │
│ [3/7] POST-FLIGHT (BEFORE restart — critical gate)              │
│   - pip check (informational only)                              │
│   - import all 5 apps in fresh subprocess                       │
│   - WSGI entry-point load test (frappe.app:application)         │
│   - on FAIL → AUTO-ROLLBACK → exit 1                            │
│                                                                 │
│ [5/7] SAFE RESTART                                              │
│   - timeout 15s supervisorctl stop + force_kill_frappe_workers  │
│   - timeout 30s supervisorctl start + poll for 8/8 RUNNING      │
│   - on FAIL → AUTO-ROLLBACK                                     │
│                                                                 │
│ [6/7] SMOKE TEST                                                │
│   - poll /api/method/ping every 1s up to 30s                    │
│   - first 200 → success                                         │
│   - never 200 → AUTO-ROLLBACK                                   │
│                                                                 │
│ [7/7] PROMOTE                                                   │
│   - save post-update snapshot                                   │
│   - log success line + both snapshot paths                      │
└─────────────────────────────────────────────────────────────────┘
```

### Flags

| Flag | Effect | When to use |
|---|---|---|
| `--dry-run` | Pre-flight only, no changes | Before first run; sanity check |
| `--skip-update` | Skip git pull + pip install (still does restart + smoke) | Test full restart pipeline in maintenance window |
| `--no-restart` | Skip supervisor restart + smoke test | Validate env health with zero disruption |
| `--no-rollback` | Disable auto-rollback (dangerous) | Forensic debugging only |
| `--help` | Show usage | — |

### Exit codes

- `0` — full success, both snapshots written
- `1` — failure at any step; if rollback enabled, env was restored to pre-update snapshot

### Logs

Every run writes a log file at `/home/frappe/snapshots/bench-update-safe-<ts>.log` with full timestamped output.

---

## Manual Recovery (when wrapper is missing or fails)

### Manual rollback to latest snapshot

```bash
sudo -u frappe /home/frappe/scripts/rollback.sh
```

### Manual rollback to specific snapshot

```bash
sudo -u frappe /home/frappe/scripts/rollback.sh /home/frappe/snapshots/pre-update-20260430-074153.txt
```

### Manual rollback without restart (env only, no supervisor restart)

```bash
sudo -u frappe /home/frappe/scripts/rollback.sh --no-restart
```

### Bare-minimum manual playbook (if scripts directory is missing)

```bash
# 1. Snapshot CURRENT state
sudo -u frappe /home/frappe/frappe-bench/env/bin/pip freeze \
  > /home/frappe/snapshots/manual-$(date +%Y%m%d-%H%M%S).txt

# 2. Update
sudo -u frappe bench update --pull --requirements

# 3. Verify imports BEFORE restart (this is what was missing on 2026-04-29)
sudo -u frappe /home/frappe/frappe-bench/env/bin/python -c \
  "import frappe, press, daman_backup, frappe_theme_switcher, sanad_business_intelligence_ai; print('OK')"

# 4. Only restart if step 3 returned OK
sudo -u frappe bench restart

# 5. Healthcheck
curl -sS -o /dev/null -w "%{http_code}\n" \
  -H "Host: autodeploypanel.mvpstorm.com" http://127.0.0.1/api/method/ping
```

If step 3 fails: **STOP**. Do not restart. Roll back via:

```bash
sudo -u frappe /home/frappe/frappe-bench/env/bin/pip install \
  --force-reinstall --no-deps -r /home/frappe/snapshots/<latest>.txt
```

---

## Health Check Quick Reference

Use any of these one-liners to verify state:

```bash
# Supervisor — expect 8 RUNNING (redis x2, web x1, socketio x1, schedule x1, workers x3)
supervisorctl status | grep -v RUNNING | grep -v pkg_resources

# Boot test — must print "OK"
sudo -u frappe /home/frappe/frappe-bench/env/bin/python -c \
  "import frappe, press, daman_backup, frappe_theme_switcher, sanad_business_intelligence_ai; print('OK')"

# Public endpoint — must be 200
curl -sS -o /dev/null -w "%{http_code}\n" https://autodeploypanel.mvpstorm.com/api/method/ping

# Dependency drift — should be empty (no output)
sudo -u frappe /home/frappe/frappe-bench/env/bin/pip check

# Venv ownership — must be 0
find /home/frappe/frappe-bench/env/ -not -user frappe 2>/dev/null | wc -l

# All-in-one validation (read-only, no disruption)
sudo -u frappe bench-update-safe --skip-update --no-restart
```

---

## Snapshots Convention

| Location | `/home/frappe/snapshots/` |
|---|---|
| Owner | `frappe:frappe` |
| Naming | `<context>-YYYYMMDD-HHMMSS.txt` |
| Contexts | `pre-update`, `pre-realign`, `pre-rollback`, `post-update-ok`, `manual` |
| Run logs | `bench-update-safe-YYYYMMDD-HHMMSS.log` |
| Cleanup | TODO Phase 3: cron prunes > 90 days old |

The wrapper takes a snapshot **before every update**, so the most recent `pre-update-*.txt` is always the rollback target.

---

## Scripts Inventory (`/home/frappe/scripts/`)

| File | Lines | Purpose |
|---|---|---|
| `lib.sh` | 225 | Shared helpers: logging, role-switch (as_frappe/as_root), boot test, healthcheck, **safe_restart**, force_kill_frappe_workers |
| `pre-flight.sh` | 88 | Standalone pre-update validation; takes a snapshot |
| `post-flight.sh` | 67 | Standalone post-pip-install validation; never restarts |
| `rollback.sh` | 81 | Restore env from a snapshot + safe_restart; can be run independently |
| `bench-update-safe` | 159 | Main orchestrator |

The `lib.sh` `safe_restart()` function is the v2 critical fix: it replaces direct `supervisorctl restart` with timeout-bounded stop + force-kill of stuck workers + start with verify + healthcheck poll. Without it, a single stuck worker hangs the whole restart and brings down the site (we observed this on 2026-04-30 07:34 during testing — 3-min outage from a stuck `long-worker-0` in STOPPING state).

---

## Source Repository

The scripts live at `/home/frappe/scripts/` on press-ctrl. Source-of-truth copy on the Hetzner dev box at `/home/eslam/data/sanad-scripts/press-ctrl/`. Future Phase 1 will commit them to a git repo (`accurate-systems/press-ctrl-config` or chosen location).

To redeploy after editing the source:

```bash
# From Hetzner dev box
cd /home/eslam/data/sanad-scripts/press-ctrl/
tar czf /tmp/sanad-scripts.tgz lib.sh pre-flight.sh post-flight.sh rollback.sh bench-update-safe
scp /tmp/sanad-scripts.tgz root@89.167.116.92:/tmp/
ssh root@89.167.116.92 'cd /home/frappe/scripts && \
  tar xzf /tmp/sanad-scripts.tgz && \
  chown frappe:frappe * && \
  chmod 755 *.sh bench-update-safe && \
  chmod 644 lib.sh'
```

---

## Pending Hardening

| Phase | Item | Status |
|---|---|---|
| 1 | Generate `env-lock-prod.txt` and commit to a private repo | ✅ done 2026-04-30 (`deploy/sanad-ops/press-ctrl/`) |
| 1 | Push this runbook to Outline as well | pending — user decision |
| 3 | Cert sync on renewal (per-server certbot deploy hook) | ✅ done 2026-04-30 (press-f1) |
| 3 | Daily TLS audit cron with alert on non-LE / expiring | ✅ done 2026-04-30 (press-ctrl) |
| 3 | Auto-clear stale Agent Request Failure (10-min cycle) | ✅ done 2026-04-30 (Press scheduler) |
| 3 | Uptime monitor on `/api/method/ping` (Telegram/email alert if 5xx) | pending — needs tool decision (UptimeRobot / Uptime Kuma / Healthchecks.io) |
| 5 | Full rollback drill in maintenance window — deliberate break + verify wrapper auto-restores | pending — needs maintenance window |
| 5 | Live cert-audit drill — swap LE→self-signed on press-f1, verify alert, restore | pending — needs maintenance window (will trip circuit breaker briefly) |

---

## Cert Protection Automation (added 2026-04-30, after lesson #125)

Three independent layers of defense against the cert/circuit-breaker class of bug.

### Layer 1 — Certbot deploy hook (cert sync on renewal)

**Path:** `/etc/letsencrypt/renewal-hooks/deploy/sync-press-agent-cert.sh` on press-f1.
**Source-of-truth:** `deploy/sanad-ops/press-ctrl/scripts/sync-press-agent-cert.sh` in this repo.

Runs after every successful certbot renewal. Atomic (`install -o frappe -g frappe -m 600/644`) into `/home/frappe/agent/tls/{fullchain,privkey,agent-only-fullchain,agent-only-privkey}.pem`, then `nginx -t` + `nginx -s reload`. Logs to `/var/log/cert-sync.log`. Aborts on any failure (no false-success).

**Not on u4/u5:** they don't run certbot locally — their cert is push-managed by the Press TLS Certificate doctype. Layer 2 (audit cron) catches drift on those servers regardless.

### Layer 2 — Daily TLS audit cron

**Cron:** `/etc/cron.d/press-cert-audit` on press-ctrl, runs `0 6 * * *` (06:00 Asia/Riyadh local).
**Script:** `/home/frappe/scripts/check-press-agent-certs.py` — Python stdlib `ssl` probe of each server (press-ctrl, press-f1, u4, u5) on port 443.
**Source-of-truth:** `deploy/sanad-ops/press-ctrl/scripts/check-press-agent-certs.py`.
**Tests:** 4 unit tests in same dir (`test_check_press_agent_certs.py`) verifying issuer + expiry logic.

Alerts on:
- non-LE issuer (catches a bootstrap-cert regression, the 2026-04-30 root cause)
- cert expired
- cert expires within 14 days

Today writes alerts to stdout + `/var/log/press-cert-audit.log`. Cron emails root on non-zero exit. Phase 3+ will wire alerts to Telegram/email.

### Layer 3 — Auto-clear stale Agent Request Failure rows

**Module:** `press.scheduled_jobs.clear_stale_agent_request_failures.execute`.
**Source:** `press/scheduled_jobs/clear_stale_agent_request_failures.py`.
**Tests:** `press/scheduled_jobs/test_clear_stale.py` (4 tests, hermetic via injected `frappe` mock).
**Schedule:** `*/10 * * * *` in `press/hooks.py` `scheduler_events.cron`.

For each `Agent Request Failure` row older than 10 minutes:
1. If the Server doc no longer exists → delete the orphan row.
2. Otherwise call `Agent.ping()`. If it succeeds → delete the row.
3. If `ping()` raises (any reason) → keep the row for the next cycle.

This means `Agent.should_skip_requests()` self-heals once the server is reachable again. Without it, a single transient network blip permanently traps every subsequent agent job in Undelivered status (the 2026-04-30 incident).

**Operational note:** If the audit (Layer 2) fires an alert, the trip will also create rows in `tabAgent Request Failure`. Layer 3 will clear them automatically once the underlying issue is fixed and the agent is reachable again — no manual `DELETE` needed.

### Verifying all three are healthy

```bash
# Layer 1 — hook installed?
ssh -i ~/.ssh/github_key_apr20 root@89.167.57.21 \
  'ls -la /etc/letsencrypt/renewal-hooks/deploy/sync-press-agent-cert.sh && tail -3 /var/log/cert-sync.log'

# Layer 2 — cron + script + log exist; manual run returns OK
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  'cat /etc/cron.d/press-cert-audit && /usr/bin/python3 /home/frappe/scripts/check-press-agent-certs.py'

# Layer 3 — Frappe shows the job as registered + active
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 'cd /home/frappe/frappe-bench && \
  sudo -u frappe bench --site demo.mvpstorm.com mariadb --batch -e \
    "SELECT name, method, stopped, cron_format, last_execution FROM \`tabScheduled Job Type\` \
     WHERE method LIKE \"%clear_stale%\" \\G"'
```

---

## Related Documents

- `/etc/sanad/press-ctrl-rules.md` (on the box) — abridged operator-facing rules
- `/home/eslam/docs/plans/2026-04-30-press-ctrl-stability-runbook.md` — full plan + post-mortem with Objective / Definition of Done / Before-After
- [Known Issues & Fixes](known-issues-and-fixes.md) — broader troubleshooting
- [Root Cause Patches](root-cause-patches.md) — patches to upstream agents/templates
- [Deployment Guide](deployment-guide.md) — provisioning new servers/benches/domains

---

## Lessons Logged

The 2026-04-29 incident contributed three new entries to the team's lessons-learned log:

- **#122** `bench update` upgraded pydantic but wiped pydantic_core — 10h hidden outage
- **#123** 7,153 root-owned files in bench venv from past `sudo pip install` — silent time bomb
- **#124** press `pyproject.toml` `>=` deps pulled pre-release transitives — `bench setup requirements` fails (fixed in fork: alibabacloud family pinned to `==`, alibabacloud-credentials declared direct)

See `frappe-press-lessons.md` (auto-memory) for the full text of each.

---

## How to push commits from press-ctrl (deploy key read-only workaround)

Press-ctrl has two GitHub deploy keys, both **read-only**. Direct `git push` fails with:
`ERROR: Permission to Veela-Beauty/press.git denied to deploy key`

### Method: Push via Hetzner dev box (65.109.65.159)

The Hetzner dev box has `~/.ssh/id_ed25519` added to GitHub as `elgogary` with write access.

1. **On press-ctrl**: Create a bundle of the commit(s):
   ```bash
   cd /home/frappe/frappe-bench/apps/press
   git bundle create /tmp/press_fix.bundle cloudflare-dns~1..cloudflare-dns
   ```

2. **From Hetzner dev box**: SCP the bundle and push:
   ```bash
   scp -i ~/.ssh/id_ed25519_old root@89.167.116.92:/tmp/press_fix.bundle /tmp/
   cd /tmp && git clone git@github.com:Veela-Beauty/press.git press-push 2>/dev/null || true
   cd /tmp/press-push && git checkout cloudflare-dns && git pull
   git pull /tmp/press_fix.bundle cloudflare-dns
   git push origin cloudflare-dns
   ```

3. **Back on press-ctrl**: Sync local with remote:
   ```bash
   git fetch veela cloudflare-dns && git reset --hard veela/cloudflare-dns
   ```

## press-f1 MariaDB exposed to internet — fixed 2026-05-06

**Issue**: Hetzner abuse report — MariaDB port 3306 was openly accessible from any IP on the internet. `bind-address = 0.0.0.0` with no firewall.

**Why bind-address can't be changed**: press-f1 runs Docker bench containers that connect to the host MariaDB via the public IP `89.167.57.21:3306` (configured in `common_site_config.json` `db_host`). Binding to `127.0.0.1` would break all bench sites.

**Fix**: iptables firewall rules to restrict port 3306 to trusted sources only.

### Rules applied

| Priority | Source | Action |
|----------|--------|--------|
| 1 | press-ctrl (89.167.116.92) | ACCEPT |
| 2 | press-f1 local (89.167.57.21) | ACCEPT |
| 3 | Docker bridge (172.17.0.0/16) | ACCEPT |
| 4 | Localhost (127.0.0.1) | ACCEPT |
| 5 | Everything else | DROP |

### Verification

```
External (dev box 65.109.65.159):  BLOCKED ✓
press-ctrl (89.167.116.92):       ALLOWED ✓
Docker bench containers:          ALLOWED ✓
```

### Persistence
- `iptables-persistent` installed
- Rules saved to `/etc/iptables/rules.v4`
- `netfilter-persistent.service` enabled on boot

### Recovery
```bash
# View rules
iptables -L INPUT -n -v --line-numbers | grep 3306

# Add a new trusted IP
iptables -I INPUT 5 -p tcp --dport 3306 -s <NEW_IP> -j ACCEPT
netfilter-persistent save

# Delete a rule
iptables -D INPUT <line-number>
netfilter-persistent save
```
