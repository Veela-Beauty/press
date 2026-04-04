"""AI response linter — detects dangerous patterns in LLM output.

Three categories:
  Category 1 (Hard block): Removed from response, escalation auto-started.
  Category 2 (Approval):   Flagged in response, requires TL + Admin approval.
  Category 3 (Warning):    Warning shown inline, user confirms to proceed.

Two-pass scanning:
  Pass 1: Fenced code blocks (```...```) — language-aware matching.
  Pass 2: Prose and inline code — catches bypass attempts outside fences.

Pure Python — no Frappe dependency. Safe to import anywhere.
"""

import re
from dataclasses import dataclass, field


@dataclass
class Violation:
    category: int
    pattern: str
    matched_text: str
    description: str
    start: int = 0
    end: int = 0


@dataclass
class LintResult:
    sanitized_text: str
    violations: list[Violation] = field(default_factory=list)

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    @property
    def most_severe_category(self) -> int:
        """Most severe category found. 1=most severe, 3=least. 0=none."""
        if not self.violations:
            return 0
        return min(v.category for v in self.violations)

    # Keep old name as alias for backwards compat during transition
    @property
    def max_category(self) -> int:
        return self.most_severe_category


# --- Fenced code block regex ---
# Matches ``` with optional language tag (allowing trailing spaces and CRLF),
# body captured with negative lookahead (handles backtick-quoted identifiers),
# closed by ``` on its own line.
FENCE_BLOCK = re.compile(
    r"```[^\n]*\r?\n((?:(?!```)[\s\S])*?)```",
    re.MULTILINE,
)


# --- Category 1: Hard block patterns ---
# Each has a "fence" pattern (inside code blocks) and "prose" pattern (anywhere).

CAT1_RULES = [
    {
        "name": "DELETE SQL",
        "description": "Raw SQL DELETE statement — data loss risk",
        "fence": re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE),
        "prose": re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE),
    },
    {
        "name": "DROP TABLE",
        "description": "DROP TABLE statement — permanent table deletion",
        "fence": re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
        "prose": re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
    },
    {
        "name": "TRUNCATE",
        "description": "TRUNCATE statement — deletes all rows permanently",
        "fence": re.compile(r"\bTRUNCATE\s+(?:TABLE\s+)?\w+", re.IGNORECASE),
        "prose": re.compile(r"\bTRUNCATE\s+(?:TABLE\s+)?\w+", re.IGNORECASE),
    },
    {
        "name": "rm -rf",
        "description": "Recursive force delete — irreversible file deletion",
        "fence": re.compile(
            r"\brm\s+(?:-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*|-r\s+-f\b|-f\s+-r\b|--recursive\s+--force|--force\s+--recursive|-rf)\s",
            re.IGNORECASE,
        ),
        "prose": re.compile(
            r"\brm\s+(?:-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*|-r\s+-f\b|-f\s+-r\b|--recursive\s+--force|--force\s+--recursive|-rf)\s",
            re.IGNORECASE,
        ),
    },
    {
        "name": "shutil.rmtree",
        "description": "Python recursive directory deletion",
        "fence": re.compile(r"shutil\.rmtree\s*\(", re.IGNORECASE),
        "prose": re.compile(r"shutil\.rmtree\s*\(", re.IGNORECASE),
    },
    {
        "name": "bench destroy",
        "description": "Destroys entire bench installation",
        "fence": re.compile(r"\bbench\s+destroy\b", re.IGNORECASE),
        "prose": re.compile(r"\bbench\s+destroy\b", re.IGNORECASE),
    },
    {
        "name": "bench uninstall-app",
        "description": "Uninstalls app — may lose customizations",
        "fence": re.compile(r"\bbench\s+uninstall-app\b", re.IGNORECASE),
        "prose": re.compile(r"\bbench\s+uninstall-app\b", re.IGNORECASE),
    },
    {
        "name": "bench drop-site",
        "description": "Drops entire site and database",
        "fence": re.compile(r"\bbench\s+drop-site\b", re.IGNORECASE),
        "prose": re.compile(r"\bbench\s+drop-site\b", re.IGNORECASE),
    },
    {
        "name": "credential modification",
        "description": "Direct credential modification via frappe.conf",
        "fence": re.compile(
            r"frappe\.conf\.\w*(?:password|secret|key)\s*=", re.IGNORECASE
        ),
        "prose": None,  # Not detectable reliably in prose
    },
    {
        "name": "site_config.json write",
        "description": "Direct write to site_config.json — credential exposure risk",
        "fence": re.compile(
            r"open\s*\([^)]*site_config\.json[^)]*,\s*['\"]w", re.IGNORECASE
        ),
        "prose": None,
    },
]

# --- Category 2: Approval required ---

CAT2_RULES = [
    {
        "name": "bulk delete_doc loop",
        "description": "Bulk deletion loop — may delete many records",
        "fence": re.compile(
            r"for\s+\w+\s+in\s+frappe\.(?:get_all|db\.sql)[\s\S]*?frappe\.delete_doc\s*\(",
            re.IGNORECASE,
        ),
        "prose": None,
    },
    {
        "name": "bench migrate staging",
        "description": "Database migration on staging site — may alter production-like data",
        "fence": re.compile(
            r"bench\s+--site\s+\S*(?:staging|stg)\S*\s+migrate\b", re.IGNORECASE
        ),
        "prose": None,
    },
    {
        "name": "permission change",
        "description": "Permission modification — security impact",
        "fence": re.compile(
            r"frappe\.permissions\.(?:add|remove|update)_permission\s*\(",
            re.IGNORECASE,
        ),
        "prose": None,
    },
]

# --- Category 3: Warning + confirm ---

CAT3_RULES = [
    {
        "name": "bench clear-cache",
        "description": "Clears all cache — may cause temporary slowdown",
        "fence": re.compile(r"\bbench\s+clear-cache\b", re.IGNORECASE),
        "prose": None,
    },
    {
        "name": "single delete_doc",
        "description": "Document deletion — confirm before proceeding",
        "fence": re.compile(r"frappe\.delete_doc\s*\(", re.IGNORECASE),
        "prose": None,
    },
    {
        "name": "git reset --hard",
        "description": "Hard git reset — discards uncommitted changes",
        "fence": re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE),
        "prose": None,
    },
]


def _extract_fence_blocks(text: str) -> list[tuple[int, int, str]]:
    """Extract all fenced code blocks as (start, end, body) tuples."""
    blocks = []
    for m in FENCE_BLOCK.finditer(text):
        blocks.append((m.start(), m.end(), m.group(1)))
    return blocks


def _scan_rules(text: str, rules: list[dict], category: int, key: str,
                offset: int = 0) -> list[Violation]:
    """Scan text against a rule list, returning violations."""
    violations = []
    for rule in rules:
        pattern = rule.get(key)
        if pattern is None:
            continue
        for m in pattern.finditer(text):
            violations.append(
                Violation(
                    category=category,
                    pattern=rule["name"],
                    matched_text=m.group(0)[:200],
                    description=rule["description"],
                    start=offset + m.start(),
                    end=offset + m.end(),
                )
            )
    return violations


def lint_response(text: str) -> LintResult:
    """Lint an AI response for dangerous patterns.

    Two-pass scan:
      1. Fenced code blocks — all 3 categories checked.
      2. Prose/inline code — Category 1 patterns checked (bypass prevention).

    Returns a LintResult with sanitized_text and violations list.
    """
    if not text:
        return LintResult(sanitized_text="")

    violations = []
    fence_blocks = _extract_fence_blocks(text)
    cat1_block_spans = []  # Track which fence blocks have Cat 1 violations

    # --- Pass 1: Scan fenced code blocks ---
    for block_start, block_end, body in fence_blocks:
        # Category 1 — check and mark for removal
        cat1_hits = _scan_rules(body, CAT1_RULES, 1, "fence", block_start)
        if cat1_hits:
            violations.extend(cat1_hits)
            cat1_block_spans.append((block_start, block_end))

        # Category 2 — flag only
        violations.extend(_scan_rules(body, CAT2_RULES, 2, "fence", block_start))

        # Category 3 — flag only, skip if block already has Cat 2 hit
        cat2_in_block = any(
            v.category == 2 and block_start <= v.start < block_end
            for v in violations
        )
        if not cat2_in_block:
            violations.extend(_scan_rules(body, CAT3_RULES, 3, "fence", block_start))

    # --- Pass 2: Scan prose (text outside fenced blocks) for Cat 1 ---
    fence_ranges = set()
    for bs, be, _ in fence_blocks:
        for i in range(bs, be):
            fence_ranges.add(i)

    # Build prose text by replacing fenced blocks with spaces (preserve offsets)
    prose_chars = list(text)
    for bs, be, _ in fence_blocks:
        for i in range(bs, be):
            prose_chars[i] = " "
    prose_text = "".join(prose_chars)

    # Scan prose for Cat 1 patterns only
    prose_violations = _scan_rules(prose_text, CAT1_RULES, 1, "prose")
    violations.extend(prose_violations)
    # Mark prose Cat 1 violations for sanitization (these are inline, just flag them)

    # --- Build sanitized text: remove Cat 1 fence blocks ---
    sanitized = text
    # Remove in reverse order to preserve offsets
    for block_start, block_end in sorted(cat1_block_spans, reverse=True):
        sanitized = sanitized[:block_start] + sanitized[block_end:]

    # For prose Cat 1 violations: we can't cleanly remove inline text,
    # so we leave sanitized_text as-is but the violations are recorded.
    # The frontend will handle displaying the warning.

    # Clean up empty lines from removed blocks
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)

    return LintResult(sanitized_text=sanitized, violations=violations)
