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
| 1 | Generate `env-lock-prod.txt` and commit to a private repo | pending — needs lock-file repo decision |
| 1 | Push this runbook to Outline as well | pending — user decision |
| 3 | Daily drift-check cron (alerts if `pip freeze` ≠ lock file) | pending |
| 3 | Uptime monitor on `/api/method/ping` (Telegram/email alert if 5xx) | pending — needs tool decision (UptimeRobot / Uptime Kuma / Healthchecks.io) |
| 5 | Full rollback drill in maintenance window — deliberate break + verify wrapper auto-restores | pending — needs maintenance window |

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
