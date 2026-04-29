# Press Log Server Architecture (Self-Hosted on press-ctrl)

> Built 2026-04-29. See `docs/runbook/log-server.md` for ops procedures.

## High-level picture

```mermaid
graph TB
  subgraph press-f1["press-f1.sandbox.mvpstorm.com (bench server)"]
    direction TB
    Bench0006["bench-0006-* containers<br/>(10 sites)"]
    Bench0011["bench-0011-* containers<br/>(5 sites)"]
    Bench0015["bench-0015-* containers<br/>(3 sites)"]
    BenchOther["… 17 total benches"]

    BenchLogs[("/home/frappe/benches/&lt;bench&gt;/logs/<br/>monitor.json.log<br/>(bind-mount from container)")]

    Bench0006 -.bind-mount.-> BenchLogs
    Bench0011 -.bind-mount.-> BenchLogs
    Bench0015 -.bind-mount.-> BenchLogs
    BenchOther -.bind-mount.-> BenchLogs

    Filebeat["Filebeat 7.17.29<br/>(host-level systemd)<br/>+ pipeline=monitor"]
    BenchLogs --> Filebeat
  end

  subgraph press-ctrl["press-ctrl.veelabeauty.com (Press control plane + log host)"]
    direction TB
    Nginx["nginx :443<br/>logs.sandbox.mvpstorm.com<br/>HTTP Basic auth"]

    subgraph LogStack["Docker Compose: /opt/log-server/"]
      ES["ElasticSearch 7.17.20<br/>:9200 (loopback only)<br/>1 GB heap, single-node"]
      Kibana["Kibana 7.17.20<br/>:5601 (loopback only)<br/>basepath=/kibana"]
      ESVolume[("es-data volume")]
      ES --> ESVolume
    end

    Nginx -- /elasticsearch/* --> ES
    Nginx -- /kibana/* --> Kibana
    Nginx -- /filebeat/* --> ES

    Press["Frappe Press<br/>(in frappe-bench container)"]
    PressDB[("MariaDB:<br/>Log Server doctype<br/>Press Settings.log_server")]
    Press --> PressDB
  end

  Filebeat -- "HTTPS POST<br/>auth=frappe:&lt;FRAPPE_QUERY_PASSWORD&gt;" --> Nginx

  Press -- "GET /elasticsearch/filebeat-*/_search<br/>auth=frappe:&lt;kibana_password&gt;" --> Nginx

  Browser["User browser<br/>autodeploypanel.mvpstorm.com"]
  Press -- get_current_usage --> Browser
  Browser -- "Site Overview panels<br/>(Compute / Storage / Database)" --> Browser
```

## Data flow — what fills each panel

```mermaid
sequenceDiagram
  participant User
  participant Frappe as Frappe (in bench container)
  participant FilebeatHost as Filebeat (host)
  participant ES
  participant Press
  participant Dashboard

  Note over Frappe: User makes any HTTP request to the site
  Frappe->>Frappe: Logs request to /home/frappe/frappe-bench/logs/monitor.json.log<br/>{transaction_type:request, request:{counter, path, ...}, site}

  Note over FilebeatHost: Reads from /home/frappe/benches/<bench>/logs/monitor.json.log<br/>(bind-mounted from each container)
  FilebeatHost->>ES: POST /_bulk via nginx → ingest pipeline=monitor<br/>JSON-decoded into json.* fields

  Dashboard->>Press: GET /api/method/...get_current_usage(stite)
  Press->>ES: POST /elasticsearch/filebeat-*/_search<br/>filter: json.transaction_type=request AND json.site=X<br/>sort: @timestamp desc, size 1
  ES-->>Press: latest request hit with json.request.counter
  Press-->>Press: cpu_hours = counter / 3.6e9
  Press-->>Dashboard: {cpu, storage, database, ...}
  Dashboard-->>User: "Compute: 0.00082 hours"
```

## Failure modes and what they look like to users

| Failure | What user sees | Diagnosis | Fix |
|---|---|---|---|
| ES down | "0 hours" | Press's `get_current_cpu_usage` catches all exceptions → returns 0 silently | Restart `/opt/log-server` stack |
| `kibana_password` drift between nginx and Log Server doc | "0 hours" | 401 from nginx, swallowed | Re-sync passwords |
| `monitor` ingest pipeline missing | filebeat retries every event with 404, no docs in `filebeat-*` | Check `/elasticsearch/_ingest/pipeline/monitor` | `PUT` from press repo's `playbooks/roles/filebeat_elasticsearch/files/monitor.json` |
| Filebeat ILM 405 through proxy | Filebeat won't ship anything | `journalctl -u filebeat` shows 405 errors | `setup.ilm.enabled: false` in filebeat.yml |
| Older Frappe (no `request.counter`) | "0 hours" only on some sites | ES has docs but counter field missing | Upgrade Frappe per-site (no log-side fix) |
| Bench logs not bind-mounted | filebeat reads but no real Frappe events | `docker inspect` doesn't show `/home/frappe/frappe-bench/logs` mount | Re-provision bench through Press (it'll add the mount) |

## Capacity assumptions

```mermaid
graph LR
  subgraph press-ctrl
    direction LR
    RAM["30 GB total<br/>4 GB used (existing services)<br/>~3 GB ES+Kibana<br/>~23 GB free"]
    Disk["301 GB total<br/>71 GB used (registry, Docker images)<br/>+ ~5 GB/month/bench (filebeat)<br/>~218 GB free for 1+ year"]
  end
```

ES growth estimates:
- ~5 GB / month / active bench
- 17 benches → ~85 GB / month at full activity
- Realistic ~30 GB / month given typical traffic
- 6 months until disk pressure → set up index retention by then

## Security model

- ES + Kibana bound to **127.0.0.1** only on press-ctrl. Not reachable from internet.
- Public access only via nginx HTTPS with **HTTP Basic auth** (htpasswd).
- TLS via Let's Encrypt — auto-renewing daily 03:00 UTC via `/etc/cron.d/certbot`.
- Frappe `frappe` user (used by Press's queries + Filebeat ingest) has same password as the htpasswd entry — **must stay in sync** with `Log Server.kibana_password`.
- Kibana UI has its own `admin` user with its own password (separate htpasswd).
- ES `xpack.security` is **disabled** because authentication happens at nginx level. ES itself is open to anyone who can reach 127.0.0.1:9200 on press-ctrl — only press-ctrl root + the Docker network can.

## What's NOT included

- **Multi-node ES cluster** — single-node is fine until > 100 benches
- **Index Lifecycle Management** — manual deletion via cron until rollover policy is configured
- **Automated backups** — weekly volume snapshot is a manual ops task
- **Kibana custom dashboards** — Press doesn't use Kibana UI; we have it for ad-hoc debugging only
- **Alerting** — no Alertmanager or similar wired up
