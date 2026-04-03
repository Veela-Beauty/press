# Critical Issues Tracker

## P1 — Blocking

### u4 Agent 401 Auth Failure
- **Impact:** All scheduled jobs to u4 fail (Purge Binlogs, Backups)
- **Root cause:** PBKDF2 hash in `/home/frappe/agent/config.json` on u4 doesn't match Press DB password
- **Fix:** See Lesson 59 in frappe-press-lessons.md

### press-f1 Backup Agent SSL Mismatch
- **Impact:** Automated site backups fail with `SSLCertVerificationError`
- **Root cause:** Backup agent uses `press-f1.sandbox.mvpstorm.com` but cert doesn't cover it
- **Fix:** Issue cert for `press-f1.sandbox.mvpstorm.com` or update agent SSL config

## P2 — Degraded Experience

### V16 Sites Can't Actually Run
- **Impact:** V16 bench deploys (Docker image created) but sites can't start without Python 3.14 runtime
- **Fix:** Install Python 3.14 on press-f1; Frappe v16 Docker base image may include it

### No Log Server (Elasticsearch)
- **Impact:** Analytics pages show empty charts
- **Fix:** Deploy an Elasticsearch/Kibana stack and configure `Press Settings.log_server`

### Cluster public flag resets on every save
- **Impact:** New Site flow breaks whenever anyone edits the Cluster record
- **Fix:** Patch Press `Cluster.after_save()` to re-set `public=1` if it was previously public

## P3 — Future Improvements

### Every new Hetzner server needs manual bootstrap
- 4 manual steps: loopback IP, Ansible, Nginx proxy, press_url
- **Fix:** Create Hetzner private network (vpc_id), snapshot image, fix `_setup_unified_server()` press_url variable

### No backup verification
- Sites are "backed up" but restores are never tested
- **Fix:** Periodic restore-to-test-site job

### Single point of failure (press-f1)
- All sites on one server
- **Fix:** Add press-f2, press-f3 servers to the cluster
