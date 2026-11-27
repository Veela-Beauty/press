"""Which provider sends an SMS to which country, at what price (owner 2026-11-27). Plain functions, no Frappe."""

import json

FIREBASE = "Google Firebase"
DEFAULT_ROUTES = {
	"SA": {"provider": FIREBASE, "price": 0.18},
	"EG": {"provider": FIREBASE, "price": 0.13},
	"default": {"provider": FIREBASE, "price": 0.20},
}


def parse(raw):
	"""The saved route table (JSON text or dict), or the defaults when empty or unreadable."""
	if isinstance(raw, dict) and raw.get("default"):
		return raw
	try:
		table = json.loads(raw) if raw else None
	except (TypeError, ValueError):
		table = None
	return table if isinstance(table, dict) and table.get("default") else DEFAULT_ROUTES


def route_for(country, table):
	return table.get(str(country or "").upper()) or table["default"]


def mode_of(provider):
	return "firebase" if provider == FIREBASE else "server"


def clean(rows):
	"""A table saved from the Routes page as a route dict. Raises ValueError on a bad price or no 'default' row."""
	table = {}
	for row in rows or []:
		country = str(row.get("country") or "").strip()
		key = "default" if country.lower() == "default" else country.upper()
		provider = str(row.get("provider") or "").strip()
		try:
			price = float(row.get("price"))
		except (TypeError, ValueError):
			raise ValueError(f"Price for {key or '?'} is not a number") from None
		if not key or not provider or price < 0:
			raise ValueError(f"Route for {key or '?'} needs a country, a provider and a price of 0 or more")
		table[key] = {"provider": provider, "price": price}
	if "default" not in table:
		raise ValueError("The routes need an 'Any other country' row")
	return table
