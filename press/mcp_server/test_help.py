# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Unit tests for press.mcp_server.help — discoverability tool."""
from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from press.mcp_server.help import (
	BUILTIN_TOOLS,
	CATEGORIES,
	DISCOVERABILITY_HINT,
	TOOL_CATEGORY,
	get_tool_help,
)
from press.mcp_server.server import handle as mcp_handle
from press.mcp_server.tools import TOOLS


class TestHelp(FrappeTestCase):
	def test_index_no_scope_returns_all_tools(self):
		# Empty scope = "all" by convention
		result = get_tool_help(caller_scope=[])
		self.assertIn("categories", result)
		# At least the 5 known categories should appear with tools
		self.assertGreaterEqual(len(result["categories"]), 4)
		self.assertEqual(result["in_scope_count"], result["total_in_index"])

	def test_index_with_narrow_scope_filters_to_scoped_only(self):
		result = get_tool_help(
			caller_scope=["clone_bench", "site_status"],
			scope_only=True,
		)
		# Flatten all tool names
		names = [t["name"] for cat in result["categories"] for t in cat["tools"]]
		self.assertEqual(set(names), {"clone_bench", "site_status"})

	def test_index_scope_only_false_shows_all_marks_in_scope(self):
		result = get_tool_help(
			caller_scope=["clone_bench"],
			scope_only=False,
		)
		# Should include ALL tools, but in_scope flag distinguishes
		all_tools = [t for cat in result["categories"] for t in cat["tools"]]
		in_scope_names = [t["name"] for t in all_tools if t["in_scope"]]
		self.assertEqual(in_scope_names, ["clone_bench"])
		self.assertGreater(len(all_tools), 1)

	def test_single_tool_detail_returns_full_spec(self):
		result = get_tool_help(tool="clone_bench", caller_scope=[])
		self.assertEqual(result["tool"], "clone_bench")
		self.assertEqual(result["risk"], "medium")
		self.assertEqual(result["category"], "bench_rg")
		self.assertIn("release_group", result["required_args"])
		self.assertIn("example_call", result)
		self.assertEqual(result["example_call"]["tool"], "clone_bench")
		self.assertTrue(result["in_scope"])  # empty scope = all

	def test_single_tool_detail_unknown_tool_returns_error(self):
		result = get_tool_help(tool="not_a_tool", caller_scope=[])
		self.assertIn("error", result)
		self.assertIn("available", result)

	def test_category_filter(self):
		result = get_tool_help(category="dangerous", caller_scope=[])
		self.assertEqual(len(result["categories"]), 1)
		self.assertEqual(result["categories"][0]["id"], "dangerous")
		# All tools in the category should be high-risk
		for t in result["categories"][0]["tools"]:
			self.assertEqual(t["risk"], "high")

	def test_every_tool_has_a_category_mapping(self):
		# Drift detector — TOOLS in tools.py must all have a TOOL_CATEGORY entry.
		# Catches the case where someone adds a tool but forgets to update help.py.
		missing = [t for t in TOOLS if t not in TOOL_CATEGORY]
		self.assertEqual(missing, [], f"Tools missing category mapping: {missing}")

	def test_every_category_id_is_known(self):
		# Catches typos in TOOL_CATEGORY values.
		unknown = {cid for cid in TOOL_CATEGORY.values() if cid not in CATEGORIES}
		self.assertEqual(unknown, set(), f"Unknown category ids: {unknown}")

	def test_builtin_tools_set_includes_help_and_list_tools(self):
		# Drift guard: if someone removes 'list_tools' alias, agents that
		# call it instead of 'help' silently break.
		self.assertEqual(BUILTIN_TOOLS, {"help", "list_tools"})

	def test_discoverability_hint_mentions_help(self):
		# The hint should always tell agents how to call help.
		self.assertIn("help", DISCOVERABILITY_HINT.lower())

	# ------------------------------------------------------------------
	# Server-handle integration: auth path for built-in tools (T2A)
	# Critical: wraps the discoverability layer in token verification so
	# anonymous callers can't enumerate the catalog. A bug here = info leak.
	# ------------------------------------------------------------------

	def test_handle_help_with_no_token_raises(self):
		result = mcp_handle(tool="help")
		self.assertFalse(result["ok"])
		self.assertEqual(result["error_type"], "PermissionError")
		self.assertIn("token", result["error"].lower())

	def test_handle_help_with_bogus_token_raises(self):
		result = mcp_handle(tool="help", token="not-a-real-token-xxxxxxxxx")
		self.assertFalse(result["ok"])
		self.assertEqual(result["error_type"], "PermissionError")

	def test_handle_list_tools_alias_routes_to_help(self):
		# 'list_tools' is the alias; should hit the same auth path.
		result = mcp_handle(tool="list_tools")
		self.assertFalse(result["ok"])
		self.assertEqual(result["error_type"], "PermissionError")
