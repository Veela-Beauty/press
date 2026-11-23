# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""The split of 0.7.54 kept every path: each catalog tool resolves to a whitelisted function, no tool is in
two catalog parts, and deploy_flow.py still exports every deploy_ops tool. Mock-only: reads code, writes
nothing."""

from __future__ import annotations

import ast
import importlib
import pathlib

import frappe
from frappe.tests.utils import FrappeTestCase

from press.mcp_server import deploy_flow, tools


class TestToolPaths(FrappeTestCase):
	def test_every_tool_method_resolves_and_the_deploy_flow_ones_stay_whitelisted(self):
		"""The MCP dispatcher calls a tool's method in-process, so it need not be whitelisted
		(bench_ops.* are not); the deploy_flow tools were, and the split must keep them so."""
		broken = {}
		for name, spec in tools.TOOLS.items():
			try:
				fn = frappe.get_attr(spec["method"])
			except Exception as e:  # report every broken path, not only the first
				broken[name] = f"{spec['method']}: {e!r}"
				continue
			if not callable(fn):
				broken[name] = f"{spec['method']}: not callable"
			elif spec["method"].startswith("press.mcp_server.deploy_flow.") and fn not in frappe.whitelisted:
				broken[name] = f"{spec['method']}: no longer whitelisted"
		self.assertEqual(broken, {})

	def test_each_tool_is_in_one_catalog_part(self):
		parts = tools._PARTS
		self.assertEqual(len(tools.TOOLS), sum(len(p) for p in parts))
		self.assertTrue(parts and all(parts))

	def test_deploy_flow_still_exports_every_deploy_ops_name(self):
		"""Functions and constants alike: a caller of deploy_flow.X must get the object deploy_ops defines."""
		ops = pathlib.Path(deploy_flow.__file__).with_name("deploy_ops")
		missing = []
		for path in sorted(ops.glob("*.py")):
			if path.name.startswith("_"):
				continue
			module = importlib.import_module(f"press.mcp_server.deploy_ops.{path.stem}")
			for name in _defined_names(path):
				if getattr(deploy_flow, name, None) is not getattr(module, name):
					missing.append(f"{path.stem}.{name}")
		self.assertEqual(missing, [])


def _defined_names(path) -> list[str]:
	"""The functions, classes and constants a module defines itself (not the ones it imports)."""
	names = []
	for node in ast.parse(path.read_text()).body:
		if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
			names.append(node.name)
		elif isinstance(node, ast.Assign):
			names += [t.id for t in node.targets if isinstance(t, ast.Name)]
		elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
			names.append(node.target.id)
	return names
