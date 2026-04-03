"""
Code health scoring functions — 8 quality dimensions per app.
Called from bench_code_health.py (the @whitelist stub).
"""

from .bench_code_health import _exec, _safe, CLAUDE_SECTIONS, README_KEYWORDS, HARD_LIMIT, SOFT_LIMIT


def score_claude(bench, app):
    app = _safe(app)
    r = _exec(bench, f"cat apps/{app}/CLAUDE.md 2>/dev/null || echo __MISSING__")
    c = r.get("output", "")
    if "__MISSING__" in c:
        return 0
    if len(c.strip()) < 50:
        return 20
    score = 20
    for s in CLAUDE_SECTIONS:
        if f"## {s}" in c or f"# {s}" in c:
            score += 14
    return min(score, 100)


def score_readme(bench, app):
    app = _safe(app)
    r = _exec(bench, f"cat apps/{app}/README.md 2>/dev/null || echo __MISSING__")
    c = r.get("output", "").lower()
    if "__missing__" in c:
        return 0
    if len(c.strip()) < 50:
        return 20
    score = 20
    for kw in README_KEYWORDS:
        if kw in c:
            score += 12
    return min(score, 100)


def score_docs(bench, app):
    app = _safe(app)
    r = _exec(bench, f"find apps/{app}/docs -type f -name '*.md' 2>/dev/null | wc -l")
    n = int(r.get("output", "0").strip() or 0)
    if n == 0:
        return 0
    return min(30 + n * 10, 100)


def score_tests(bench, app):
    app = _safe(app)
    r = _exec(bench, f"find apps/{app} -name 'test_*.py' -not -path '*__pycache__*' | wc -l")
    tests = int(r.get("output", "0").strip() or 0)
    r2 = _exec(bench, f"find apps/{app} -name '*.py' -not -name 'test_*' -not -path '*__pycache__*' | wc -l")
    code = int(r2.get("output", "0").strip() or 0)
    if code == 0:
        return 0
    return min(round(tests / code * 200), 100)


def score_clean(bench, app):
    app = _safe(app)
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
    under = sum(1 for n in nums if n < SOFT_LIMIT)
    over = sum(1 for n in nums if n > HARD_LIMIT)
    return max(0, min(round(under / len(nums) * 100) - over * 2, 100))


def score_patterns(bench, app):
    app = _safe(app)
    r = _exec(bench, f"grep -r -c 'except:' apps/{app}/ --include='*.py' 2>/dev/null | awk -F: '{{s+=$2}} END {{print s+0}}'")
    bare = int(r.get("output", "0").strip() or 0)
    r2 = _exec(bench, f"grep -r -c 'console\\.log' apps/{app}/ --include='*.js' --include='*.vue' 2>/dev/null | awk -F: '{{s+=$2}} END {{print s+0}}'")
    console = int(r2.get("output", "0").strip() or 0)
    r3 = _exec(bench, f"grep -r -c 'print(' apps/{app}/ --include='*.py' 2>/dev/null | awk -F: '{{s+=$2}} END {{print s+0}}'")
    prints = int(r3.get("output", "0").strip() or 0)
    return max(0, 100 - (bare * 5 + console + prints) * 2)


def score_lessons(bench, app):
    app = _safe(app)
    r = _exec(bench, f"test -f apps/{app}/lessons-learned.md && echo Y || "
                     f"test -f apps/{app}/LESSONS.md && echo Y || "
                     f"test -f apps/{app}/docs/wiki/lessons-learned.md && echo Y || echo N")
    return 100 if r.get("output", "").strip() == "Y" else 0


def score_security(bench, app):
    """Check for hardcoded secrets — uses assignment-context patterns to reduce false positives."""
    app = _safe(app)
    # Patterns that look for actual value assignments, not just keyword mentions
    patterns = [
        r"api_key\s*=\s*['\"][A-Za-z0-9]",
        r"password\s*=\s*['\"][^'\"]{8,}",
        r"secret_key\s*=\s*['\"][A-Za-z0-9]",
        r"AKIA[0-9A-Z]{16}",
    ]
    total = 0
    for pat in patterns:
        r = _exec(bench, f"grep -r -Ec '{pat}' apps/{app}/ --include='*.py' 2>/dev/null | awk -F: '{{s+=$2}} END {{print s+0}}'")
        total += int(r.get("output", "0").strip() or 0)
    return max(0, 100 - total * 20)
