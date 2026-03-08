# Overview

## What This Is

Self-hosted Frappe Press — a white-label cloud platform for deploying ERPNext/Frappe sites, running at `demo.mvpstorm.com`.

## Architecture

```
┌─────────────────────────────────┐     ┌─────────────────────────────────┐
│  Server 1 (press-ctrl)          │     │  Server 2 (press-f1)            │
│  89.167.116.92                  │     │  89.167.57.21                   │
│                                 │     │                                 │
│  - Press controller (Frappe)    │     │  - App server (Docker benches)  │
│  - Dashboard (Vue.js SPA)       │     │  - Agent (API on port 443)      │
│  - Scheduler (job polling)      │     │  - MariaDB                      │
│  - Build orchestrator           │     │  - Nginx proxy                  │
│  - Docker registry (:5000)      │     │  - Redis                        │
│                                 │     │                                 │
│  Site: demo.mvpstorm.com        │     │  Sites: *.demo.mvpstorm.com     │
└────────────┬────────────────────┘     └──────────────┬──────────────────┘
             │                                          │
             │  Agent API (HTTPS :443)                  │
             │  Poll every 5 seconds                    │
             └──────────────────────────────────────────┘
```

## Key Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **Press** | Controller app (Python/Frappe) | Server 1 |
| **Dashboard** | User-facing Vue.js SPA | Server 1 (`/dashboard`) |
| **Agent** | Server management API | Server 2 (`:443`) |
| **Docker Registry** | Stores bench images | Server 1 (`:5000`) |
| **Cloudflare** | DNS management | API (replaces AWS Route53) |

## Standalone Mode

Server 2 runs in "standalone" mode — one physical machine acts as:
- **Server** (app server)
- **Database Server** (MariaDB)
- **Proxy Server** (Nginx)

Press requires THREE separate DocType records for the same machine, each with its own `agent_password`.

## Available Versions

| Version | Status | Apps |
|---------|--------|------|
| **v14** | Stable (EOL) | frappe, erpnext, hrms, payments |
| **v15** | Stable (recommended) | frappe, erpnext, hrms, payments, webshop, lending |
| **v16** | Disabled (needs Python 3.12+) | All Frappe apps |

## Credentials & Access

| What | URL | User |
|------|-----|------|
| Dashboard | `https://demo.mvpstorm.com/dashboard` | `test@mvpstorm.com` |
| Admin desk | `https://demo.mvpstorm.com/app` | `Administrator` |
| SSH Server 1 | `ssh press-ctrl` | root |
| SSH Server 2 | `ssh press-f1` | root |
