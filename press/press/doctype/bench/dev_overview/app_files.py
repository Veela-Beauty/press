# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Read-only access to the source files of an app installed on a bench: list a folder and read one file
(moved from bench_dev_overview.py in 0.7.56)."""

from typing import Any

import frappe

from press.utils import ensure_team_access


# 1 MB cap on app file reads. App source files are mostly <100 KB; the cap
# stops accidental reads of huge generated/vendored files (e.g. compiled JS
# bundles, locale .po files) that would blow past Frappe's response budget.
_APP_FILE_MAX_BYTES = 1 * 1024 * 1024


# Path-traversal guard: reject any segment that resolves outside apps/<app>/.
_APP_FILE_BANNED = ("..", "")


def _validate_app_path(app: str, relative_path: str) -> str:
	"""Sanitize + canonicalize the requested file path.

	Returns the absolute path inside the container (under
	/home/frappe/frappe-bench/apps/<app>/) ready to pass to `cat`.
	Raises frappe.ValidationError on traversal attempts or empty input.
	"""
	if not app or not isinstance(app, str) or "/" in app or app in _APP_FILE_BANNED:
		raise frappe.ValidationError(f"app name {app!r} is invalid")
	if not relative_path or not isinstance(relative_path, str):
		raise frappe.ValidationError("relative_path must be a non-empty string")
	# Reject ../ traversal and absolute paths (re-rooting via leading /)
	if relative_path.startswith("/"):
		raise frappe.ValidationError("relative_path must not be absolute")
	for seg in relative_path.split("/"):
		if seg in _APP_FILE_BANNED or seg.startswith(".."):
			raise frappe.ValidationError(
				f"relative_path segment {seg!r} is not allowed"
			)
	# Container-side path. The bench's docker_execute pwd is already
	# /home/frappe/frappe-bench, but we use the absolute path for clarity
	# and to avoid the agent's subdir kwarg.
	return f"/home/frappe/frappe-bench/apps/{app}/{relative_path}"


@frappe.whitelist()
def bench_read_app_file(
	bench_name: str,
	app: str,
	relative_path: str,
) -> dict[str, Any]:
	"""Read a source file from an app installed in this bench.

	Args:
		bench_name: Bench docname (e.g. "bench-0015-000012-press-f1")
		app: app name as installed in apps/ (e.g. "erpnext", "frappe", "press")
		relative_path: path under apps/<app>/ (e.g.
			"erpnext/accounts/report/general_ledger/general_ledger.py")

	Returns:
		{path, content, encoding, size_bytes} on success, or
		{error, path} on missing file / oversize / read failure.

	Read-only by design — no write counterpart. Use site_file_write for
	user-uploaded content; source files should not be edited via MCP.
	"""
	ensure_team_access(bench_name=bench_name)
	abs_path = _validate_app_path(app, relative_path)
	bench = frappe.get_doc("Bench", bench_name)
	# Wrap in `bash -lc '...'` for the same reason as run_sql_on_site:
	# the host shell would otherwise interpret `<` and `|` as its own
	# redirects/pipes. See run_sql_on_site docstring for full rationale.
	size_cmd = f"bash -lc 'wc -c < {abs_path} 2>/dev/null || echo MISSING'"
	try:
		size_raw = bench.docker_execute(size_cmd, create_log=False)
	except Exception as e:
		return {"error": str(e), "path": abs_path}
	size_text = (size_raw.get("output") or "").strip()
	if not size_text or size_text == "MISSING":
		return {"error": "not_found", "path": abs_path}
	try:
		size_bytes = int(size_text)
	except ValueError:
		return {"error": "could_not_stat", "path": abs_path, "raw": size_text}
	if size_bytes > _APP_FILE_MAX_BYTES:
		return {
			"error": "too_large",
			"path": abs_path,
			"size_bytes": size_bytes,
			"limit_bytes": _APP_FILE_MAX_BYTES,
		}
	# base64-pipe to dodge any binary content / control chars that would
	# corrupt the stdout payload going back through Press Agent.
	read_cmd = f"bash -lc 'base64 -w0 {abs_path}'"
	try:
		raw = bench.docker_execute(read_cmd, create_log=False)
	except Exception as e:
		return {"error": str(e), "path": abs_path}
	import base64 as _b64
	encoded = (raw.get("output") or "").strip()
	try:
		data = _b64.b64decode(encoded)
	except Exception:
		return {"error": "decode_failed", "path": abs_path}
	# Try utf-8; fall back to base64 for binaries (rare in apps/).
	try:
		content = data.decode("utf-8")
		return {
			"path": abs_path,
			"content": content,
			"encoding": "utf-8",
			"size_bytes": size_bytes,
		}
	except UnicodeDecodeError:
		return {
			"path": abs_path,
			"content_b64": encoded,
			"encoding": "base64",
			"size_bytes": size_bytes,
		}


@frappe.whitelist()
def bench_list_app_files(
	bench_name: str,
	app: str,
	relative_path: str = "",
	pattern: str | None = None,
) -> dict[str, Any]:
	"""List files under apps/<app>/<relative_path>/ inside the bench container.

	Args:
		bench_name: Bench docname
		app: app name
		relative_path: subdir under apps/<app>/ ("" = app root)
		pattern: optional glob (e.g. "*.py", "**/general_ledger*"). Find -name.

	Returns: {dir, files: [...], count} (capped at 200 entries).
	"""
	ensure_team_access(bench_name=bench_name)
	# Reuse path validator with a sentinel name when relative_path is empty
	probe_path = relative_path if relative_path else "."
	# Validation: empty string is fine ("." resolves to app root); other
	# checks (../, /) still apply.
	if relative_path:
		_validate_app_path(app, relative_path)
	if "/" in app or not app or app in _APP_FILE_BANNED:
		raise frappe.ValidationError(f"app name {app!r} is invalid")
	dir_abs = f"/home/frappe/frappe-bench/apps/{app}"
	if relative_path:
		dir_abs = f"{dir_abs}/{relative_path}"
	bench = frappe.get_doc("Bench", bench_name)
	# find with -path stays inside the dir, -maxdepth caps recursion
	if pattern:
		# Sanitize pattern: only allow alphanumeric + glob chars
		import re as _re
		if not _re.match(r"^[A-Za-z0-9_./*?\[\]-]+$", pattern):
			raise frappe.ValidationError(
				f"pattern {pattern!r} contains disallowed characters"
			)
		# Wrap in bash -lc so the | head pipe runs in the container
		find_cmd = (
			f"bash -lc \"find {dir_abs} -name '{pattern}' -type f "
			f"2>/dev/null | head -200\""
		)
	else:
		find_cmd = (
			f"bash -lc 'find {dir_abs} -maxdepth 2 -type f "
			f"2>/dev/null | head -200'"
		)
	try:
		raw = bench.docker_execute(find_cmd, create_log=False)
	except Exception as e:
		return {"error": str(e), "dir": dir_abs}
	output = (raw.get("output") or "").strip()
	if not output:
		return {"dir": dir_abs, "files": [], "count": 0}
	files = [line.strip() for line in output.split("\n") if line.strip()]
	return {"dir": dir_abs, "files": files, "count": len(files)}
