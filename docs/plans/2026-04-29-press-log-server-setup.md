# Press Log Server (ElasticSearch) Setup Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get the Site Overview Compute / Storage / Database panels to show real numbers by deploying ElasticSearch + Filebeat on the existing infra, registering a Log Server in Press, and wiring `Press Settings.log_server` to it.

**Architecture:** Bypass Press's Ansible-driven Log Server provisioning (which expects a dedicated VM) and instead run ES + Kibana as Docker Compose services on press-ctrl, fronted by the existing nginx reverse proxy with TLS for `logs.sandbox.mvpstorm.com`. Each bench server (currently just press-f1) gets a Filebeat agent on the host that ships nginx access logs from all bench containers to ES. Press queries `https://logs.sandbox.mvpstorm.com/elasticsearch/filebeat-*/_search` exactly as its analytics layer expects.

**Tech Stack:** ElasticSearch 7.x, Kibana 7.x, Filebeat 7.x, Docker Compose, nginx, Let's Encrypt (certbot), Frappe Press

---

## Objective

Make the Compute / Storage / Database panels on every Site Overview show real values by creating the missing log-aggregation pipeline. Press's analytics code already expects this exact shape; the only thing missing is the infrastructure.

**Summary:** deploy ES + Kibana on press-ctrl, ship bench nginx logs into it via Filebeat, register a Log Server doctype manually, point Press at it.

## Definition of Done

- [ ] DNS `logs.sandbox.mvpstorm.com` → `89.167.116.92` (Cloudflare A record)
- [ ] TLS cert issued and auto-renewing for `logs.sandbox.mvpstorm.com`
- [ ] ES container running on press-ctrl, port 9200 internal-only
- [ ] Kibana container running on press-ctrl, port 5601 internal-only
- [ ] ES has `frappe` user with HTTP Basic auth, password matches the value we put on the Log Server doc
- [ ] nginx on press-ctrl proxies:
  - `https://logs.sandbox.mvpstorm.com/elasticsearch/*` → ES :9200
  - `https://logs.sandbox.mvpstorm.com/kibana/*` → Kibana :5601 (with separate basic auth)
- [ ] Filebeat on press-f1 host shipping nginx access logs from every bench's container to ES
- [ ] ES index pattern `filebeat-*` exists with at least one bench's traffic indexed
- [ ] `Log Server` record created in Press with hostname=`logs.sandbox.mvpstorm.com`, `is_server_setup=1`, `monitoring_password` and `kibana_password` matching the deployed ES auth
- [ ] `Press Settings.log_server` = `logs.sandbox.mvpstorm.com`
- [ ] Manual smoke test: `update_cpu_usages` runs without errors and writes to `Site Usage` for at least one site
- [ ] Site Overview for `stlube-stg.sandbox.mvpstorm.com` shows non-zero **Compute** after some traffic + scheduler tick
- [ ] Site Overview shows real **Database** size from Site Usage records
- [ ] Documentation in `docs/runbook/log-server.md` covers: re-issue cert, restart ES, rotate password, add a new bench server's filebeat
- [ ] Backup strategy documented (ES data volume snapshot once a week)
- [ ] All changes committed to `cloudflare-dns` branch and pushed to GitHub

## Before / After

**Before (today's state)**
```
Press Settings.log_server: None
nginx access logs:         live in each bench container, never aggregated
tabSite Usage:             empty for every site (0 records install-wide)
Site Overview Compute:     0 hours
Site Overview Storage:     0 Bytes
Site Overview Database:    0 Bytes
```

**After (DoD met)**
```
Press Settings.log_server: logs.sandbox.mvpstorm.com
press-ctrl :9200           ES container (Docker Compose)
press-ctrl :5601           Kibana container (Docker Compose)
nginx logs flow:           bench container → host filebeat → ES filebeat-YYYY.MM.DD
tabSite Usage:             populated by update_cpu/disk schedulers
Site Overview Compute:     real CPU time per site (e.g. 0.34 hours / 1 hour plan)
Site Overview Storage:     real public + private file sizes
Site Overview Database:    real DB size from agent reports
Daily Usage chart:         renders 30-day rolling chart
```

| Metric | Before | After |
|---|---|---|
| Log aggregation infra | none | ES + Kibana on press-ctrl |
| Sites with usage data | 0 / 27 | 27 / 27 over time |
| Compute panel | always 0 | real value (~24h delay for first ingest) |
| Storage / Database panels | always 0 | real values within 1 hour |
| Disk used by ES on press-ctrl | 0 | grows ~1-5 GB/month/bench (configure retention) |
| RAM used by ES + Kibana | 0 | ~3 GB (ES heap 1G + Kibana 0.5G + buffers) |
| Monthly cost | €0 | €0 (no new server) |

---

## File Structure

| Action | Path | Purpose |
|---|---|---|
| Create | `/opt/log-server/docker-compose.yml` | ES + Kibana stack |
| Create | `/opt/log-server/.env` | Password + heap config |
| Create | `/etc/nginx/sites-available/logs.sandbox.mvpstorm.com` | TLS reverse proxy |
| Create | `/etc/nginx/htpasswd-elasticsearch` | Basic auth for `frappe` user (Press's query auth) |
| Create | `/etc/nginx/htpasswd-kibana` | Separate basic auth for Kibana UI |
| Create on press-f1 | `/etc/filebeat/filebeat.yml` | Ship nginx logs to ES |
| Create on press-f1 | `/etc/systemd/system/filebeat.service` (via apt) | Auto-start filebeat |
| Create | `docs/runbook/log-server.md` (in press repo) | Operations manual |

---

## Tasks

### Task 1: DNS + TLS for `logs.sandbox.mvpstorm.com`

**Files:** none in repo (Cloudflare web UI + certbot on press-ctrl)

- [ ] **Step 1.1: Add Cloudflare A record**

In Cloudflare DNS for `mvpstorm.com`:
- Type: A
- Name: `logs.sandbox`
- IPv4: `89.167.116.92`
- Proxy: **DNS only** (gray cloud — must be DNS-only because Press's analytics layer talks raw HTTPS to ES, not through Cloudflare)
- TTL: Auto

Verify:
```bash
dig +short logs.sandbox.mvpstorm.com
# Expect: 89.167.116.92
```

- [ ] **Step 1.2: Issue Let's Encrypt cert via certbot on press-ctrl**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "certbot certonly --nginx -d logs.sandbox.mvpstorm.com --non-interactive --agree-tos -m eslam.elgogary@gmail.com"
```

Expected: `Successfully received certificate.` Cert at `/etc/letsencrypt/live/logs.sandbox.mvpstorm.com/fullchain.pem`.

If certbot's nginx plugin fails (port 80 conflict), use webroot:
```bash
certbot certonly --webroot -w /var/www/html -d logs.sandbox.mvpstorm.com ...
```

- [ ] **Step 1.3: Verify auto-renewal cron**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "systemctl list-timers | grep certbot"
```

Expected: a `certbot.timer` is active. If not: `systemctl enable --now certbot.timer`.

---

### Task 2: Generate auth passwords

**Files:** `/opt/log-server/.env`, `/etc/nginx/htpasswd-elasticsearch`, `/etc/nginx/htpasswd-kibana`

- [ ] **Step 2.1: Generate 3 strong passwords**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 'mkdir -p /opt/log-server && cd /opt/log-server && \
  echo "ELASTIC_PASSWORD=$(openssl rand -hex 24)" > .env && \
  echo "KIBANA_PASSWORD=$(openssl rand -hex 24)" >> .env && \
  echo "FRAPPE_QUERY_PASSWORD=$(openssl rand -hex 24)" >> .env && \
  chmod 600 .env && cat .env'
```

Save the 3 passwords — you'll need them for Press doctype config in Task 5.

- [ ] **Step 2.2: Create nginx htpasswd files**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 'cd /opt/log-server && \
  source .env && \
  apt-get install -y apache2-utils && \
  htpasswd -bc /etc/nginx/htpasswd-elasticsearch frappe "$FRAPPE_QUERY_PASSWORD" && \
  htpasswd -bc /etc/nginx/htpasswd-kibana admin "$KIBANA_PASSWORD"'
```

Expected: two files created, contents look like `frappe:$apr1$...` and `admin:$apr1$...`.

---

### Task 3: Deploy ElasticSearch + Kibana via Docker Compose

**Files:** `/opt/log-server/docker-compose.yml`

- [ ] **Step 3.1: Write the compose file**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 'cat > /opt/log-server/docker-compose.yml <<COMPOSE
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.17.20
    container_name: log-elasticsearch
    restart: unless-stopped
    environment:
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
      - xpack.security.enabled=false
      # Press authenticates at the nginx layer, not at ES. ES is bound to 127.0.0.1 only.
    ulimits:
      memlock:
        soft: -1
        hard: -1
    volumes:
      - es-data:/usr/share/elasticsearch/data
    ports:
      - "127.0.0.1:9200:9200"
    healthcheck:
      test: ["CMD-SHELL", "curl -fs http://localhost:9200/_cluster/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
  kibana:
    image: docker.elastic.co/kibana/kibana:7.17.20
    container_name: log-kibana
    restart: unless-stopped
    depends_on:
      elasticsearch: { condition: service_healthy }
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
      - SERVER_BASEPATH=/kibana
      - SERVER_REWRITEBASEPATH=true
    ports:
      - "127.0.0.1:5601:5601"
volumes:
  es-data:
COMPOSE'
```

- [ ] **Step 3.2: Set vm.max_map_count (ES requires it)**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  'sysctl -w vm.max_map_count=262144 && \
   grep -q "vm.max_map_count" /etc/sysctl.conf || echo "vm.max_map_count=262144" >> /etc/sysctl.conf'
```

- [ ] **Step 3.3: Start the stack**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "cd /opt/log-server && docker compose up -d"
```

- [ ] **Step 3.4: Wait for ES healthy + verify**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "for i in {1..20}; do curl -s http://127.0.0.1:9200/_cluster/health | grep -q green && echo READY && break; sleep 5; done; \
   curl -s http://127.0.0.1:9200/_cluster/health"
```

Expected: `{"cluster_name":"docker-cluster","status":"green",...}`. If yellow → that's also OK for single-node.

---

### Task 4: nginx reverse proxy for HTTPS

**Files:** `/etc/nginx/sites-available/logs.sandbox.mvpstorm.com`

- [ ] **Step 4.1: Write the nginx site config**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 'cat > /etc/nginx/sites-available/logs.sandbox.mvpstorm.com <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name logs.sandbox.mvpstorm.com;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name logs.sandbox.mvpstorm.com;

    ssl_certificate     /etc/letsencrypt/live/logs.sandbox.mvpstorm.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/logs.sandbox.mvpstorm.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # ElasticSearch query path — used by Press analytics + filebeat ingest
    location /elasticsearch/ {
        auth_basic "Press Logs ES";
        auth_basic_user_file /etc/nginx/htpasswd-elasticsearch;
        proxy_pass http://127.0.0.1:9200/;
        proxy_set_header Host \$host;
        proxy_buffering off;
        client_max_body_size 100M;
    }

    # Kibana UI — separate basic auth, never queried by Press
    location /kibana/ {
        auth_basic "Kibana";
        auth_basic_user_file /etc/nginx/htpasswd-kibana;
        proxy_pass http://127.0.0.1:5601;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Filebeat ingest path — same backend as /elasticsearch/, scoped path so we
    # could later restrict per-server certs/auth without affecting Press's query path
    location /filebeat/ {
        auth_basic "Filebeat Ingest";
        auth_basic_user_file /etc/nginx/htpasswd-elasticsearch;
        proxy_pass http://127.0.0.1:9200/;
        client_max_body_size 100M;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/logs.sandbox.mvpstorm.com /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx'
```

- [ ] **Step 4.2: Verify HTTPS reaches ES through nginx**

From your laptop:
```bash
source /opt/log-server/.env  # on press-ctrl, capture FRAPPE_QUERY_PASSWORD
curl -u frappe:$FRAPPE_QUERY_PASSWORD https://logs.sandbox.mvpstorm.com/elasticsearch/_cluster/health
```

Expected: same JSON `{"cluster_name":...,"status":"green"...}` you got internally.

- [ ] **Step 4.3: Verify Kibana loads**

In your browser: `https://logs.sandbox.mvpstorm.com/kibana/`
- Should prompt basic auth (`admin` / `KIBANA_PASSWORD`)
- After auth, Kibana UI should load

---

### Task 5: Register Log Server in Press (skipping Ansible)

**Files:** none in repo (DB record only)

- [ ] **Step 5.1: Create Log Server doc via Frappe console**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 'cd /home/frappe/frappe-bench && \
  source /opt/log-server/.env && \
  bench --site demo.mvpstorm.com console <<PY
import frappe
doc = frappe.get_doc({
    "doctype": "Log Server",
    "hostname": "logs",
    "domain": "sandbox.mvpstorm.com",
    "ip": "89.167.116.92",
    "private_ip": "89.167.116.92",
    "ssh_user": "root",
    "ssh_port": 22,
    "agent_password": frappe.generate_hash(),
    "monitoring_password": "$FRAPPE_QUERY_PASSWORD",
    "kibana_password": "$FRAPPE_QUERY_PASSWORD",
    "frappe_user_password": frappe.generate_hash(),
    "is_server_setup": 1,
    "status": "Active",
}).insert(ignore_permissions=True)
frappe.db.commit()
print("Created Log Server:", doc.name)
PY'
```

The doc.name will be `logs.sandbox.mvpstorm.com` — the same string Press uses to build query URLs.

**Note:** we set `monitoring_password` and `kibana_password` to the SAME value (the htpasswd password for `frappe` user). Press's analytics code reads `kibana_password` for its ES query auth.

- [ ] **Step 5.2: Set Press Settings.log_server**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 'cd /home/frappe/frappe-bench && \
  bench --site demo.mvpstorm.com console <<PY
import frappe
frappe.db.set_single_value("Press Settings", "log_server", "logs.sandbox.mvpstorm.com")
frappe.db.commit()
print("Press Settings.log_server set")
PY'
```

- [ ] **Step 5.3: Verify Press can reach ES through its analytics layer**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 'cd /home/frappe/frappe-bench && \
  bench --site demo.mvpstorm.com console <<PY
from press.api.analytics import get_current_cpu_usage
result = get_current_cpu_usage("stlube-stg.sandbox.mvpstorm.com")
print("get_current_cpu_usage returned:", result)
PY'
```

Expected: returns a number (probably 0 since no logs yet) without raising. If it raises with "Connection error" or "Auth failed" — fix the password / URL before proceeding.

---

### Task 6: Install Filebeat on press-f1, ship bench nginx logs

**Files on press-f1:** `/etc/filebeat/filebeat.yml`, systemd unit (auto-installed by apt)

- [ ] **Step 6.1: Find where each bench's nginx writes access logs**

Each bench is a Docker container on press-f1. Press's nginx-in-bench writes access logs inside the container. Filebeat needs them on the HOST. Two options:
- (a) Mount each bench's `/var/log/nginx/` to a host path
- (b) Use Docker's logging driver to write to host filesystem

For zero-touch on existing benches, use (a) by reading directly from each container's overlay filesystem. Filebeat 7.x has a `docker.container_logs` autodiscover that does this automatically:

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  'ssh -o StrictHostKeyChecking=no root@89.167.57.21 \
     "docker exec bench-0006-000023-press-f1 ls /home/frappe/frappe-bench/logs/ 2>/dev/null | head -5 && \
      docker inspect bench-0006-000023-press-f1 --format=\"{{.GraphDriver.Data.MergedDir}}\""'
```

This tells us the log path inside container + the overlay path on host. We'll use the overlay path approach.

- [ ] **Step 6.2: Install Filebeat 7.17 on press-f1**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  'ssh root@89.167.57.21 "
    curl -fsSL https://artifacts.elastic.co/GPG-KEY-elasticsearch | apt-key add - && \
    echo \"deb https://artifacts.elastic.co/packages/7.x/apt stable main\" > /etc/apt/sources.list.d/elastic-7.x.list && \
    apt-get update && apt-get install -y filebeat=7.17.20"'
```

- [ ] **Step 6.3: Configure Filebeat with Docker autodiscover**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  'source /opt/log-server/.env && \
   ssh root@89.167.57.21 "cat > /etc/filebeat/filebeat.yml <<FB
filebeat.autodiscover:
  providers:
    - type: docker
      hints.enabled: false
      templates:
        - condition:
            contains:
              docker.container.name: bench-
          config:
            - type: container
              paths:
                - /var/lib/docker/containers/\\\${data.docker.container.id}/*.log
              exclude_lines: ['^\\s*\$']

output.elasticsearch:
  hosts: [\"https://logs.sandbox.mvpstorm.com/filebeat\"]
  username: \"frappe\"
  password: \"\$FRAPPE_QUERY_PASSWORD\"
  ssl.verification_mode: full
FB
systemctl enable --now filebeat"'
```

- [ ] **Step 6.4: Verify Filebeat is shipping logs**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "ssh root@89.167.57.21 'systemctl status filebeat --no-pager | head -20 && journalctl -u filebeat -n 30 --no-pager | tail -30'"
```

Expected: `active (running)`, no errors. Some "harvester started" lines per bench.

- [ ] **Step 6.5: Confirm ES has filebeat-* index**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  'source /opt/log-server/.env && \
   curl -u frappe:$FRAPPE_QUERY_PASSWORD https://logs.sandbox.mvpstorm.com/elasticsearch/_cat/indices?v 2>&1 | grep filebeat'
```

Expected: at least one `filebeat-7.17.20-YYYY.MM.DD-NNNNNN` index with non-zero `docs.count`.

- [ ] **Step 6.6: Generate test traffic to a real site**

In the browser, hit `https://stlube-stg.sandbox.mvpstorm.com/app` a few times so its nginx writes access log entries.

---

### Task 7: Validate end-to-end

- [ ] **Step 7.1: Force-run update_cpu_usages**

```bash
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 'cd /home/frappe/frappe-bench && \
  bench --site demo.mvpstorm.com console <<PY
from press.press.doctype.site.site_usages import update_cpu_usages
update_cpu_usages()
print("triggered")
import time; time.sleep(15)
import frappe
v = frappe.db.get_value("Site", "stlube-stg.sandbox.mvpstorm.com", "current_cpu_usage")
print("stlube-stg current_cpu_usage:", v)
PY'
```

Expected: a non-zero value (representing % of plan) OR 0 if site has no plan but the function ran without error.

- [ ] **Step 7.2: Open Site Overview in Playwright + screenshot**

Reload `/dashboard/sites/stlube-stg.sandbox.mvpstorm.com/overview`. Take screenshot. Compute panel should show fractional hours OR a number reflecting recent traffic.

- [ ] **Step 7.3: Verify Daily Usage chart loads**

```javascript
// In Playwright console:
fetch('/api/method/press.api.analytics.daily_usage', {
  method: 'POST', credentials: 'include',
  headers: {'Content-Type':'application/json','X-Frappe-CSRF-Token':'token'},
  body: JSON.stringify({name:'stlube-stg.sandbox.mvpstorm.com', timezone:'Europe/Berlin'})
}).then(r=>r.json()).then(console.log)
```

Expected: `data` array has entries (one per day with traffic), `plan_limit` may still be 0 if no plan.

---

### Task 8: Documentation + commit

**Files:** `docs/runbook/log-server.md` (in press repo)

- [ ] **Step 8.1: Write the runbook**

Cover:
- Architecture diagram
- How to restart ES / Kibana (`cd /opt/log-server && docker compose restart`)
- How to rotate the frappe query password (regen, update htpasswd, update Log Server doc, update filebeat)
- How to renew TLS cert manually
- How to add a new bench server's filebeat (rerun Task 6 steps on the new host)
- How to set up retention (delete filebeat indices older than 90d via curator or ILM)
- Backup strategy (weekly snapshot of `/var/lib/docker/volumes/log-server_es-data` to MinIO)

- [ ] **Step 8.2: Commit + relay-push**

```bash
git add docs/runbook/log-server.md
git commit -m "docs(runbook): log server (ES + Filebeat) operations manual"
# Relay-push from Hetzner box (same pattern as previous session commits)
```

---

## Risks & Rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| ES OOMs press-ctrl | Heap capped at 1G, single-node mode, 26G free RAM headroom | `docker compose down` + `Press Settings.log_server = ""` |
| TLS cert renewal breaks | Certbot timer + nginx reload hook standard pattern | Manual `certbot renew --deploy-hook 'systemctl reload nginx'` |
| Filebeat ships too much / fills disk | Default Filebeat retention is 90d, ES disk ~5G/month/bench | Add ILM policy or curator cron once we see real growth |
| Auth bypass — wrong password in Press doc | Step 5.3 verification fails immediately if auth wrong | Just update Log Server doc with correct password |
| Bench nginx logs not actually JSON-parseable | Press's analytics expects request_type field; filebeat-docker module parses by default | If parsing fails, install Filebeat nginx module (`filebeat modules enable nginx`) |
| ES data corruption | None at first; week 2 add weekly volume snapshot | Restore from snapshot, accept gap |

**Total impact**: pure addition. Existing benches and Press functionality continue working with `log_server=""` if anything goes wrong; nothing depends on ES being up.

---

## Time estimate

| Task | Est. |
|---|---|
| 1: DNS + TLS | 15 min |
| 2: Passwords + htpasswd | 5 min |
| 3: Docker Compose stack | 30 min (ES boot ~2 min) |
| 4: nginx reverse proxy | 15 min |
| 5: Register Log Server + Press settings | 10 min |
| 6: Filebeat on press-f1 | 45 min (autodiscover validation iteration) |
| 7: Validation | 30 min (waiting for ingest + scheduler) |
| 8: Runbook + commit | 30 min |
| **Total** | **~3 hours** |

---

## Out of scope (call out, don't deliver)

- Replicating Press's full Ansible playbook (`log.yml`) — we're using Docker Compose instead
- Multi-server ES cluster — single-node is fine until > 100 benches
- Log shipping from Press itself (control plane logs) — separate concern
- Custom Kibana dashboards — Press doesn't use Kibana, only ES query API
- Migrating historical Site Usage data — past 16 days have no logs, will start tracking from now
