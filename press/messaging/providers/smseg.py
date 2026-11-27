"""SMS Smart Egypt (smseg.com). The request shape Veela's old shop used: a JSON POST of username, password,
sendername, mobiles (digits, country code first, no '+') and message. The success reply shape is not documented to us:
any 2xx whose body does not say "error" counts as handed over; the first "Send a test SMS" on the Providers page
confirms it."""

import requests

URL = "https://smssmartegypt.com/sms/api/json/"
TIMEOUT_SECONDS = 8


def send(settings, to_e164, text):
	payload = {
		"username": settings.get("username"),
		"password": settings.get("password"),
		"sendername": settings.get("sender_name"),
		"mobiles": str(to_e164 or "").lstrip("+"),
		"message": text,
	}
	try:
		reply = requests.post(
			URL, json=payload, timeout=TIMEOUT_SECONDS, headers={"Accept": "application/json"}
		)
	except requests.RequestException as error:
		return False, f"smseg unreachable: {type(error).__name__}"
	body = (reply.text or "")[:300]
	if not reply.ok:
		return False, f"smseg HTTP {reply.status_code}: {body}"
	if '"error"' in body.lower():
		return False, f"smseg refused: {body}"
	return True, body
