"""
Dev Tools API — dev overview, git status, console, logs, process management.
Kept in a separate file because bench.py is already >700 lines.
"""
import re
from typing import Any

import frappe
from frappe import _

from press.press.doctype.bench.bench_app_ownership import is_app_owned_by_current_team
from press.utils import ensure_team_access
from press.press.doctype.bench.dev_overview.site_container import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	_LOG_FILES,
	_LOG_PATTERN,
	_SQL_COMMENT_RE,
	_WRITE_KEYWORDS,
	_get_site_bench,
	get_db_processlist,
	get_recent_logs,
	kill_db_process,
	run_python_on_site,
	run_sql_on_site,
)
from press.press.doctype.bench.dev_overview.app_files import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	_APP_FILE_BANNED,
	_APP_FILE_MAX_BYTES,
	_validate_app_path,
	bench_list_app_files,
	bench_read_app_file,
)
from press.press.doctype.bench.dev_overview.code_server import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	_can_use_code_server,
	_ensure_code_server_role_access,
	get_code_server_status,
	restart_code_server,
	rotate_code_server_password,
	set_code_server_password_expiry_days,
	setup_code_server,
)
from press.press.doctype.bench.dev_overview.ssh import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	SSH_RULE_MUST_FOLLOW,
	bench_ssh_connect,
	bench_ssh_instructions,
	bench_ssh_register_key,
	generate_ssh_certificate,
	get_ssh_certificate,
)
from press.press.doctype.bench.dev_overview.panel import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	get_app_git_status,
	get_bench_app_names,
	get_bench_dev_info,
	get_dev_overview_benches,
	get_dev_panel_data,
	push_app_to_github,
	restart_bench_for_site,
)


# ── App Source Read API ──────────────────────────────────────────────────────


# ── SSH Instructions API ─────────────────────────────────────────────────────
