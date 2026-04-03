# Code Health Dashboard — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Embed code health circle-packing visualization and dependency graph into the Press dashboard so teams can evaluate bench code quality from the UI — no CLI needed.

**Architecture:** A new whitelisted API (`bench_code_health.py`) scans apps inside bench Docker containers via `docker_execute`, collects file line counts + rule violations, returns JSON. A Vue component (`BenchCodeHealth.vue`) renders D3 circle-packing inline. Accessed from the Site Dev Tab and Bench Detail page. Two modes: health circles (file structure + violations) and codegraph (module dependencies).

**Tech Stack:** Python (scanner), D3.js v7 (visualization), Vue 3 Options API (frappe-ui), `docker_execute` (container access)

---

## Constraints

- `bench_dev_overview.py` is 540 lines — NO more additions. New file only.
- `SiteDevTab.vue` is 613 lines — new visualization goes in a SEPARATE component.
- `docker_execute` doesn't support `$()` subshells or `cd`. Use `find`, `wc -l`, `git -C`.
- Health JSON can be 1MB+ for large projects — cache results, don't re-scan on every page load.
- All code files checked: `.py`, `.js`, `.ts`, `.tsx`, `.vue`, `.dart`, `.rs`, `.go`

## File Inventory

| File | Action | Lines (est) | Purpose |
|------|--------|-------------|---------|
| `press/press/doctype/bench/bench_code_health.py` | CREATE | ~180 | Scanner API — runs inside container, returns health JSON |
| `dashboard/src/components/BenchCodeHealth.vue` | CREATE | ~350 | D3 circle-packing + summary stats component |
| `dashboard/src/components/SiteDevTab.vue` | MODIFY | +15 | Add "Code Health" button + lazy-load component |

---

### Task 1: Backend — `bench_code_health.py` Scanner API

**Files:**
- Create: `press/press/doctype/bench/bench_code_health.py`

**Step 1: Write the whitelisted API**

The scanner runs inside the Docker container via `docker_execute`. It uses `find` to list files, `wc -l` to count lines. Returns nested JSON matching the `scan_codebase.py` output format.

```python
# press/press/doctype/bench/bench_code_health.py
"""
Code health scanner for benches — runs inside Docker containers.
Returns circle-packing JSON with file structure + health status.
"""

import json
import frappe

HARD_LIMIT = 700
SOFT_LIMIT = 500
CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".vue", ".dart", ".rs", ".go", ".jsx", ".svelte"}


@frappe.whitelist()
def scan_bench_health(bench_name, app_filter=None):
    """Scan all apps in a bench and return health data for circle-packing visualization.
    
    Args:
        bench_name: Bench doctype name
        app_filter: Optional — only scan this specific app
    
    Returns: dict with nested children (folders/files) + stats
    """
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)
    
    # 1. Get file listing with line counts from container
    filter_path = f"apps/{app_filter}" if app_filter else "apps"
    cmd = (
        f"find {filter_path} -type f "
        f"\\( -name '*.py' -o -name '*.js' -o -name '*.ts' -o -name '*.tsx' "
        f"-o -name '*.vue' -o -name '*.dart' -o -name '*.rs' -o -name '*.go' "
        f"-o -name '*.json' -o -name '*.html' -o -name '*.css' -o -name '*.md' \\) "
        f"-not -path '*node_modules*' -not -path '*__pycache__*' "
        f"-not -path '*.git*' -not -path '*dist*' "
        f"-exec wc -l {{}} +"
    )
    
    result = bench.docker_execute(cmd, save_output=False, create_log=False)
    output = result.get("output", "")
    
    # 2. Parse wc -l output into {path: lines}
    file_data = {}
    for line in output.strip().split("\n"):
        line = line.strip()
        if not line or line.endswith(" total"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            file_data[parts[1]] = int(parts[0])
    
    # 3. Build nested tree structure
    tree = _build_tree(file_data, bench_name)
    _compute_stats(tree)
    
    return tree


def _build_tree(file_data, root_name):
    """Convert flat {path: lines} dict into nested tree for D3 circle packing."""
    root = {"name": root_name, "children": []}
    
    for filepath, lines in sorted(file_data.items()):
        parts = filepath.split("/")
        # Skip the "apps/" prefix
        if parts[0] == "apps":
            parts = parts[1:]
        
        node = root
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                # Leaf file
                ext = "." + part.rsplit(".", 1)[-1] if "." in part else ""
                health = "non-code"
                if ext in CODE_EXTS:
                    if lines > HARD_LIMIT:
                        health = "violation"
                    elif lines > SOFT_LIMIT:
                        health = "warning"
                    else:
                        health = "clean"
                node["children"].append({
                    "name": part,
                    "ext": ext,
                    "lines": lines,
                    "health": health,
                })
            else:
                # Find or create directory node
                existing = next((c for c in node.get("children", []) if c.get("name") == part and "children" in c), None)
                if not existing:
                    existing = {"name": part, "children": []}
                    node.setdefault("children", []).append(existing)
                node = existing
    
    return root


def _compute_stats(tree):
    """Add aggregate stats to each directory node."""
    if "children" not in tree:
        is_code = tree.get("ext", "") in CODE_EXTS
        return {
            "total_files": 1 if is_code else 0,
            "total_lines": tree.get("lines", 0),
            "clean": 1 if tree.get("health") == "clean" else 0,
            "warning": 1 if tree.get("health") == "warning" else 0,
            "violation": 1 if tree.get("health") == "violation" else 0,
        }
    
    stats = {"total_files": 0, "total_lines": 0, "clean": 0, "warning": 0, "violation": 0}
    for child in tree["children"]:
        child_stats = _compute_stats(child)
        for k in stats:
            stats[k] += child_stats[k]
    
    tree["stats"] = stats
    if stats["total_files"] > 0:
        tree["health_pct"] = round(stats["clean"] / stats["total_files"] * 100)
    return stats


@frappe.whitelist()
def get_health_summary(bench_name):
    """Quick summary without full tree — for dashboard badges."""
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)
    
    cmd = (
        "find apps -type f -name '*.py' -o -name '*.js' -o -name '*.ts' "
        "-o -name '*.tsx' -o -name '*.vue' "
        "| grep -v node_modules | grep -v __pycache__ | grep -v .git "
        "| xargs wc -l 2>/dev/null | grep -v ' total$' "
        "| awk '{print $1}'"
    )
    
    result = bench.docker_execute(cmd, save_output=False, create_log=False)
    lines_list = [int(x) for x in result.get("output", "").strip().split("\n") if x.strip().isdigit()]
    
    total = len(lines_list)
    violations = sum(1 for l in lines_list if l > HARD_LIMIT)
    warnings = sum(1 for l in lines_list if SOFT_LIMIT < l <= HARD_LIMIT)
    clean = total - violations - warnings
    
    return {
        "total_files": total,
        "total_lines": sum(lines_list),
        "clean": clean,
        "warning": warnings,
        "violation": violations,
        "health_pct": round(clean / total * 100) if total else 0,
    }
```

**Step 2: Deploy to server and verify API works**

```bash
scp press/press/doctype/bench/bench_code_health.py press-ctrl:/home/frappe/frappe-bench/apps/press/press/press/doctype/bench/bench_code_health.py
ssh press-ctrl "sudo supervisorctl restart frappe-bench-web:*"
```

Test via console:
```python
from press.press.doctype.bench.bench_code_health import get_health_summary
result = get_health_summary('bench-0014-000007-u5-default')
print(result)  # Should show {total_files: N, clean: N, warning: N, violation: N, health_pct: N}
```

**Step 3: Commit**

```bash
git add press/press/doctype/bench/bench_code_health.py
git commit -m "feat(api): bench code health scanner — runs inside Docker containers"
```

---

### Task 2: Frontend — `BenchCodeHealth.vue` Circle Packing Component

**Files:**
- Create: `dashboard/src/components/BenchCodeHealth.vue`

**Step 1: Create the Vue component**

This is a self-contained component that:
- Takes `benchName` prop
- Calls `scan_bench_health` API on mount
- Renders D3 circle packing with health colors
- Shows summary stats header
- Click to zoom, hover for tooltip, click file for sidebar details

The D3 code is adapted from `code-health.html` (already tested and working).

Key structure:
```vue
<template>
  <div class="relative h-[600px] rounded-lg border border-gray-200 bg-gray-950">
    <!-- Header with stats -->
    <div class="absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-4 py-3">
      <div class="flex items-center gap-4 text-xs text-gray-400">
        <span class="flex items-center gap-1"><span class="h-2 w-2 rounded-full bg-green-500"></span> {{ stats.clean }} clean</span>
        <span class="flex items-center gap-1"><span class="h-2 w-2 rounded-full bg-yellow-500"></span> {{ stats.warning }} warn</span>
        <span class="flex items-center gap-1"><span class="h-2 w-2 rounded-full bg-red-500"></span> {{ stats.violation }} violations</span>
        <span>{{ stats.total_files }} files · {{ stats.total_lines?.toLocaleString() }} lines</span>
      </div>
      <div class="flex gap-2">
        <Button size="sm" variant="ghost" :loading="scanning" @click="scan">
          <template #icon><lucide-refresh-ccw class="h-3.5 w-3.5" /></template>
        </Button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="scanning && !healthData" class="flex h-full items-center justify-center">
      <div class="text-center text-gray-500">
        <div class="mx-auto mb-3 h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent"></div>
        Scanning bench code health...
      </div>
    </div>

    <!-- D3 SVG -->
    <svg v-show="healthData" ref="chart" class="h-full w-full"></svg>

    <!-- Tooltip -->
    <div v-show="tooltip.show" ref="tooltip" class="pointer-events-none absolute z-50 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-xs shadow-lg"
      :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }">
      <div class="font-semibold text-white">{{ tooltip.name }}</div>
      <div class="text-gray-400">{{ tooltip.lines }} lines · {{ tooltip.ext }}</div>
      <div :style="{ color: tooltip.color }" class="mt-1 font-semibold">{{ tooltip.health }}</div>
    </div>
  </div>
</template>
```

Script section uses D3 `pack()` layout — same algorithm as `code-health.html` but adapted for Vue lifecycle (render on mount, re-render on resize, cleanup on unmount).

**Step 2: Build and verify**

```bash
scp dashboard/src/components/BenchCodeHealth.vue press-ctrl:/home/frappe/frappe-bench/apps/press/dashboard/src/components/BenchCodeHealth.vue
ssh press-ctrl "bench build --app press"
```

**Step 3: Commit**

```bash
git add dashboard/src/components/BenchCodeHealth.vue
git commit -m "feat(ui): BenchCodeHealth circle-packing component with D3"
```

---

### Task 3: Integration — Wire into SiteDevTab

**Files:**
- Modify: `dashboard/src/components/SiteDevTab.vue` (+15 lines)

**Step 1: Add lazy-loaded Code Health section**

After the "App Status" section, add:

```vue
<!-- Code Health Visualization -->
<div class="rounded-lg border border-gray-200 bg-white shadow-sm">
  <div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
    <p class="text-sm font-semibold">Code Health</p>
    <Button size="sm" :variant="showHealth ? 'solid' : 'outline'" @click="showHealth = !showHealth">
      {{ showHealth ? 'Hide' : 'Show' }} Health Map
    </Button>
  </div>
  <BenchCodeHealth v-if="showHealth" :bench-name="$site?.doc?.bench" />
</div>
```

Add to data:
```javascript
showHealth: false,
```

Add import:
```javascript
import BenchCodeHealth from './BenchCodeHealth.vue';
```

Add to components:
```javascript
components: { BenchCodeHealth },
```

**Step 2: Build and test**

```bash
scp dashboard/src/components/SiteDevTab.vue press-ctrl:...
ssh press-ctrl "bench build --app press && bench clear-cache"
```

Navigate to Dev tab → click "Show Health Map" → should render circle packing.

**Step 3: Commit**

```bash
git add dashboard/src/components/SiteDevTab.vue
git commit -m "feat(dev-tab): integrate Code Health visualization"
```

---

### Task 4: Health Badge in Bench Detail

**Files:**
- Modify: `dashboard/src/objects/group.js` (via server patch — upstream file)

**Step 1: Add health badge to bench detail header**

Call `get_health_summary` and show a colored badge:
- `89% healthy` (green)
- `65% healthy` (yellow)  
- `40% healthy` (red)

This is a lightweight API call (no full scan) that returns just the counts.

**Step 2: Commit**

```bash
git commit -m "feat(ui): health score badge on bench detail page"
```

---

## Testing Strategy

- **API tests**: Call `scan_bench_health` and `get_health_summary` via bench console — verify JSON structure
- **Visual tests**: Open Dev tab, click "Show Health Map", verify circles render with correct colors
- **Edge cases**: Empty bench (no apps), bench with only JSON files (all non-code), bench container not running (graceful error)

## Deployment

```bash
# 1. Push to GitHub
git push accurate-systems cloudflare-dns

# 2. Sync to server
git bundle create /tmp/health.bundle <from>..<to>
scp /tmp/health.bundle press-ctrl:/tmp/
ssh press-ctrl "cd apps/press && git fetch /tmp/health.bundle && git merge FETCH_HEAD --ff-only"

# 3. Build and restart
ssh press-ctrl "bench build --app press && bench clear-cache"
ssh press-ctrl "supervisorctl restart frappe-bench-web:* frappe-bench-workers:*"
```

## Future Enhancements (not in this plan)

- Codegraph dependency view as second tab in the component
- Per-app health comparison (before/after deploy)
- Health score history over time (store in DB)
- Auto-block deploys if health drops below threshold
