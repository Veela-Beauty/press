#!/usr/bin/env python3
"""Audit: Bench Shell Log insert uses ignore_permissions=True.

Narrowly scoped — locks in the 2026-05-19 Bench Shell Log fix. Catches
regression if anyone reverts the ignore_permissions=True on
create_bench_shell_log().

We considered a wider audit (every audit-log doctype, every insert from
press/) and found 33 hits — mostly bootstrap scripts, scheduled jobs, and
webhook handlers where the actor runs with System or guest+elevated perms.
None of those fire the bug in practice. The Bench Shell Log case is unique
because docker_execute is called from a Vue dashboard polling flow (Bench
Watch panel polls every 10s as a non-System team user), so the audit-log
insert lands in a context where perm-gating fails the user-visible action.

USAGE:
    python3 scripts/audit_audit_log_inserts.py           # exits 1 if regressed

If we ever find a SECOND audit-log doctype that suffers the same pattern,
add it to the AUDIT_LOG_DOCTYPES_REQUIRING_BYPASS list below + the relevant
file/function.

WIRE INTO CI: press/test_auth.py:TestDashboardContracts runs this in-process.
"""
from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


# Map: (file_path_relative_to_repo, function_or_marker, audit-log doctype name).
# Each tuple represents an audit-log insert from a user-facing code path
# whose perm gate must be bypassed. Add new entries here (NOT remove
# existing ones) if you find another instance of the same pattern in the wild.
AUDIT_LOG_INSERTS_REQUIRING_BYPASS = [
	(
		"press/press/doctype/bench_shell_log/bench_shell_log.py",
		"def create_bench_shell_log",
		"Bench Shell Log",
	),
]


def check_one(file_rel: str, function_marker: str, doctype: str) -> str | None:
	"""Return error message if the function block is missing ignore_permissions=True,
	or None if the bypass is present.
	"""
	path = REPO_ROOT / file_rel
	if not path.exists():
		return f"file not found: {file_rel}"
	text = path.read_text()
	# Find the function block: everything from function_marker to the next top-level def or eof
	start = text.find(function_marker)
	if start == -1:
		return f"function marker {function_marker!r} not found in {file_rel}"
	tail = text[start:]
	# Stop at the next top-level `def ` or `class `
	next_def = len(tail)
	for marker in ("\ndef ", "\nclass "):
		idx = tail.find(marker, len(function_marker))
		if idx != -1 and idx < next_def:
			next_def = idx
	block = tail[:next_def]
	# Block must contain an .insert(ignore_permissions=True) for the doctype
	if doctype not in block:
		return f"function {function_marker!r} in {file_rel} doesn't reference doctype {doctype!r}"
	if ".insert(ignore_permissions=True)" not in block:
		return (
			f"{file_rel}::{function_marker} writes {doctype} via .insert() WITHOUT "
			f"ignore_permissions=True — non-System team users will hit PermissionError"
		)
	return None


def main() -> int:
	failures = []
	for file_rel, marker, doctype in AUDIT_LOG_INSERTS_REQUIRING_BYPASS:
		err = check_one(file_rel, marker, doctype)
		if err:
			failures.append(err)
		else:
			print(f"OK  {doctype}: {file_rel}::{marker} uses ignore_permissions=True")

	if failures:
		print()
		print(f"!! {len(failures)} REGRESSED:")
		for f in failures:
			print(f"  -- {f}")
		print()
		print("Fix: restore the .insert(ignore_permissions=True) on the audit-log row.")
		print("Without it, non-System team users hit PermissionError on every flow that")
		print("triggers the audit log (e.g. every 10s on bench Actions pages via the")
		print("Bench Watch poll).")
		return 1
	return 0


if __name__ == "__main__":
	sys.exit(main())
