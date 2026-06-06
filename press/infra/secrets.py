# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Fork-local secret accessor for the infra control plane.

Resolves a named secret to a readable FILE PATH (ssh-keygen -s needs a path).
Gate 0 injects the CA key via one of two env vars (sourced from Infisical at
deploy time); we never persist it in the DB or a doctype.

Resolution order for a name:
1. <PATH_ENV> points at a mounted key file -> return that path.
2. <VALUE_ENV> holds the key material -> materialize to a 0600 file in the
   site's private dir -> return the path.
3. Otherwise frappe.throw, so onboarding honestly reports the host Unreachable
   until Gate 0 is provisioned."""
from __future__ import annotations

import hashlib
import os

import frappe

# name -> (path-env, value-env)
_ENV = {
	"infra/ssh_ca_private": ("SANAD_SSH_CA_PRIVATE_PATH", "SANAD_SSH_CA_PRIVATE"),
}


def get_infisical_secret(name: str) -> str:
	path_env, value_env = _ENV.get(name, (None, None))
	if not path_env:
		frappe.throw(f"Unknown infra secret {name!r}")
	mounted = os.environ.get(path_env)
	if mounted:
		if not os.path.exists(mounted):
			frappe.throw(f"infra secret {name}: {path_env}={mounted} does not exist")
		return mounted
	value = os.environ.get(value_env)
	if value:
		return _materialize(name, value)
	frappe.throw(f"infra secret {name} is not provisioned (set {path_env} or {value_env}); Gate 0 pending")


def _materialize(name: str, value: str) -> str:
	safe = hashlib.sha256(name.encode()).hexdigest()[:16]
	d = frappe.get_site_path("private", "infra-secrets")
	os.makedirs(d, exist_ok=True)
	os.chmod(d, 0o700)
	path = os.path.join(d, safe)
	data = value if value.endswith("\n") else value + "\n"
	if not (os.path.exists(path) and open(path).read() == data):
		fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
		with os.fdopen(fd, "w") as f:
			f.write(data)
	os.chmod(path, 0o600)
	return path
