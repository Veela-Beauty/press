# Scaling Self-Hosted Press

Guide for scaling a self-hosted Frappe Press deployment from a single server to multi-server architecture.

## Current Architecture (Single Server)

```
Press Controller (press-ctrl / 89.167.116.92)
  - Frappe Bench + Press app
  - Docker Registry (:5000)
  - Build Server
  - Dashboard (autodeploypanel.mvpstorm.com)
        |
        | Agent API + Docker Pull
        v
App Server (press-f1 / 89.167.57.21)
  - Nginx (proxy + bench configs)
  - Docker containers (benches)
  - MariaDB (local)
  - Redis, Agent
  - Serves: *.sandbox.mvpstorm.com
```

**Default resource profile (4vCPU / 8GB RAM):**
- 1 gunicorn worker / 4 threads per bench container
- No swap configured
- Default MariaDB settings (no tuning)
- Single point of failure

## Known Bottlenecks

### 1. Nginx Proxy Buffer Overflow (502 after login)

Frappe's authenticated response headers (session cookies, CSP, X-headers) exceed nginx's default `proxy_buffer_size` of 4k/8k.

**Symptom:** 502 Bad Gateway after login, unauthenticated pages work fine.

**Diagnosis:**
```bash
tail -f /var/log/nginx/error.log
# Look for: upstream sent too big header while reading response header from upstream
```

**Fix:** Add to each `@webserver` location block in `/home/frappe/benches/<bench>/nginx.conf`:
```nginx
proxy_buffer_size 32k;
proxy_buffers 8 32k;
proxy_busy_buffers_size 64k;
```

Then: `nginx -t && systemctl reload nginx`

> **Note:** New deploys overwrite bench nginx.conf. To make permanent, patch the agent's nginx template.

### 2. Gunicorn Workers

Default: 1 worker / 4 threads per bench. Under load, this is the primary bottleneck.

### 3. MariaDB Defaults

Default MariaDB config is tuned for minimal resource usage, not production workloads.

### 4. No Swap

Without swap, OOM killer terminates processes when memory is exhausted.

## Phase 1: Optimize Single Server (~20 clients)

### Server Upgrade

Upgrade press-f1 to **8 vCPU / 16GB RAM** (Hetzner CX42 or equivalent).

### Gunicorn Workers

Set 4 workers per bench for better concurrency:

```bash
# In bench container or bench config
environment.GUNICORN_WORKERS=4
```

Each worker handles one request at a time (with 4 threads for I/O). 4 workers = 4 concurrent requests per bench.

### MariaDB Tuning

Edit `/etc/mysql/mariadb.conf.d/50-server.cnf`:

```ini
[mysqld]
innodb_buffer_pool_size = 4G
max_connections = 500
innodb_log_file_size = 256M
innodb_flush_log_at_trx_commit = 2
innodb_flush_method = O_DIRECT
query_cache_type = 0
```

Then: `systemctl restart mariadb`

### Swap

```bash
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### Redis

```bash
# /etc/redis/redis.conf
maxmemory 1gb
maxmemory-policy allkeys-lru
```

### Monitoring

```bash
htop                          # CPU/RAM per process
docker stats                  # Per-container resource usage
mysqladmin processlist        # Active DB connections
```

## Phase 2: Horizontal Scaling (~200 clients)

### Architecture

```
Press Controller (press-ctrl)
  - Dashboard + API
  - Build Server
  - Docker Registry
        |
        | Agent API
   _____|_____________________
  |           |               |
  v           v               v
App Srv 1   App Srv 2     App Srv 3
(f1)        (f2)          (f3)
nginx       nginx         nginx
docker      docker        docker
agent       agent         agent
  |           |               |
  |___________|_______________|
              |
              v
  Dedicated DB Server
  16GB+ RAM, SSD
  MariaDB (innodb_buffer_pool = 10G)
```

### How Press Routes Traffic

Press uses **host-based routing** via the Proxy Server doctype:

1. DNS wildcard (`*.sandbox.mvpstorm.com`) points to the Proxy Server IP
2. Proxy Server nginx matches the `Host` header to a site
3. Each site maps to an upstream (bench container on a specific app server)
4. Bench-level `nginx.conf` has explicit `server_name` for its sites

This is NOT round-robin load balancing — each site lives on exactly one app server. Press distributes sites across servers at creation time.

### Adding App Servers

1. Provision new server in Hetzner (8vCPU / 16GB)
2. Add Server record in Press (type: App Server)
3. Run `setup_server()` then `setup_standalone()` via Press
4. Add to Release Group so new deploys create benches on all servers
5. New sites can be placed on the new server

### Dedicated DB Server

1. Provision DB server (16GB+ RAM, fast SSD)
2. Add Database Server record in Press
3. Configure `mariadb_root_password` in the record
4. Point app servers to external DB (update bench container env)

### Capacity Planning

| Metric | Per App Server (8GB) | Per App Server (16GB) |
|--------|---------------------|----------------------|
| Benches | 3-5 | 6-10 |
| Sites per bench | 10-15 | 10-15 |
| Total sites | 30-75 | 60-150 |
| Gunicorn workers | 4 per bench | 4 per bench |

Rule of thumb: **~50 sites per 8GB app server** with 4 gunicorn workers per bench.

## Deploy Workflow (Pulling Code Fixes)

When an app has a bug fix that needs to reach a running site:

1. **Fix and push** the code to the app's git repo
2. **Create Deploy Candidate** in Press with updated commit hash
3. **Build** the Deploy Candidate (creates Docker image)
4. **Deploy** to create a new bench with the updated image
5. **Migrate** existing sites to the new bench, or recreate if broken

```python
# Example: Create Deploy Candidate with updated app hash
dc = frappe.get_doc({
    "doctype": "Deploy Candidate",
    "group": "bench-0005",
    "apps": [
        {"app": "frappe", "hash": "abc123"},
        {"app": "erpnext", "hash": "def456"},
        {"app": "my_app", "hash": "FIXED_COMMIT_HASH"}
    ]
})
dc.insert()
dc.build()
```

Full cycle takes ~10 minutes (clone, build image, push, deploy container, create/migrate site).

## Two-Layer Nginx Routing

Understanding nginx routing is critical for debugging 502s and site access issues:

1. **proxy.conf** (`/home/frappe/agent/nginx/proxy.conf`) — Agent-managed, wildcard `server_name`, maps sites to upstreams via `$upstream_server_hash`
2. **bench nginx.conf** (`/home/frappe/benches/<bench>/nginx.conf`) — Per-bench, explicit `server_name` for each site

Nginx uses exact match first, so bench configs take priority over proxy.conf wildcards. When a new bench is deployed, its nginx.conf must list the site's domain as `server_name`.

After any deploy or site migration, verify:
```bash
# Check upstream ports
grep "^upstream" /home/frappe/agent/nginx/proxy.conf
# Check site-to-server mapping
grep "server_name" /home/frappe/benches/*/nginx.conf
# Test config
nginx -t
```
