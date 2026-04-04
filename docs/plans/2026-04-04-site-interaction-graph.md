# Site Interaction Graph — Design Plan

**Date**: 2026-04-04
**Status**: Planned (next session)
**Priority**: HIGH — completes the cross-app visibility story

## Problem

Code Health currently shows per-app data (scores, compliance, circle pack).
But apps don't exist in isolation — they interact through:
- hooks.py doc_events (app A hooks into app B's DocType)
- Client Scripts (stored in DB, target any DocType)
- Server Scripts (stored in DB, target any DocType) 
- DocType Link fields (app A's DocType links to app B's DocType)
- Cross-app imports (app A imports from app B)

Users can't see these connections. A change in erpnext could break accubuild_core
and nobody knows until production breaks.

## What to Build

### New Tab: "Site Interactions" (replaces current "App Interactions")

**Current "App Interactions" tab**: shows per-app hooks/scheduler (flat list)
**New "Site Interactions" tab**: shows cross-app dependency graph (visual)

### Data Sources

| Source | How to extract | Stored where |
|---|---|---|
| hooks.py doc_events | Already have: `get_app_interactions()` | Redis + DB |
| Client Scripts | `frappe.get_all("Client Script", fields=["name","dt","script"])` | DB query |
| Server Scripts | `frappe.get_all("Server Script", fields=["name","reference_doctype","script"])` | DB query |
| DocType Link fields | Parse DocType JSON: find `fieldtype=Link`, `options=OtherDocType` | Docker scan |
| Cross-app imports | grep `from other_app import` in each app | Docker scan |

### API: `get_site_interactions(bench_name, site_name)`

Returns:
```json
{
  "apps": ["frappe", "erpnext", "accubuild_core", ...],
  "interactions": [
    {"source_app": "accubuild_core", "target_app": "erpnext", "type": "doc_event", 
     "detail": "hooks into Sales Invoice.on_submit", "weight": 3},
    {"source_app": "accubuild_core", "target_app": "frappe", "type": "client_script",
     "detail": "Client Script on User form", "weight": 1},
    {"source_app": "erpnext", "target_app": "frappe", "type": "link_field",
     "detail": "Customer.territory links to Territory", "weight": 45},
  ],
  "scripts": {
    "client_scripts": [{"name": "CS-001", "dt": "Sales Invoice", "app": "accubuild_core"}],
    "server_scripts": [{"name": "SS-001", "dt": "Payment Entry", "app": "accubuild_core"}],
  }
}
```

### UI: Force-directed graph (same pattern as Code Graph tab)

- **Nodes** = apps (colored by type: upstream=gray, custom=blue)
- **Edges** = interactions (colored by type: doc_event=orange, link=green, script=purple)
- **Edge thickness** = weight (number of connections)
- **Click node** = sidebar shows all interactions for that app
- **Filter toggles**: doc_events, link_fields, client_scripts, server_scripts, imports
- **Legend**: interaction types with colors

### Files to Change

| File | Change |
|---|---|
| bench_code_health.py | `get_site_interactions()` @whitelist API |
| health-d3.js | `renderSiteGraph()` function (or reuse renderCodeGraph with different data) |
| BenchCodeHealth.vue | Replace "App Interactions" tab with "Site Interactions" |
| HealthAdvanced.vue | OR add as new child component |

### Dependencies

- Needs `site_name` (not just bench_name) to query Client/Server Scripts from the site DB
- Uses `bench --site X execute frappe.get_all` for DB-stored scripts
- OR uses docker_execute to query inside the container

### Implementation Order

1. Backend: `get_site_interactions()` — extract all cross-app edges
2. Cache in Code Health Scan DocType (scan_type="site_interactions")
3. Frontend: replace App Interactions tab with visual graph
4. Add script details in sidebar (click edge → show which scripts/hooks)
