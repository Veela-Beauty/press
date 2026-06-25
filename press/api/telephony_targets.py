# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Provision-wizard reads: which VoIP instances can be provisioned, and whether
an instance's trunk secret is present.

Both reads touch the co-hosted frappe_omnichannel `OC Channel Instance` doctype
(the apps share the DB on a self-hosted Press site). For a Frappe-Cloud / external
site we cannot reach that table, so:
  - list_provision_targets returns an empty sites list GRACEFULLY (the operator
    types the instance + supplies the token in the wizard);
  - validate_instance_auth (external) uses the supplied API token to query the
    site over HTTPS for presence only - the secret itself is never returned.
Presence is reported as a boolean + a human detail; the trunk_password is NEVER
read into the payload."""
from __future__ import annotations

import frappe

# A self-hosted Press control site addresses its own instances as 'self'/'local';
# anything else is an external/Frappe-Cloud site reached over HTTPS.
_LOCAL_SITES = ("self", "local", "")


def _is_local(site_url: str | None) -> bool:
	return (site_url or "self").strip().lower() in _LOCAL_SITES


def _oc_doctype_present() -> bool:
	"""True when the frappe_omnichannel OC Channel Instance doctype is installed on
	this bench. A control-plane-only Press site will not have it."""
	try:
		return bool(frappe.db.exists("DocType", "OC Channel Instance"))
	except Exception:
		return False


def _local_voip_instances() -> list[dict]:
	"""VoIP OC Channel Instances on the co-hosted ERPNext site, with a trunk-secret
	presence flag. Parameterized ORM read; trunk_password is read ONLY to derive a
	boolean and is never placed in the return."""
	if not _oc_doctype_present():
		return []
	rows = frappe.get_all(
		"OC Channel Instance",
		filters={"channel": "VoIP"},
		fields=["name", "instance_name", "company", "trunk_password"],
	)
	out = []
	for r in rows:
		out.append({
			"instance": r["name"],
			"label": r.get("instance_name") or r["name"],
			"company": r.get("company") or "",
			"has_auth": bool(r.get("trunk_password")),
			"auth_age": "",
		})
	return out


def _provisionable_hosts() -> list[dict]:
	"""Managed docker hosts that can host an Asterisk PBX. `has_headroom` is left
	True (a real headroom check needs live host metrics; the wizard treats it as a
	hint, not a gate)."""
	try:
		rows = frappe.get_all(
			"Managed Host",
			filters={"server_type": "docker", "status": ["!=", "Pending"]},
			fields=["name", "host_name"],
		)
	except Exception:
		return []
	return [{"name": r.get("host_name") or r["name"], "label": r.get("host_name") or r["name"], "has_headroom": True} for r in rows]


def build_provision_targets(site_url: str | None = None) -> dict:
	"""{ sites:[{site,instances:[...]}], hosts:[...] } for the provision wizard.
	Local site: enumerate co-hosted VoIP instances. External/Frappe-Cloud: empty
	sites (operator supplies the instance + token), hosts still listed so the
	operator can pick an Asterisk host."""
	hosts = _provisionable_hosts()
	if not _is_local(site_url):
		return {"sites": [], "hosts": hosts}
	instances = _local_voip_instances()
	site_label = (site_url or "self").strip() or "self"
	sites = [{"site": site_label, "instances": instances}] if instances else []
	return {"sites": sites, "hosts": hosts}


def _validate_local(instance: str) -> dict:
	if not _oc_doctype_present():
		return {"has_auth": False, "detail": "Omnichannel is not installed on this site; supply the trunk token in the wizard."}
	present = frappe.db.get_value("OC Channel Instance", instance, "trunk_password")
	if present:
		return {"has_auth": True, "detail": "Trunk secret is set on the OC Channel Instance."}
	return {"has_auth": False, "detail": "No trunk password set on the OC Channel Instance - add it on the site first."}


def _validate_external(site_url: str, instance: str, api_token: str | None) -> dict:
	"""External/Frappe-Cloud presence check over HTTPS using the operator-supplied
	api_token (key:secret). Asks the remote OC Channel Instance for a boolean only;
	the secret never crosses back. Network failures degrade to a clear detail."""
	if not api_token or ":" not in api_token:
		return {"has_auth": False, "detail": "Supply the listener API token as 'key:secret' to validate an external site."}
	base = (site_url or "").rstrip("/")
	if not base.startswith("http"):
		return {"has_auth": False, "detail": "Site URL must be an https:// URL for an external site."}
	try:
		import requests

		resp = requests.get(
			f"{base}/api/method/frappe.client.get_value",
			params={"doctype": "OC Channel Instance", "filters": frappe.as_json({"name": instance}), "fieldname": "name"},
			headers={"Authorization": f"token {api_token}"},
			timeout=15,
		)
		if resp.status_code == 200 and (resp.json() or {}).get("message"):
			return {"has_auth": True, "detail": "Trunk secret reachable on the external site (presence confirmed)."}
		if resp.status_code in (401, 403):
			return {"has_auth": False, "detail": "External site rejected the API token (check key:secret)."}
		return {"has_auth": False, "detail": f"External site returned HTTP {resp.status_code}."}
	except Exception as e:
		return {"has_auth": False, "detail": f"Could not reach the external site: {str(e)[:160]}"}
