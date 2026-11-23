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

# A site's secrets never leave the site: the code that reads site_config.json runs on the site and hides them there,
# so they reach neither this tool's answer nor the Agent Job output Press keeps. Hidden: the value of any key whose name
# holds password, secret, token or key, and the password inside a URL value (redis://:password@host). Before 0.7.45
# only db_password* and encryption_key* were held back, so app secrets (a seal key, a converter password, the redis
# passwords) came back in clear.
_HIDDEN = "(hidden)"


def _site_code(site: str, body: list[str]) -> str:
	"""The code sent to the site: body runs inside one function, with conf and clean(k, v) beside it. conf is the bench's
	common_site_config.json with the site's site_config.json over it, the files frappe.conf is built from (values set
	only at run time, such as environment overrides, are not in it). The code needs no Frappe, so it runs with the
	bench's plain Python (_run_on_site); 0.7.46 ran it in `bench console`, whose start took about 1.2 s of each call."""
	return (
		"def _press_config():\n"
		"\timport json, re\n"
		"\tconf = {}\n"
		f"\tfor path in ('sites/common_site_config.json', {f'sites/{site}/site_config.json'!r}):\n"
		"\t\twith open(path) as f:\n"
		"\t\t\tconf.update(json.load(f))\n"
		"\twords = ('password', 'secret', 'token', 'key')\n"
		"\turl_password = re.compile(r'^([a-z][a-z0-9+.-]*://[^:@/]*:)[^@/]+(@)', re.I)\n"
		"\tdef clean(k, v):\n"
		"\t\tif any(w in str(k).lower() for w in words):\n"
		f"\t\t\treturn {_HIDDEN!r}\n"
		"\t\tif isinstance(v, str):\n"
		f"\t\t\treturn url_password.sub(r'\\g<1>{_HIDDEN}\\g<2>', v)\n"
		"\t\treturn v\n" + "".join(f"\t{line}\n" for line in body) + "_press_config()\n"
	)


@frappe.whitelist()
def site_config_get(site_name: str, key: str | None = None) -> dict[str, Any]:
	"""Read site_config.json. If key is given, return {key: value}; else return all keys.

	db_password* and encryption_key* are never returned; any other secret (a key name holding password, secret, token
	or key, and the password inside a URL) comes back as "(hidden)", hidden on the site itself (_site_code).
	"""
	if key:
		_validate_config_key(key)
		body = [
			f"v = clean({key!r}, conf.get({key!r}))",
			f"print(json.dumps({{'key': {key!r}, 'value': v}}))",
		]
	else:
		body = [
			"safe = {k: clean(k, v) for k, v in conf.items() "
			"if not any(str(k).startswith(p) for p in ('db_password', 'encryption_key'))}",
			"print(json.dumps(safe))",
		]
	return _run_on_site(site_name, body)


def _run_on_site(site_name: str, body: list[str]) -> dict[str, Any]:
	"""Run _site_code(body) in the site's bench container with the bench's plain Python and parse what it prints.
	The guard is run_python_on_site's: team access first, then the site's bench."""
	import base64

	from press.press.doctype.bench.bench_dev_overview import _get_site_bench
	from press.utils import ensure_team_access

	ensure_team_access(site_name=site_name)
	site, bench = _get_site_bench(site_name)
	b64 = base64.b64encode(_site_code(site.name, body).encode()).decode()
	try:
		result = bench.docker_execute(f"bash -c 'echo {b64} | base64 -d | env/bin/python -'")
		output, returncode = result.get("output") or "", result.get("returncode")
	except Exception as e:
		return {"error": str(e)}
	if returncode:
		return {"error": "reading the site config failed", "output": output[-500:]}
	return _parse_python_output(output)


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
			raise frappe.PermissionError(f"site_config key {key!r} is sensitive; cannot be accessed via MCP")


def _resolve_site_path(site_name: str, relative_path: str) -> str:
	"""Canonicalize and validate that the path stays under public/files/ or private/files/."""
	if not relative_path or ".." in relative_path.split("/"):
		raise frappe.ValidationError("relative_path must not contain `..` segments")
	allowed_prefixes = ("public/files/", "private/files/")
	if not any(relative_path.startswith(p) for p in allowed_prefixes):
		raise frappe.ValidationError(f"relative_path must start with one of {allowed_prefixes}")
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
