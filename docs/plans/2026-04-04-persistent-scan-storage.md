# Persistent Scan Storage — Design Needed

**Date**: 2026-04-04
**Status**: Planned (next session)
**Priority**: HIGH — data loss on Redis restart/TTL expiry

## Problem

1. All scan results stored in Redis cache only (24h TTL, volatile)
2. `loadCachedData` doesn't reload interactions/scripts (only scores/compliance via scan_single_app)
3. Every page refresh can trigger expensive docker_execute calls
4. Redis restart = all scan data lost = user must re-scan everything

## Current State

| Data | Storage | Persists? |
|---|---|---|
| Health summary | Redis `code_health:summary:{bench}` | 24h TTL |
| App scores | Redis `code_health:scores:{app}:{commit}` | 24h TTL |
| Compliance | Redis `code_health:compliance:{app}:{commit}` | 24h TTL |
| Stack info | Redis `code_health:stack:{app}:{commit}` | 24h TTL |
| App commits | Redis `code_health:commits:{bench}` | 60s TTL |
| Single app scan | Redis `code_health:single_app:{app}:{commit}` | 24h TTL |
| Graph data | Redis `code_health:graph:{app}:{commit}` | 24h TTL |
| Interactions | NOT CACHED — only in Vue component state | Lost on refresh |
| Scripts inventory | NOT CACHED — only in Vue component state | Lost on refresh |

## Proposed Solution

### New DocType: `Code Health Scan`

```
Code Health Scan
├── bench (Link → Bench)
├── app_name (Data)
├── commit_hash (Data)
├── scanned_at (Datetime)
├── scan_type (Select: summary/scores/compliance/stack/interactions/scripts/graph)
├── result_json (JSON — stores the full result)
├── status (Select: Success/Failed)
```

- Unique key: (bench, app_name, commit_hash, scan_type)
- On scan: write to DB + Redis cache
- On load: read from Redis first, fall back to DB
- No TTL in DB — permanent until new commit replaces it
- Redis still used as fast cache layer on top

### What Changes

1. Every `_set_cached()` call also writes to `Code Health Scan` DocType
2. Every `_get_cached()` checks Redis first, then falls back to DB query
3. `loadCachedData` in Vue loads ALL data types including interactions/scripts
4. `list_bench_health` reads from DB instead of Redis for the listing page

### Benefits

- Scan once, data persists forever (until new commit)
- Redis restart = no data loss (DB is authoritative)
- Listing page shows historical data even after cache expiry
- Can add trends/history later (score over time per app)
