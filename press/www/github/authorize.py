# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# For license information, please see license.txt


import json
from base64 import b64decode

import frappe
import requests

from press.utils import log_error


def get_context(context):
	code = frappe.form_dict.code
	state = frappe.form_dict.state
	redirect_url = frappe.utils.get_url("/dashboard")
	if code and state:
		try:
			decoded_state = json.loads(b64decode(state).decode())
		except Exception:
			frappe.flags.redirect_location = frappe.utils.get_url("/dashboard")
			raise frappe.Redirect
		flow = decoded_state.get("flow")
		if flow == "user_auth":
			# Per-user GitHub OAuth (Option C) — handle via the github_auth module
			from press.api.github_auth import handle_user_auth_callback
			success, info = handle_user_auth_callback(code, decoded_state)
			frappe.db.commit()
			base = frappe.utils.get_url()
			if success:
				redirect_url = f"{base}/dashboard/settings/developer?github_connected={info}"
			else:
				redirect_url = f"{base}/dashboard/settings/developer?github_error={info}"
		else:
			# Legacy flow — team-level app installation tokens
			team = decoded_state["team"]
			redirect_url = frappe.utils.get_url(decoded_state["url"])
			obtain_access_token(code, team)
			frappe.db.commit()
	frappe.flags.redirect_location = redirect_url
	raise frappe.Redirect


def obtain_access_token(code, team):
	response = None
	try:
		client_id = frappe.db.get_single_value("Press Settings", "github_app_client_id")
		client_secret = frappe.db.get_single_value(
			"Press Settings", "github_app_client_secret"
		)
		data = {"client_id": client_id, "client_secret": client_secret, "code": code}
		headers = {"Accept": "application/json"}
		response = requests.post(
			"https://github.com/login/oauth/access_token", data=data, headers=headers
		).json()
		frappe.db.set_value("Team", team, "github_access_token", response["access_token"])
	except Exception:
		log_error("Access Token Error", team=team, code=code, response=response)
