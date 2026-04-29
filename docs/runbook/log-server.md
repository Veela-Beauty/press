# Log Server Runbook

Operations manual for the ElasticSearch + Kibana + Filebeat stack that backs Press's site analytics layer.

## Architecture

```
press-f1 (each bench's container stdout)
  ↓ Filebeat 7.17.29 (host-level, type=container input)
  ↓ HTTPS POST https://logs.sandbox.mvpstorm.com/elasticsearch/_bulk
  ↓ HTTP Basic auth: frappe:<FRAPPE_QUERY_PASSWORD>
  ↓
press-ctrl
  ├─ nginx :443 (TLS for logs.sandbox.mvpstorm.com)
  │   ├─ /elasticsearch/* → ES :9200    (Press query path + Filebeat ingest)
  │   └─ /kibana/*       → Kibana :5601 (admins for debugging)
  ├─ Docker Compose stack at /opt/log-server/
  │   ├─ log-elasticsearch (1G heap, single-node, xpack.security off)
  │   └─ log-kibana
  └─ Volume: log-server_es-data
```

## Configuration files

| Path | Purpose |
|---|---|
| `/opt/log-server/.env` | passwords (KIBANA_PASSWORD, FRAPPE_QUERY_PASSWORD) — `chmod 600` |
| `/opt/log-server/docker-compose.yml` | ES + Kibana stack |
| `/etc/nginx/sites-available/logs.sandbox.mvpstorm.com` | TLS reverse proxy with basic auth |
| `/etc/nginx/htpasswd-elasticsearch` | basic auth for `frappe` user (Press queries + Filebeat ingest) |
| `/etc/nginx/htpasswd-kibana` | basic auth for Kibana UI |
| `/etc/letsencrypt/live/logs.sandbox.mvpstorm.com/` | TLS cert (auto-renewed) |
| `/etc/cron.d/certbot` | daily renewal cron |
| **on press-f1**: `/etc/filebeat/filebeat.yml` | output URL + auth — also has `setup.ilm.enabled: false` and `setup.template.enabled: false` (workaround for proxy 405 on PUT to ILM URLs) |

## Daily ops

### Restart the stack
```bash
ssh root@press-ctrl "cd /opt/log-server && docker compose restart"
```

### Check ES health
```bash
ssh root@press-ctrl "source /opt/log-server/.env && \
  curl -sk -u frappe:\$FRAPPE_QUERY_PASSWORD \
    https://logs.sandbox.mvpstorm.com/elasticsearch/_cluster/health"
```
Expect `status: green` (yellow is OK on single-node).

### View Kibana
Browser: `https://logs.sandbox.mvpstorm.com/kibana/`
User: `admin` / password from `/opt/log-server/.env` (KIBANA_PASSWORD).

### Check Filebeat status on a bench server
```bash
ssh root@press-f1 "systemctl status filebeat --no-pager | head -20 && \
  tail -20 /var/log/filebeat/filebeat"
```

### List indices + doc counts
```bash
ssh root@press-ctrl "source /opt/log-server/.env && \
  curl -sk -u frappe:\$FRAPPE_QUERY_PASSWORD \
    'https://logs.sandbox.mvpstorm.com/elasticsearch/_cat/indices?v'"
```

## Common tasks

### Rotate the `frappe` query password

1. Generate new password: `openssl rand -hex 24`
2. Update on press-ctrl:
   ```bash
   ssh root@press-ctrl 'sed -i "s/^FRAPPE_QUERY_PASSWORD=.*/FRAPPE_QUERY_PASSWORD=NEW/" /opt/log-server/.env && \
     source /opt/log-server/.env && \
     htpasswd -b /etc/nginx/htpasswd-elasticsearch frappe "$FRAPPE_QUERY_PASSWORD" && \
     systemctl reload nginx'
   ```
3. Update Press's Log Server doc (kibana_password field) via console:
   ```python
   doc = frappe.get_doc('Log Server', 'logs.sandbox.mvpstorm.com')
   doc.kibana_password = 'NEW'
   doc.monitoring_password = 'NEW'
   doc.save(ignore_permissions=True)
   frappe.db.commit()
   ```
4. Update each bench server's filebeat `password:` and restart filebeat.

### Renew TLS cert manually

```bash
ssh root@press-ctrl "certbot renew --deploy-hook 'systemctl reload nginx'"
```

(Cron at `/etc/cron.d/certbot` does this automatically daily at 03:00.)

### Add a new bench server's filebeat

```bash
ssh root@new-server "
  curl -fsSL https://artifacts.elastic.co/GPG-KEY-elasticsearch | gpg --dearmor > /usr/share/keyrings/elasticsearch-keyring.gpg && \
  echo 'deb [signed-by=/usr/share/keyrings/elasticsearch-keyring.gpg] https://artifacts.elastic.co/packages/7.x/apt stable main' > /etc/apt/sources.list.d/elastic-7.x.list && \
  apt-get update && apt-get install -y filebeat
"
# Then copy /etc/filebeat/filebeat.yml from press-f1, update name: field, and restart
```

### Backup ES data
```bash
ssh root@press-ctrl "docker exec log-elasticsearch \
  curl -X PUT 'http://localhost:9200/_snapshot/borgmatic' -H 'Content-Type: application/json' -d '{...}'"
```
For now: weekly volume snapshot (manual).

## Known limitations

### Compute panel still shows 0 hours

**Why:** Press's analytics layer queries `filebeat-*` for documents with `json.transaction_type=request` — these come from Frappe's `monitor.json.log` which lives **inside each bench Docker container** at `/home/frappe/frappe-bench/logs/monitor.json.log`. The host-level Filebeat we set up only sees container stdout/stderr (system logs, sshd, errors), not bench app logs.

**Path forward (follow-up):** one of:
- Mount each bench's `logs/` dir as a host volume so host Filebeat can read it
- Run a sidecar Filebeat container per bench
- Modify Press's analytics queries to use container stdout fields instead of monitor.json.log

This was out of scope for this plan; the ES + nginx + Filebeat-shell infrastructure is in place ready to receive the right log shape once we build it.

### Storage / Database panels still 0

Read from `tabSite Usage` table — populated by `update_disk_usages` scheduler. That scheduler queries the bench agent's reported disk sizes, not ES. Independent of log_server. Will populate naturally on next 15- or 45-minute scheduler tick now that sites are `Active`.

### ILM disabled

Filebeat's automatic Index Lifecycle Management is **disabled** in `filebeat.yml` because the nginx → ES proxy returns 405 for the date-math PUT requests Filebeat sends during ILM setup. Indexes are created daily by date suffix (e.g. `filebeat-7.17.29-2026.04.29`). Manual cleanup needed for old indices:

```bash
# Delete indices older than 90 days
curl -sk -u frappe:$PWD -XDELETE \
  "https://logs.sandbox.mvpstorm.com/elasticsearch/filebeat-7.17.29-$(date -d '90 days ago' +%Y.%m.%d)"
```

Add a weekly cron to automate.

## Recovery

### ES container won't start
1. Check disk space: `df -h /var/lib/docker`
2. Check ES logs: `docker logs log-elasticsearch --tail 100`
3. If heap-related: edit `docker-compose.yml`, drop `ES_JAVA_OPTS=-Xms1g -Xmx1g` to 512m, restart.

### Press analytics fails with auth error
1. Verify password in `/opt/log-server/.env` matches the one stored on `Log Server` doc → `kibana_password` field
2. Test: `curl -u frappe:$PWD https://logs.sandbox.mvpstorm.com/elasticsearch/_cluster/health`

### Roll back the entire log server
```bash
# Disable Press integration
bench --site demo.mvpstorm.com console <<<'frappe.db.set_single_value("Press Settings", "log_server", ""); frappe.db.commit()'

# Stop the stack
ssh root@press-ctrl "cd /opt/log-server && docker compose down"

# Filebeat keeps running but cannot reach ES — harmless, will retry forever
# To stop it: ssh root@press-f1 "systemctl stop filebeat"
```
No data loss for Press itself; Site Overview just shows 0 again.

## Build history

- 2026-04-29: initial setup. Plan: `docs/plans/2026-04-29-press-log-server-setup.md`
- All 4 indices `filebeat-7.17.29-2026.04.{26,27,28,29}` created, 73k+ docs (mostly container stdout).
