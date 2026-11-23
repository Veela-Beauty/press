# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Deploy / release / site-update workflow tools for MCP agents: a STUB since 0.7.54.

The tools live in press/mcp_server/deploy_ops/ (candidates, waits, site_tools, agent_tools,
server_memory, app_sources). This module re-exports them, so the catalog's method paths
(press.mcp_server.deploy_flow.<tool>) and every `from press.mcp_server.deploy_flow import ...` keep
working. Add new tools to a deploy_ops module, not here.

All resource scoping is enforced by the MCP server at dispatch time (server._extract_target).
"""

from __future__ import annotations

import frappe  # noqa: F401  tests patch press.mcp_server.deploy_flow.frappe.db.* through this name

from press.mcp_server.deploy_ops.candidates import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	_BENCH_PROVISION_JOB_TYPES,
	_derive_provision_stage,
	bench_provision_progress,
	deploy_candidate_schedule_build,
	deploy_candidate_status,
	release_group_create_deploy_candidate,
)
from press.mcp_server.deploy_ops.waits import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	HTTP_WAIT_CAP_SECONDS,
	bench_deploy_and_wait,
	site_update_and_wait,
	site_update_with_hint,
	wait_for_bench_flip,
)
from press.mcp_server.deploy_ops.site_tools import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	list_sites_on_release_group,
	mint_dashboard_login_url,
	site_schedule_update,
	site_status,
)
from press.mcp_server.deploy_ops.agent_tools import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	agent_health,
	agent_job_list,
	agent_job_progress,
	agent_job_traceback,
)
from press.mcp_server.deploy_ops.server_memory import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	_HOST_MEMORY_PRESSURE_CACHE_TTL,
	host_memory_pressure,
)
from press.mcp_server.deploy_ops.app_sources import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	_installation_for_owner,
	_repo_is_public,
	_resolve_app_source,
	app_release_approve,
	app_source_fetch_latest,
	bench_set_app_branch,
	list_pending_releases,
	register_existing_app,
)


# ---------------------------------------------------------------------------
# App lifecycle tools — fetch latest, list pending, register existing
# ---------------------------------------------------------------------------
