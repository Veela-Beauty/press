#!/usr/bin/env python3
"""Audit: press/mcp_server/tools.py ↔ dashboard/src/components/mcp/_tool_catalog.js parity.

The two files describe the same set of MCP tools — backend = source of truth
(determines what dispatching/auth/scope check does), frontend mirror = used
by the Issue Token dialog to show the scope picker. If a tool exists in
tools.py but not _tool_catalog.js, it CANNOT be granted via the UI (the
checkbox doesn't exist). If a tool exists in _tool_catalog.js but not
tools.py, the UI shows a checkbox that produces a non-functional token.

tools.py's header comment says "MUST stay in sync" — this audit enforces it.

USAGE:
    python3 scripts/audit_mcp_catalog_parity.py           # exits 1 if drifted

WIRE INTO CI: press/test_auth.py:TestDashboardContracts runs this in-process.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_PY = REPO_ROOT / "press" / "mcp_server" / "tools.py"
CATALOG_JS = REPO_ROOT / "dashboard" / "src" / "components" / "mcp" / "_tool_catalog.js"


def py_tool_names() -> set[str]:
	"""Tool names declared in TOOLS dict in tools.py."""
	text = TOOLS_PY.read_text()
	# Find TOOLS: dict[str, dict] = { ... } and extract keys
	tools_start = text.find("TOOLS: dict[str, dict] = {")
	if tools_start == -1:
		raise RuntimeError("Could not find TOOLS dict in tools.py")
	# Find matching closing brace by depth counting
	depth = 0
	end = tools_start
	for i, ch in enumerate(text[tools_start:], start=tools_start):
		if ch == "{":
			depth += 1
		elif ch == "}":
			depth -= 1
			if depth == 0:
				end = i
				break
	block = text[tools_start:end]
	# Tool keys are at indent depth 1 (single leading tab). Deeper keys
	# (e.g. args_schema property names like "override", "ttl_minutes") sit
	# at depth 3+ and must be excluded.
	keys = re.findall(r'^\t"([a-z0-9_]+)"\s*:\s*\{', block, re.MULTILINE)
	return set(keys)


def js_tool_names() -> set[str]:
	"""Tool names declared in TOOL_CATALOG in _tool_catalog.js."""
	text = CATALOG_JS.read_text()
	# Pattern: `\tname: { category: '...', risk: '...', ... }`
	# Each tool entry is at depth 1 (single leading tab). Lines inside
	# TOOL_CATEGORIES have `id:`/`label:` not `category:`/`risk:` so a strict
	# match on both keys keeps the audit precise.
	keys = re.findall(
		r'^\t([a-z0-9_]+)\s*:\s*\{[^}]*\bcategory\s*:[^}]*\brisk\s*:',
		text,
		re.MULTILINE,
	)
	return set(keys)


def main() -> int:
	py_names = py_tool_names()
	js_names = js_tool_names()

	print(f"tools.py:           {len(py_names)} tools")
	print(f"_tool_catalog.js:   {len(js_names)} tools")

	in_py_not_js = sorted(py_names - js_names)
	in_js_not_py = sorted(js_names - py_names)

	if in_py_not_js or in_js_not_py:
		if in_py_not_js:
			print(f"\n!! {len(in_py_not_js)} tools in tools.py but NOT in _tool_catalog.js:")
			for n in in_py_not_js:
				print(f"  -- {n}  (cannot be granted via Issue Token UI)")
		if in_js_not_py:
			print(f"\n!! {len(in_js_not_py)} tools in _tool_catalog.js but NOT in tools.py:")
			for n in in_js_not_py:
				print(f"  -- {n}  (UI checkbox would produce a token with a dead scope)")
		print("\nFix: add the missing tool(s) to whichever file is short.")
		print(f"  Backend catalog: {TOOLS_PY.relative_to(REPO_ROOT)}")
		print(f"  Frontend mirror: {CATALOG_JS.relative_to(REPO_ROOT)}")
		return 1

	print(f"OK — both files list exactly the same {len(py_names)} tools.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
