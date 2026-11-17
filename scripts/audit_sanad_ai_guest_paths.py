#!/usr/bin/env python3
"""Audit that the Sanad AI control center guest paths are in press/auth.py ALLOWED_PATHS.

Client sites call these methods with a per-site service token, not a Press login.
Without an entry the auth hook answers 401 "Access not allowed for this URL" (the
2026-11-09 revoke_for_site incident). Add every new guest path of the control center
to REQUIRED below and to ALLOWED_PATHS in the same change.

USAGE:
    python3 scripts/audit_sanad_ai_guest_paths.py    # exits 1 if any path is missing
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AUTH_FILE = REPO_ROOT / "press" / "auth.py"

REQUIRED = [
	"/api/method/sanad_ai_control_center.api.provision_for_site",
	"/api/method/sanad_ai_control_center.api.revoke_for_site",
	"/api/method/sanad_ai_control_center.api.policy_for_site",
	"/api/method/sanad_ai_control_center.api.release_for_site",
	"/api/method/sanad_ai_control_center.usage_ingest.ingest_usage",
	"/api/method/sanad_ai_control_center.governance_ingest.ingest_governance_snapshot",
]


def allowed_paths(source: str) -> list[str]:
	"""The string entries of the ALLOWED_PATHS list, read without importing frappe."""
	for node in ast.parse(source).body:
		if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "ALLOWED_PATHS" for t in node.targets):
			return [e.value for e in node.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
	raise SystemExit("ALLOWED_PATHS not found in press/auth.py")


def main() -> int:
	allowed = set(allowed_paths(AUTH_FILE.read_text()))
	missing = [p for p in REQUIRED if p not in allowed]
	for path in missing:
		print(f"MISSING from ALLOWED_PATHS: {path}")
	if not missing:
		print(f"OK: all {len(REQUIRED)} Sanad AI guest paths are allow-listed")
	return 1 if missing else 0


if __name__ == "__main__":
	sys.exit(main())
