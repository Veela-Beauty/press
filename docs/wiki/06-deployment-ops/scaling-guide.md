# Scaling Guide

How to grow your Accurate Systems Cloud infrastructure from a single server to a multi-server cluster.

---

## Scaling Stages

```
Stage 1                    Stage 2                      Stage 3
Single Server              Split Roles                  Multi-Server Cluster
─────────────              ───────────                  ────────────────────

┌─────────────┐      ┌─────────────┐              ┌─────────────┐
│ Controller  │      │ Controller  │              │ Controller  │
│ + App Server│      │ (Press only)│              │ (Press only)│
│ + Database  │      └──────┬──────┘              └──────┬──────┘
│ + Proxy     │             │                            │
└─────────────┘      ┌──────┴──────┐         ┌──────────┼──────────┐
                     │ App Server  │         │          │          │
  ~5-10 sites        │ + Database  │    ┌────┴───┐ ┌────┴───┐ ┌───┴────┐
                     │ + Proxy     │    │ App #1 │ │ App #2 │ │ App #3 │
                     └─────────────┘    │ + DB   │ │ + DB   │ │ + DB   │
                                        └────────┘ └────────┘ └────────┘
                      ~10-50 sites
                                         ~50-200+ sites
```

---

## Stage 1: Single Server (Standalone)

**Current setup.** One server runs everything — Press controller, app server, database, proxy.

| Resource | Limit |
|----------|-------|
| Sites | 5–10 (depending on traffic) |
| vCPU | 4 shared |
| RAM | 8 GB |
| Disk | 80 GB |

**When to scale:** CPU consistently > 70%, RAM > 6 GB, or site response times degrade.

### How It Works Now

- **Controller** (`press-ctrl`): Runs Press app, dashboard, build jobs, Docker registry
- **App Server** (`press-f1`): Runs tenant sites in Docker containers, MariaDB, Nginx proxy
- Sites are created via dashboard → Press builds Docker image → deploys container on app server

---

## Stage 2: Add More App Servers

When `press-f1` is full, add a second (or third) app server to the same cluster.

### Step-by-Step

**1. Provision a new Hetzner server**

From the Press dashboard: **Servers → + New Server**

Or via Hetzner API (automated by Press if Hetzner token is configured in Cluster):
- Type: CX31 or CX41 (4–8 vCPU, 8–16 GB RAM)
- Image: Ubuntu 22.04
- Location: Same as existing servers (Falkenstein)

**2. Bootstrap the server**

```bash
# On press-ctrl as frappe user
bench --site demo.mvpstorm.com execute press.do_retry.bootstrap_new_server \
  --args '["new-server.sandbox.mvpstorm.com"]'

# Wait for Ansible to complete (5-15 min), then:
bench --site demo.mvpstorm.com execute press.do_retry.post_ansible_setup \
  --args '["new-server.sandbox.mvpstorm.com"]'

# Verify agent responds
bench --site demo.mvpstorm.com execute press.do_retry.ping_server_agent_authed \
  --args '["new-server.sandbox.mvpstorm.com"]'
```

See [Server Provisioning Guide](server-provisioning.md) for full details.

**3. Add DNS records**

In Cloudflare, add an A record for the new server:
- `new-server.sandbox.mvpstorm.com` → new server's public IP

The wildcard `*.sandbox.mvpstorm.com` already routes to the existing proxy. If using per-server routing, add specific records.

**4. Add server to Release Group**

In the Press dashboard:
- Go to the Release Group (e.g., `bench-0001`)
- Add the new server to the group
- Deploy a bench to the new server

**5. Migrate sites**

Move sites from the overloaded server to the new one:

```bash
# From Press dashboard: Site → Actions → Migrate
# Or via API:
bench --site demo.mvpstorm.com execute press.api.site.migrate \
  --kwargs '{"name": "site-name.sandbox.mvpstorm.com", "server": "new-server.sandbox.mvpstorm.com"}'
```

### DNS for Multiple App Servers

| Pattern | DNS Setup | Pros | Cons |
|---------|-----------|------|------|
| **Wildcard to proxy** | `*.domain` → proxy server | Simple, one record | Single point of failure |
| **Per-site DNS** | Each site → its server IP | Direct routing, no proxy | More DNS records to manage |
| **Load balancer** | `*.domain` → LB IP | Auto-distribution | Extra cost, complexity |

**Current approach:** Wildcard to proxy server (press-f1). The proxy routes to the correct container.

---

## Stage 3: Dedicated Database Servers

When sites grow large (heavy queries, big datasets), split the database to a dedicated server.

### When to Split

- MariaDB using > 4 GB RAM
- Slow queries affecting other sites
- Database backup time > 5 minutes
- Disk I/O becoming a bottleneck

### How Press Handles This

Press has built-in support for separate app and database servers:

| DocType | Role |
|---------|------|
| **Server** | App server — runs Docker containers with Frappe/ERPNext |
| **Database Server** | MariaDB — stores site databases |
| **Proxy Server** | Nginx — routes traffic to the correct container |

In standalone mode (current), one machine fills all three roles. To split:

1. Create a new **Database Server** in Press
2. Provision it (same bootstrap process)
3. New sites automatically use the dedicated DB server
4. Existing sites can be migrated with `bench --site ... migrate`

---

## Load Balancer (When and How)

### When Do You Need a Load Balancer?

| Sites | Traffic | LB Needed? | Why |
|-------|---------|:----------:|-----|
| < 30 | Low-medium | **No** | Single proxy server handles it |
| 30-80 | Medium | **Optional** | Failover protection, zero-downtime deploys |
| 80-150 | High | **Recommended** | Single proxy becomes bottleneck, SSL termination overhead |
| 150+ | Any | **Required** | Mandatory for HA, traffic distribution, and health checks |

### Load Balancer Options

| Option | Cost | Complexity | Best For |
|--------|------|:----------:|----------|
| **Hetzner Load Balancer** | ~EUR5/mo | Low | Quick setup, auto health checks |
| **Nginx reverse proxy** (dedicated) | ~EUR5/mo (CX11) | Medium | Full control, custom routing rules |
| **HAProxy** (dedicated) | ~EUR5/mo (CX11) | Medium-High | Advanced features, TCP+HTTP modes |
| **Cloudflare Load Balancing** | ~EUR5/mo per pool | Low | Global distribution, DDoS protection built-in |

**Recommended: Hetzner Load Balancer** for simplicity, or **Cloudflare LB** if you already use Cloudflare DNS (which we do).

### Hetzner Load Balancer Setup

```bash
# 1. Create LB in Hetzner Cloud Console
#    - Type: LB11 (25 targets, 10k concurrent connections)
#    - Location: Same as your servers (Falkenstein)
#    - Algorithm: Round Robin or Least Connections

# 2. Add targets (your proxy/app servers)
#    - press-f1 (89.167.57.21)
#    - press-f2 (new server IP)
#    - etc.

# 3. Configure services
#    - Frontend: HTTPS (443) -> Backend: HTTPS (443)
#    - Frontend: HTTP (80) -> Backend: HTTP (80)
#    - Health check: GET /api/method/ping -> expect 200

# 4. Update DNS
#    - Change *.sandbox.mvpstorm.com A record from app server IP -> LB public IP
#    - Change *.demo.mvpstorm.com A record from app server IP -> LB public IP
```

### Cloudflare Load Balancer Setup

Since we already use Cloudflare DNS, this is the lowest-friction option:

```
Cloudflare Dashboard -> Traffic -> Load Balancing

1. Create Pool: "europe-pool"
   - Origin: press-f1 (89.167.57.21)
   - Origin: press-f2 (new IP)
   - Health check: HTTPS GET /api/method/ping
   - Interval: 60s, timeout: 5s

2. Create Load Balancer
   - Hostname: *.sandbox.mvpstorm.com
   - Default pool: europe-pool
   - Fallback pool: (same pool or a failover pool)
   - Steering: Random (simplest) or Least Outstanding Requests

3. SSL/TLS
   - Cloudflare handles SSL termination (Full mode)
   - Origin servers still need valid certs for Cloudflare -> Origin connection
```

### Press Integration with Load Balancer

Press routes sites to specific servers via the **Proxy Server** DocType. With a load balancer:

1. **Site-to-Server mapping** stays the same (Press tracks which server hosts which site)
2. **LB routes traffic** to the correct proxy/app server based on health checks
3. **Nginx on each server** routes to the correct Docker container based on hostname

```
Client -> LB (*.domain.com) -> Server-N -> Nginx -> Docker container -> Site
                  |
          Health checks remove
          unhealthy servers
```

**Important:** The LB does NOT replace Press site routing. It distributes traffic across proxy servers. Each proxy still knows which container to forward to.

---

## 200-Site Architecture Blueprint

Running 200 ERPNext sites requires careful planning. Here is the concrete architecture:

### Server Layout

```
                          +------------------+
                          |  Load Balancer   |
                          |  (Hetzner LB11)  |
                          |  EUR5/mo         |
                          +--------+---------+
                                   |
              +--------------------+--------------------+
              |                    |                     |
     +--------+--------+  +-------+--------+  +--------+--------+
     | Proxy Server #1 |  | Proxy Server #2|  | Proxy Server #3 |
     | CX11 (EUR5/mo)  |  | CX11 (EUR5/mo) |  | CX11 (EUR5/mo)  |
     | Nginx only       |  | Nginx only      |  | Nginx only       |
     +--------+---------+  +-------+---------+  +--------+---------+
              |                    |                      |
    +---------+---------+   +-----+-----+    +-----------+-----------+
    |         |         |   |     |     |    |           |           |
+---+--+ +---+--+ +---+--++--+--++--+--++---+--+  +---+--+   +---+--+
|App #1| |App #2| |App #3||A #4 ||A #5 ||App #6|  |App #7|   |App #8|
|CX41  | |CX41  | |CX41  ||CX41 ||CX41 ||CX41  |  |CX41  |   |CX41  |
|25    | |25    | |25    ||25   ||25   ||25    |  |25    |   |25    |
|sites | |sites | |sites ||sites||sites||sites |  |sites |   |sites |
+---+--+ +---+--+ +---+--++--+--++--+--++---+--+  +---+--+   +---+--+
    |        |        |      |      |       |        |            |
    +--------+----+---+------+------+       +--------+----+-------+
                  |                                       |
           +------+------+                         +------+------+
           | DB Server #1|                         | DB Server #2|
           | CX41 (16GB) |                         | CX41 (16GB) |
           | 100 sites   |                         | 100 sites   |
           +-------------+                         +-------------+

           +-------------+
           | Controller  |
           | CX33 (8GB)  |     +--------------+
           | Press +     |---->| Docker       |
           | Build Server|     | Registry     |
           +-------------+     | (on ctrl)    |
                               +--------------+
```

### Resource Requirements (200 Sites)

| Role | Count | Spec | Cost/mo | Purpose |
|------|:-----:|------|--------:|---------|
| **Controller** | 1 | CX33 (4vCPU, 8GB, 80GB) | EUR15 | Press app, dashboard, builds, registry |
| **Load Balancer** | 1 | Hetzner LB11 | EUR5 | Traffic distribution, health checks |
| **Proxy Server** | 2-3 | CX11 (2vCPU, 2GB, 20GB) | EUR10-15 | Nginx SSL termination, routing |
| **App Server** | 8 | CX41 (8vCPU, 16GB, 160GB) | EUR160 | Docker containers, site workloads |
| **Database Server** | 2 | CX41 (8vCPU, 16GB, 160GB) | EUR40 | MariaDB for 100 sites each |
| **Monitoring** | 1 | CX11 (2vCPU, 2GB, 20GB) | EUR5 | Prometheus + Grafana (optional) |
| **Total** | **15-16** | | **~EUR235-240** | **200 sites** |

**Cost per site: ~EUR1.20/mo** infrastructure cost.

### Alternative: Fewer, Bigger Servers

| Role | Count | Spec | Cost/mo |
|------|:-----:|------|--------:|
| Controller | 1 | CX33 | EUR15 |
| Load Balancer | 1 | LB11 | EUR5 |
| App+Proxy Server | 5 | CCX33 (8 dedicated vCPU, 32GB) | EUR250 |
| Database Server | 2 | CCX23 (4 dedicated vCPU, 16GB) | EUR80 |
| **Total** | **9** | | **~EUR350** |

Dedicated CPU (CCX) costs more but gives predictable performance. Choose this for SLA-bound clients.

---

## Edge Cases at Scale (100+ Sites)

These issues do NOT appear at 10-30 sites but WILL appear at 100+:

### 1. Build Queue Saturation

**Problem:** At 200 sites, app updates trigger 200 Docker image rebuilds. Each build takes 5-20 minutes. The build queue backs up for hours.

**Symptoms:** Deploy Candidate stuck in "Running" for hours. New site creation delayed.

**Fix:**
- Dedicated build server (separate from controller): CX41 with 16GB RAM
- Parallel builds: configure `workers.build` count > 1 in `common_site_config.json`
- Stagger updates: do not update all sites at once -- use Release Groups to batch

```json
{
  "workers": {
    "build": {"timeout": 3600, "workers": 3}
  }
}
```

### 2. Docker Registry Disk Explosion

**Problem:** Each build creates a new Docker image (~500MB-1GB). 200 sites x 10 versions = 1-2 TB.

**Symptoms:** Controller disk full, builds fail, `docker push` errors.

**Fix:**
- Registry garbage collection: `docker exec registry bin/registry garbage-collect /etc/docker/registry/config.yml`
- Prune old images: keep only last 3 versions per site
- External registry: move to Hetzner Object Storage or S3-compatible storage

```bash
# Weekly cleanup cron on controller
0 3 * * 0 docker exec registry bin/registry garbage-collect /etc/docker/registry/config.yml --delete-untagged
```

### 3. MariaDB Connection Pool Exhaustion

**Problem:** Each site opens 4-6 persistent DB connections. 100 sites on one DB server = 400-600 connections. Default MariaDB `max_connections` = 151.

**Symptoms:** `Too many connections` errors, sites returning 500.

**Fix:**
```ini
# /etc/mysql/mariadb.conf.d/99-press.cnf
[mysqld]
max_connections = 1000
innodb_buffer_pool_size = 8G
innodb_log_file_size = 1G
table_open_cache = 4000
thread_cache_size = 128
```

### 4. Backup Window Too Long

**Problem:** Backing up 200 sites sequentially takes 6-10 hours. If a backup fails mid-way, you have inconsistent state.

**Symptoms:** Backup Agent Jobs timing out, partial backups.

**Fix:**
- Parallel backups: Press already supports concurrent backup jobs
- Stagger backup times: configure different backup windows per server
- Use MariaDB `mariabackup` instead of `mysqldump` for large databases (faster, non-blocking)
- External backup storage: push to S3/Hetzner Object Storage

### 5. Scheduler Overload on Controller

**Problem:** Press scheduler runs jobs every 5 seconds. With 200 sites, `poll_pending_jobs` queries grow. The scheduler itself becomes a bottleneck.

**Symptoms:** `poll_pending_jobs` taking > 5 seconds, job results delayed, site status not updating.

**Fix:**
- Increase scheduler workers: `bench setup supervisor` with higher worker count
- Dedicate controller resources: ensure Press controller is NOT also an app server
- DB indexes: verify indexes on `Agent Job` (status, server, modified)
- Archive old Agent Jobs: jobs older than 30 days should be archived

### 6. DNS Record Limits

**Problem:** At 200 sites, you have 200+ DNS A records if using per-site DNS. Cloudflare free tier allows 3500 records per zone -- not a hard limit yet, but API calls slow down.

**Symptoms:** Site creation takes longer, DNS propagation delays.

**Fix:**
- Use wildcard DNS (`*.cluster.domain.com`) -- one record covers all sites in a cluster
- Press creates CNAME records for custom domains pointing to the wildcard
- Rate limit DNS API calls: Press already batches Cloudflare API calls

### 7. SSL Certificate Renewal Storms

**Problem:** With 200 sites and per-site certs, certbot tries to renew dozens at once. Let's Encrypt rate limits: 50 certs per domain per week.

**Symptoms:** `certbot renew` fails for some certs, sites get SSL warnings.

**Fix:**
- **Use wildcard certs** (already our approach): one `*.cluster.domain.com` covers all sites
- Custom domains: use HTTP-01 challenge (one per domain) instead of DNS-01
- Stagger custom domain cert renewals across the week

### 8. Agent Job Table Grows Massive

**Problem:** At 200 sites with frequent operations (backups, updates, monitoring), the `Agent Job` table grows to millions of rows. Press queries become slow.

**Symptoms:** Dashboard loading slowly, "Recent Jobs" taking 10+ seconds.

**Fix:**
```sql
-- Archive old agent jobs (run monthly via cron)
DELETE FROM `tabAgent Job`
WHERE modified < DATE_SUB(NOW(), INTERVAL 90 DAY)
  AND status IN ('Success', 'Failure');
```

---

## 200-Site Deployment Checklist

### Phase 1: Foundation (0-50 sites)
- [ ] Controller + 2 app servers (standalone mode)
- [ ] Wildcard DNS for each cluster domain
- [ ] Automated backups configured
- [ ] Monitoring basic: `supervisorctl status` + disk alerts
- [ ] Build worker dedicated (not sharing with web workers)

### Phase 2: Growth (50-100 sites)
- [ ] Add 2 more app servers (total: 4)
- [ ] Split database to dedicated DB server
- [ ] Add load balancer (Hetzner LB or Cloudflare LB)
- [ ] MariaDB tuning: `max_connections`, `innodb_buffer_pool_size`
- [ ] Docker registry cleanup cron
- [ ] Agent Job archival cron (monthly)

### Phase 3: Scale (100-200 sites)
- [ ] Add 4 more app servers (total: 8)
- [ ] Second dedicated DB server
- [ ] Dedicated build server (separate from controller)
- [ ] Parallel build workers (3+)
- [ ] Prometheus + Grafana monitoring
- [ ] Backup parallelization
- [ ] DNS consolidated to wildcards (no per-site records)
- [ ] Load test with realistic traffic before onboarding clients
- [ ] Disaster recovery plan: daily full backups to external storage

### Phase 4: Enterprise (200+ sites)
- [ ] Multiple clusters (geographic distribution)
- [ ] Read replicas for heavy-read sites
- [ ] CDN (Cloudflare) for static assets
- [ ] SLA monitoring and alerting (PagerDuty/Opsgenie)
- [ ] Automated scaling scripts (add server on threshold breach)

---

## Stage 4: Multiple Clusters (Regions)

For geographic distribution or client isolation:

```
Cluster: Europe (Falkenstein)          Cluster: Middle East (Jeddah)
┌──────────┐  ┌──────────┐            ┌──────────┐  ┌──────────┐
│ App #1   │  │ App #2   │            │ App #1   │  │ App #2   │
│ EU sites │  │ EU sites │            │ ME sites │  │ ME sites │
└──────────┘  └──────────┘            └──────────┘  └──────────┘
       │              │                      │              │
       └──────┬───────┘                      └──────┬───────┘
              │                                     │
       ┌──────┴──────┐                       ┌──────┴──────┐
       │  DB Server  │                       │  DB Server  │
       │  (EU)       │                       │  (ME)       │
       └─────────────┘                       └─────────────┘
```

Press supports multiple clusters natively. Each cluster has:
- Its own set of servers
- Its own Hetzner project (or other provider)
- Its own root domain and DNS zone
- Independent scaling

---

## Server Plan Sizing Guide

| Plan | vCPU | RAM | Disk | Sites | Use Case |
|------|------|-----|------|-------|----------|
| **Starter** | 2 | 4 GB | 40 GB | 1–3 | Development, demo |
| **Small** | 4 | 8 GB | 80 GB | 5–15 | Small production |
| **Medium** | 8 | 16 GB | 160 GB | 15–40 | Medium production |
| **Large** | 16 | 32 GB | 320 GB | 40–100 | Large production |
| **Dedicated** | 32 | 64 GB | 500 GB | 100+ | Enterprise |

**Rule of thumb:** Each Frappe/ERPNext site needs ~200–500 MB RAM at rest, more under load.

---

## Scaling Checklist

### Before Adding a Server
- [ ] Current server CPU > 70% sustained
- [ ] RAM usage > 75% sustained
- [ ] Site response times degrading
- [ ] Hetzner API token configured in Press Cluster
- [ ] DNS wildcard or per-site records planned

### After Adding a Server
- [ ] Server bootstrapped and agent responding
- [ ] DNS records created in Cloudflare
- [ ] Server added to Release Group
- [ ] Bench deployed to new server
- [ ] Test site created and verified
- [ ] Sites migrated from overloaded server
- [ ] Monitoring configured (if using Prometheus/Grafana)

### Monitoring What to Watch

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| CPU usage | > 60% avg | > 80% avg | Add app server |
| RAM usage | > 70% | > 85% | Upgrade plan or split DB |
| Disk usage | > 70% | > 85% | Expand disk or archive old backups |
| Site response | > 2s avg | > 5s avg | Investigate slow queries, add capacity |
| Docker containers | > 10 per server | > 20 | Add app server |
| MariaDB connections | > 100 | > 200 | Split to dedicated DB |

---

## Cost Estimation

Based on Hetzner pricing (Europe):

| Setup | Monthly Cost | Capacity |
|-------|-------------|----------|
| 1 controller + 1 app (CX33) | ~€30 | 5–15 sites |
| 1 controller + 2 app (CX33) | ~€45 | 15–30 sites |
| 1 controller + 2 app (CX41) + 1 DB (CX41) | ~€80 | 30–60 sites |
| 1 controller + 4 app + 2 DB | ~€150 | 60–120 sites |

Costs scale linearly. Each additional CX33 (~€15/mo) adds capacity for ~10-15 more sites.

---

## Related Docs

- [Server Provisioning](server-provisioning.md) — how to bootstrap new servers
- [Ops Toolkit](ops-toolkit.md) — management scripts for server operations
- [Architecture](../00-getting-started/architecture.md) — system design overview
