"""The role that may read Press MCP Call Log (0.7.59).

The call log holds every MCP agent's code, SQL and output on every site; before 0.7.59 every System Manager could read
it. Its DocType now grants read to MCP Auditor only; this creates the role. Who holds it is decided per site, not here.
Idempotent.
"""

import frappe


def execute():
	if not frappe.db.exists("Role", "MCP Auditor"):
		frappe.get_doc({"doctype": "Role", "role_name": "MCP Auditor", "desk_access": 1}).insert(
			ignore_permissions=True
		)
