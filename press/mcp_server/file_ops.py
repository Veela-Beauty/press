# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Constrained file + site_config operations for MCP agents.

These exist so agents don't have to use the unrestricted site_run_python tool
for routine config edits and file reads. All operations are path-validated
to stay within the site's public/private folders.
"""
from __future__ import annotations

import json
import os
from typing import Any

import frappe

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB cap on file_read/file_write

_SENSITIVE_PREFIXES = ("db_password", "encryption_key")


@frappe.whitelist()
def site_config_get(site_name: str, key: str | None = None) -> dict[str, Any]:
	"""Read site_config.json. If key is given, return {key: value}; else return all keys.

	Sensitive keys (db_password*, encryption_key*) are never returned.
	"""
	from press.press.doctype.bench.bench_dev_overview import run_python_on_site

	if key:
		_validate_config_key(key)
		code = (
			"import frappe, json\n"
			f"v = frappe.conf.get({key!r})\n"
			f"print(json.dumps({{'key': {key!r}, 'value': v}}))"
		)
	else:
		code = (
			"import frappe, json\n"
			"safe = {k: v for k, v in dict(frappe.conf).items() "
			"if not any(k.startswith(p) for p in ('db_password', 'encryption_key'))}\n"
			"print(json.dumps(safe))"
		)
	raw = run_python_on_site(site_name=site_name, code=code)
	return _parse_python_output(raw)


@frappe.whitelist()
def site_config_set(site_name: str, key: str, value: Any) -> dict[str, str]:
	"""Set a single site_config.json key.

	Sensitive keys (db_password*, encryption_key*) cannot be modified via this tool.
	"""
	_validate_config_key(key)
	value_json = json.dumps(value)
	code = (
		"import frappe\n"
		"from frappe.installer import update_site_config\n"
		f"update_site_config({key!r}, {value_json})\n"
		"print('OK')"
	)
	from press.press.doctype.bench.bench_dev_overview import run_python_on_site

	raw = run_python_on_site(site_name=site_name, code=code)
	return {"status": "set", "key": key, "result": str(raw).strip()}


@frappe.whitelist()
def site_file_read(site_name: str, relative_path: str) -> dict[str, Any]:
	"""Read a file from the site's public/files/ or private/files/ folder.

	Returns text content (utf-8) or base64 for binary files.
	"""
	safe_path = _resolve_site_path(site_name, relative_path)
	from press.press.doctype.bench.bench_dev_overview import run_python_on_site

	code = (
		"import os, json, base64\n"
		f"path = {safe_path!r}\n"
		"if not os.path.exists(path):\n"
		"    print(json.dumps({'error': 'not_found', 'path': path}))\n"
		f"elif os.path.getsize(path) > {MAX_FILE_BYTES}:\n"
		"    print(json.dumps({'error': 'too_large', 'size': os.path.getsize(path)}))\n"
		"else:\n"
		"    with open(path, 'rb') as f:\n"
		"        data = f.read()\n"
		"    try:\n"
		"        text = data.decode('utf-8')\n"
		"        print(json.dumps({'path': path, 'content': text, 'encoding': 'utf-8'}))\n"
		"    except UnicodeDecodeError:\n"
		"        print(json.dumps({'path': path, 'content_b64': base64.b64encode(data).decode(), 'encoding': 'base64'}))\n"
	)
	raw = run_python_on_site(site_name=site_name, code=code)
	return _parse_python_output(raw)


@frappe.whitelist()
def site_file_write(
	site_name: str,
	relative_path: str,
	content: str,
	encoding: str = "utf-8",
) -> dict[str, Any]:
	"""Write content to the site's public/files/ or private/files/ folder.

	encoding must be 'utf-8' or 'base64'. Content capped at MAX_FILE_BYTES.
	"""
	safe_path = _resolve_site_path(site_name, relative_path)
	if encoding not in ("utf-8", "base64"):
		raise frappe.ValidationError("encoding must be 'utf-8' or 'base64'")
	# base64 is ~33% bigger than raw; use 2x as a rough upper cap before decoding
	if len(content) > MAX_FILE_BYTES * 2:
		raise frappe.ValidationError(f"content too large (>{MAX_FILE_BYTES} bytes)")
	from press.press.doctype.bench.bench_dev_overview import run_python_on_site

	code = (
		"import os, json, base64\n"
		f"path = {safe_path!r}\n"
		f"encoding = {encoding!r}\n"
		f"raw = {content!r}\n"
		"data = base64.b64decode(raw) if encoding == 'base64' else raw.encode('utf-8')\n"
		f"if len(data) > {MAX_FILE_BYTES}:\n"
		"    print(json.dumps({'error': 'too_large', 'size': len(data)}))\n"
		"else:\n"
		"    os.makedirs(os.path.dirname(path), exist_ok=True)\n"
		"    with open(path, 'wb') as f:\n"
		"        f.write(data)\n"
		"    print(json.dumps({'path': path, 'bytes_written': len(data)}))\n"
	)
	raw = run_python_on_site(site_name=site_name, code=code)
	return _parse_python_output(raw)


def _validate_config_key(key: str) -> None:
	"""Reject empty keys and sensitive key names."""
	if not key or not isinstance(key, str):
		raise frappe.ValidationError("key must be a non-empty string")
	lowered = key.lower()
	for prefix in _SENSITIVE_PREFIXES:
		if lowered.startswith(prefix):
			raise frappe.PermissionError(
				f"site_config key {key!r} is sensitive; cannot be accessed via MCP"
			)


def _resolve_site_path(site_name: str, relative_path: str) -> str:
	"""Canonicalize and validate that the path stays under public/files/ or private/files/."""
	if not relative_path or ".." in relative_path.split("/"):
		raise frappe.ValidationError("relative_path must not contain `..` segments")
	allowed_prefixes = ("public/files/", "private/files/")
	if not any(relative_path.startswith(p) for p in allowed_prefixes):
		raise frappe.ValidationError(
			f"relative_path must start with one of {allowed_prefixes}"
		)
	full = f"sites/{site_name}/{relative_path}"
	normalized = os.path.normpath(full)
	if not normalized.startswith(f"sites/{site_name}/"):
		raise frappe.ValidationError("path canonicalization escaped site root")
	return normalized


def _parse_python_output(raw: Any) -> dict[str, Any]:
	"""Parse JSON from run_python_on_site stdout. Falls back to wrapping as raw string."""
	if raw is None:
		return {"raw": None}
	text = str(raw).strip()
	if not text:
		return {"raw": ""}
	for line in reversed(text.splitlines()):
		line = line.strip()
		if line.startswith("{") and line.endswith("}"):
			try:
				return json.loads(line)
			except (ValueError, TypeError):
				continue
	return {"raw": text}
