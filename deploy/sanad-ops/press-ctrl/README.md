# Press-Ctrl Operations Config

Source-of-truth for press-ctrl operational artifacts: Python env lock file, safety scripts, and operator rules.

**Server:** press-ctrl @ `89.167.116.92` (autodeploypanel.mvpstorm.com)
**Full runbook:** [docs/wiki/06-deployment-ops/press-ctrl-stability-runbook.md](../../../docs/wiki/06-deployment-ops/press-ctrl-stability-runbook.md)

---

## What's here

```
deploy/sanad-ops/press-ctrl/
├── env-lock-prod.txt           Canonical pip freeze of the verified-good env
├── scripts/
│   ├── lib.sh                  Shared bash helpers (logging, role-switch,
│   │                           safe_restart, force_kill_frappe_workers, etc.)
│   ├── pre-flight.sh           Pre-update validation (ownership, pip check,
│   │                           boot test, supervisor state, snapshot)
│   ├── post-flight.sh          Post-pip-install validation (boot test +
│   │                           WSGI load — runs BEFORE supervisor restart)
│   ├── rollback.sh             Restore env from a snapshot + safe restart
│   └── bench-update-safe       Main orchestrator — REPLACES `bench update`
└── rules/
    └── press-ctrl-rules.md     Operator-facing iron rules (mirror of
                                /etc/sanad/press-ctrl-rules.md on the box)
```

---

## env-lock-prod.txt

Generated 2026-04-30 from `pip freeze` after the post-pydantic-incident realignment. Every Python package the bench needs at the exact version known to boot cleanly. **Update this file only after a verified successful run of `bench-update-safe`** — and never by hand.

### How to regenerate

After a successful safe update on press-ctrl:
```bash
ssh root@89.167.116.92 \
  'sudo -u frappe /home/frappe/frappe-bench/env/bin/pip freeze' \
  > /home/eslam/data/erpnext-app-repos/press_local/deploy/sanad-ops/press-ctrl/env-lock-prod.txt
cd /home/eslam/data/erpnext-app-repos/press_local
git add deploy/sanad-ops/press-ctrl/env-lock-prod.txt
git commit -m "ops(press-ctrl): refresh env-lock-prod.txt (after <change>)"
git push accurate-systems cloudflare-dns
```

### How to use it for disaster recovery

If press-ctrl needs to be rebuilt or restored:
```bash
git clone <press-fork> && cd press
sudo -u frappe /home/frappe/frappe-bench/env/bin/pip install \
  --force-reinstall --no-deps -r deploy/sanad-ops/press-ctrl/env-lock-prod.txt
```

### How to detect drift (Phase 3 will automate this)

```bash
diff <(ssh root@89.167.116.92 'sudo -u frappe /home/frappe/frappe-bench/env/bin/pip freeze') \
     deploy/sanad-ops/press-ctrl/env-lock-prod.txt
```
Any output = the live env has drifted from the lock. Investigate with `git log` to see when the lock was last updated and what changed.

---

## scripts/

These five files are **deployed onto press-ctrl** at `/home/frappe/scripts/` and the orchestrator is symlinked to `/usr/local/bin/bench-update-safe`. The copies in this directory are the source-of-truth.

### Deploy procedure

After editing any script in this directory:
```bash
cd deploy/sanad-ops/press-ctrl/scripts
tar czf /tmp/sanad-scripts.tgz lib.sh pre-flight.sh post-flight.sh rollback.sh bench-update-safe
scp -i ~/.ssh/id_ed25519_old /tmp/sanad-scripts.tgz root@89.167.116.92:/tmp/
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 'cd /home/frappe/scripts && \
  tar xzf /tmp/sanad-scripts.tgz && \
  chown frappe:frappe * && \
  chmod 755 *.sh bench-update-safe && \
  chmod 644 lib.sh && \
  ls -la'
```

### Verify the deployed scripts match this directory

```bash
for f in lib.sh pre-flight.sh post-flight.sh rollback.sh bench-update-safe; do
  diff <(ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 "cat /home/frappe/scripts/$f") \
       "deploy/sanad-ops/press-ctrl/scripts/$f" && echo "$f: MATCH" || echo "$f: DRIFT"
done
```

---

## rules/press-ctrl-rules.md

Mirror of `/etc/sanad/press-ctrl-rules.md` on press-ctrl. Operator-facing rules. After editing here:

```bash
scp -i ~/.ssh/id_ed25519_old \
  deploy/sanad-ops/press-ctrl/rules/press-ctrl-rules.md \
  root@89.167.116.92:/etc/sanad/press-ctrl-rules.md
```

The wiki version at `docs/wiki/06-deployment-ops/press-ctrl-stability-runbook.md` is more comprehensive and is the long-form companion to this concise on-box file.

---

## Future additions (Phase 3)

When monitoring lands:
- `monitoring/drift-check.cron` — daily cron that runs the diff above
- `monitoring/uptime-config.yml` — Uptime Kuma / UptimeRobot config (TBD)
- `monitoring/alert-channel.env` — Telegram bot token / email recipient (in Infisical, NOT committed)

---

## Why this lives in the press fork (not a separate repo)

Pragmatic choice — single repo to maintain, push pipeline already proven, scope clear (it's `deploy/`, parallel to other deploy artifacts). If ops scripts ever grow to cover other servers (Lipton, AccuBuild prod, etc.), we can promote `sanad-ops/` to its own repo via `git filter-repo`.

---

## Related

- [docs/wiki/06-deployment-ops/press-ctrl-stability-runbook.md](../../../docs/wiki/06-deployment-ops/press-ctrl-stability-runbook.md) — full runbook (incident postmortem, pipeline diagram, manual recovery, lessons)
- `/home/eslam/docs/plans/2026-04-30-press-ctrl-stability-runbook.md` (on dev box) — original plan with Objective / Definition of Done / Before-After
- Auto-memory: `press-ctrl-stability.md` and `frappe-press-lessons.md` lessons #122 / #123 / #124
