# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Short-TTL SSH certificate signer (R1/R4).

The CA private key lives in Infisical, never on disk in the repo and never in a
doctype. We pull it just-in-time, sign an 8h cert scoped to one per-host
principal, and let it expire. A stolen cert is useless within a workday.
"""
from __future__ import annotations

import subprocess

CERT_TTL = "+8h"


def _ca_private_key() -> str:
	"""Path to the CA private key, materialised from Infisical at call time."""
	from press.infra.secrets import get_infisical_secret

	return get_infisical_secret("infra/ssh_ca_private")


def sign_cert(principal: str, pubkey_path: str) -> str:
	"""Sign `pubkey_path` with the CA, scoped to `principal`, valid for CERT_TTL.
	Returns the path to the generated `*-cert.pub`.
	"""
	ca = _ca_private_key()
	cmd = [
		"ssh-keygen", "-s", ca,
		"-I", f"infra-{principal}",
		"-n", principal,
		"-V", CERT_TTL,
		pubkey_path,
	]
	result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
	if result.returncode != 0:
		raise RuntimeError(f"ssh-keygen sign failed: {result.stderr}")
	return pubkey_path.replace(".pub", "-cert.pub")
