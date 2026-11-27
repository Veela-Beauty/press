# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Communications, SMS (owner 2026-11-27; spec ~/docs/superpowers/specs/2026-11-27-basher-sms-activation-codes-design.md).

Dashboard calls (owner only: a System User whose Press role is Platform Admin, because the pages show costs and
provider logins): list_sites, set_sms_codes, sms_log, cost_by_client, get_routes, save_routes, list_providers,
save_provider, test_provider.

Client sites: request_sms (guest, POST, rate limited). A Basher site asks before every SMS; Press checks the site's key,
picks the route for the number's country, logs one SMS Log row at the route's price, then answers "firebase" (the phone
sends it) or sends the text through the local provider and answers "server". The number and the text are never stored.
"""

import hmac
import json

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import get_url, nowdate

from press.agent import Agent
from press.messaging import providers, routes
from press.press.doctype.team.team_roles import has_role_access

TOKEN_KEY = "basher_sms_token"
URL_KEY = "basher_sms_press_url"
SMS_KEYS = (TOKEN_KEY, URL_KEY)
BASHER_APP = "basher_hr"
# Calling codes we route by; any other number takes the "default" route. Longest prefix first.
CALLING_CODES = (
	("966", "SA"),
	("971", "AE"),
	("965", "KW"),
	("974", "QA"),
	("973", "BH"),
	("968", "OM"),
	("962", "JO"),
	("20", "EG"),
)


def _is_system_user():
	return frappe.db.get_value("User", frappe.session.user, "user_type") == "System User"


def _only_owner():
	if not (_is_system_user() and has_role_access("Platform Admin")):
		raise frappe.PermissionError(frappe._("Only the Platform Admin sees SMS costs and providers."))


def _country(e164):
	digits = str(e164 or "").lstrip("+")
	for code, country in CALLING_CODES:
		if digits.startswith(code):
			return country
	return ""


def _month_range(month):
	"""("YYYY-MM-01", first day of the next month) for "YYYY-MM"; the current month when empty."""
	month = month or nowdate()[:7]
	year, mon = month.split("-") if len(month) == 7 and month[4] == "-" else (None, None)
	if not (year and year.isdigit() and mon.isdigit() and 1 <= int(mon) <= 12):
		raise ValueError(f"Month must look like 2026-11, not {month}")
	y, mo = int(year), int(mon)
	nxt = (y + 1, 1) if mo == 12 else (y, mo + 1)
	return f"{y:04d}-{mo:02d}-01", f"{nxt[0]:04d}-{nxt[1]:02d}-01"


def _routes():
	return routes.parse(frappe.db.get_single_value("Messaging Settings", "routes"))


def _stored_token(site):
	return frappe.db.get_value(
		"Site Config", {"parent": site, "parenttype": "Site", "key": TOKEN_KEY}, "value"
	)


def _site_row(site):
	return frappe.db.get_value("Site", site, ["name", "team", "status"], as_dict=True)


def _log(**fields):
	frappe.get_doc({"doctype": "SMS Log", **fields}).insert(ignore_permissions=True)


def _send_through(provider_name, e164, text):
	doc = frappe.get_doc("SMS Provider", provider_name)
	if not doc.enabled:
		return False, f"{provider_name} is disabled"
	settings = {
		"username": doc.username,
		"password": doc.get_password("password", raise_exception=False),
		"sender_name": doc.sender_name,
	}
	return providers.send(doc.provider_type, settings, e164, text)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=120, seconds=60)
def request_sms(site, token, e164, text, purpose="Basher activation"):
	stored = _stored_token(site)
	row = _site_row(site)
	if (
		not (stored and token and hmac.compare_digest(str(stored), str(token)))
		or not row
		or row.status != "Active"
	):
		raise frappe.PermissionError("SMS codes are not on for this site")
	country = _country(e164)
	route = routes.route_for(country, _routes())
	mode = routes.mode_of(route["provider"])
	entry = {
		"site": row.name,
		"team": row.team,
		"country": country,
		"provider": route["provider"],
		"mode": mode,
		"cost_usd": route["price"],
		"purpose": purpose,
	}
	if mode == "firebase":
		_log(**entry, delivered=1)
		return {"mode": "firebase"}
	ok, _detail = _send_through(route["provider"], e164, text)
	_log(**entry, delivered=1 if ok else 0)
	if not ok:
		frappe.throw(frappe._("The SMS provider did not take the message"), frappe.ValidationError)
	return {"mode": "server"}


@frappe.whitelist()
def list_sites():
	_only_owner()
	start, end = _month_range(None)
	sites = frappe.get_all("Site", filters={"status": "Active"}, fields=["name", "team"], order_by="name asc")
	with_app = set(
		frappe.get_all("Site App", filters={"app": BASHER_APP, "parenttype": "Site"}, pluck="parent")
	)
	switched = set(
		frappe.get_all("Site Config", filters={"key": TOKEN_KEY, "parenttype": "Site"}, pluck="parent")
	)
	counts = {
		r.site: r.n
		for r in frappe.get_all(
			"SMS Log",
			filters=[["creation", ">=", start], ["creation", "<", end]],
			fields=["site", "count(name) as n"],
			group_by="site",
		)
	}
	clients = _client_names({s.team for s in sites})
	return [
		{
			"site": s.name,
			"team": s.team,
			"client": clients.get(s.team, s.team),
			"sms_this_month": counts.get(s.name, 0),
			"on": s.name in switched,
		}
		for s in sites
		if s.name in with_app
	]


def _client_names(teams):
	if not teams:
		return {}
	rows = frappe.get_all("Team", filters={"name": ["in", list(teams)]}, fields=["name", "team_title"])
	return {t.name: t.team_title or t.name for t in rows}


@frappe.whitelist()
def set_sms_codes(site, on):
	_only_owner()
	on = str(on).lower() in ("1", "true")
	doc = frappe.get_doc("Site", site)
	if on:
		doc._update_configuration({TOKEN_KEY: frappe.generate_hash(length=40), URL_KEY: get_url()})
	else:
		doc.configuration = [row for row in doc.configuration if row.key not in SMS_KEYS]
		doc.save()
	Agent(doc.server).update_site_config(doc)
	return {"site": site, "on": on}


@frappe.whitelist()
def sms_log(team=None, month=None, start=0, limit=100):
	_only_owner()
	first, end = _month_range(month)
	filters = [["creation", ">=", first], ["creation", "<", end]]
	if team:
		filters.append(["team", "=", team])
	rows = frappe.get_all(
		"SMS Log",
		filters=filters,
		fields=["creation", "site", "team", "country", "provider", "cost_usd"],
		order_by="creation desc",
		start=int(start),
		page_length=min(int(limit), 500),
	)
	clients = _client_names({r.team for r in rows})
	return [
		{
			"time": str(r.creation)[:16],
			"site": r.site,
			"client": clients.get(r.team, r.team),
			"country": r.country,
			"provider": r.provider,
			"cost_usd": r.cost_usd,
		}
		for r in rows
	]


@frappe.whitelist()
def cost_by_client(month=None):
	_only_owner()
	first, end = _month_range(month)
	rows = frappe.get_all(
		"SMS Log",
		filters=[["creation", ">=", first], ["creation", "<", end]],
		fields=["team", "count(distinct site) as sites", "count(name) as sms", "sum(cost_usd) as cost_usd"],
		group_by="team",
		order_by="cost_usd desc",
	)
	clients = _client_names({r.team for r in rows})
	out = [
		{
			"team": r.team,
			"client": clients.get(r.team, r.team),
			"sites": r.sites,
			"sms": r.sms,
			"cost_usd": round(r.cost_usd or 0, 2),
		}
		for r in rows
	]
	total = {
		"sites": sum(r["sites"] for r in out),
		"sms": sum(r["sms"] for r in out),
		"cost_usd": round(sum(r["cost_usd"] for r in out), 2),
	}
	return {"month": first[:7], "rows": out, "total": total}


@frappe.whitelist()
def get_routes():
	_only_owner()
	table = _routes()
	order = [*sorted(k for k in table if k != "default"), "default"]
	return {
		"firebase_project": frappe.db.get_single_value("Messaging Settings", "firebase_project")
		or "basher-hr",
		"rows": [{"country": k, "provider": table[k]["provider"], "price": table[k]["price"]} for k in order],
		"providers": [routes.FIREBASE, *frappe.get_all("SMS Provider", filters={"enabled": 1}, pluck="name")],
	}


@frappe.whitelist()
def save_routes(rows):
	_only_owner()
	rows = json.loads(rows) if isinstance(rows, str) else rows
	try:
		table = routes.clean(rows)
	except ValueError as error:
		frappe.throw(str(error), frappe.ValidationError)
	known = {routes.FIREBASE, *frappe.get_all("SMS Provider", filters={"enabled": 1}, pluck="name")}
	unknown = sorted({r["provider"] for r in table.values()} - known)
	if unknown:
		frappe.throw(
			frappe._("Set up these providers first: {0}").format(", ".join(unknown)), frappe.ValidationError
		)
	settings = frappe.get_single("Messaging Settings")
	settings.routes = json.dumps(table)
	settings.save(ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist()
def list_providers():
	_only_owner()
	rows = frappe.get_all(
		"SMS Provider",
		fields=["name", "provider_type", "sender_name", "enabled", "username"],
		order_by="name asc",
	)
	built_in = {
		"name": routes.FIREBASE,
		"provider_type": "firebase",
		"sender_name": "",
		"enabled": 1,
		"has_login": True,
		"mode": "firebase",
	}
	custom = [
		{
			"name": r.name,
			"provider_type": r.provider_type,
			"sender_name": r.sender_name,
			"enabled": r.enabled,
			"has_login": bool(r.username),
			"mode": "server",
		}
		for r in rows
	]
	return [built_in, *custom]


@frappe.whitelist()
def save_provider(provider_name, provider_type, sender_name, username=None, password=None, enabled=1):
	_only_owner()
	if provider_type not in providers.TYPES:
		frappe.throw(frappe._("Unknown provider type {0}").format(provider_type), frappe.ValidationError)
	exists = frappe.db.exists("SMS Provider", provider_name)
	if exists:
		doc = frappe.get_doc("SMS Provider", provider_name)
	else:
		doc = frappe.get_doc({"doctype": "SMS Provider", "provider_name": provider_name})
	doc.update({"provider_type": provider_type, "sender_name": sender_name, "enabled": int(enabled)})
	if username is not None:
		doc.username = username
	if password:
		doc.password = password
	if exists:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)
	return {"name": doc.name}


@frappe.whitelist()
def test_provider(provider_name, mobile):
	"""Send one test SMS to `mobile` (full international number, for example +201012345678). Not logged."""
	_only_owner()
	ok, detail = _send_through(provider_name, mobile, "Basher: test SMS from Press.")
	return {"ok": ok, "detail": detail}
