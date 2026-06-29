"""GitHub integration Watch Tower alerts."""
import frappe
from ._helpers import ts_now


def check_github_token_health(doc_dict, rule):
	"""
	Check if GitHub API token is working. Fires if:
	- Token is missing from Press Settings
	- Token returns 401/403 from GitHub API
	- More than 10 App Sources have last_github_poll_failed=1
	"""
	from ..email_branding import wrap_email, send_alert_email
	import requests

	issues = []
	ts = ts_now()

	token = frappe.db.get_single_value("Press Settings", "github_access_token")
	if not token:
		issues.append("No GitHub access token configured in Press Settings")
	else:
		try:
			resp = requests.get(
				"https://api.github.com/rate_limit",
				headers={"Authorization": f"token {token}"},
				timeout=10,
			)
			if resp.status_code == 401:
				issues.append("GitHub token is <b>expired or revoked</b> (401 Unauthorized)")
			elif resp.status_code == 403:
				issues.append("GitHub token is <b>forbidden</b> (403) \u2014 may need new scopes")
			elif resp.status_code == 200:
				data = resp.json()
				remaining = data.get("rate", {}).get("remaining", 0)
				limit = data.get("rate", {}).get("limit", 0)
				if limit <= 60:
					issues.append(
						f"GitHub token not providing authenticated rate limit "
						f"(limit={limit}, expected 5000). Token may be invalid."
					)
				elif remaining < 100:
					issues.append(
						f"GitHub API rate limit low: <b>{remaining}/{limit}</b> remaining"
					)
		except Exception as e:
			issues.append(f"Could not reach GitHub API: {str(e)[:100]}")

	failed_polls = frappe.db.count("App Source", {"last_github_poll_failed": 1})
	if failed_polls > 10:
		issues.append(f"<b>{failed_polls}</b> App Sources have failed GitHub polls")

	if not issues:
		return False

	body = "<ul>"
	for issue in issues:
		body += f"<li style='color:#ef4444'>{issue}</li>"
	body += "</ul>"
	body += """<p style="margin-top:12px">
<b>Fix:</b> Go to Press Settings \u2192 set a valid GitHub Personal Access Token
(fine-grained, read-only public repos, 1-year expiry).</p>"""

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\U0001f511 GitHub Token Alert \u2014 {ts}",
		message=wrap_email("\U0001f511 GitHub Token Health", body, f"Press &bull; {ts}"),
	)
	return True
