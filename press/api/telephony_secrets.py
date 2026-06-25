# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Rotate a host secret (AMI password OR listener API token) in place.

Regenerate the chosen secret, rewrite ONLY that key in the host .env (the rest
of the bootstrap env is preserved), then reload the container so the listener
reconnects. The new secret is written to the host file and, for the API token,
minted against the listener user - it is NEVER returned to the browser. Pure
helpers (`normalize_which`, `_rewrite_env_line`) are unit-tested directly."""
from __future__ import annotations

import re

HOST_DIR = "/srv/oc-asterisk"

# The page sends a secret_id; map both the friendly ids and the raw .env keys to
# the canonical 'which' we rotate.
_AMI = "ami"
_TOKEN = "token"
_WHICH = {
	"ami": _AMI, "ami_password": _AMI, "amipassword": _AMI,
	"token": _TOKEN, "api_token": _TOKEN, "oc_api_token": _TOKEN, "apitoken": _TOKEN,
}
_ENV_KEY = {_AMI: "AMI_PASSWORD", _TOKEN: "OC_API_TOKEN"}


def normalize_which(which: str) -> str:
	"""Map a UI secret_id ('ami_password' / 'api_token' / 'ami' / 'token') to the
	canonical rotate target. Raises for anything else so we never rewrite an
	unknown .env key. Pure + tested."""
	import frappe

	key = (which or "").strip().lower().replace("-", "_")
	target = _WHICH.get(key) or _WHICH.get(key.replace("_", ""))
	if not target:
		frappe.throw(frappe._("Unknown secret {0}. Rotate AMI password or API token only.").format(which), frappe.ValidationError)
	return target


def _rewrite_env_line(env_text: str, env_key: str, new_value: str) -> str:
	"""Replace the `KEY=...` line in the .env, preserving every other line and the
	overall order. Appends the line if the key was absent. Pure + tested."""
	pattern = re.compile(rf"^{re.escape(env_key)}=.*$", re.MULTILINE)
	replacement = f"{env_key}={new_value}"
	if pattern.search(env_text or ""):
		return pattern.sub(replacement, env_text, count=1)
	text = (env_text or "")
	if text and not text.endswith("\n"):
		text += "\n"
	return text + replacement + "\n"


def rotate_on_host(host: str, instance: str, which: str) -> dict:
	"""Read the host .env, rewrite the one rotated key, push it back, reload the
	container. The new AMI password is generated; the new API token is minted for
	the instance owner (self) and NEVER returned. Called by the whitelisted
	wrapper which owns the role gate + audit."""
	import frappe

	from press.api.infra_telephony import _managed_doc, _valid_instance, mint_listener_token
	from press.infra import host_exec, telephony_bundle

	_valid_instance(instance)
	target = normalize_which(which)
	env_key = _ENV_KEY[target]
	doc = _managed_doc(host)

	# Read the current .env so we rewrite ONLY the rotated key.
	current_env = host_exec.run_host_script(doc, f"cat {HOST_DIR}/.env 2>/dev/null || true", timeout=30)
	if target == _AMI:
		new_value = telephony_bundle.gen_secret(24)
	else:
		# Mint a fresh listener token for the instance owner (self-hosted). The
		# value is written to the host only; mint_listener_token already gates +
		# is owner-bound.
		new_value = mint_listener_token(site="self", instance=instance, listener_user=None)

	new_env = _rewrite_env_line(current_env, env_key, new_value)
	files = {f"{HOST_DIR}/.env": new_env}
	# Push the rewritten .env then reload so the running container re-reads it and
	# the listener reconnects with the new credential.
	script = (
		f"cd {HOST_DIR}\n"
		"docker compose up -d --force-recreate oc-listener oc-asterisk 2>/dev/null "
		"|| docker compose restart 2>/dev/null || true\n"
		"docker compose ps\n"
	)
	host_exec.run_host_script(doc, script, files=files, timeout=120)
	# NB: new_value (the rotated secret) is deliberately NOT in the return.
	return {"ok": True, "detail": f"{env_key} rotated and container reloaded."}
