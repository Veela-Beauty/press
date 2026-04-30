# Press-Ctrl Operational Rules

**Server:** press-ctrl @ `89.167.116.92` (autodeploypanel.mvpstorm.com)
**Last incident:** 2026-04-29 21:03 — `pydantic`/`pydantic_core` mismatch → 10h outage
**Postmortem:** `/home/eslam/docs/plans/2026-04-30-press-ctrl-stability-runbook.md`

---

## The Iron Rules

### 1. NEVER run `sudo pip install` or `pip install` as root

**Why:** It writes files into the bench venv with `root:root` ownership. The next `bench update` (which runs as `frappe`) hits `Permission denied` and fails halfway. We had **7,153 root-owned files** in the venv from past mistakes — silently waiting to break the next update.

**Correct:**
```bash
sudo -u frappe /home/frappe/frappe-bench/env/bin/pip install <pkg>
# or, even better:
sudo -u frappe bash -c 'cd /home/frappe/frappe-bench && bench setup requirements --python'
```

If you ever need to fix accidental ownership pollution:
```bash
chown -R frappe:frappe /home/frappe/frappe-bench/env/
```

---

### 2. NEVER run a bare `bench update` on production

**Why:** No pre-flight check, no rollback. The 2026-04-29 incident happened because `bench update` upgraded `pydantic` but failed to install matching `pydantic_core`. The defect stayed hidden for 10 hours until workers were recycled.

**Correct (once available):**
```bash
sudo -u frappe bench-update-safe              # full safe update (preflight + update + postflight + safe restart + smoke + auto-rollback)
sudo -u frappe bench-update-safe --dry-run    # preview only — pre-flight runs, no changes made
sudo -u frappe bench-update-safe --skip-update --no-restart   # validate env health only (no updates, no disruption)
```

**The wrapper does:**
1. Pre-flight — venv ownership check, pip check (warning), 5-app boot test, supervisor state, save pip-freeze snapshot to `/home/frappe/snapshots/`
2. Update — `bench update --pull --requirements --no-backup`
3. Post-flight — boot test in fresh subprocess + WSGI entry-point load test (BEFORE supervisor restart)
4. Auto-rollback — if post-flight fails, restores env from snapshot + restarts (no human intervention needed)
5. Safe restart — supervisorctl stop with 15s timeout + force-kill stragglers + start with 30s timeout + healthcheck poll up to 30s
6. Auto-rollback — if restart or healthcheck fails, restores env from snapshot

**Manual emergency rollback** (if wrapper fails or for ad-hoc recovery):
```bash
sudo -u frappe /home/frappe/scripts/rollback.sh                            # use latest snapshot
sudo -u frappe /home/frappe/scripts/rollback.sh /path/to/snapshot.txt      # specific snapshot
```

**Manual playbook** (if `/usr/local/bin/bench-update-safe` is missing):
```bash
sudo -u frappe /home/frappe/frappe-bench/env/bin/pip freeze > /home/frappe/snapshots/pre-update-$(date +%Y%m%d-%H%M%S).txt
sudo -u frappe bench update --pull --requirements
sudo -u frappe /home/frappe/frappe-bench/env/bin/python -c "import frappe, press, daman_backup, frappe_theme_switcher, sanad_business_intelligence_ai; print('OK')"  # MUST return OK before next step
sudo -u frappe bench restart
curl -sS -o /dev/null -w "%{http_code}\n" -H "Host: autodeploypanel.mvpstorm.com" http://127.0.0.1/api/method/ping
```

If the import test fails: **STOP**. Do not restart. Roll back via `pip install --force-reinstall --no-deps -r <snapshot>.txt`.

---

### 3. Updates only happen in a maintenance window

**Why:** Even with `bench-update-safe`, a failed update may need manual intervention. Don't update during peak hours.

**Maintenance windows (default):**
- Weekdays 02:00 — 04:00 Cairo time
- Sundays 22:00 — 24:00 Cairo time

For ad-hoc updates: ping the team in `#press-ops` channel first, get an ack, then update.

---

### 4. NEVER force-push to `cloudflare-dns` branch

**Why:** It's our white-label fork's primary deploy branch. Force-push deletes other engineers' commits.

**Correct:**
- Always merge or rebase locally, then push (no force)
- For divergent histories, open a PR for review

---

### 5. Server changes are reversible by default

Before any destructive operation, take a snapshot:
```bash
# Frappe site backup
sudo -u frappe bench --site demo.mvpstorm.com backup --with-files

# pip freeze before pip changes
sudo -u frappe /home/frappe/frappe-bench/env/bin/pip freeze > /home/frappe/snapshots/<context>-$(date +%Y%m%d-%H%M%S).txt

# git tag before risky merges
cd /home/frappe/frappe-bench/apps/press && git tag pre-<change>-$(date +%Y%m%d)
```

---

## Health-Check Quick Reference

```bash
# Supervisor — all must be RUNNING
supervisorctl status

# Python imports — must print "OK"
sudo -u frappe /home/frappe/frappe-bench/env/bin/python -c "import frappe, press, daman_backup; print('OK')"

# Public endpoint — must be 200
curl -sS -o /dev/null -w "%{http_code}\n" https://autodeploypanel.mvpstorm.com/api/method/ping

# Dependency drift — must be empty (no output)
sudo -u frappe /home/frappe/frappe-bench/env/bin/pip check

# Venv ownership — must be 0
find /home/frappe/frappe-bench/env/ -not -user frappe 2>/dev/null | wc -l
```

---

## Escalation

If a Frappe process is FATAL and you can't recover in 10 minutes:
1. Check error logs: `tail -80 /home/frappe/frappe-bench/logs/web.error.log`
2. Compare current `pip freeze` to most recent snapshot in `/home/frappe/snapshots/`
3. If pkg mismatch suspected, restore from snapshot
4. If still stuck: contact Eslam, share the error log + supervisorctl status output
5. Do **not** randomly try `bench update` again — it's likely what caused the issue

---

## Snapshots Directory

Path: `/home/frappe/snapshots/`
Naming: `<context>-YYYYMMDD-HHMMSS.txt` — context is one of: `pre-update`, `pre-realign`, `pre-rollback`, `manual`

Auto-cleaned: snapshots older than 90 days are pruned by `/etc/cron.d/snapshot-cleanup` (TODO Phase 3).

---

*Last updated: 2026-04-30. If you change this file, update `MEMORY.md` and the wiki runbook accordingly.*
