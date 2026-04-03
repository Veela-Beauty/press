"""
Code health scanner for benches — runs inside Docker containers.
Returns circle-packing JSON + scoring + compliance data.

Stub file: constants, cache, _exec, and @whitelist wrappers.
Logic lives in sibling modules:
  - health_scoring.py  — 8 quality dimension scorers
  - health_tree.py     — circle-packing tree builder + stats
  - health_inventory.py — hooks interactions + scripts inventory
"""

import frappe

HARD_LIMIT = 700
SOFT_LIMIT = 500
CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".vue", ".dart", ".rs", ".go", ".jsx", ".svelte", ".kt", ".swift"}
ASSET_EXTS = {".json", ".yaml", ".yml", ".toml", ".xml", ".html", ".css", ".scss", ".md", ".sh", ".sql"}
CLAUDE_SECTIONS = ["Stack", "Commands", "Structure", "Architecture", "Conventions", "Key Context"]
README_KEYWORDS = ["install", "setup", "usage", "run", "architecture", "structure", "deploy"]
UPSTREAM_APPS = {
    "frappe", "erpnext", "hrms", "payments", "lending", "webshop", "lms",
    "helpdesk", "insights", "gameplan", "builder", "wiki", "drive", "crm",
    "print_designer", "ifrs_reporting",
}

SECURITY_PATTERNS = [
    ("api_key.*=.*['\\\"][A-Za-z0-9_-]{20,}", "hardcoded API key"),
    ("password.*=.*['\\\"][^'\\\"]{8,}", "hardcoded password"),
    ("token.*=.*['\\\"][A-Za-z0-9_-]{20,}", "hardcoded token"),
    ("AKIA[0-9A-Z]{16}", "AWS access key"),
    ("ghp_[A-Za-z0-9]{36}", "GitHub personal token"),
    ("gho_[A-Za-z0-9]{36}", "GitHub OAuth token"),
    ("sk-[A-Za-z0-9]{20,}", "secret key (OpenAI/Stripe)"),
]

CACHE_TTL = 3600 * 24  # 24 hours


# ── Shared helpers (imported by sibling modules) ─────────────────────────

import re as _re

_SAFE_NAME = _re.compile(r'^[a-zA-Z0-9_\-\.]+$')


def _safe(name):
    """Validate name is safe for shell interpolation (alphanumeric + _-. only)."""
    if not name or not _SAFE_NAME.match(name):
        frappe.throw(f"Invalid name for shell command: {name!r}")
    return name


def _exec(bench, cmd):
    """Shorthand for docker_execute with no logging."""
    return bench.docker_execute(cmd, save_output=False, create_log=False)


def _get_app_commits(bench):
    """Get commit hashes for all apps in the bench."""
    r = _exec(bench, "for d in apps/*/; do echo \"$(basename $d):$(git -C $d rev-parse --short HEAD 2>/dev/null || echo none)\"; done")
    commits = {}
    for line in r.get("output", "").strip().split("\n"):
        if ":" in line:
            app, h = line.strip().split(":", 1)
            commits[app.strip()] = h.strip()
    return commits


def _cache_key(prefix, app, commit):
    return f"code_health:{prefix}:{app}:{commit}"


def _get_cached(prefix, app, commit):
    import json
    val = frappe.cache.get_value(_cache_key(prefix, app, commit))
    if val:
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def _set_cached(prefix, app, commit, data):
    import json
    frappe.cache.set_value(_cache_key(prefix, app, commit), json.dumps(data), expires_in_sec=CACHE_TTL)


def _list_apps(bench):
    r = _exec(bench, "ls apps/")
    return [a.strip() for a in r.get("output", "").split() if a.strip()]


# ── @whitelist API wrappers ──────────────────────────────────────────────

@frappe.whitelist()
def list_bench_health():
    """List all active benches with team, server, app count, and cached health data.
    No docker commands — reads from Frappe DB + Redis cache only (fast)."""
    frappe.only_for("System Manager")

    benches = frappe.get_all(
        "Bench",
        fields=["name", "status", "group", "group.title as group_title",
                "server", "server.title as server_title",
                "cluster.title as cluster_title",
                "is_development_bench", "creation"],
        filters={"status": ["not in", ["Archived"]]},
        order_by="name asc",
        limit=200,
    )
    if not benches:
        return []

    bench_names = [b.name for b in benches]

    # Sites per bench
    site_counts = {}
    for s in frappe.get_all("Site", fields=["bench", "count(name) as cnt"],
                            filters={"bench": ["in", bench_names], "status": ["!=", "Archived"]},
                            group_by="bench"):
        site_counts[s.bench] = s.cnt

    # Apps per bench (from Bench App child table)
    app_counts = {}
    for a in frappe.get_all("Bench App", fields=["parent", "count(name) as cnt"],
                            filters={"parent": ["in", bench_names]},
                            group_by="parent"):
        app_counts[a.parent] = a.cnt

    # Team from Release Group
    # Resolve team IDs → display names
    group_teams = {}
    groups = list({b.group for b in benches if b.group})
    if groups:
        team_ids = set()
        for g in frappe.get_all("Release Group", fields=["name", "team"],
                                filters={"name": ["in", groups]}):
            group_teams[g.name] = g.team
            if g.team:
                team_ids.add(g.team)
        # Look up team display names
        team_names = {}
        if team_ids:
            for t in frappe.get_all("Team", fields=["name", "team_title", "user"],
                                    filters={"name": ["in", list(team_ids)]}):
                team_names[t.name] = t.team_title or t.user or t.name
        # Replace IDs with display names
        for g_name in group_teams:
            tid = group_teams[g_name]
            group_teams[g_name] = team_names.get(tid, tid)

    results = []
    for b in benches:
        # Check if we have cached health summary
        cached_summary = frappe.cache.get_value(f"code_health:summary:{b.name}")
        health = None
        if cached_summary:
            import json
            try:
                health = json.loads(cached_summary)
            except (json.JSONDecodeError, TypeError):
                pass

        results.append({
            "name": b.name,
            "status": b.status,
            "group": b.group,
            "group_title": b.group_title,
            "server": b.server,
            "server_title": b.server_title,
            "cluster_title": b.cluster_title,
            "is_dev": b.is_development_bench,
            "creation": str(b.creation),
            "site_count": site_counts.get(b.name, 0),
            "app_count": app_counts.get(b.name, 0),
            "team": group_teams.get(b.group, ""),
            "health": health,
        })
    return results


@frappe.whitelist()
def scan_bench_health(bench_name, app_filter=None):
    """Scan apps in a bench — returns circle-packing JSON with health data."""
    from .health_tree import build_tree, compute_stats
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)

    filter_path = f"apps/{_safe(app_filter)}" if app_filter else "apps"
    cmd = (
        f"find {filter_path} -type f "
        f"\\( -name '*.py' -o -name '*.js' -o -name '*.ts' -o -name '*.tsx' "
        f"-o -name '*.vue' -o -name '*.dart' -o -name '*.rs' -o -name '*.go' "
        f"-o -name '*.json' -o -name '*.html' -o -name '*.css' -o -name '*.md' \\) "
        f"-not -path '*node_modules*' -not -path '*__pycache__*' "
        f"-not -path '*.git*' -not -path '*dist*' "
        f"-exec wc -l {{}} +"
    )
    result = _exec(bench, cmd)
    file_data = {}
    for line in result.get("output", "").strip().split("\n"):
        line = line.strip()
        if not line or line.endswith(" total"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            file_data[parts[1]] = int(parts[0])

    tree = build_tree(file_data, bench_name)
    compute_stats(tree)
    return tree


@frappe.whitelist()
def get_health_summary(bench_name):
    """Quick health summary — counts only, no full tree."""
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)

    cmd = (
        "find apps -type f "
        "\\( -name '*.py' -o -name '*.js' -o -name '*.ts' -o -name '*.tsx' -o -name '*.vue' \\) "
        "-not -path '*node_modules*' -not -path '*__pycache__*' -not -path '*.git*' "
        "-exec wc -l {} +"
    )
    result = _exec(bench, cmd)
    nums = []
    for line in result.get("output", "").strip().split("\n"):
        line = line.strip()
        if not line or line.endswith(" total"):
            continue
        parts = line.split(None, 1)
        if parts and parts[0].isdigit():
            nums.append(int(parts[0]))

    total = len(nums)
    violations = sum(1 for l in nums if l > HARD_LIMIT)
    warnings = sum(1 for l in nums if SOFT_LIMIT < l <= HARD_LIMIT)
    clean = total - violations - warnings

    sec_r = _exec(bench, "grep -r -Ec 'api_key\\s*=\\s*[\\x27\"]|password\\s*=\\s*[\\x27\"][^\\x27\"]{8,}|secret_key\\s*=\\s*[\\x27\"]|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{20}' "
                         "apps/ --include='*.py' 2>/dev/null | "
                         "grep -v node_modules | grep -v __pycache__ | "
                         "awk -F: '{s+=$2} END {print s+0}'")
    security_alerts = int(sec_r.get("output", "0").strip() or 0)

    import json as _json
    summary = {
        "total_files": total, "total_lines": sum(nums),
        "clean": clean, "warning": warnings, "violation": violations,
        "health_pct": round(clean / total * 100) if total else 0,
        "security_alerts": security_alerts,
    }
    # Cache for the listing page (no TTL — refreshed on next scan)
    frappe.cache.set_value(f"code_health:summary:{bench_name}", _json.dumps(summary), expires_in_sec=CACHE_TTL)
    return summary


@frappe.whitelist()
def get_app_scores(bench_name, include_all=False):
    """Score each app on 8 quality dimensions. Cached per (app, commit)."""
    from .health_scoring import (score_claude, score_readme, score_docs, score_tests,
                                  score_clean, score_patterns, score_lessons, score_security)
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)
    apps = _list_apps(bench)
    commits = _get_app_commits(bench)

    results = []
    for app in apps:
        if not include_all and app in UPSTREAM_APPS:
            continue
        commit = commits.get(app, "")
        cached = _get_cached("scores", app, commit) if commit else None
        if cached:
            results.append(cached)
            continue
        scores = {
            "claude_md": score_claude(bench, app),
            "readme": score_readme(bench, app),
            "documentation": score_docs(bench, app),
            "tests": score_tests(bench, app),
            "clean_code": score_clean(bench, app),
            "code_patterns": score_patterns(bench, app),
            "lessons": score_lessons(bench, app),
            "security": score_security(bench, app),
        }
        scores["overall"] = round(sum(scores.values()) / len(scores))
        entry = {"app": app, "scores": scores}
        if commit:
            _set_cached("scores", app, commit, entry)
        results.append(entry)
    return results


@frappe.whitelist()
def get_docs_compliance(bench_name):
    """Check documentation compliance per app. Cached per (app, commit)."""
    from .health_scoring import score_security
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)

    CHECKS = [
        ("CLAUDE.md", "test -f apps/{app}/CLAUDE.md"),
        ("README.md", "test -f apps/{app}/README.md"),
        ("docs/wiki/", "test -d apps/{app}/docs/wiki"),
        ("DEVLOG.md", "test -f apps/{app}/DEVLOG.md"),
        ("tests/", "test -d apps/{app}/tests"),
        ("lessons", "test -f apps/{app}/lessons-learned.md"),
        (".gitignore", "test -f apps/{app}/.gitignore"),
    ]

    apps = _list_apps(bench)
    commits = _get_app_commits(bench)

    results = []
    for app in apps:
        commit = commits.get(app, "")
        cached = _get_cached("compliance", app, commit) if commit else None
        if cached:
            results.append(cached)
            continue

        checks = []
        passed = 0
        for name, cmd_tpl in CHECKS:
            r = _exec(bench, cmd_tpl.format(app=app) + " && echo PASS || echo FAIL")
            ok = r.get("output", "").strip() == "PASS"
            checks.append({"name": name, "status": ok})
            if ok:
                passed += 1

        sec = score_security(bench, app)
        sec_ok = sec >= 80
        checks.append({"name": "Security", "status": sec_ok, "score": sec})
        if sec_ok:
            passed += 1

        total = len(checks)
        entry = {
            "app": app, "is_custom": app not in UPSTREAM_APPS,
            "checks": checks, "passed": passed, "total": total,
            "compliance_pct": round(passed / total * 100) if total else 0,
        }
        if commit:
            _set_cached("compliance", app, commit, entry)
        results.append(entry)
    return results


@frappe.whitelist()
def get_app_stack_info(bench_name):
    """Tech stack summary per app. Cached per (app, commit)."""
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)
    apps = _list_apps(bench)
    commits = _get_app_commits(bench)

    results = []
    for app in apps:
        commit = commits.get(app, "")
        cached = _get_cached("stack", app, commit) if commit else None
        if cached:
            results.append(cached)
            continue
        app = _safe(app)
        info = {"app": app, "framework": "unknown", "version": ""}

        r = _exec(bench, f"test -f apps/{app}/hooks.py && echo frappe || "
                         f"test -f apps/{app}/pubspec.yaml && echo flutter || "
                         f"test -f apps/{app}/Cargo.toml && echo rust || "
                         f"test -f apps/{app}/package.json && echo node || echo unknown")
        info["framework"] = r.get("output", "").strip() or "unknown"

        r = _exec(bench, f"grep -m1 __version__ apps/{app}/*/__init__.py 2>/dev/null || echo ?")
        ver = r.get("output", "").strip()
        if "__version__" in ver:
            info["version"] = ver.split("=")[-1].strip().strip("'\"")

        r = _exec(bench, f"find apps/{app} -name '*.py' -not -path '*__pycache__*' -not -path '*.git*' | wc -l")
        info["py_files"] = int(r.get("output", "0").strip() or 0)

        r = _exec(bench, f"find apps/{app} \\( -name '*.js' -o -name '*.ts' -o -name '*.vue' \\) -not -path '*node_modules*' -not -path '*.git*' | wc -l")
        info["js_files"] = int(r.get("output", "0").strip() or 0)

        r = _exec(bench, f"find apps/{app} \\( -name '*.py' -o -name '*.js' -o -name '*.vue' \\) "
                         f"-not -path '*node_modules*' -not -path '*__pycache__*' -not -path '*.git*' "
                         f"-exec wc -l {{}} + 2>/dev/null | tail -1")
        total_line = r.get("output", "").strip()
        info["total_lines"] = int(total_line.split()[0]) if total_line and total_line.split()[0].isdigit() else 0

        r = _exec(bench, f"git -C apps/{app} rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown")
        info["branch"] = r.get("output", "").strip() or "unknown"

        r = _exec(bench, f"git -C apps/{app} rev-parse --short HEAD 2>/dev/null || echo ?")
        info["commit_hash"] = r.get("output", "").strip()

        r = _exec(bench, f"git -C apps/{app} remote get-url origin 2>/dev/null || echo ?")
        remote = r.get("output", "").strip()
        if "github.com" in remote:
            info["repository"] = remote.split("github.com")[-1].strip("/:.").replace(".git", "")
        else:
            info["repository"] = ""

        if commit:
            _set_cached("stack", app, commit, info)
        results.append(info)
    return results


@frappe.whitelist()
def get_app_interactions(bench_name):
    """Scan hooks.py per app — returns doc_events, scheduler, overrides."""
    from .health_inventory import scan_app_interactions
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)
    return scan_app_interactions(bench)


@frappe.whitelist()
def get_scripts_inventory(bench_name):
    """Inventory: client scripts, controllers, whitelisted methods, reports per app."""
    from .health_inventory import scan_scripts_inventory
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)
    return scan_scripts_inventory(bench)
