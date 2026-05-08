# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Shared parsing helpers for the MCP server module.

Single source of truth for "JSON string | list | None → list[str]" conversion.
Avoids 5 copies of the same logic across auth.py, server.py, dashboard.py, admin.py.
"""
from __future__ import annotations

import json


def safe_parse_list(value) -> list[str]:
	"""Coerce JSON string, list, or None into a list of strings."""
	if value is None:
		return []
	if isinstance(value, list):
		return [str(s) for s in value]
	if isinstance(value, str):
		try:
			parsed = json.loads(value)
			if isinstance(parsed, list):
				return [str(s) for s in parsed]
		except (ValueError, TypeError):
			pass
	return []


def safe_parse_dict(value) -> dict:
	"""Coerce JSON string, dict, or None into a dict."""
	if value is None:
		return {}
	if isinstance(value, dict):
		return value
	if isinstance(value, str):
		try:
			parsed = json.loads(value)
			if isinstance(parsed, dict):
				return parsed
		except (ValueError, TypeError):
			pass
	return {}
