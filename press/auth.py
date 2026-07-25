# Copyright (c) 2022, Frappe and contributors
# For license information, please see license.txt

import json
import os
import traceback

import frappe

PRESS_AUTH_KEY = "press-auth-logs"
PRESS_AUTH_MAX_ENTRIES = 1000000


ALLOWED_PATHS = [
	"/api/method/create-site-migration",
	"/api/method/create-version-upgrade",
	"/api/method/migrate-to-private-bench",
	"/api/method/find-my-sites",
	"/api/method/frappe.core.doctype.communication.email.mark_email_as_seen",
	"/api/method/frappe.realtime.get_user_info",
	"/api/method/frappe.realtime.can_subscribe_doc",
	"/api/method/frappe.realtime.can_subscribe_doctype",
	"/api/method/frappe.realtime.has_permission",
	"/api/method/frappe.www.login.login_via_frappe",
	"/api/method/frappe.integrations.oauth2.authorize",
	"/api/method/frappe.integrations.oauth2.approve",
	"/api/method/frappe.integrations.oauth2.get_token",
	"/api/method/frappe.integrations.oauth2.openid_profile",
	"/api/method/frappe.integrations.oauth2_logins.login_via_frappe",
	"/api/method/frappe.website.doctype.web_page_view.web_page_view.make_view_log",
	"/api/method/frappe.desk.form.utils.add_comment",
	"/api/method/get-user-sites-list-for-new-ticket",
	"/api/method/ping",
	"/api/method/login",
	"/api/method/logout",
	"/api/method/press.press.doctype.razorpay_webhook_log.razorpay_webhook_log.razorpay_webhook_handler",
	"/api/method/press.press.doctype.razorpay_webhook_log.razorpay_webhook_log.razorpay_authorized_payment_handler",
	"/api/method/press.press.doctype.stripe_webhook_log.stripe_webhook_log.stripe_webhook_handler",
	"/api/method/press.press.doctype.drip_email.drip_email.unsubscribe",
	"/api/method/upload_file",
	"/api/method/frappe.search.web_search",
	"/api/method/frappe.email.queue.unsubscribe",
	"/api/method/press.utils.telemetry.capture_read_event",
	"/api/method/validate_plan_change",
	"/api/method/marketplace-apps",
	"/api/method/press.www.dashboard.get_context_for_dev",
	"/api/method/frappe.website.doctype.web_form.web_form.accept",
	"/api/method/frappe.core.doctype.user.user.test_password_strength",
	"/api/method/frappe.core.doctype.user.user.update_password",
	"/api/method/get_central_migration_data",
	# Sanad AI control center: client sites self-provision AI seats here, authed
	# by a per-site service token (not a Press login). Scoped to this one path.
	"/api/method/sanad_ai_control_center.api.provision_for_site",
	# Sanad AI control center: client sites push their daily usage rollups here,
	# authed by the same per-site service token. Scoped to this one path.
	"/api/method/sanad_ai_control_center.usage_ingest.ingest_usage",
	# Sanad AI control center: client sites push a governance-exposure snapshot here,
	# authed by the same per-site service token. Scoped to this one path.
	"/api/method/sanad_ai_control_center.governance_ingest.ingest_governance_snapshot",
	# Tessera License Manager: client sites validate their license here, authed
	# by the license key (not a Press login). Scoped to this one path.
	"/api/method/tessera_server.api.validate",
]

ALLOWED_WILDCARD_PATHS = [
	"/api/method/press.api.",
	"/api/method/press.saas.",
	"/api/method/wiki.",
	"/api/method/frappe.integrations.oauth2_logins.",
	"/api/method/press.www.marketplace.index.",
	"/api/method/press.press.doctype.bench.bench_dev_overview.",
	"/api/method/press.press.doctype.bench.bench_app_management.",
	"/api/method/press.press.doctype.bench.health_analysis.",
	# Bench Code Health — quality scan API. Called from BenchCodeHealth.vue,
	# CodeHealth.vue, HealthAdvanced.vue (3 frontend mounts: Site Dev tab
	# Health panel + /dashboard/code-health full page). 10+ whitelisted
	# methods (scan_bench, get_summary, get_files, get_file_detail, etc.).
	# Audit 2026-05-18: caught during bench_dev_watch fix follow-up
	# (same logout-on-poll symptom would fire whenever a non-System user
	# expanded the Health panel or visited /dashboard/code-health).
	"/api/method/press.press.doctype.bench.bench_code_health.",
	# Bench Dev Watch — get_watch_status polls every ~10s from the
	# BenchWatchStatus panel on /groups/<bench>/actions. Without this
	# entry, every poll returns 401 for non-System users; the Vue
	# dashboard maps 401 → "session expired" and force-logs them out.
	# Symptom users report: "clicking Launch Code Server logs me out"
	# (the click is incidental — the next Watch poll is what kills the
	# session). Reproduced 2026-05-18 via press.auth.json.log: 221 Guest
	# transitions on bench_dev_watch.* in 2k log lines. Same fix pattern
	# as the 2026-05-10 deploy_candidate_build / site_clone allowlist add.
	"/api/method/press.press.doctype.bench.bench_dev_watch.",
	# Deploy Candidate Build endpoints called directly by the dashboard
	# (DeployCandidate.vue: get_build_estimate, get_failure_details,
	# redeploy, fail_and_redeploy, stop_and_fail). Without this allowlist
	# entry, NON-System users get 401 from the auth_hook, which the Vue
	# dashboard interprets as 'session expired' and force-logs-out.
	# Reproduced 2026-05-10: Marco clicked Update Bench → Deploy → got
	# logged out because the deploy succeeded (200) but the followup
	# get_build_estimate call returned 401.
	"/api/method/press.press.doctype.deploy_candidate_build.",
	# Site Clone (called from SiteActionCell.vue: clone_site)
	"/api/method/press.press.doctype.site.site_clone.",
	# Release Group Clone (called from CloneBenchPrompt.vue: clone_release_group,
	# clone_release_group_only). Wired up in commit 63c5a0d5fc as the "Create a
	# new bench" pivot in the Clone Site dialog. Without this entry, non-System
	# team users get "Access not allowed for this URL" the moment they click
	# Clone + Deploy or Clone RG only. Reported 2026-05-19 by ahmedmowafy74@gmail.com
	# (Marko's team) — first new team member to exercise the flow.
	"/api/method/press.press.doctype.release_group.release_group_clone.",
	# Bench VSCode launcher (called from VSCodeLaunchDialog.vue:
	# get_vscode_remote_url). Method lives at bench.bench_vscode, not
	# bench.bench_dev_overview as a stale Vue caller assumed. Once the Vue
	# caller is fixed to use the right path (commit fixing this allowlist),
	# the request still needs to clear auth_hook — hence this entry.
	"/api/method/press.press.doctype.bench.bench_vscode.",
	# AI governance API (called from AiPolicyGate.vue: acknowledge_policy,
	# AiTeamRules.vue: update_team_ai_rules). Same 401-logout pattern would
	# fire for any non-System user who accepted the AI policy or edited
	# per-team AI rules. Caught by the dashboard-allowlist audit script
	# (scripts/audit_dashboard_allowlist.py) on 2026-05-19 — these two callers
	# had been live for weeks without anyone non-System hitting them.
	"/api/method/press.press.ai.api.",
	# Partner payment payout (called from PartnerNewPayout.vue)
	"/api/method/press.press.doctype.partner_payment_payout.",
	# MCP server endpoints — token holders authenticate via custom opaque
	# token scheme inside server.handle, NOT via Frappe's standard
	# key:secret. The auth_hook must let the request through so our token
	# verifier can run. Auth-side enforcement lives in press/mcp_server/auth.py
	# (verify_token + _resolve_for_builtin) which fail-closed on bad tokens.
	"/api/method/press.mcp_server.",
]

DENIED_PATHS = [
	# Added from frappe/wwww/..
	"/printview",
	"/printpreview",
]


DENIED_WILDCARD_PATHS = [
	"/api/",
]


def hook():  # noqa: C901
	if frappe.form_dict.cmd:
		path = f"/api/method/{frappe.form_dict.cmd}"
	else:
		path = frappe.request.path

	user_type = frappe.get_cached_value("User", frappe.session.user, "user_type")

	# Allow unchecked access to System Users
	if user_type == "System User":
		return

	if path in DENIED_PATHS:
		log(path, user_type)
		frappe.throw("Access not allowed for this URL", frappe.AuthenticationError)

	for denied in DENIED_WILDCARD_PATHS:
		if path.startswith(denied):
			for allowed in ALLOWED_WILDCARD_PATHS:
				if path.startswith(allowed):
					return
			if path in ALLOWED_PATHS:
				return

			log(path, user_type)
			frappe.throw("Access not allowed for this URL", frappe.AuthenticationError)

	return


def log(path, user_type):
	data = {
		"ip": frappe.local.request_ip,
		"timestamp": frappe.utils.now(),
		"user_type": user_type,
		"path": path,
		"user": frappe.session.user,
		"referer": frappe.request.headers.get("Referer", ""),
	}

	if frappe.cache().llen(PRESS_AUTH_KEY) > PRESS_AUTH_MAX_ENTRIES:
		frappe.cache().ltrim(PRESS_AUTH_KEY, 1, -1)
	serialized = json.dumps(data, sort_keys=True, default=str)
	frappe.cache().rpush(PRESS_AUTH_KEY, serialized)


def flush():
	log_file = os.path.join(frappe.utils.get_bench_path(), "logs", "press.auth.json.log")
	try:
		# Fetch all entries without removing from cache
		logs = frappe.cache().lrange(PRESS_AUTH_KEY, 0, -1)
		if logs:
			logs = list(map(frappe.safe_decode, logs))
			with open(log_file, "a", os.O_NONBLOCK) as f:
				f.write("\n".join(logs))
				f.write("\n")
			# Remove fetched entries from cache
			frappe.cache().ltrim(PRESS_AUTH_KEY, len(logs) - 1, -1)
	except Exception:
		traceback.print_exc()
