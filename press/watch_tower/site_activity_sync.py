"""
Site Activity Sync -  collects last user login from remote sites.

Runs daily. For each Active site, asks the Press agent to query
the site's database for the most recent login. Stores result
in a custom field `last_user_login` on the Site doctype.

This is the ONLY way to know if actual users are active on a site,
since Press itself only tracks dashboard logins, not site logins.

Design for scale:
- 1 lightweight SQL per site per day (MAX on indexed column)
- Agent handles the remote execution asynchronously
- Result stored on Site doc for fast local reads by lifecycle manager
"""
import frappe
from frappe.utils import now_datetime, get_datetime
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


# The SQL we run on each remote site's database
# Column is `operation` not `activity_type` in Frappe v15
LAST_LOGIN_QUERY = """
SELECT MAX(creation) as last_login
FROM `tabActivity Log`
WHERE operation = 'Login'
"""

# Fallback: check tabUser.last_login directly
LAST_LOGIN_FALLBACK = """
SELECT MAX(last_login) as last_login
FROM `tabUser`
WHERE name != 'Administrator' AND name != 'Guest'
AND last_login IS NOT NULL
"""


def setup_custom_field():
	"""Create the last_user_login field on Site doctype (run once)."""
	create_custom_fields({
		"Site": [
			{
				"fieldname": "last_user_login",
				"label": "Last User Login",
				"fieldtype": "Datetime",
				"insert_after": "modified",
				"read_only": 1,
				"description": "Last actual user login on the site (synced daily by Watch Tower)",
			}
		]
	})


def sync_site_activity():
	"""Daily job: query each active site for last user login."""
	if not frappe.db.exists("DocType", "Site"):
		return
	sites = frappe.get_all(
		"Site",
		filters={"status": "Active"},
		fields=["name", "server", "bench"],
	)

	synced = 0
	failed = 0

	for site in sites:
		try:
			_sync_single_site(site)
			synced += 1
		except Exception as e:
			failed += 1
			# Don't log every failure -  agent may be temporarily down
			if failed <= 3:
				frappe.log_error(
					title=f"Site Activity Sync: {site.name}",
					message=str(e),
				)

	frappe.db.commit()
	frappe.logger().info(
		f"Site Activity Sync: {synced} synced, {failed} failed out of {len(sites)}"
	)


def _sync_single_site(site):
	"""Query one site's database for last login via Press agent."""
	from press.agent import Agent

	agent = Agent(site.server)
	site_doc = frappe.get_doc("Site", site.name)

	# Run the query via agent → site's MariaDB
	response = agent.run_sql_query_in_database(
		site_doc, LAST_LOGIN_QUERY, commit=False,
	)
	last_login = _extract_value(response)

	if not last_login:
		# Try fallback query (User.last_login)
		response = agent.run_sql_query_in_database(
			site_doc, LAST_LOGIN_FALLBACK, commit=False,
		)
		last_login = _extract_value(response)

	if last_login:
		frappe.db.set_value(
			"Site", site.name,
			"last_user_login", get_datetime(last_login),
			update_modified=False,
		)


def _extract_value(response):
	"""Extract the first value from agent SQL response.

	Agent returns: {"success": true, "data": [{"query": ..., "output": {"columns": [...], "data": [[val]]}}]}
	"""
	if not response or not response.get("success"):
		return None

	data = response.get("data")
	if not data:
		return None

	# data is a list of query results
	if isinstance(data, list) and data:
		query_result = data[0]
		if isinstance(query_result, dict):
			output = query_result.get("output", {})
			if isinstance(output, dict):
				rows = output.get("data", [])
				if rows and rows[0] and rows[0][0]:
					return rows[0][0]

	# Fallback: try direct output format
	output = response.get("output", [])
	if output and isinstance(output, list) and output[0]:
		row = output[0]
		if isinstance(row, dict):
			return row.get("last_login")
		if isinstance(row, (list, tuple)) and row:
			return row[0]

	return None
