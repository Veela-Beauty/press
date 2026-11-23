# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""MCP tool catalog — declarative mapping of tool name to whitelisted method.

Since 0.7.54 the entries live in press/mcp_server/tool_catalog/ (core, bench_code, sites_benches, deploy,
bench_control); this module merges them into TOOLS and keeps the lookups. Add a tool to the part for its area.

Each entry:
	method: dotted-path to the underlying whitelisted Python function
	description: shown in tool list
	required_args: list of arg names the tool requires
	args_schema: JSON Schema fragment describing every arg the tool accepts.
		The dispatcher uses `required_args` for validation; `args_schema` is
		published to MCP clients (and the dashboard test-call form) so they
		know the exact canonical name + type of each parameter without
		guessing from natural language descriptions.
	risk: 'low' | 'medium' | 'high' — gates the dialog UX + verify_token

WHEN ADDING / REMOVING / RENAMING A TOOL IN A PART, ALSO UPDATE:
	dashboard/src/components/mcp/_tool_catalog.js  (frontend mirror used by
	the Issue Token dialog to show categories, risk badges, and search).
The two files MUST stay in sync; otherwise the new tool will not appear in
the scope picker and existing tokens with that scope cannot be issued via UI.

Every `required_args` entry MUST appear as a property in `args_schema` —
enforced at import time by `_assert_schema_covers_required_args()` below.
"""
from __future__ import annotations

from press.mcp_server.tool_catalog._schema import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	_ARG_FRAGMENTS,
	_schema,
)
from press.mcp_server.tool_catalog.bench_code import BENCH_CODE_TOOLS
from press.mcp_server.tool_catalog.bench_control import BENCH_CONTROL_TOOLS
from press.mcp_server.tool_catalog.core import CORE_TOOLS
from press.mcp_server.tool_catalog.deploy import DEPLOY_TOOLS
from press.mcp_server.tool_catalog.sites_benches import SITES_BENCHES_TOOLS

# Tool name -> spec
TOOLS: dict[str, dict] = {
	**CORE_TOOLS,
	**BENCH_CODE_TOOLS,
	**SITES_BENCHES_TOOLS,
	**DEPLOY_TOOLS,
	**BENCH_CONTROL_TOOLS,
}

_PARTS = (CORE_TOOLS, BENCH_CODE_TOOLS, SITES_BENCHES_TOOLS, DEPLOY_TOOLS, BENCH_CONTROL_TOOLS)


def _assert_each_tool_in_one_part() -> None:
	"""Import-time check: a tool name in two parts would keep only the later spec, silently (0.7.54)."""
	seen: set[str] = set()
	for part in _PARTS:
		twice = seen & part.keys()
		if twice:
			raise RuntimeError(f"tools {sorted(twice)!r} are defined in two tool_catalog parts; keep one")
		seen |= part.keys()


_assert_each_tool_in_one_part()


def _assert_schema_covers_required_args() -> None:
	"""Import-time consistency check: every required_arg must appear in args_schema.

	Catches mismatches at server start instead of when a client first calls the
	tool. Without this check, a tool whose `required_args` list grew but whose
	`args_schema` didn't update would publish a misleading schema to clients.
	"""
	for tool_name, spec in TOOLS.items():
		required = spec.get("required_args", [])
		schema = spec.get("args_schema", {})
		props = schema.get("properties", {})
		missing = [a for a in required if a not in props]
		if missing:
			raise RuntimeError(
				f"tool {tool_name!r}: required_args {missing!r} are not declared "
				f"in args_schema.properties (keys: {sorted(props.keys())}). "
				f"Add them to args_schema or remove from required_args."
			)


_assert_schema_covers_required_args()


def get_tool_spec(tool_name: str) -> dict | None:
	return TOOLS.get(tool_name)


def list_tool_names() -> list[str]:
	return sorted(TOOLS.keys())


def get_tool_risk(tool_name: str) -> str:
	"""Return 'low', 'medium', or 'high'. Defaults to 'medium' for unclassified."""
	spec = TOOLS.get(tool_name)
	if not spec:
		return "high"  # unknown tool → fail-closed
	return spec.get("risk", "medium")


def list_risky_tools() -> list[str]:
	"""All tools classified as 'high' risk."""
	return sorted(name for name, spec in TOOLS.items() if spec.get("risk") == "high")
