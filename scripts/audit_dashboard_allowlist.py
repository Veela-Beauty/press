#!/usr/bin/env python3
"""Audit dashboard call paths vs press/auth.py ALLOWED_WILDCARD_PATHS.

Catches the recurring "new whitelisted method called from Vue but not in the
auth allowlist" bug. Without auth-hook coverage, non-System team users get a
401 on the first call; the Vue dashboard interprets 401 as session-expired
and force-logs-out. Three documented incidents in two weeks (2026-05-10
deploy_candidate_build, 2026-05-18 bench_dev_watch + bench_code_health,
2026-05-19 release_group_clone + bench_vscode + press.ai.api).

USAGE:
    python3 scripts/audit_dashboard_allowlist.py           # exits 1 if any gap
    python3 scripts/audit_dashboard_allowlist.py --print   # also list every
                                                            # caller + which
                                                            # rule allows it

WIRE INTO CI:
    Add as a step in scripts/pre_push_check.py so any PR that adds a new
    whitelisted method gets a "missing from allowlist" failure before merge.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
AUTH_FILE = REPO_ROOT / "press" / "auth.py"
DASHBOARD_SRC = REPO_ROOT / "dashboard" / "src"

# Matches dotted paths that look like Press whitelisted method calls. We
# anchor on the typical roots ('press.api', 'press.press', 'press.saas',
# 'press.mcp_server', 'press.www') to keep noise low.
PATH_PATTERN = re.compile(
	r"\bpress\.(?:api|press|saas|mcp_server|www)\.[a-z0-9_.]+",
	re.IGNORECASE,
)


def load_allowlist() -> tuple[set[str], set[str]]:
	"""Return (exact, wildcard) sets from press/auth.py."""
	content = AUTH_FILE.read_text()
	# Find both lists by their starts. ALLOWED_PATHS is exact; ALLOWED_WILDCARD_PATHS
	# is prefix-matched.
	def section(start: str, end: str) -> str:
		i = content.find(start)
		j = content.find(end)
		return content[i:j] if i >= 0 and j > i else ""

	exact_section = section("ALLOWED_PATHS", "ALLOWED_WILDCARD_PATHS")
	wildcard_section = section("ALLOWED_WILDCARD_PATHS", "DENIED_PATHS")

	exact = set(re.findall(r'"/api/method/([^"]+)"', exact_section))
	wildcards = set(re.findall(r'"/api/method/([^"]+?)\.?",', wildcard_section))
	# wildcard entries end with `.` in source; we strip it for prefix matching.
	wildcards = {w.rstrip(".") for w in wildcards}
	return exact, wildcards


def collect_callers() -> dict[str, list[Path]]:
	"""Walk dashboard/src and return {dotted_path: [files where it appears]}."""
	callers: dict[str, list[Path]] = {}
	for ext in ("*.vue", "*.js", "*.ts"):
		for path in DASHBOARD_SRC.rglob(ext):
			text = path.read_text(errors="ignore")
			for match in PATH_PATTERN.findall(text):
				# Skip module paths that don't end in a method call —
				# `press.press.doctype.bench.bench_dev_overview` (bare module)
				# is not a real caller; the actual call is `bench_dev_overview.foo`.
				# Heuristic: a caller must have at least 4 dots (root.module.submod.method).
				if match.count(".") >= 3:
					callers.setdefault(match, []).append(path.relative_to(REPO_ROOT))
	return callers


def is_allowed(path: str, exact: set[str], wildcards: set[str]) -> str | None:
	"""Return the rule that allows the path, or None if not allowed."""
	if path in exact:
		return f"exact:{path}"
	for prefix in wildcards:
		if path.startswith(prefix + ".") or path == prefix:
			return f"wildcard:{prefix}.*"
	return None


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"--print",
		dest="print_all",
		action="store_true",
		help="Print every caller + which rule allows it (useful for spot-audit)",
	)
	args = parser.parse_args()

	if not AUTH_FILE.exists():
		print(f"ERROR: {AUTH_FILE} not found — run this from the press repo root", file=sys.stderr)
		return 2

	exact, wildcards = load_allowlist()
	callers = collect_callers()

	print(f"Audit: {len(callers)} unique dotted-path callers in {DASHBOARD_SRC.relative_to(REPO_ROOT)}")
	print(f"Allowlist: {len(exact)} exact, {len(wildcards)} wildcards")
	print()

	missing: list[tuple[str, list[Path]]] = []
	for path in sorted(callers):
		rule = is_allowed(path, exact, wildcards)
		if rule is None:
			missing.append((path, callers[path]))
		elif args.print_all:
			print(f"  OK   {path:80s} via {rule}")

	if missing:
		print(f"!! {len(missing)} CALLERS NOT IN ALLOWLIST:")
		for path, files in missing:
			print(f"  -- {path}")
			for f in files[:5]:
				print(f"       {f}")
			if len(files) > 5:
				print(f"       ... and {len(files) - 5} more files")
		print()
		print("Fix: add an entry to ALLOWED_WILDCARD_PATHS in press/auth.py covering")
		print("the missing prefixes. Without this, non-System team users get 401")
		print("on the first call, and the Vue dashboard force-logs-them-out.")
		return 1

	print("OK — every dashboard dotted-path caller is covered.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
