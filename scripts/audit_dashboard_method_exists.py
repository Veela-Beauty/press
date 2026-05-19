#!/usr/bin/env python3
"""Audit: every dotted-path call from dashboard/src points at a real Python symbol.

Catches the "Vue calls press.press.doctype.X.Y.method but the method actually
lives at press.press.doctype.X.Z.method" trap. Reported 2026-05-19 by Ahmed
hitting the VSCodeLaunchDialog 'has no attribute' error.

USAGE:
    python3 scripts/audit_dashboard_method_exists.py           # exits 1 if any miss
    python3 scripts/audit_dashboard_method_exists.py --print   # also list every
                                                                # resolved caller

WIRE INTO CI: press/test_auth.py:TestDashboardContracts runs this in-process.

LIMITS:
    Resolves by parsing module files for top-level `def <name>(`. Doesn't
    follow re-exports, class methods, or runtime-generated symbols. The few
    legitimately dynamic call sites should be added to KNOWN_DYNAMIC at the
    bottom of this file rather than papering over with a broad skip.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_SRC = REPO_ROOT / "dashboard" / "src"

# A dotted-path is only treated as a method CALL if it appears in one of these
# call shapes. Bare strings like `const API = 'press.press.doctype...'` get
# concatenated at runtime and are tracked via the allowlist audit instead.
# Patterns:
#   call('press.api.foo',           — frappe-ui's call() helper
#   url: 'press.api.foo',           — createResource({url: '...'})
#   method: 'press.api.foo',        — frappe.call({method: '...'})
#   "press.api.foo"                 — same as above with double quotes
CALL_SHAPE_PATTERN = re.compile(
	r"""
	(?:
		# call('path', ...) or call("path", ...)
		\bcall\s*\(\s*['"](?P<call>press\.(?:api|press|saas|mcp_server|www)\.[a-z0-9_.]+)['"]
		|
		# url: 'path' or url: "path"
		\burl\s*:\s*['"](?P<url>press\.(?:api|press|saas|mcp_server|www)\.[a-z0-9_.]+)['"]
		|
		# method: 'path' or method: "path"
		\bmethod\s*:\s*['"](?P<method>press\.(?:api|press|saas|mcp_server|www)\.[a-z0-9_.]+)['"]
	)
	""",
	re.IGNORECASE | re.VERBOSE,
)

# Callers that legitimately can't be statically resolved (e.g. dotted path
# built from a runtime variable). Each entry MUST carry a comment.
# DO NOT add net-new misses here — fix them instead. The whole point of
# this audit is to prevent the set from growing.
KNOWN_DYNAMIC: set[str] = set()


def collect_callers() -> dict[str, list[Path]]:
	"""Return {dotted_path: [files where it appears]} for paths that appear
	in a recognised call shape (call(...), url:..., method:...). Bare
	string constants used for runtime concatenation are skipped — those are
	tracked by the allowlist audit, not this one.
	"""
	callers: dict[str, list[Path]] = {}
	for ext in ("*.vue", "*.js", "*.ts"):
		for path in DASHBOARD_SRC.rglob(ext):
			text = path.read_text(errors="ignore")
			for m in CALL_SHAPE_PATTERN.finditer(text):
				dotted = m.group("call") or m.group("url") or m.group("method")
				if dotted and dotted.count(".") >= 3:
					callers.setdefault(dotted, []).append(path.relative_to(REPO_ROOT))
	return callers


def resolve_to_python_file(dotted: str) -> tuple[Path | None, str | None]:
	"""Given press.press.doctype.bench.bench_vscode.get_vscode_remote_url, return
	(REPO_ROOT/press/press/doctype/bench/bench_vscode.py, 'get_vscode_remote_url')
	or (None, None) if no module file matches.
	"""
	parts = dotted.split(".")
	# Try every split point: module = parts[:i], symbol = parts[i:]
	for i in range(len(parts) - 1, 0, -1):
		module_path = REPO_ROOT / Path(*parts[:i]).with_suffix(".py")
		if module_path.exists():
			symbol = ".".join(parts[i:])
			return module_path, symbol
		# Also try as __init__.py for package imports
		init_path = REPO_ROOT / Path(*parts[:i]) / "__init__.py"
		if init_path.exists():
			symbol = ".".join(parts[i:])
			return init_path, symbol
	return None, None


def has_top_level_def(path: Path, symbol: str) -> bool:
	"""Check whether `path` defines `symbol` as a top-level function or class.

	Symbol may be 'foo' or 'ClassName.foo' for a method. For class methods we
	check that the class exists and the method is defined inside it.
	"""
	try:
		tree = ast.parse(path.read_text(), filename=str(path))
	except SyntaxError:
		return False

	if "." in symbol:
		class_name, method_name = symbol.split(".", 1)
		for node in ast.iter_child_nodes(tree):
			if isinstance(node, ast.ClassDef) and node.name == class_name:
				for sub in ast.iter_child_nodes(node):
					if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name == method_name:
						return True
				return False
		return False

	for node in ast.iter_child_nodes(tree):
		if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
			return True
		# Re-exports: `from .x import symbol` or `from .x import symbol as alias`
		if isinstance(node, ast.ImportFrom):
			for alias in node.names:
				if (alias.asname or alias.name) == symbol:
					return True
		# Module-level assignments (rare but legit: `foo = some_function`)
		if isinstance(node, ast.Assign):
			for target in node.targets:
				if isinstance(target, ast.Name) and target.id == symbol:
					return True
	return False


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--print", dest="print_all", action="store_true")
	args = parser.parse_args()

	callers = collect_callers()
	print(f"Audit: {len(callers)} unique dotted-path callers")

	missing: list[tuple[str, Path | None, str | None, list[Path]]] = []
	for dotted in sorted(callers):
		if dotted in KNOWN_DYNAMIC:
			continue
		mod, symbol = resolve_to_python_file(dotted)
		if mod is None:
			# Module file doesn't exist at all
			missing.append((dotted, None, None, callers[dotted]))
			continue
		if not has_top_level_def(mod, symbol):
			missing.append((dotted, mod.relative_to(REPO_ROOT), symbol, callers[dotted]))
			continue
		if args.print_all:
			print(f"  OK   {dotted} → {mod.relative_to(REPO_ROOT)}::{symbol}")

	if missing:
		print(f"\n!! {len(missing)} VUE CALLERS POINT AT MISSING METHODS:")
		for dotted, mod, symbol, files in missing:
			if mod is None:
				print(f"  -- {dotted}")
				print(f"       no Python module file found for this path")
			else:
				print(f"  -- {dotted}")
				print(f"       module {mod} exists but has no top-level `{symbol}`")
			for f in files[:3]:
				print(f"       called from: {f}")
			if len(files) > 3:
				print(f"       ... and {len(files) - 3} more files")
		print("\nFix: rename the Vue caller to point at the real symbol, OR add the")
		print("missing whitelisted method. If the caller is intentionally dynamic,")
		print("add the dotted path to KNOWN_DYNAMIC in this script with a comment.")
		return 1

	print("OK — every dashboard dotted-path caller resolves to a real method.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
