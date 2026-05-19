#!/usr/bin/env python3
"""Audit: every dotted-path call from dashboard/src is decorated with @frappe.whitelist.

Catches the "I added a Python method and a Vue caller, but forgot the
@frappe.whitelist() decorator → 'not whitelisted' error" trap.

USAGE:
    python3 scripts/audit_dashboard_whitelisted.py           # exits 1 if any miss
    python3 scripts/audit_dashboard_whitelisted.py --print   # also list every OK

WIRE INTO CI: press/test_auth.py:TestDashboardContracts runs this in-process.

LIMITS:
    Same as audit_dashboard_method_exists.py — top-level def only, doesn't
    chase re-exports or class methods. Add the same KNOWN_DYNAMIC entries
    for legit dynamic paths (this script imports them from the sibling
    audit_dashboard_method_exists module to stay in lockstep).
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from audit_dashboard_method_exists import (  # noqa: E402
	KNOWN_DYNAMIC,
	collect_callers,
	resolve_to_python_file,
)


def is_whitelisted(path: Path, symbol: str) -> bool:
	"""Return True if the top-level `symbol` in `path` carries any
	@frappe.whitelist or @dashboard_whitelist decorator. We accept either
	because both register the function with Frappe's whitelist registry.
	"""
	try:
		tree = ast.parse(path.read_text(), filename=str(path))
	except SyntaxError:
		return False

	def has_whitelist_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
		for dec in node.decorator_list:
			# Match: @frappe.whitelist, @frappe.whitelist(...), @dashboard_whitelist, @dashboard_whitelisted, @rate_limited (any of these implies whitelist registration)
			name = ""
			if isinstance(dec, ast.Name):
				name = dec.id
			elif isinstance(dec, ast.Attribute):
				name = dec.attr
			elif isinstance(dec, ast.Call):
				if isinstance(dec.func, ast.Name):
					name = dec.func.id
				elif isinstance(dec.func, ast.Attribute):
					name = dec.func.attr
			if name in ("whitelist", "dashboard_whitelist", "dashboard_whitelisted"):
				return True
		return False

	# Frappe's dispatcher only calls module-level functions for a dotted path
	# like `press.api.x.method` — it never resolves to a class method with the
	# same name. So check TOP-LEVEL ONLY. (If a module has both a top-level
	# function `foo` and a class method `Bar.foo`, the dispatcher reaches the
	# top-level one — which is the one we audit.)
	target = symbol.split(".")[-1]
	for node in ast.iter_child_nodes(tree):
		if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target:
			return has_whitelist_decorator(node)
		# Re-exports: assume they pull a whitelisted symbol (worst case we get
		# a false negative; this audit's goal is to catch FORGOTTEN decorators
		# on freshly-written methods, not re-exports).
		if isinstance(node, ast.ImportFrom):
			for alias in node.names:
				if (alias.asname or alias.name) == target:
					return True
	return False


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--print", dest="print_all", action="store_true")
	args = parser.parse_args()

	callers = collect_callers()
	print(f"Audit: {len(callers)} unique dotted-path callers (recognised call shape only)")

	missing: list[tuple[str, Path, str, list[Path]]] = []
	for dotted in sorted(callers):
		if dotted in KNOWN_DYNAMIC:
			continue
		mod, symbol = resolve_to_python_file(dotted)
		if mod is None:
			# Caught by audit_dashboard_method_exists.py — skip here
			continue
		if not is_whitelisted(mod, symbol):
			missing.append((dotted, mod.relative_to(REPO_ROOT), symbol, callers[dotted]))
			continue
		if args.print_all:
			print(f"  OK   {dotted} → @whitelist")

	if missing:
		print(f"\n!! {len(missing)} VUE CALLERS HIT METHODS WITHOUT @frappe.whitelist:")
		for dotted, mod, symbol, files in missing:
			print(f"  -- {dotted}")
			print(f"       {mod}::{symbol} has no @whitelist decorator")
			for f in files[:3]:
				print(f"       called from: {f}")
		print("\nFix: add @frappe.whitelist() above the method. Without it, the dashboard")
		print("gets 'is not whitelisted' from Frappe for every call.")
		return 1

	print("OK — every dashboard dotted-path caller resolves to a whitelisted method.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
