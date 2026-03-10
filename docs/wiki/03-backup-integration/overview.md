# Backup Integration Guide

How the Daman Backup system integrates with the Press dashboard to provide server-level backup management.

Related: [File Reference Matrix](../01-backend-development/file-reference-matrix.md) | [Architecture](../00-getting-started/architecture.md)

---

## What It Does

Daman Backup manages server-level backups using **BorgBackup** (deduplicating backup program) orchestrated through **borgmatic** (configuration wrapper) running inside a Docker container. It integrates into Press as:

1. **Frappe Desk** (admin) -- Create/edit Backup Servers, Clients, Settings, Jobs
2. **Press Dashboard** (team) -- Run/monitor/cancel/retry backups, view logs, manage alerts

```
Press Dashboard (Vue)          Frappe Desk (admin)
      |                              |
      v                              v
  press_api.py                 DocType forms
  (8 methods)                  (direct CRUD)
      |                              |
      +----------+-------------------+
                 |
                 v
          DocTypes (10)
          backup_api.py (queue + stats)
                 |
                 v
       portainer_borgmatic_api.py
          (execution engine)
                 |
                 v
        borgmatic container
          (Docker Direct)
                 |
                 v
          BorgBackup repos
        (local or remote SSH)
```

---

## Architecture

### Execution Modes

| Mode | How It Works | When to Use |
|------|-------------|-------------|
| **Docker Direct** | `docker exec` into borgmatic container | Single-server, press-ctrl hosting |
| **Portainer API** | HTTP API to remote Portainer instance | Multi-server, remote execution |

Configured in **Backup Settings** (single DocType).

### borgmatic Container

Runs on the host with `sleep infinity` entrypoint. Backups execute via `docker exec`:

```bash
docker exec borgmatic borgmatic --config /etc/borgmatic/config.yaml create
```

For remote repos, SSHFS mounts the remote storage inside the container at runtime.

### Data Flow

1. **Scheduler** (`tasks.py`) triggers backups based on Backup Job schedules
2. **Queue** creates a `Backup Job Queue` entry with status "Queued"
3. **Worker** picks up the job, sets status to "Running"
4. **Execution** dispatches to `portainer_borgmatic_api.py` which runs borgmatic
5. **Logging** creates `Backup Run Log` with output, duration, errors
6. **Health** updates `Backup Client` health status fields
7. **Alerts** checked hourly/daily/weekly by `backup_alert_rule.py` scheduler

---

## DocTypes

### Core DocTypes

| DocType | Type | Purpose |
|---------|------|---------|
| **Backup Settings** | Single | Global config: execution mode, container name, Portainer URL/credentials |
| **Backup Server** | Master | Where backups are stored: SSH host, repo path, storage type |
| **Backup Client** | Master | What to back up: source paths, schedule, linked to Server |
| **Backup Job** | Master | Scheduled job definition: client, frequency, retention |
| **Backup Job Queue** | Master | Async execution queue: status, progress, timestamps |
| **Backup Run Log** | Master | Execution history: output, duration, exit code, errors |
| **Backup Alert Rule** | Master | Alert config: type, frequency, thresholds, recipients |

### Child & Support DocTypes

| DocType | Type | Parent |
|---------|------|--------|
| **Backup Job Source Path** | Child | Backup Job |
| **Server Assigned Client** | Child | Backup Server |
| **Server Provider** | Master | Cloud provider definitions |

### Relationships

```
Backup Settings (single)
    |
    v
Backup Server  <----  Backup Client
    |                      |
    v                      v
Server Assigned       Backup Job
Client (child)             |
                           v
                    Backup Job Queue
                           |
                           v
                    Backup Run Log

Backup Alert Rule (standalone, checks all clients)
```

### Permissions

| DocType | System Manager | Press Admin |
|---------|---------------|-------------|
| Backup Settings | Read + Write | Read + Write |
| Backup Client | Full RWCD | Full RWCD |
| Backup Server | Full RWCD | Full RWCD |
| Backup Job Queue | Full RWCD | Full RWCD |
| Backup Run Log | Full RWCD | Read only |
| Backup Alert Rule | Full RWCD | Full RWCD |

Press Admin role is required for dashboard users (`eng.elgogary` etc.) who access backup features through the Vue dashboard.

---

## API Endpoints

### Press Dashboard API (`press_api.py`)

All methods are `@frappe.whitelist()` and respect DocType permissions.

| Method | Purpose | Returns |
|--------|---------|---------|
| `get_backup_overview()` | Unified dashboard data | Server stats, job queue counts, client health |
| `get_client_detail(client_name)` | Single client details | Config, recent jobs, health status |
| `get_alert_summary()` | Alert rules list | All rules with enabled/triggered counts |
| `get_alert_detail(alert_name)` | Single alert for editing | All alert fields |
| `create_alert(**kwargs)` | Create new alert rule | `{success, name}` |
| `update_alert(**kwargs)` | Update existing alert | `{success, name}` |
| `toggle_alert(alert_name, enabled)` | Enable/disable alert | `{success}` |
| `delete_alert(alert_name)` | Delete alert rule | `{success}` |

### Backup Execution API (`backup_api.py`)

The main API for running backups, checking health, and managing the job queue. ~1149 lines (needs splitting).

| Category | Methods |
|----------|---------|
| Queue management | Enqueue backup, cancel job, retry failed job |
| Statistics | Client stats, server stats, job history |
| Health checks | Check backup age, repo integrity, storage usage |
| Legacy | Direct borgmatic execution (non-queued) |

---

## Dashboard Pages

All Vue pages live in the Press repo at `dashboard/src/pages/backups/`.

### BackupOverview.vue (~198 lines)

Unified dashboard with three sections:
- **Server stats**: backup server count, total storage, health indicators
- **Job queue**: Queued/Running/Success/Failed/Cancelled counts with action buttons
- **Client table**: health status per client with Run Backup action

Action buttons: Run All Backups, Cancel (queued/running), Retry (failed)

### ServerBackups.vue (~167 lines)

ObjectList of all backup servers. Row actions:
- **Run Backup**: triggers backup for all clients on that server
- **Check Health**: runs health check (repo integrity, storage)

### BackupJobs.vue (~127 lines)

ObjectList of job queue entries. Row actions based on status:
- Queued/Running: **Cancel**
- Failed/Cancelled: **Retry**

### BackupAlerts.vue (~292 lines)

Full CRUD page with Dialog for create/edit:
- Fields: alert_name, priority, rule_type, alert_type, check_frequency, email_recipients, webhook_url, thresholds
- Row actions: Edit, Enable/Disable toggle, Delete
- Uses frappe-ui `Dialog`, `FormControl`, `Button`

### Navigation

Added to `NavigationItems.vue` under "Backups" group:
- Backup Overview (`/backups/overview`)
- Server Backups (`/backups/server-backups`)
- Backup Jobs (`/backups/jobs`)
- Backup Alerts (`/backups/alerts`)

Routes defined in `router.js`.

---

## Scheduler Tasks

Defined in `hooks.py` under `scheduler_events`:

| Frequency | Task | What It Does |
|-----------|------|-------------|
| Hourly | `check_hourly_alerts` | Evaluate hourly alert rules |
| Hourly | `cleanup_old_jobs` | Remove job queue entries older than 30 days |
| Hourly | `trigger_scheduled_backups` | Check Backup Jobs and enqueue due backups |
| Hourly | `cleanup_stale_jobs` | Mark jobs stuck >6h as Failed |
| Every 6h | `check_six_hour_alerts` | Evaluate 6-hour alert rules |
| Every 6h | `update_all_clients_stats` | Refresh storage/health stats for all clients |
| Daily | `check_daily_alerts` | Evaluate daily alert rules |
| Daily | `cleanup_old_backup_logs` | Remove run logs older than 30 days |
| Daily | `check_backup_health` | Flag clients with no backup in 24h |
| Weekly | `check_weekly_alerts` | Evaluate weekly alert rules |

---

## Tests

40 tests total, all passing. Key test files:

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_alert_crud.py` | 12 | All 5 alert CRUD endpoints + edge cases |
| `tests/test_press_api.py` | -- | Overview and detail endpoints |
| `doctype/*/test_*.py` | ~28 | Per-DocType standard tests |

Run tests:
```bash
bench run-tests --app daman_backup
```

---

## Key Decisions

1. **Separate `press_api.py`** instead of adding to `backup_api.py` (already >1000 lines)
2. **`fetch()` instead of `createResource`** in Vue pages -- simpler for cross-app API calls
3. **Framework permissions** instead of `ignore_permissions=True` -- DocType role perms control access
4. **borgmatic container with `sleep infinity`** -- always running, execute on demand via `docker exec`
5. **Single grouped SQL query** for job stats instead of 5 separate COUNT queries

---

## Known Technical Debt

- `backup_api.py` is 1149 lines -- needs splitting into queue, stats, and legacy modules
- Vue pages use `fetch()` -- should migrate to `createResource` for loading states
- BackupOverview needs auto-refresh for live monitoring
- No end-to-end test with actual BorgBackup execution
