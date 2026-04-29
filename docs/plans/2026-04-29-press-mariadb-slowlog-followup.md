# Press MariaDB Slowlog + Proxy Nginx Logs Follow-Up Plan

> **Status:** Drafted 2026-04-29 after the log-server stack went live. Not yet executed.
> **Prerequisite:** Log Server (ElasticSearch + Filebeat) must be running — see `docs/runbook/log-server.md`.

**Goal:** Populate the last 3 "No data" panels on the Advanced Analytics page by shipping two more log sources to ES: MariaDB slowlog (per bench's database) and nginx access logs from the proxy server.

**Architecture:** Extends the existing Filebeat 7.17 stack on press-f1 with two new inputs and corresponding ES ingest pipelines. No new infrastructure; reuses the running ES container on press-ctrl.

**Tech Stack:** Filebeat 7.17 (existing), MariaDB slowlog format, nginx access log JSON format, Press's `mariadb_slow_query` and `nginx` ingest pipelines (already in the press repo at `playbooks/roles/filebeat_elasticsearch/files/`).

---

## Objective

Get **Requests by IP**, **Frequent Slow Queries**, and **Top Slow Queries** panels to show real data on the Site Insights → Advanced Analytics page.

**Summary:** wire two log sources into the existing Filebeat → ES pipeline.

## Definition of Done

- [ ] **MariaDB slowlog** flowing to ES with index `filebeat-*` and ingest pipeline `mariadb_slow_query`
- [ ] **Proxy nginx access logs** flowing to ES with the existing `nginx` ingest pipeline
- [ ] **Requests by IP** panel populates for at least 1 site with traffic
- [ ] **Frequent Slow Queries** panel populates for at least 1 site running queries >100ms
- [ ] **Top Slow Queries** panel populates for the same
- [ ] No regression on the 8 panels that work today (run-tests + Playwright check)
- [ ] Runbook updated: how to add new bench server + how to enable MariaDB slowlog per bench
- [ ] Commits on `cloudflare-dns` branch pushed to GitHub

## Before / After

**Before (today)**
```
Site Insights → Advanced Analytics:
  Working   (8 panels): Background Jobs, Background Jobs CPU Usage,
                        Frequent Requests, Slowest Requests,
                        Individual Request Time, Frequent Background Jobs,
                        Slowest Background Jobs, Individual Background Job Time
  Empty     (3 panels): Requests by IP, Frequent Slow Queries, Top Slow Queries
```

**After (DoD met)**
```
Site Insights → Advanced Analytics:
  Working  (11 panels): all of the above, plus
                        Requests by IP — top 10 IPs by request count + chart over time
                        Frequent Slow Queries — top 10 queries by frequency
                        Top Slow Queries — top 10 queries by total CPU time
```

| Metric | Before | After |
|---|---|---|
| Advanced Analytics panels with data | 8 / 11 | 11 / 11 |
| ES indices | 1 (`filebeat-*` for monitor.json + container stdout) | 1 (same — adds slowlog + nginx records to the same daily index) |
| Filebeat inputs on press-f1 | 3 (system, container stdout, monitor.json.log) | 5 (+ MariaDB slowlog, + nginx access log) |
| ES ingest pipelines | 2 (`monitor`, `nginx`) | 3 (+ `mariadb_slow_query`) |
| Disk used by ES | grows ~5 GB/month | grows ~10 GB/month (slow queries are noisy) |

---

## File Structure

| Action | Path | Purpose |
|---|---|---|
| Modify on press-f1 | `/etc/filebeat/inputs.d/mariadb_slowlog.yml` | Filebeat input that reads each bench's MariaDB slowlog |
| Modify on press-f1 | `/etc/filebeat/inputs.d/nginx_proxy.yml` | Filebeat input for the proxy server's nginx access logs |
| Install in ES | `_ingest/pipeline/mariadb_slow_query` | Parses slowlog format + extracts query / time / db |
| Modify on each bench's container | enable `slow_query_log=ON` in MariaDB config | Currently default off; needs `bench --site <site> set-config` per site OR a docker compose change |
| Modify | `docs/runbook/log-server.md` | Add "How to add MariaDB slowlog tracking" section |

---

## Tasks

### Task 1: Install `mariadb_slow_query` ingest pipeline in ES

**Files:** none in repo (HTTP call to ES)

- [ ] **Step 1.1: Install pipeline from press repo file**

The pipeline definition lives at `press/playbooks/roles/filebeat_elasticsearch/files/mariadb_slow_query.json` (verify exists before this step).

```bash
ssh root@press-ctrl 'source /opt/log-server/.env && \
  curl -sk -u frappe:$FRAPPE_QUERY_PASSWORD -XPUT \
    https://logs.sandbox.mvpstorm.com/elasticsearch/_ingest/pipeline/mariadb_slow_query \
    -H "Content-Type: application/json" \
    --data-binary @/home/frappe/frappe-bench/apps/press/press/playbooks/roles/filebeat_elasticsearch/files/mariadb_slow_query.json'
```

Expected: `{"acknowledged":true}`. If the file doesn't exist in the repo, fetch it from upstream Frappe Press.

---

### Task 2: Enable MariaDB slowlog on a representative bench

**Files:** none in repo (config tweak per bench database)

Currently MariaDB's `slow_query_log` is OFF on all benches. We need to:
- Turn it on
- Set `slow_query_log_file = /var/lib/mysql/<db_name>-slow.log`
- Set `long_query_time = 0.1` (queries slower than 100ms)
- Make the file readable by the host (so Filebeat can ship it)

- [ ] **Step 2.1: Pick a test bench (one with active traffic)**

Use `bench-0011-000112-press-f1` (gwis-stg lives here, lots of recent traffic).

- [ ] **Step 2.2: Enable slowlog inside the bench container's MariaDB**

Press benches run their own MariaDB inside each container. Connect via:
```bash
docker exec -it bench-0011-000112-press-f1 bash
mysql -u root -p$(cat /home/frappe/frappe-bench/sites/common_site_config.json | python -c "import json,sys; print(json.load(sys.stdin)['root_password'])") <<'SQL'
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 0.1;
SET GLOBAL slow_query_log_file = '/var/log/mysql/slow.log';
SQL
```

This is **runtime-only** — survives until container restart. To make permanent, edit `/etc/mysql/conf.d/slow-log.cnf` inside the container OR rebuild the bench image with the config baked in.

- [ ] **Step 2.3: Verify slowlog is being written**

```bash
docker exec bench-0011-000112-press-f1 ls -la /var/log/mysql/slow.log
docker exec bench-0011-000112-press-f1 tail -5 /var/log/mysql/slow.log
```

Should see slow query entries after a few minutes of traffic.

- [ ] **Step 2.4: Mount the slowlog dir from container to host**

This is the trickier part — by default `/var/log/mysql/` lives only inside the container. Two options:
- **(a)** Add a host bind-mount at bench creation time (requires Press provisioning change)
- **(b)** Periodically `docker cp` the slowlog out (hack)
- **(c)** Run `mysqldump --slow-log` from cron (nope, not a thing)
- **(d)** Use Filebeat with Docker autodiscover → reads `/var/lib/docker/containers/<id>/<id>-json.log` (only stdout, won't help)

Path forward: **(a)** is the right answer but requires Press's bench Dockerfile/compose changes. Alternative: use a sidecar Filebeat container per bench that mounts the bench's MariaDB volume. Both are real changes.

For this plan: **defer slowlog volume strategy to a separate task.** First step is making the pipeline + Filebeat input ready so when the volume becomes available, ingestion just works.

---

### Task 3: Add Filebeat input for MariaDB slowlog (placeholder, won't ingest until Task 2.4 done)

- [ ] **Step 3.1: Write input config**

```bash
ssh root@press-f1 "cat > /etc/filebeat/inputs.d/mariadb_slowlog.yml <<'YML'
- type: log
  enabled: true
  paths:
    # When bench's MariaDB slowlog is bind-mounted to host, configure path here.
    # Today: this list is empty so this input is a no-op.
    - /home/frappe/benches/*/mariadb-slow.log

  pipeline: mariadb_slow_query
  fields:
    log_type: mariadb_slow_query

  multiline.pattern: '^# Time:'
  multiline.negate: true
  multiline.match: after
YML
systemctl restart filebeat"
```

The multiline regex matches MariaDB slowlog format: each entry starts with `# Time:`, all lines after are part of the same query.

- [ ] **Step 3.2: Verify Filebeat doesn't error on missing files**

```bash
ssh root@press-f1 "journalctl -u filebeat -n 30 --no-pager | grep -i 'mariadb\|error'"
```

Expected: no errors from this input. Filebeat handles missing-path gracefully (just doesn't ship anything).

---

### Task 4: Filebeat input for proxy nginx access logs

The "Requests by IP" panel filters by `agent.name=proxy_server`. Press's NginxRequestGroupByChart looks at NGINX access logs from the proxy (the front-facing nginx) — different source than monitor.json.log inside the bench.

**Where do proxy nginx logs live?** Press provisions a proxy server (in this setup, that's also press-f1 since we're single-server). Nginx access logs typically at `/var/log/nginx/access.log` on the proxy host.

- [ ] **Step 4.1: Verify proxy nginx logs path**

```bash
ssh root@press-f1 "ls -la /var/log/nginx/access.log* 2>&1 | head"
```

If logs aren't in JSON format (default nginx text format), the `nginx` ingest pipeline (already installed) will parse them via grok.

- [ ] **Step 4.2: Add Filebeat input**

```bash
ssh root@press-f1 "cat > /etc/filebeat/inputs.d/nginx_proxy.yml <<'YML'
- type: log
  enabled: true
  paths:
    - /var/log/nginx/access.log

  pipeline: nginx
  fields:
    log_type: nginx_access
YML
systemctl restart filebeat"
```

- [ ] **Step 4.3: Generate test traffic + verify ingest**

Hit a site (e.g. `https://gwis-stg.sandbox.mvpstorm.com`). Within 30 sec, ES should have entries with `nginx.access.*` fields. Verify:

```bash
ssh root@press-ctrl 'source /opt/log-server/.env && \
  curl -sk -u frappe:$FRAPPE_QUERY_PASSWORD \
    "https://logs.sandbox.mvpstorm.com/elasticsearch/filebeat-*/_search?q=fields.log_type:nginx_access&size=1&pretty"'
```

Should return at least one hit with `nginx.access` fields filled in.

---

### Task 5: Verify panels populate

- [ ] **Step 5.1: Test on busy site via Playwright**

Open `/dashboard/sites/gwis-stg.sandbox.mvpstorm.com/insights/analytics`. Expand Advanced Analytics. Wait 5 sec. Confirm:
- Requests by IP shows IPs (after Task 4)
- Frequent Slow Queries shows queries (after Task 2 + 3 once volume is fixed)
- Top Slow Queries same

If still empty after the steps complete, debug:
- Check `get_advanced_analytics` API returns no errors
- Verify ES indices have the relevant fields (`source.ip`, `mariadb.slowlog.*`)

---

### Task 6: Document + commit

- [ ] **Step 6.1: Update runbook**

Append to `docs/runbook/log-server.md`:
- "Adding MariaDB slowlog to a bench" section with the conf changes
- "Adding proxy nginx logs" section explaining the input config

- [ ] **Step 6.2: Commit + push**

```
git commit -m "feat(log-server): MariaDB slowlog + proxy nginx ingestion"
```

---

## Risks

| Risk | Mitigation |
|---|---|
| MariaDB slowlog volume can't easily get to host without changing bench provisioning | Defer the volume work; Task 3 lays the groundwork |
| Slowlog at `long_query_time=0.1` is noisy → ES grows fast | Start at 1.0s, lower if needed; configure ILM at this point |
| Wrong proxy nginx log path on different server topologies | Audit `proxy_server` field on Server doc before assuming |
| `mariadb_slow_query.json` pipeline not in our press fork (upstream-only) | Fetch from upstream + commit to our `playbooks/roles/filebeat_elasticsearch/files/` |
| Re-enabling slowlog impacts MariaDB performance | Negligible at long_query_time=0.1 for typical Frappe workload |

## Out of scope (called out)

- Setting up the **Monitor Server** doctype (Prometheus stack) — separate plan, only needed if user wants Grafana dashboards too. Not required for any panel on Advanced Analytics.
- Migrating older Frappe sites to log `request.counter` — that's a per-site Frappe upgrade, not a log infrastructure change.
- Index Lifecycle Management for retention — manual cleanup cron is enough for now (slowlog will eat disk faster though, may force ILM sooner).

## Time estimate

| Task | Est. |
|---|---|
| 1: Install pipeline | 10 min |
| 2: Enable slowlog (1 bench) | 30 min |
| 3: Filebeat input config | 15 min |
| 4: Proxy nginx Filebeat input | 30 min |
| 5: Validate panels | 30 min |
| 6: Docs + commit | 30 min |
| **Total (excluding bench volume mount)** | **~2 hr** |
| **Bench volume mount work (Task 2.4)** | 1+ day (touches Press bench Dockerfile) |

Without the bench volume mount work, the slowlog input is a no-op. The proxy nginx work is independent and lands the "Requests by IP" panel.

Recommended split:
- **Phase 1 (this plan, ~2 hr):** Tasks 1, 3, 4, 5, 6 — gets "Requests by IP" working, lays groundwork for slowlog
- **Phase 2 (separate plan, 1+ day):** Bench Dockerfile change to mount MariaDB log dir to host
