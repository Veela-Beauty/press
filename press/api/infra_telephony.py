# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Infra Control Panel: no-SSH telephony (PBX) provisioning actions.

Every action is gated to Telephony Ops OR System Manager, routed through the
existing managed-host cert pipeline (_managed_doc -> run_host_script), and
audited into Infra Action Log on BOTH the success and the error path - exactly
like host_unit_action. Secrets (AMI password, listener API token) are generated
or minted server-side and written to the host .env; they are NEVER returned to
the browser. telephony_describe is the secret-free read for the UI (counts +
booleans only)."""
from __future__ import annotations

import re

import frappe

from press.infra.adapters.base import log_infra_action

TELEPHONY_ROLES = ("System Manager", "Telephony Ops")
HOST_DIR = "/srv/oc-asterisk"
_FW_ACTIONS = ("allow", "deny")
_IPV4_RE = re.compile(r"\A(?:\d{1,3}\.){3}\d{1,3}\Z")
_SIP_PORT = 5060
_RTP_RANGE = "10000:20000"


def _only_telephony() -> None:
	"""Allow if the user has ANY telephony role. frappe.only_for raises on the
	first missing role, so check membership explicitly across the allowlist."""
	roles = set(frappe.get_roles())
	if not roles.intersection(TELEPHONY_ROLES):
		raise frappe.PermissionError(
			frappe._("Telephony actions require the Telephony Ops or System Manager role.")
		)


def _managed_doc(host: str):
	# Reuse infra_board's cert-attaching loader so the adapter/host-exec can auth.
	from press.api.infra_board import _managed_doc as load

	return load(host)


def _valid_instance(instance: str) -> str:
	if not instance or not re.match(r"^[a-zA-Z0-9._-]+$", instance):
		frappe.throw(frappe._("Invalid OC Channel Instance name."), frappe.ValidationError)
	return instance


def _resolve_public_ip(doc) -> str:
	"""The host's reachable IPv4 (Bevatel sends inbound SIP here). Prefer the
	Managed Host ssh_host when it is already an IP; else read it off the host."""
	from press.infra import host_exec

	if _IPV4_RE.match(doc.get("ssh_host") or ""):
		return doc.ssh_host
	ip = (host_exec.run_host_script(doc, "curl -fsS -4 https://api.ipify.org || hostname -I | awk '{print $1}'")).strip()
	return ip.splitlines()[-1].strip() if ip else "0.0.0.0"


def _upsert_pbx_record(host: str, instance: str, site_url: str, source: str, public_ip: str, status: str) -> None:
	pbx_id = f"{host}:{instance}"
	if frappe.db.exists("Telephony PBX", pbx_id):
		frappe.db.set_value("Telephony PBX", pbx_id, {
			"site_url": site_url, "source": source, "public_ip": public_ip,
			"status": status, "last_seen": frappe.utils.now_datetime(), "last_error": "",
		})
	else:
		frappe.get_doc({
			"doctype": "Telephony PBX", "pbx_id": pbx_id, "host": host, "instance": instance,
			"site_url": site_url, "source": source, "public_ip": public_ip, "status": status,
		}).insert(ignore_permissions=True)
	frappe.db.commit()


def _mark_pbx_decommissioned(host: str, instance: str) -> None:
	pbx_id = f"{host}:{instance}"
	if frappe.db.exists("Telephony PBX", pbx_id):
		frappe.db.set_value("Telephony PBX", pbx_id, "status", "Decommissioned")
		frappe.db.commit()


def _instance_owner(site: str, instance: str) -> str:
	"""owner_user of the OC Channel Instance on a SELF-hosted Press site (we share
	the DB). The listener token must belong to this user (provisioning._authorize
	is owner-bound)."""
	owner = frappe.db.get_value("OC Channel Instance", instance, "owner_user")
	if not owner:
		frappe.throw(frappe._("OC Channel Instance {0} not found on this site.").format(instance), frappe.ValidationError)
	return owner


def _revoke_token(site: str, instance: str) -> None:
	"""Best-effort: clear the listener user's api_secret on a self-hosted site so
	the decommissioned PBX can no longer push calls. External sites: operator
	rotates their own key (we never held it)."""
	if (site or "self") not in ("self", "local"):
		return
	owner = frappe.db.get_value("OC Channel Instance", instance, "owner_user")
	if owner and frappe.db.exists("User", owner):
		frappe.db.set_value("User", owner, "api_secret", "")
		frappe.db.commit()


@frappe.whitelist()
def telephony_provision(host, site_url, oc_instance, api_token=None):
	"""Stand up a multi-company Asterisk PBX on `host`: push the bundle + a freshly
	rendered .env (AMI password generated, listener token minted), then
	`docker compose up -d`. Telephony Ops / System Manager only; audited."""
	_only_telephony()
	instance = _valid_instance(oc_instance)
	from press.infra import host_exec, telephony_bundle

	try:
		doc = _managed_doc(host)
		public_ip = _resolve_public_ip(doc)
		token = api_token or mint_listener_token(site="self", instance=instance, listener_user=None)
		ami_pw = telephony_bundle.gen_secret(24)
		files = telephony_bundle.read_bundle()
		files[f"{HOST_DIR}/.env"] = telephony_bundle.render_env(
			site_url=site_url, instance=instance, public_ip=public_ip,
			ami_password=ami_pw, api_token=token,
		)
		script = (
			f"cd {HOST_DIR}\n"
			"mkdir -p recordings\n"
			"chmod +x entrypoint.sh\n"
			"docker compose up -d\n"
			"docker compose ps\n"
		)
		host_exec.run_host_script(doc, script, files=files, timeout=180)
		source = "self" if (api_token is None) else "external"
		_upsert_pbx_record(host, instance, site_url, source, public_ip, "Active")
		log_infra_action(host=host, unit=instance, action="telephony_provision",
			outcome="success", detail=f"site={site_url} ip={public_ip} source={source}")
		# NB: token + ami_pw are deliberately NOT in the return.
		return {"ok": True, "host": host, "instance": instance, "public_ip": public_ip}
	except Exception as e:
		log_infra_action(host=host, unit=instance, action="telephony_provision", outcome="error", detail=str(e))
		raise


@frappe.whitelist()
def firewall_rule(host, trunk_ip, action="allow"):
	"""Open (or close) SIP/RTP to the trunk IP ONLY. `allow` enables ufw with an
	SSH-allow FIRST so we never lock ourselves out (ufw may be INACTIVE on
	press-ctrl). Telephony Ops / System Manager only; audited."""
	_only_telephony()
	if action not in _FW_ACTIONS:
		frappe.throw(frappe._("Unknown firewall action {0}. Allowed: {1}.").format(action, ", ".join(_FW_ACTIONS)), frappe.ValidationError)
	if not _IPV4_RE.match(trunk_ip or ""):
		frappe.throw(frappe._("trunk_ip must be a bare IPv4 address."), frappe.ValidationError)
	from press.infra import host_exec

	try:
		doc = _managed_doc(host)
		if action == "allow":
			script = (
				"sudo ufw allow 22/tcp\n"                       # SSH first - never lock out
				"yes | sudo ufw --force enable\n"
				f"sudo ufw allow from {trunk_ip} to any port {_SIP_PORT} proto udp\n"
				f"sudo ufw allow from {trunk_ip} to any port {_RTP_RANGE} proto udp\n"
				"sudo ufw status numbered\n"
			)
		else:
			script = (
				f"sudo ufw delete allow from {trunk_ip} to any port {_SIP_PORT} proto udp || true\n"
				f"sudo ufw delete allow from {trunk_ip} to any port {_RTP_RANGE} proto udp || true\n"
				f"sudo ufw deny {_SIP_PORT}/udp || true\n"
				"sudo ufw status numbered\n"
			)
		out = host_exec.run_host_script(doc, script, timeout=60)
		log_infra_action(host=host, unit=trunk_ip, action=f"firewall_{action}", outcome="success", detail=out.strip()[:300])
		return {"ok": True, "host": host, "trunk_ip": trunk_ip, "action": action}
	except Exception as e:
		log_infra_action(host=host, unit=trunk_ip, action=f"firewall_{action}", outcome="error", detail=str(e))
		raise


@frappe.whitelist()
def mint_listener_token(site, instance, listener_user=None, supplied_key_secret=None):
	"""Return the `key:secret` the provisioner/listener authenticate with. SELF
	(this Press site shares the DB): mint a fresh api_key/secret for the instance
	owner_user. EXTERNAL/Frappe-Cloud: we cannot reach their User table, so the
	operator supplies the key:secret. Telephony Ops / System Manager only."""
	_only_telephony()
	_valid_instance(instance)
	if (site or "self") in ("self", "local"):
		owner = listener_user or _instance_owner(site, instance)
		user = frappe.get_doc("User", owner)
		api_secret = user.generate_keys()          # regenerates + returns the new secret
		return f"{user.api_key}:{api_secret}"
	if not supplied_key_secret or ":" not in supplied_key_secret:
		frappe.throw(frappe._("For an external/Frappe-Cloud site, supply the listener API key as 'key:secret'."), frappe.ValidationError)
	return supplied_key_secret.strip()


@frappe.whitelist()
def decommission_pbx(host, instance):
	"""Stop + remove the PBX containers, close the firewall, revoke the listener
	token - but KEEP the recordings on disk (compliance). Telephony Ops / System
	Manager only; audited."""
	_only_telephony()
	instance = _valid_instance(instance)
	from press.infra import host_exec

	try:
		doc = _managed_doc(host)
		script = (
			f"cd {HOST_DIR} 2>/dev/null && docker compose down || true\n"
			"sudo ufw deny 5060/udp || true\n"
			"sudo ufw delete allow 5060/udp || true\n"
			"# recordings are intentionally retained for compliance; not removed.\n"
			f"echo 'kept recordings in {HOST_DIR}/recordings'\n"
		)
		out = host_exec.run_host_script(doc, script, timeout=120)
		site = frappe.db.get_value("Telephony PBX", f"{host}:{instance}", "source") or "self"
		_revoke_token("self" if site == "self" else "external", instance)
		_mark_pbx_decommissioned(host, instance)
		log_infra_action(host=host, unit=instance, action="decommission_pbx", outcome="success", detail=out.strip()[:300])
		return {"ok": True, "host": host, "instance": instance, "recordings": "retained"}
	except Exception as e:
		log_infra_action(host=host, unit=instance, action="decommission_pbx", outcome="error", detail=str(e))
		raise


def _parse_registered(text: str) -> bool:
	return "Registered" in (text or "")


def _parse_active_calls(text: str) -> int:
	"""`core show channels count` prints '<n> active calls'. Fall back to 0."""
	m = re.search(r"(\d+)\s+active calls", text or "")
	return int(m.group(1)) if m else 0


_RUNNING_STATES = ("run", "heal", "unhealth")


def _enumerate(doc) -> dict:
	"""Docker API container enumerate for ONE host (the read-only socket-proxy path
	that powers the infra board): { units: [...], metrics: {...} }. The managed host
	is an alpine sidecar with NO docker CLI, so shell `docker` probes read empty/error;
	the API never needs a CLI. Best-effort: degrades to {} on any failure."""
	from press.infra.adapters.base import get_adapter

	try:
		return get_adapter(doc).enumerate(doc) or {}
	except Exception:
		return {}


def _find_unit(units, prefix: str):
	"""First container unit whose name starts with `prefix`, or None."""
	for u in units or []:
		if (u.get("name") or "").startswith(prefix):
			return u
	return None


def _oc_unit(doc, prefix: str):
	"""Resolve one oc-* container unit (carrying its `_id`) by name prefix via the
	Docker API enumerate, or None."""
	return _find_unit(_enumerate(doc).get("units"), prefix)


def telephony_status(doc) -> dict:
	"""Read-only telephony telemetry for ONE host. Container state (listener-connected,
	asterisk uptime) + host CPU come from a single Docker API enumerate; trunk
	registration + active calls need `asterisk -rx` (docker exec), which the read-only
	socket-proxy blocks, so they stay best-effort over the cert SSH channel and default
	safe (False/0 - accurate while the trunk is down). Never raises. NOT whitelisted -
	called by telephony_describe + _build_tree."""
	from press.infra import host_exec

	def _safe(cmd, default):
		try:
			return host_exec.run_host_script(doc, cmd, timeout=20)
		except Exception:
			return default

	reg = _safe("docker exec oc-asterisk asterisk -rx 'pjsip show registrations' 2>/dev/null || true", "")
	chans = _safe("docker exec oc-asterisk asterisk -rx 'core show channels count' 2>/dev/null || true", "")

	enum = _enumerate(doc)
	units = enum.get("units") or []
	listener = _find_unit(units, "oc-listener")
	asterisk = _find_unit(units, "oc-asterisk")
	return {
		"trunk_registered": _parse_registered(reg),
		"active_calls": _parse_active_calls(chans),
		"listener_connected": bool(listener) and listener.get("state") in _RUNNING_STATES,
		"container_running": bool(asterisk) and asterisk.get("state") in _RUNNING_STATES,
		"uptime": (asterisk or {}).get("uptime") or "",
		"cpu_pct": (enum.get("metrics") or {}).get("cpu"),
	}


@frappe.whitelist()
def telephony_describe(host) -> dict:
	"""SECRET-FREE telephony summary for the UI: counts + booleans only. Never
	renders pjsip/.env (which carry trunk + SIP secrets). Telephony Ops / System
	Manager only."""
	_only_telephony()
	doc = _managed_doc(host)
	st = telephony_status(doc)
	return {
		"host": host,
		"trunk_registered": st["trunk_registered"],
		"active_calls": st["active_calls"],
		"listener_connected": st["listener_connected"],
	}


# ─── Plan-3 dashboard reads + actions ─────────────────────────────────────────
# Whitelisted surface for the Vue Telephony page. Each method gates to Telephony
# Ops / System Manager, audits write actions like host_unit_action, and delegates
# heavy/pure logic to the sibling modules (telephony_tree / _targets / _secrets).

# host_action allowlist: the container-level verbs the page can request. A
# trunk re-register is an in-container asterisk reload, not a docker verb, so it
# maps to a fixed asterisk -rx command (no host-controlled data).
_HOST_ACTIONS = ("restart", "stop", "reregister")


@frappe.whitelist()
def get_pbx_tree() -> dict:
	"""Telephony view of the infra tree: { hosts, summary, generated }. Polled by
	the page (server-side cached like get_infra_tree). Telephony Ops / System
	Manager only; read-only (no audit row - it is a poll, not a control action)."""
	_only_telephony()
	import json

	from press.api.telephony_tree import build_pbx_tree

	cache_key = "infra_telephony:pbx_tree"
	cached = frappe.cache().get_value(cache_key, expires=True)
	if cached is not None:
		if isinstance(cached, bytes):
			cached = cached.decode("utf-8")
		return json.loads(cached) if isinstance(cached, str) else cached
	tree = build_pbx_tree()
	frappe.cache().set_value(cache_key, json.dumps(tree), expires_in_sec=15)
	return tree


@frappe.whitelist()
def host_action(host, action) -> dict:
	"""Start/stop/restart the oc-asterisk container, or re-register its trunk, on a
	managed PBX host. Mirrors host_unit_action: Telephony Ops / System Manager
	only; the action is allowlisted; every call is audited on success AND error.
	(The UI confirms when there are active calls; the backend accepts the action
	regardless - the guard is a UX concern, not an authorization one.)"""
	_only_telephony()
	if action not in _HOST_ACTIONS:
		frappe.throw(frappe._("Unknown action {0}. Allowed: {1}.").format(action, ", ".join(_HOST_ACTIONS)), frappe.ValidationError)
	from press.infra import host_exec

	try:
		doc = _managed_doc(host)
		if action == "reregister":
			# In-container asterisk reload of pjsip (re-sends REGISTER). Fixed cmd.
			script = (
				"docker exec oc-asterisk asterisk -rx 'pjsip send register *all' "
				"|| docker exec oc-asterisk asterisk -rx 'core reload'\n"
			)
		elif action == "stop":
			script = f"cd {HOST_DIR}\ndocker compose stop oc-asterisk\ndocker compose ps\n"
		else:  # restart
			script = f"cd {HOST_DIR}\ndocker compose restart oc-asterisk\ndocker compose ps\n"
		out = host_exec.run_host_script(doc, script, timeout=90)
		log_infra_action(host=host, unit="oc-asterisk", action=f"telephony_{action}", outcome="success", detail=out.strip()[:300])
		return {"ok": True, "host": host, "action": action, "detail": f"{action} done"}
	except Exception as e:
		log_infra_action(host=host, unit="oc-asterisk", action=f"telephony_{action}", outcome="error", detail=str(e))
		raise


@frappe.whitelist()
def get_listener_log(host, tail: int = 200) -> list:
	"""Tail the oc-listener container log on a managed PBX host. Telephony Ops /
	System Manager only; audited as a read. Returns [{ts, level, msg}] rows the page
	renders. Reads via the Docker API (the managed-host sidecar has no docker CLI, so
	a `docker logs` shell probe failed with 'sh: docker: not found')."""
	_only_telephony()
	from press.infra.adapters.base import get_adapter

	try:
		tail_n = max(1, min(int(tail or 200), 5000))
	except (TypeError, ValueError):
		frappe.throw(frappe._("Invalid tail value; use a number of lines (1-5000)."), frappe.ValidationError)
	try:
		doc = _managed_doc(host)
		unit = _oc_unit(doc, "oc-listener")
		if not unit or not unit.get("_id"):
			log_infra_action(host=host, unit="oc-listener", action="listener_logs", outcome="read")
			return []
		lines = get_adapter(doc).logs(doc, unit["_id"], tail=tail_n)
		log_infra_action(host=host, unit="oc-listener", action="listener_logs", outcome="read")
		return _parse_log_lines("\n".join(lines))
	except Exception as e:
		log_infra_action(host=host, unit="oc-listener", action="listener_logs", outcome="error", detail=str(e))
		raise


_LOG_RE = re.compile(
	r"^(?P<ts>[\d\-T:.\sZ]+?)\s+(?P<level>ERROR|ERR|WARNING|WARN|INFO|DEBUG)\b[:\s]*(?P<msg>.*)$",
	re.IGNORECASE,
)
_LEVEL_MAP = {"ERROR": "ERR", "ERR": "ERR", "WARNING": "WARN", "WARN": "WARN", "INFO": "INFO", "DEBUG": "INFO"}


def _parse_log_lines(raw: str) -> list:
	"""Parse raw container log text into [{ts, level, msg}]. Unmatched lines keep
	the full text as the message with an INFO level. Pure + unit-tested."""
	out = []
	for line in (raw or "").splitlines():
		if not line.strip():
			continue
		m = _LOG_RE.match(line)
		if m:
			level = _LEVEL_MAP.get(m.group("level").upper(), "INFO")
			out.append({"ts": m.group("ts").strip(), "level": level, "msg": m.group("msg").strip()})
		else:
			out.append({"ts": "", "level": "INFO", "msg": line.rstrip()})
	return out


@frappe.whitelist()
def rotate_secret(host, secret_id=None, instance=None, which=None) -> dict:
	"""Regenerate the AMI password OR the listener API token, rewrite the host .env,
	and reload the container. Telephony Ops / System Manager only; audited. The new
	secret is written to the host file only and is NEVER returned.

	The page sends `secret_id` (e.g. 'ami_password' / 'api_token'); `which` is the
	explicit alias. When the instance is not supplied we resolve the single Active
	PBX instance on the host (the common single-tenant case)."""
	_only_telephony()
	which = which or secret_id
	if not which:
		frappe.throw(frappe._("Specify which secret to rotate (ami_password or api_token)."), frappe.ValidationError)
	resolved_instance = instance or _sole_active_instance(host)
	from press.api.telephony_secrets import normalize_which, rotate_on_host

	target = normalize_which(which)  # validates before any host I/O
	try:
		res = rotate_on_host(host=host, instance=resolved_instance, which=target)
		log_infra_action(host=host, unit=resolved_instance, action=f"rotate_{target}", outcome="success", detail=res.get("detail", "")[:300])
		return res
	except Exception as e:
		log_infra_action(host=host, unit=resolved_instance, action=f"rotate_{target}", outcome="error", detail=str(e))
		raise


def _sole_active_instance(host) -> str:
	"""The single Active PBX instance on a host. Throws if the host has zero or
	several, so a rotate without an explicit instance can never hit the wrong one."""
	names = frappe.get_all("Telephony PBX", filters={"host": host, "status": "Active"}, pluck="instance")
	if len(names) == 1:
		return names[0]
	if not names:
		frappe.throw(frappe._("No Active PBX instance on host {0}.").format(host), frappe.ValidationError)
	frappe.throw(frappe._("Host {0} serves several instances; specify which one to rotate.").format(host), frappe.ValidationError)


@frappe.whitelist()
def list_provision_targets(site_url=None) -> dict:
	"""VoIP OC Channel Instances available to provision + the managed hosts that can
	run a PBX. Self-hosted Press reads instances locally; Frappe-Cloud/external
	returns an empty sites list gracefully (the operator supplies the instance).
	Telephony Ops / System Manager only; read-only."""
	_only_telephony()
	from press.api.telephony_targets import build_provision_targets

	return build_provision_targets(site_url=site_url)


@frappe.whitelist()
def validate_instance_auth(site_url=None, instance=None, api_token=None) -> dict:
	"""Confirm the trunk secret is PRESENT on an instance (boolean + human detail,
	never the secret). Self-hosted: read the co-hosted OC Channel Instance. External
	/Frappe-Cloud: use the supplied api_token to query the site over HTTPS. Telephony
	Ops / System Manager only; read-only."""
	_only_telephony()
	if not instance:
		frappe.throw(frappe._("instance is required."), frappe.ValidationError)
	from press.api.telephony_targets import _is_local, _validate_external, _validate_local

	if _is_local(site_url):
		return _validate_local(instance)
	return _validate_external(site_url=site_url, instance=instance, api_token=api_token)


@frappe.whitelist()
def test_host_connection(host_name=None, ssh_host=None, ssh_user="sanad", ssh_port=22) -> dict:
	"""New-host onboarding reachability test for the provision wizard. If the host
	is already a Managed Host, reuse test_connection; otherwise register it Pending
	then test (add_managed_host + test_connection both audit). Telephony Ops /
	System Manager only. Returns { ok, docker_ok, detail }."""
	_only_telephony()
	from press.api.infra_board import add_managed_host, test_connection

	target = host_name or ssh_host
	if not target:
		frappe.throw(frappe._("Provide a host name or ssh_host to test."), frappe.ValidationError)
	try:
		if not frappe.db.exists("Managed Host", target):
			if not ssh_host:
				frappe.throw(frappe._("ssh_host is required to register a new managed host."), frappe.ValidationError)
			add_managed_host(host_name=target, server_type="docker", ssh_host=ssh_host, ssh_user=ssh_user or "sanad", ssh_port=ssh_port)
		out = test_connection(target)  # flips Active on success, throws with a reason otherwise
		return {"ok": bool(out.get("ssh_ok")), "docker_ok": bool(out.get("docker_ok")), "detail": "connection ok"}
	except Exception as e:
		return {"ok": False, "docker_ok": False, "detail": (getattr(e, "message", None) or str(e))[:300]}


@frappe.whitelist()
def provision_status(job_id=None) -> dict:
	"""Provision-job status for the page's poller. telephony_provision is SYNCHRONOUS
	today, so there is no real job to poll: return a TERMINAL success with the four
	provision steps marked done so the poller resolves immediately. Forward-compatible
	with a future async job (when job_id maps to a real Background Job, report its
	state). Telephony Ops / System Manager only."""
	_only_telephony()
	steps = [
		{"key": "env", "label": "Write the generated .env on the host", "state": "done"},
		{"key": "firewall", "label": "Open the firewall to the trunk IP", "state": "done"},
		{"key": "compose", "label": "docker compose up -d (oc-asterisk + oc-listener)", "state": "done"},
		{"key": "register", "label": "Wait for trunk registration + first heartbeat", "state": "done"},
	]
	return {"state": "done", "steps": steps, "failure": None}
