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

---

### Task 5: App Stack Summary — tech stack + dependencies per app

**Files:**
- Add to: `press/press/doctype/bench/bench_code_health.py`

**Goal:** For each app in the bench, show a summary card:

| Field | How to detect |
|-------|---------------|
| Framework | `hooks.py` → Frappe, `pubspec.yaml` → Flutter, `package.json` → Node/React/Vue, `Cargo.toml` → Rust |
| Language | Count `.py` vs `.js`/`.ts` vs `.dart` vs `.rs` files |
| App version | Read from `__init__.py` (`__version__`) or `pyproject.toml` |
| Total files / lines | From health scan |
| Key dependencies | Parse `pyproject.toml` [project.dependencies] or `package.json` dependencies |

**Step 1: Add `get_app_stack_info` API**

```python
@frappe.whitelist()
def get_app_stack_info(bench_name):
    """Return tech stack summary per app in the bench."""
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)
    
    # List apps
    r = bench.docker_execute("ls apps/", save_output=False, create_log=False)
    apps = [a.strip() for a in r.get("output", "").split() if a.strip()]
    
    results = []
    for app in apps:
        info = {"app": app, "framework": "unknown", "language": "Python", "version": ""}
        
        # Detect framework
        r = bench.docker_execute(
            f"test -f apps/{app}/hooks.py && echo frappe || "
            f"test -f apps/{app}/pubspec.yaml && echo flutter || "
            f"test -f apps/{app}/Cargo.toml && echo rust || "
            f"test -f apps/{app}/package.json && echo node || echo unknown",
            save_output=False, create_log=False,
        )
        info["framework"] = r.get("output", "").strip() or "unknown"
        
        # Get version
        r = bench.docker_execute(
            f"grep -m1 __version__ apps/{app}/*/__init__.py 2>/dev/null || echo ?",
            save_output=False, create_log=False,
        )
        ver = r.get("output", "").strip()
        if "__version__" in ver:
            info["version"] = ver.split("=")[-1].strip().strip("'\"")
        
        # Count files by type
        r = bench.docker_execute(
            f"find apps/{app} -name '*.py' -not -path '*__pycache__*' | wc -l",
            save_output=False, create_log=False,
        )
        info["py_files"] = int(r.get("output", "0").strip() or 0)
        
        r = bench.docker_execute(
            f"find apps/{app} \\( -name '*.js' -o -name '*.ts' -o -name '*.vue' \\) -not -path '*node_modules*' | wc -l",
            save_output=False, create_log=False,
        )
        info["js_files"] = int(r.get("output", "0").strip() or 0)
        
        results.append(info)
    
    return results
```

**Step 2: Commit**

```bash
git add press/press/doctype/bench/bench_code_health.py
git commit -m "feat(api): app stack summary — framework, version, file counts per app"
```

---

### Task 6: Docs Compliance Checker — enforce team standards

**Files:**
- Add to: `press/press/doctype/bench/bench_code_health.py`

**Goal:** Check every app against your documentation standards (from `rules/project-docs.md`):

| Check | Required | How to detect |
|-------|----------|---------------|
| CLAUDE.md | All apps | `test -f apps/{app}/CLAUDE.md` |
| README.md | All apps | `test -f apps/{app}/README.md` |
| docs/wiki/ | Apps with 3+ DocTypes | `test -d apps/{app}/docs/wiki` |
| DEVLOG.md | All custom apps | `test -f apps/{app}/DEVLOG.md` |
| tests/ | All apps | `test -d apps/{app}/tests` |
| .gitignore | All apps | `test -f apps/{app}/.gitignore` |

**Compliance score:** Each check = 1 point. Max 6 per app. Show as percentage.

**Step 1: Add `get_docs_compliance` API**

```python
@frappe.whitelist()
def get_docs_compliance(bench_name):
    """Check documentation compliance per app against team standards."""
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)
    
    CHECKS = [
        ("CLAUDE.md", "test -f apps/{app}/CLAUDE.md"),
        ("README.md", "test -f apps/{app}/README.md"),
        ("docs/wiki/", "test -d apps/{app}/docs/wiki"),
        ("DEVLOG.md", "test -f apps/{app}/DEVLOG.md"),
        ("tests/", "test -d apps/{app}/tests"),
        (".gitignore", "test -f apps/{app}/.gitignore"),
    ]
    
    # List apps
    r = bench.docker_execute("ls apps/", save_output=False, create_log=False)
    apps = [a.strip() for a in r.get("output", "").split() if a.strip()]
    
    # Skip upstream apps — only check custom apps
    upstream = {"frappe", "erpnext", "hrms", "payments", "lending", "webshop", "lms",
                "helpdesk", "insights", "gameplan", "builder", "wiki", "drive", "crm",
                "print_designer", "ifrs_reporting"}
    
    results = []
    for app in apps:
        is_custom = app not in upstream
        checks = []
        passed = 0
        for name, cmd_tpl in CHECKS:
            cmd = cmd_tpl.format(app=app)
            r = bench.docker_execute(
                cmd + " && echo PASS || echo FAIL",
                save_output=False, create_log=False,
            )
            status = r.get("output", "").strip() == "PASS"
            checks.append({"name": name, "status": status})
            if status:
                passed += 1
        
        results.append({
            "app": app,
            "is_custom": is_custom,
            "checks": checks,
            "passed": passed,
            "total": len(CHECKS),
            "compliance_pct": round(passed / len(CHECKS) * 100),
        })
    
    return results
```

**Current state (bench-0005):**

| App | CLAUDE | README | docs/ | tests/ | Compliance |
|-----|--------|--------|-------|--------|------------|
| accubuild_core | Y | Y | Y | Y | **100%** |
| sanad_business_intelligence_ai | Y | Y | Y | N | 83% |
| frappe_theme_switcher | N | Y | Y | N | 50% |
| tamkeen_suite_app | N | Y | N | N | 33% |

**Step 2: Commit**

```bash
git add press/press/doctype/bench/bench_code_health.py
git commit -m "feat(api): docs compliance checker — enforce team standards per app"
```

---

### Task 7: Unified Dashboard Component — combine all metrics

**Files:**
- Modify: `dashboard/src/components/BenchCodeHealth.vue`

**Goal:** Three sections in one component:

```
┌─────────────────────────────────────────────────┐
│ Code Health Dashboard                    [Scan] │
├─────────────────────────────────────────────────┤
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ │
│ │ 89%     │ │ 2,128   │ │ 323K    │ │ 54     │ │
│ │ Health  │ │ Files   │ │ Lines   │ │ Violations│
│ └─────────┘ └─────────┘ └─────────┘ └────────┘ │
├─────────────────────────────────────────────────┤
│ [Health Map] [Stack Info] [Docs Compliance]     │
├─────────────────────────────────────────────────┤
│ Tab 1: Circle packing visualization             │
│ Tab 2: App cards with framework, version, files │
│ Tab 3: Compliance checklist per app (Y/N grid)  │
└─────────────────────────────────────────────────┘
```

**Step 1: Add tabs to BenchCodeHealth.vue**

Three tabs: Health Map (D3 circles), Stack (app cards), Compliance (checklist grid).
Each tab lazy-loads its data on first click.

**Step 2: Commit**

```bash
git add dashboard/src/components/BenchCodeHealth.vue
git commit -m "feat(ui): unified code health dashboard with 3 tabs"
```

---

---

### Task 8: Scoring Engine — rate each dimension 0-100

**Files:**
- Add to: `press/press/doctype/bench/bench_code_health.py`

**Goal:** Score each app on 6 dimensions. Not just "exists/doesn't exist" — actually read content and check quality.

**Scoring dimensions:**

| Dimension | How scored (0-100) |
|-----------|-------------------|
| **CLAUDE.md** | 0=missing, 20=exists but empty, +15 per required section found (Stack, Commands, Structure, Architecture, Conventions, Key Context) = max 100 |
| **README** | 0=missing, 20=exists, +20 per section (What it does, Install, Run, Architecture, Contributing) = max 100 |
| **Documentation** | 0=no docs/, 30=docs/ exists, +15 per wiki file (overview, architecture, doctype-tree, api-reference) = max 90, +10 if >5 files |
| **Tests** | 0=no tests/, test file ratio: (test_files / code_files) * 200, capped at 100 |
| **Clean Code** | (files_under_500 / total_code_files) * 100. Penalty: -2 per file >700 lines |
| **Code Patterns** | 100 - (anti_pattern_violations / total_lines * 1000). bare except, print(), console.log, etc. |

```python
@frappe.whitelist()
def get_app_scores(bench_name):
    """Score each app on 6 quality dimensions for radar chart."""
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)
    
    r = bench.docker_execute("ls apps/", save_output=False, create_log=False)
    apps = [a.strip() for a in r.get("output", "").split() if a.strip()]
    
    upstream = {"frappe", "erpnext", "hrms", "payments", "lending", "ifrs_reporting",
                "webshop", "lms", "helpdesk", "insights", "print_designer", "wiki"}
    
    results = []
    for app in apps:
        if app in upstream:
            continue
        
        scores = {
            "claude_md": _score_claude_md(bench, app),
            "readme": _score_readme(bench, app),
            "documentation": _score_docs(bench, app),
            "tests": _score_tests(bench, app),
            "clean_code": _score_clean_code(bench, app),
            "code_patterns": _score_patterns(bench, app),
        }
        scores["overall"] = round(sum(scores.values()) / len(scores))
        results.append({"app": app, "scores": scores})
    
    return results


CLAUDE_SECTIONS = ["Stack", "Commands", "Structure", "Architecture", "Conventions", "Key Context"]

def _score_claude_md(bench, app):
    r = bench.docker_execute(f"cat apps/{app}/CLAUDE.md 2>/dev/null || echo __MISSING__",
                             save_output=False, create_log=False)
    content = r.get("output", "")
    if "__MISSING__" in content:
        return 0
    if len(content.strip()) < 50:
        return 20
    score = 20  # exists
    for section in CLAUDE_SECTIONS:
        if f"## {section}" in content or f"# {section}" in content:
            score += 13
    return min(score, 100)


README_SECTIONS = ["install", "setup", "usage", "run", "architecture", "structure"]

def _score_readme(bench, app):
    r = bench.docker_execute(f"cat apps/{app}/README.md 2>/dev/null || echo __MISSING__",
                             save_output=False, create_log=False)
    content = r.get("output", "").lower()
    if "__missing__" in content:
        return 0
    if len(content.strip()) < 50:
        return 20
    score = 20
    for keyword in README_SECTIONS:
        if keyword in content:
            score += 16
    return min(score, 100)


def _score_docs(bench, app):
    r = bench.docker_execute(f"find apps/{app}/docs -type f -name '*.md' 2>/dev/null | wc -l",
                             save_output=False, create_log=False)
    count = int(r.get("output", "0").strip() or 0)
    if count == 0:
        return 0
    if count <= 2:
        return 30
    if count <= 5:
        return 60
    return min(30 + count * 10, 100)


def _score_tests(bench, app):
    r = bench.docker_execute(
        f"find apps/{app} -name 'test_*.py' -not -path '*__pycache__*' | wc -l",
        save_output=False, create_log=False,
    )
    test_count = int(r.get("output", "0").strip() or 0)
    r2 = bench.docker_execute(
        f"find apps/{app} -name '*.py' -not -name 'test_*' -not -path '*__pycache__*' | wc -l",
        save_output=False, create_log=False,
    )
    code_count = int(r2.get("output", "0").strip() or 0)
    if code_count == 0:
        return 0
    ratio = test_count / code_count
    return min(round(ratio * 200), 100)


def _score_clean_code(bench, app):
    r = bench.docker_execute(
        f"find apps/{app} \\( -name '*.py' -o -name '*.js' -o -name '*.vue' \\) "
        f"-not -path '*node_modules*' -not -path '*__pycache__*' "
        f"-exec wc -l {{}} + 2>/dev/null | grep -v ' total$'",
        save_output=False, create_log=False,
    )
    lines_data = []
    for line in r.get("output", "").strip().split("\n"):
        parts = line.strip().split(None, 1)
        if parts and parts[0].isdigit():
            lines_data.append(int(parts[0]))
    if not lines_data:
        return 100
    under_500 = sum(1 for l in lines_data if l < 500)
    over_700 = sum(1 for l in lines_data if l > 700)
    score = round((under_500 / len(lines_data)) * 100) - (over_700 * 2)
    return max(0, min(score, 100))


def _score_patterns(bench, app):
    r = bench.docker_execute(
        f"grep -r -c 'except:' apps/{app}/ --include='*.py' 2>/dev/null | "
        f"awk -F: '{{s+=$2}} END {{print s+0}}'",
        save_output=False, create_log=False,
    )
    bare_except = int(r.get("output", "0").strip() or 0)
    r2 = bench.docker_execute(
        f"grep -r -c 'console\\.log' apps/{app}/ --include='*.js' --include='*.vue' 2>/dev/null | "
        f"awk -F: '{{s+=$2}} END {{print s+0}}'",
        save_output=False, create_log=False,
    )
    console_logs = int(r2.get("output", "0").strip() or 0)
    r3 = bench.docker_execute(
        f"grep -r -c 'print(' apps/{app}/ --include='*.py' 2>/dev/null | "
        f"awk -F: '{{s+=$2}} END {{print s+0}}'",
        save_output=False, create_log=False,
    )
    prints = int(r3.get("output", "0").strip() or 0)
    
    violations = bare_except * 5 + console_logs + prints
    return max(0, 100 - violations * 2)
```

**Step 1: Commit**

```bash
git commit -m "feat(api): 6-dimension scoring engine for app quality radar chart"
```

---

### Task 9: Radar Chart Component — visual per-app quality shape

**Files:**
- Create: `dashboard/src/components/AppRadarChart.vue`

**Goal:** D3 radar chart per app. 6 axes = 6 dimensions. Full hexagon = perfect. Dents = weak areas.

```
        CLAUDE.md (90%)
           /\
          /  \
  Tests  /    \ README
  (20%) /      \ (75%)
        \      /
  Clean  \    / Docs
  Code    \  /  (60%)
   (89%)   \/
      Patterns (95%)
```

**Implementation:** D3 radar polygon chart. Each app gets its own radar. Side by side for comparison.

Key Vue structure:
```vue
<template>
  <div class="grid grid-cols-2 gap-4 lg:grid-cols-3">
    <div v-for="app in appScores" :key="app.app"
      class="rounded-lg border border-gray-200 p-4">
      <div class="mb-2 flex items-center justify-between">
        <h3 class="text-sm font-semibold">{{ app.app }}</h3>
        <Badge :label="app.scores.overall + '%'"
          :theme="app.scores.overall >= 80 ? 'green' : app.scores.overall >= 50 ? 'orange' : 'red'" />
      </div>
      <svg :ref="'radar-' + app.app" class="h-48 w-full"></svg>
    </div>
  </div>
</template>
```

D3 draws a polygon per app using `d3.lineRadial()` with 6 data points.

**Step 1: Commit**

```bash
git commit -m "feat(ui): radar chart component for per-app quality scoring"
```

---

### Updated Task 7: Unified Dashboard — now 4 tabs

```
┌─────────────────────────────────────────────────┐
│ Code Health Dashboard                    [Scan] │
├─────────────────────────────────────────────────┤
│ Overall: 76% │ 2,128 files │ 323K lines │ 54 ⚠ │
├─────────────────────────────────────────────────┤
│ [Health Map] [Radar Scores] [Stack] [Compliance]│
├─────────────────────────────────────────────────┤
│ Tab 1: Circle packing — file structure + health │
│ Tab 2: Radar charts per app — 6 quality axes    │
│ Tab 3: App cards — framework, version, files    │
│ Tab 4: Compliance grid — Y/N per standard       │
└─────────────────────────────────────────────────┘
```

---

## Full Feature Summary

| What | From one look you see |
|------|----------------------|
| **Health Map** | Every file as a circle — green/yellow/red. Click to zoom. Violations glow red. |
| **Radar Scores** | Per-app hexagon chart — CLAUDE.md, README, docs, tests, clean code, patterns. Dents = weak areas. |
| **Stack Info** | Each app's framework, version, Python/JS file count |
| **Docs Compliance** | Which apps follow your standards. Red = missing docs. Forces team to comply. |
| **Health Badge** | Quick number on bench detail header (89% healthy) |

---

### Task 10: App Interaction Overlay on Health Map (Site view only)

**Files:**
- Modify: `dashboard/src/components/SiteCodeHealth.vue` (new component for site)

**Goal:** The Health Map circle packing gets an extra layer showing how apps interact — arcs drawn OVER the circles connecting apps through hooks, doc_events, client scripts, server scripts.

**Layers (toggle each from filter toolbar):**

| Layer | Visual | Data source |
|-------|--------|-------------|
| hooks | Solid arc between app circles | Parse `hooks.py` per app |
| doc_events | Solid arc, different color | Parse `hooks.py` doc_events |
| override | Dashed arc | Parse `hooks.py` override_doctype_class |
| client_script | Dotted line from script node to DocType circle | Query Client Script doctype from DB |
| server_script | Dotted line from script node to DocType circle | Query Server Script doctype from DB |
| custom_field | Thin line from field badge to target DocType | Query Custom Field doctype from DB |

**Backend API needed:**

```python
@frappe.whitelist()
def get_site_interactions(bench_name, site_name):
    """Return app-to-app interactions for a site."""
    bench = frappe.get_doc("Bench", bench_name)
    
    interactions = []
    
    # 1. Parse hooks.py per app for doc_events, override_doctype_class
    apps = get_bench_app_names(bench_name)
    for app in apps:
        r = bench.docker_execute(
            f"cat apps/{app}/hooks.py 2>/dev/null || echo NONE",
            save_output=False, create_log=False,
        )
        hooks_content = r.get("output", "")
        # Parse doc_events, override_doctype_class, scheduler_events
        # Each becomes an interaction record
    
    # 2. Query DB-stored scripts (runs on the site, not in container)
    # Client Scripts, Server Scripts, Custom Fields, Workflows
    # These need bench.docker_execute("bench --site X execute ...")
    
    return interactions
```

**D3 implementation:**
- Arcs use `d3.arc()` drawn between the center of each app's cluster circle
- Client/server scripts rendered as small diamond nodes with dotted lines to target
- Each layer has its own SVG group, toggled via CSS opacity
- Filter toolbar extends the existing health filter bar with layer toggles

---

## Prototype-to-Implementation Checklist

Before building, verify EVERY feature from both prototypes is accounted for.

**Skills to use per phase:**
- `/create-prototype` — already done (reference + site prototypes)
- `/ui-ux-ba` — review prototype against real data before implementing
- `/test-driven-development` — TDD for all backend APIs
- `/code-review` — after each task
- `/clean-code` — after each task
- `/verify` — test each feature against prototype

### Bench Prototype Checklist (code_health_dashboard_prototype.html)

**Standalone /dashboard/code-health page:**
- [ ] Summary cards row: 5 metrics (benches, health%, files, violations, security)
- [ ] Security alert banner (HIGH RISK — red)
- [ ] Table view: bench rows with health%, apps, violations, compliance, security, last scan
- [ ] Card view: mini radar per bench card
- [ ] Table/Card toggle button
- [ ] "Scan All" button

**Bench detail tabs:**
- [ ] Overview tab: overall radar + score breakdown
- [ ] Overview tab: app ranking with progress bars (sorted best→worst)
- [ ] Overview tab: action required list (prioritized — security > missing docs > violations)
- [ ] Health Map tab: circle packing with REAL data from scanner API
- [ ] Health Map tab: filter toolbar (violation/warning/clean/non-code toggles with counts)
- [ ] Health Map tab: file type filters (.py/.js/.vue/.ts/.json/.md with counts)
- [ ] Health Map tab: "Showing X/Y files" live counter
- [ ] Health Map tab: zoom +/- buttons (top right)
- [ ] Health Map tab: mouse wheel zoom
- [ ] Health Map tab: click folder circle → zoom in (with 100% padding)
- [ ] Health Map tab: click background → zoom out one level
- [ ] Health Map tab: breadcrumb path on zoom
- [ ] Health Map tab: hover file → tooltip (name, lines, ext, health, violations)
- [ ] Health Map tab: click file → sidebar (path, lines, ext, size, health, MUST SPLIT badge, violations list, close button)
- [ ] Radar Scores tab: per-app radar chart (8 axes)
- [ ] Radar Scores tab: score breakdown grid per app
- [ ] Stack Info tab: app cards (framework, version, py files, js files, lines, branch)
- [ ] Compliance tab: grid table (Y/N per check: CLAUDE, README, docs, DEVLOG, tests, lessons, .gitignore, security)
- [ ] Compliance tab: HIGH RISK flag for security issues
- [ ] Compliance tab: score % per app with colored badge

### Site Prototype Checklist (site_health_prototype.html)

**Everything from bench PLUS:**
- [ ] Header: site name, bench name, app count, file count, lines
- [ ] "Back to Dev Tab" button
- [ ] Summary cards: includes DB Scripts count
- [ ] Overview tab: installed apps progress bars with file counts
- [ ] Overview tab: Quick Stats (client scripts, server scripts, custom fields, workflows, print formats)
- [ ] App Interactions tab: interaction graph (nodes = apps + script types)
- [ ] App Interactions tab: arc links (hooks, doc_events, override)
- [ ] App Interactions tab: dotted links (client_script, server_script, custom_field)
- [ ] App Interactions tab: filter toggles per interaction type
- [ ] App Interactions tab: interaction details table
- [ ] **App Interactions overlay on Health Map** (Task 10 — arcs over circle packing)
- [ ] Scripts tab: client scripts table (name, doctype, lines)
- [ ] Scripts tab: server scripts table (name, doctype, event, lines)
- [ ] Scripts tab: custom fields table (doctype, fields)
- [ ] Violations tab: sortable table (file, app, lines, health badge, violation details)
- [ ] Violations tab: red background for MUST SPLIT, yellow for WARNING

### Backend API Checklist

- [ ] `scan_bench_health(bench_name, app_filter)` — file tree + line counts + health
- [ ] `get_health_summary(bench_name)` — quick counts (no full tree)
- [ ] `get_app_scores(bench_name)` — 8-dimension scoring for radar
- [ ] `get_app_stack_info(bench_name)` — framework, version, file counts per app
- [ ] `get_docs_compliance(bench_name)` — compliance checks per app
- [ ] `get_site_interactions(bench_name, site_name)` — hooks/scripts/fields interactions

### Testing Checklist

- [ ] API: scan_bench_health returns valid JSON for bench with 3+ apps
- [ ] API: get_health_summary returns correct counts
- [ ] API: get_app_scores returns 8 scores per custom app, skips upstream
- [ ] API: get_docs_compliance checks all 8 items per app
- [ ] API: get_site_interactions parses hooks.py correctly
- [ ] API: security scanner detects hardcoded tokens (test with known pattern)
- [ ] UI: circle packing renders with 2000+ files without lag
- [ ] UI: zoom in/out works (click, wheel, buttons)
- [ ] UI: filter toggles hide/show files and update counter
- [ ] UI: file sidebar shows correct data
- [ ] UI: radar chart renders 8 axes with correct scores
- [ ] UI: compliance grid shows correct Y/N per app
- [ ] UI: interaction arcs render over circle packing
- [ ] Edge: empty bench (no apps) shows graceful empty state
- [ ] Edge: container not running shows error message
- [ ] Edge: bench with only upstream apps (no custom) shows "no custom apps"

## Future Enhancements (not in this plan)

- Per-app health comparison (before/after deploy)
- Health score history over time (store in Press DocType)
- Auto-block deploys if health drops below threshold
- Pre-deploy gate: "3 files exceed 700 lines — split before deploying"
- AI-powered deep analysis: read CLAUDE.md content quality, suggest missing sections
