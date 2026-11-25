"""Revoked SSH keys for development benches.

A development bench gets 30-day SSH certificates, and an OpenSSH certificate cannot be called back once signed. So
every minute every Active bench of a group with a development bench or a live 30-day certificate (the certificate's
principal is the group, so it opens all of them) is sent the public keys that still hold a valid certificate for it
but must not reach it any more: the user left the team or was disabled, the key was disabled or removed, the user's
Press Role no longer covers the group, or the team's SSH access was turned off. The bench's sshd reads that file
(RevokedKeys) at every login. The line is added to the bench's sshd_config once, checked with `sshd -t`, then sshd
reloads; if the reload fails the line is taken out again, so the next run retries.
"""

import base64
import hashlib
import re

import frappe
from frappe.utils import add_days, now_datetime

from press.utils import log_error

SSH_DIR = "/home/frappe/frappe-bench/config/ssh"
CACHE_KEY = "press:ssh_revoked_keys:{}"
RESEND_SECONDS = 3600  # sent again at least hourly, in case the file was changed on the bench
RETRY_SECONDS = 300  # after a failure: one Error Log, then the bench waits 5 minutes
_PLAIN_KEY = re.compile(
	r"^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(256|384|521)|sk-ssh-ed25519@openssh\.com"
	r"|sk-ecdsa-sha2-nistp256@openssh\.com) [A-Za-z0-9+/]+={0,2}$"
)


def sync_development_benches():
	for bench in benches_to_cover():
		failed = CACHE_KEY.format(bench.name) + ":failed"
		if frappe.cache.get_value(failed):
			continue
		try:
			sync_bench(bench.name, bench.group)
		except Exception:
			frappe.cache.set_value(failed, 1, expires_in_sec=RETRY_SECONDS)
			log_error("SSH revoked keys sync failed", bench=bench.name)


def benches_to_cover() -> list:
	dev_groups = frappe.get_all("Bench", {"status": "Active", "is_development_bench": 1}, pluck="group")
	long_groups = frappe.get_all(
		"SSH Certificate",
		{"certificate_type": "User", "validity": "30d", "valid_until": (">", add_days(now_datetime(), -1))},
		pluck="group",
		distinct=True,
	)
	groups = sorted({g for g in dev_groups + long_groups if g})
	if not groups:
		return []
	return frappe.get_all("Bench", {"status": "Active", "group": ("in", groups)}, ["name", "group"])


def sync_bench(bench: str, group: str) -> bool:
	content = "".join(f"{key}\n" for key in keys_to_revoke(group))
	digest = hashlib.sha256(content.encode()).hexdigest()
	if frappe.cache.get_value(CACHE_KEY.format(bench)) == digest:
		return False
	result = frappe.get_doc("Bench", bench).docker_execute(write_command(content))
	if result.get("returncode") != 0:  # the agent reports a non-zero exit as status Success
		frappe.throw(f"Writing revoked SSH keys failed ({result.get('returncode')}): {result.get('output')}")
	frappe.cache.set_value(CACHE_KEY.format(bench), digest, expires_in_sec=RESEND_SECONDS)
	return True


def keys_to_revoke(group: str) -> list[str]:
	team = frappe.db.get_value("Release Group", group, "team")
	certificates = frappe.db.sql(
		"""select c.user, c.ssh_public_key, k.name as key_name, k.is_disabled, k.is_removed, u.enabled
		from `tabSSH Certificate` c
		left join `tabUser SSH Key` k on k.name = c.user_ssh_key
		left join `tabUser` u on u.name = c.user
		where c.group = %s and c.certificate_type = 'User' and c.valid_until > %s""",
		# a day of margin: valid_until is the signing box's local time; a key listed a day longer does no harm
		(group, add_days(now_datetime(), -1)),
		as_dict=True,
	)
	reach = {}
	bad, good = set(), set()
	for c in certificates:
		if c.user not in reach:
			reach[c.user] = reaches(c.user, team, group)
		cut = not c.key_name or c.is_disabled or c.is_removed or not c.enabled or not reach[c.user]
		(bad if cut else good).add(plain_key(c.ssh_public_key))
	# sshd revokes the key, not one certificate: a key with a certificate in good standing (re-added after removal)
	# stays off the list, or its owner is locked out; whoever holds that private key may use that certificate anyway
	return sorted(key for key in bad - good if key)


def reaches(user: str, team: str | None, group: str) -> bool:
	"""role_guard's answer for this user (it reads the session; a scheduled job has none): on the enabled team with SSH
	access on (generate_certificate's own check), and the team has no roles, or he owns it, or one of his roles gives
	admin access, all benches or lists this bench, or the team is relaxed and he has no role."""
	if not user:
		return False
	if frappe.db.get_value("User", user, "user_type") == "System User":
		return True
	fields = ["user", "enabled", "relaxed_permissions", "ssh_access_enabled"]
	t = frappe.db.get_value("Team", team, fields, as_dict=True) if team else None
	if not t or not t.enabled or not t.ssh_access_enabled:
		return False
	if t.user == user:
		return True
	if not frappe.db.exists("Team Member", {"parenttype": "Team", "parent": team, "user": user}):
		return False
	return _roles_reach(user, team, group, bool(t.relaxed_permissions))


def _roles_reach(user: str, team: str, group: str, relaxed: bool) -> bool:
	if not frappe.db.exists("Press Role", {"team": team}):
		return True
	mine = frappe.get_all("Press Role User", {"parenttype": "Press Role", "user": user}, pluck="parent")
	roles = (
		frappe.get_all(
			"Press Role", {"name": ("in", mine), "team": team}, ["name", "admin_access", "all_release_groups"]
		)
		if mine
		else []
	)
	if not roles:
		return relaxed
	if any(r.admin_access or r.all_release_groups for r in roles):
		return True
	return bool(
		frappe.db.exists(
			"Press Role Resource",
			{
				"parenttype": "Press Role",
				"parent": ("in", [r.name for r in roles]),
				"document_type": "Release Group",
				"document_name": group,
			},
		)
	)


def plain_key(public_key: str | None) -> str | None:
	"""The key's type and body only: the comment is free text and never reaches the bench's shell."""
	line = " ".join((public_key or "").split()[:2])
	return line if _PLAIN_KEY.match(line) else None


def write_command(content: str) -> str:
	b64 = base64.b64encode(content.encode()).decode()  # [A-Za-z0-9+/=]: safe inside the single quotes
	d = SSH_DIR
	script = (
		f"echo {b64} | base64 -d > {d}/revoked_keys.new && mv {d}/revoked_keys.new {d}/revoked_keys && "
		f'if ! grep -q "^RevokedKeys " {d}/sshd_config; then '
		f"cp {d}/sshd_config {d}/sshd_config.before-revoked-keys && "
		f'echo "RevokedKeys {d}/revoked_keys" >> {d}/sshd_config && '
		f"if /usr/sbin/sshd -t -f {d}/sshd_config && kill -HUP $(cat {d}/sshd.pid); then :; "
		f"else cp {d}/sshd_config.before-revoked-keys {d}/sshd_config; exit 3; fi; fi"
	)
	return f"bash -c '{script}'"
