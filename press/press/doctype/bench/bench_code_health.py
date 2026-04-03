"""
Code health scanner for benches — runs inside Docker containers.
Returns circle-packing JSON + scoring + compliance data.

Two access modes:
1. Frappe whitelisted (@frappe.whitelist) — for dashboard UI
2. Token-based API (/api/method/...?token=X) — for external tools

Works on any codebase: Python, JS/TS, Vue, Dart, Rust, Go.
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

# Security patterns to detect hardcoded credentials
SECURITY_PATTERNS = [
    ("api_key.*=.*['\\\"][A-Za-z0-9_-]{20,}", "hardcoded API key"),
    ("password.*=.*['\\\"][^'\\\"]{8,}", "hardcoded password"),
    ("token.*=.*['\\\"][A-Za-z0-9_-]{20,}", "hardcoded token"),
    ("AKIA[0-9A-Z]{16}", "AWS access key"),
    ("ghp_[A-Za-z0-9]{36}", "GitHub personal token"),
    ("gho_[A-Za-z0-9]{36}", "GitHub OAuth token"),
    ("sk-[A-Za-z0-9]{20,}", "secret key (OpenAI/Stripe)"),
]


def _exec(bench, cmd):
    """Shorthand for docker_execute with no logging."""
    return bench.docker_execute(cmd, save_output=False, create_log=False)


@frappe.whitelist()
def scan_bench_health(bench_name, app_filter=None):
    """Scan apps in a bench — returns circle-packing JSON with health data."""
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)

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
    result = _exec(bench, cmd)
    output = result.get("output", "")

    file_data = {}
    for line in output.strip().split("\n"):
        line = line.strip()
        if not line or line.endswith(" total"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            file_data[parts[1]] = int(parts[0])

    tree = _build_tree(file_data, bench_name)
    _compute_stats(tree)
    return tree


@frappe.whitelist()
def get_health_summary(bench_name):
    """Quick health summary — counts only, no full tree. Uses find -exec wc."""
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

    return {
        "total_files": total, "total_lines": sum(nums),
        "clean": clean, "warning": warnings, "violation": violations,
        "health_pct": round(clean / total * 100) if total else 0,
    }


@frappe.whitelist()
def get_app_scores(bench_name):
    """Score each custom app on 8 quality dimensions for radar chart."""
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)

    r = _exec(bench, "ls apps/")
    apps = [a.strip() for a in r.get("output", "").split() if a.strip()]

    results = []
    for app in apps:
        if app in UPSTREAM_APPS:
            continue
        scores = {
            "claude_md": _score_claude(bench, app),
            "readme": _score_readme(bench, app),
            "documentation": _score_docs(bench, app),
            "tests": _score_tests(bench, app),
            "clean_code": _score_clean(bench, app),
            "code_patterns": _score_patterns(bench, app),
            "lessons": _score_lessons(bench, app),
            "security": _score_security(bench, app),
        }
        scores["overall"] = round(sum(scores.values()) / len(scores))
        results.append({"app": app, "scores": scores})
    return results


@frappe.whitelist()
def get_docs_compliance(bench_name):
    """Check documentation compliance per app."""
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

    r = _exec(bench, "ls apps/")
    apps = [a.strip() for a in r.get("output", "").split() if a.strip()]

    results = []
    for app in apps:
        checks = []
        passed = 0
        for name, cmd_tpl in CHECKS:
            r = _exec(bench, cmd_tpl.format(app=app) + " && echo PASS || echo FAIL")
            ok = r.get("output", "").strip() == "PASS"
            checks.append({"name": name, "status": ok})
            if ok:
                passed += 1

        # Security check
        sec = _score_security(bench, app)
        sec_ok = sec >= 80
        checks.append({"name": "Security", "status": sec_ok, "score": sec})
        if sec_ok:
            passed += 1

        total = len(checks)
        results.append({
            "app": app, "is_custom": app not in UPSTREAM_APPS,
            "checks": checks, "passed": passed, "total": total,
            "compliance_pct": round(passed / total * 100) if total else 0,
        })
    return results


@frappe.whitelist()
def get_app_stack_info(bench_name):
    """Tech stack summary per app."""
    frappe.only_for("System Manager")
    bench = frappe.get_doc("Bench", bench_name)

    r = _exec(bench, "ls apps/")
    apps = [a.strip() for a in r.get("output", "").split() if a.strip()]

    results = []
    for app in apps:
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

        results.append(info)
    return results


# ── Scoring functions ──────────────────────────────────────────────────────

def _score_claude(bench, app):
    r = _exec(bench, f"cat apps/{app}/CLAUDE.md 2>/dev/null || echo __MISSING__")
    c = r.get("output", "")
    if "__MISSING__" in c:
        return 0
    if len(c.strip()) < 50:
        return 20
    score = 20
    for s in CLAUDE_SECTIONS:
        if f"## {s}" in c or f"# {s}" in c:
            score += 13
    return min(score, 100)


def _score_readme(bench, app):
    r = _exec(bench, f"cat apps/{app}/README.md 2>/dev/null || echo __MISSING__")
    c = r.get("output", "").lower()
    if "__missing__" in c:
        return 0
    if len(c.strip()) < 50:
        return 20
    score = 20
    for kw in README_KEYWORDS:
        if kw in c:
            score += 11
    return min(score, 100)


def _score_docs(bench, app):
    r = _exec(bench, f"find apps/{app}/docs -type f -name '*.md' 2>/dev/null | wc -l")
    n = int(r.get("output", "0").strip() or 0)
    if n == 0:
        return 0
    return min(30 + n * 10, 100)


def _score_tests(bench, app):
    r = _exec(bench, f"find apps/{app} -name 'test_*.py' -not -path '*__pycache__*' | wc -l")
    tests = int(r.get("output", "0").strip() or 0)
    r2 = _exec(bench, f"find apps/{app} -name '*.py' -not -name 'test_*' -not -path '*__pycache__*' | wc -l")
    code = int(r2.get("output", "0").strip() or 0)
    if code == 0:
        return 0
    return min(round(tests / code * 200), 100)


def _score_clean(bench, app):
    r = _exec(bench, f"find apps/{app} \\( -name '*.py' -o -name '*.js' -o -name '*.vue' \\) "
                     f"-not -path '*node_modules*' -not -path '*__pycache__*' -not -path '*.git*' "
                     f"-exec wc -l {{}} + 2>/dev/null | grep -v ' total$'")
    nums = []
    for line in r.get("output", "").strip().split("\n"):
        p = line.strip().split(None, 1)
        if p and p[0].isdigit():
            nums.append(int(p[0]))
    if not nums:
        return 100
    under = sum(1 for l in nums if l < SOFT_LIMIT)
    over = sum(1 for l in nums if l > HARD_LIMIT)
    return max(0, min(round(under / len(nums) * 100) - over * 2, 100))


def _score_patterns(bench, app):
    r = _exec(bench, f"grep -r -c 'except:' apps/{app}/ --include='*.py' 2>/dev/null | awk -F: '{{s+=$2}} END {{print s+0}}'")
    bare = int(r.get("output", "0").strip() or 0)
    r2 = _exec(bench, f"grep -r -c 'console\\.log' apps/{app}/ --include='*.js' --include='*.vue' 2>/dev/null | awk -F: '{{s+=$2}} END {{print s+0}}'")
    console = int(r2.get("output", "0").strip() or 0)
    r3 = _exec(bench, f"grep -r -c 'print(' apps/{app}/ --include='*.py' 2>/dev/null | awk -F: '{{s+=$2}} END {{print s+0}}'")
    prints = int(r3.get("output", "0").strip() or 0)
    return max(0, 100 - (bare * 5 + console + prints) * 2)


def _score_lessons(bench, app):
    r = _exec(bench, f"test -f apps/{app}/lessons-learned.md && echo Y || "
                     f"test -f apps/{app}/LESSONS.md && echo Y || "
                     f"test -f apps/{app}/docs/wiki/lessons-learned.md && echo Y || echo N")
    return 100 if r.get("output", "").strip() == "Y" else 0


def _score_security(bench, app):
    # Simple check: look for common secret patterns without complex regex
    checks = [
        ("api_key", "*.py"),
        ("password", "*.py"),
        ("secret_key", "*.py"),
        ("AKIA", "*.py"),  # AWS key prefix
    ]
    total = 0
    for keyword, glob in checks:
        r = _exec(bench, f"grep -r -l {keyword} apps/{app}/ --include={glob} 2>/dev/null | wc -l")
        n = int(r.get("output", "0").strip() or 0)
        total += n
    # Deduct proportionally but flag HIGH RISK
    return max(0, 100 - total * 20)


# ── Tree builders ──────────────────────────────────────────────────────────

def _build_tree(file_data, root_name):
    root = {"name": root_name, "children": []}
    for filepath, lines in sorted(file_data.items()):
        parts = filepath.split("/")
        if parts[0] == "apps":
            parts = parts[1:]
        node = root
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                ext = "." + part.rsplit(".", 1)[-1] if "." in part else ""
                health = "non-code"
                if ext in CODE_EXTS:
                    health = "violation" if lines > HARD_LIMIT else "warning" if lines > SOFT_LIMIT else "clean"
                node["children"].append({"name": part, "ext": ext, "lines": lines, "health": health})
            else:
                existing = next((c for c in node.get("children", []) if c.get("name") == part and "children" in c), None)
                if not existing:
                    existing = {"name": part, "children": []}
                    node.setdefault("children", []).append(existing)
                node = existing
    return root


def _compute_stats(tree):
    if "children" not in tree:
        is_code = tree.get("ext", "") in CODE_EXTS
        return {"total_files": 1 if is_code else 0, "total_lines": tree.get("lines", 0),
                "clean": 1 if tree.get("health") == "clean" else 0,
                "warning": 1 if tree.get("health") == "warning" else 0,
                "violation": 1 if tree.get("health") == "violation" else 0}
    stats = {"total_files": 0, "total_lines": 0, "clean": 0, "warning": 0, "violation": 0}
    for child in tree["children"]:
        cs = _compute_stats(child)
        for k in stats:
            stats[k] += cs[k]
    tree["stats"] = stats
    if stats["total_files"] > 0:
        tree["health_pct"] = round(stats["clean"] / stats["total_files"] * 100)
    return stats
