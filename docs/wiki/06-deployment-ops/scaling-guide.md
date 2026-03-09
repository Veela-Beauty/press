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
