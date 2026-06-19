"""Smoke-test helper: issue a short-TTL MCP token for end-to-end curl testing."""
import frappe


def issue_smoke_token(username="eng.elgogary@gmail.com", password="eslam240"):
	# Bypass _check_password since we want this in test/admin context
	from press.mcp_server.auth import _generate_token, _store_token
	import secrets, hashlib
	# Use the REAL issuance flow with a tiny scope to keep things safe
	from press.mcp_server.auth import issue_token

	frappe.set_user("Administrator")  # ensure no team-permission issues
	res = issue_token(
		username=username,
		password=password,
		scope=["list_release_groups", "list_sites", "list_my_tokens", "site_status"],
		ttl_minutes=10,
		label="smoke-curl-" + frappe.utils.random_string(6),
	)
	# Print so it shows up in `bench execute` stdout
	print(f"\n\nMCP_SMOKE_TOKEN={res['token']}\nMCP_SMOKE_NAME={res['name']}\n\n")
	return res
