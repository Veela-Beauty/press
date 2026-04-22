# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Bench-side credential fetch API.

Called by /usr/local/bin/bench-git-setup inside bench containers during SSH
session setup. Returns a short-lived GitHub access token for the SSH user.

Auth model (MVP):
  - Caller (bench container, via curl) sends
      X-Press-Internal-Token: <bench_internal_auth_secret>
    where the secret is a Press-Settings single value shared between press-ctrl
    and press-f1 (distributed via the ssh-proxy ForceCommand as an env var).
  - Caller sends:
      X-Press-User:  <email of the dev authenticated by the SSH cert>
      X-Press-Bench: <bench name, used for audit + team membership check>
  - Press validates:
      1. secret matches Press Settings
      2. X-Press-User is a real enabled User
      3. User is a team member of the Bench's team
      4. User has an active, non-revoked User GitHub Auth

On success, returns:
  {
    "success": true,
    "github.com": "<access_token>",
    "user_email": "<email>",
    "user_full_name": "<full name>",
    "expires_in_seconds": <int>
  }

On failure (user hasn't connected, revoked, etc.):
  {
    "success": false,
    "reason": "needs_connect" | "revoked" | "not_team_member" | "unknown",
    "authorize_url": "<press-url>/api/method/press.api.github_auth.start_connect"
  }
"""

from __future__ import annotations



import frappe
from frappe.rate_limiter import rate_limit

from press.press.doctype.git_credential_session_log.git_credential_session_log import (
	log_credential_request,
)
from press.press.doctype.user_github_auth.user_github_auth import get_for_user

SECRET_HEADER = "X-Press-Internal-Token"


def _require_internal_secret() -> None:
	from frappe.utils.password import get_decrypted_password
	try:
		expected = get_decrypted_password("Press Settings", "Press Settings", "bench_internal_auth_secret")
	except Exception:
		expected = None
	if not expected:
		frappe.throw("Internal auth secret not configured", frappe.AuthenticationError)
	provided = (frappe.get_request_header(SECRET_HEADER) or "").strip()
	if not provided:
		frappe.throw(f"Missing {SECRET_HEADER} header", frappe.AuthenticationError)
	# Constant-time compare
	import hmac

	if not hmac.compare_digest(provided, expected):
		frappe.throw("Invalid internal auth secret", frappe.AuthenticationError)


def _validate_team_membership(user_email: str, bench_name: str) -> None:
	# Bench -> Release Group -> team
	bench_team = frappe.db.get_value("Bench", bench_name, "team")
	if not bench_team:
		rg_name = frappe.db.get_value("Bench", bench_name, "group")
		if rg_name:
			bench_team = frappe.db.get_value("Release Group", rg_name, "team")
	if not bench_team:
		frappe.throw(f"Bench {bench_name} not found or has no team", frappe.PermissionError)

	# Owner is always a member
	team_owner = frappe.db.get_value("Team", bench_team, "user")
	if team_owner == user_email:
		return

	# Otherwise must be in team_members
	is_member = frappe.db.exists(
		"Team Member", {"parent": bench_team, "parenttype": "Team", "user": user_email}
	)
	if not is_member:
		frappe.throw(f"{user_email} is not a member of this bench's team", frappe.PermissionError)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=120, seconds=60)
def get_for_session():
	"""Return a fresh GitHub access token for the SSH-authenticated user.

	Input (headers):
	  X-Press-Internal-Token: <bench_internal_auth_secret>
	  X-Press-User:  <email>
	  X-Press-Bench: <bench name>
	"""
	_require_internal_secret()

	user_email = (frappe.get_request_header("X-Press-User") or "").strip().lower()
	bench_name = (frappe.get_request_header("X-Press-Bench") or "").strip()

	if not user_email or not bench_name:
		frappe.throw("Missing X-Press-User or X-Press-Bench header", frappe.ValidationError)

	# Validate user exists + is enabled
	user_doc = frappe.db.get_value(
		"User", user_email, ["name", "enabled", "full_name"], as_dict=True
	)
	if not user_doc or not user_doc.enabled:
		log_credential_request(user_email, bench_name, False, "user not found or disabled")
		frappe.throw(f"User {user_email} not found or disabled", frappe.PermissionError)

	_validate_team_membership(user_email, bench_name)

	auth = get_for_user(user_email)
	if not auth:
		log_credential_request(user_email, bench_name, False, "no GitHub connection")
		base_url = frappe.utils.get_url()
		return {
			"success": False,
			"reason": "needs_connect",
			"authorize_url": f"{base_url}/dashboard/settings/developer",
			"user_email": user_email,
			"user_full_name": user_doc.full_name or user_email,
		}

	if auth.is_revoked:
		log_credential_request(user_email, bench_name, False, "GitHub revoked")
		return {
			"success": False,
			"reason": "revoked",
			"user_email": user_email,
			"user_full_name": user_doc.full_name or user_email,
		}

	token = auth.get_fresh_access_token()
	if not token:
		log_credential_request(user_email, bench_name, False, "token mint failed")
		return {
			"success": False,
			"reason": "refresh_failed",
			"user_email": user_email,
			"user_full_name": user_doc.full_name or user_email,
		}

	auth.mark_used()
	log_credential_request(user_email, bench_name, True, None)

	expires_at = frappe.utils.get_datetime(auth.expires_at)
	expires_in = int((expires_at - frappe.utils.now_datetime()).total_seconds())
	return {
		"success": True,
		"github.com": token,
		"user_email": user_email,
		"user_full_name": user_doc.full_name or user_email,
		"github_username": auth.github_username or "",
		"expires_in_seconds": max(60, expires_in),
	}
