# Code Graph Tab — Design Doc

**Date**: 2026-04-04
**Status**: Approved
**Author**: Claude + Eslam

## Problem

The Code Health dashboard shows file sizes (circle pack) and quality scores (radar), but doesn't show how code connects — which modules depend on which, which functions call which. Users can't understand architecture or plan refactors.

## Solution

Add a "Code Graph" tab using codegraph index for high-quality data + native Vue D3 for rendering. Two zoom levels: module-level (default) → function-level (click to expand). Same UX patterns as the Health Map tab.

## Architecture

```
codegraph init + index (Docker / microservice)
  → extract nodes + edges from SQLite DB
  → API: scan_app_graph(bench, app) → { nodes, edges, modules }
  → Redis cache by (app, commit)
  → Vue D3 force-directed graph
```

## API

`scan_app_graph(bench_name, app_name)` — `@whitelist`
- Runs codegraph inside Docker container
- Extracts graph from .codegraph/codegraph.db
- Returns nodes + edges + modules JSON
- Cached by (app, commit_hash)

## Data Format

```json
{
  "nodes": [
    {"id": "module_name", "type": "module", "files": 12, "classes": 5, "functions": 48},
    {"id": "module/ClassName", "type": "class", "module": "module_name", "file": "file.py", "line": 45},
    {"id": "module/func_name", "type": "function", "module": "module_name", "file": "file.py", "line": 120}
  ],
  "edges": [
    {"source": "module_a", "target": "module_b", "weight": 14, "layer": "import"},
    {"source": "module_a/ClassA", "target": "module_b/ClassB", "weight": 3, "layer": "call"}
  ]
}
```

## Frontend

- Force-directed D3 graph in `health-d3.js` → `renderCodeGraph()`
- Module-level default → click module → zoom to function-level
- Sidebar on node click (name, type, file, connections)
- Filter toggles: imports, calls, doctype_links
- Zoom controls, breadcrumb, legend
- Colors: module=blue, class=yellow, function=green, ERPNext=purple

## Files

| File | Change |
|---|---|
| bench_code_health.py | scan_app_graph() API |
| health-d3.js | renderCodeGraph() |
| BenchCodeHealth.vue | "Code Graph" tab |
| code-analysis-service/Dockerfile | npm install codegraph |
| code-analysis-service/app/main.py | /api/graph endpoint |
