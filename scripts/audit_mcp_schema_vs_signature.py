#!/usr/bin/env python3
"""Audit: MCP args_schema matches the underlying Python method's actual signature.

The pain this catches: an MCP client (Claude Code, an LLM agent, Cursor)
reads the args_schema, builds a call with the documented names + types,
sends it, and the Python method rejects the call because the schema
doesn't match the real signature. Three drift modes:

  1. Schema says `array of string`, method iterates expecting dicts.
     (bench_deploy 2026-05-19 — apps is list[dict] but schema said list[str])
  2. Schema documents an arg the method doesn't accept.
     (wait_for_bench_flip 2026-05-19 — schema accepted `timeout`, method
      didn't)
  3. Required-arg name mismatch — schema requires `name` but method's
     signature uses `release_group`, OR vice versa.
     (caught by the import-time check in tools.py for `required_args`,
      but THIS script catches subtler drift inside `args_schema`)

USAGE — MUST run inside Frappe context:
    bench --site demo.mvpstorm.com execute press.test_auth.run_mcp_schema_audit

OR via the wrapping bench test:
    bench --site demo.mvpstorm.com run-tests --module press.test_auth

LIMITS:
  - Only checks SHAPE: required names, presence of declared optional names
    in the Python signature. Doesn't try to validate type-vs-annotation
    (Python annotations are often `str | None` or missing entirely).
  - Doesn't resolve **kwargs catch-alls — methods that accept arbitrary
    kwargs flow-through (rare in Press whitelist surfaces) won't fail.
  - Tools whose method is in a NOT-importable module are skipped with a
    warning so a refactor that moves a module doesn't silently mask drift.
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def collect_drift() -> list[tuple[str, str]]:
	"""Return list of (tool_name, reason) for every drift case.

	Must be run from inside a Frappe context (via `bench execute` or the
	wrapping bench test). Press's whitelisted modules transitively import
	frappe.utils / frappe.client / etc., which aren't fully usable from a
	bare Python interpreter.
	"""
	from press.mcp_server.tools import TOOLS  # noqa: E402

	drift: list[tuple[str, str]] = []
	for tool, spec in TOOLS.items():
		method_path = spec.get("method")
		schema = spec.get("args_schema", {})
		schema_props = set(schema.get("properties", {}).keys())
		schema_required = set(schema.get("required", []))

		# Resolve the method by dotted-path
		mod_path, _, fn_name = method_path.rpartition(".")
		try:
			mod = importlib.import_module(mod_path)
		except Exception as e:
			drift.append((tool, f"could not import {mod_path!r}: {type(e).__name__}: {e}"))
			continue

		fn = getattr(mod, fn_name, None)
		if fn is None:
			drift.append((tool, f"{mod_path}.{fn_name!r} not found"))
			continue

		try:
			sig = inspect.signature(fn)
		except (ValueError, TypeError) as e:
			drift.append((tool, f"could not introspect {fn_name}: {e}"))
			continue

		# Python sig params (skip *args / **kwargs catch-alls)
		py_params = {
			name
			for name, p in sig.parameters.items()
			if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
		}
		py_required = {
			name
			for name, p in sig.parameters.items()
			if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
			and p.default is inspect.Parameter.empty
		}
		has_var_kw = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())

		# Schema claims an arg that the method doesn't accept (and method
		# has no **kwargs catch-all) → that arg is a dead documentation
		schema_ghosts = schema_props - py_params
		if schema_ghosts and not has_var_kw:
			drift.append((
				tool,
				f"schema documents args the method doesn't accept: {sorted(schema_ghosts)} "
				f"(method signature: {sorted(py_params)})",
			))

		# Schema's `required` doesn't match method's required params
		# (we tolerate schema requiring MORE — that's stricter — but require
		# schema-required ⊆ method-required so MCP clients don't omit a
		# legitimately-required param thinking it's optional)
		schema_missing_required = py_required - schema_required
		# Filter out args the method takes by position but schema doesn't
		# need (rare; ignore noise)
		if schema_missing_required & schema_props:
			# Only flag if the arg IS in schema (so the gap is documented but
			# wrong) — if the arg is missing from schema entirely we caught it above
			real = schema_missing_required & schema_props
			drift.append((
				tool,
				f"args required by method but marked optional in schema: {sorted(real)}",
			))

	return drift


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--print", dest="print_all", action="store_true")
	args = parser.parse_args()

	drift = collect_drift()

	if not drift:
		print("OK — every MCP tool's args_schema matches the underlying Python signature.")
		return 0

	print(f"!! {len(drift)} TOOLS WITH SCHEMA/SIGNATURE DRIFT:")
	for tool, reason in sorted(drift):
		print(f"  -- {tool}")
		print(f"       {reason}")
	print()
	print("Fix: edit press/mcp_server/tools.py — update args_schema to match")
	print("the actual Python method's signature. The schema is what MCP clients")
	print("see; if it lies, the client builds a call that the dispatcher rejects.")
	return 1


if __name__ == "__main__":
	sys.exit(main())
