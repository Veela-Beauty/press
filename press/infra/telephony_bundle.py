# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Load the frappe_omnichannel asterisk bundle + render its .env for a host push.

The bundle files are owned by the frappe_omnichannel app (deploy/asterisk/*) and
read from the bench install at provision time, so Press never vendors a stale
copy. render_env builds ONLY the bootstrap .env; the trunk + agent extensions are
pulled by the running provisioner from the ERPNext form (Phase A)."""
from __future__ import annotations

import secrets

import frappe

# Where the bundle lands on the managed host.
HOST_DIR = "/srv/oc-asterisk"

# Bundle files, relative to the frappe_omnichannel app's deploy/asterisk/ dir.
# Keep in sync with frappe_omnichannel/deploy/asterisk/ (see cross-plan dependency).
BUNDLE_FILES = (
	"docker-compose.yml",
	"entrypoint.sh",
	"provisioner.py",
	"listener.py",
	"config/manager.conf.template",
	"config/rtp.conf",
)


def gen_secret(n: int = 32) -> str:
	return secrets.token_urlsafe(n)[:max(n, 24)]


def _read_app_file(rel: str) -> str:
	import os

	base = frappe.get_app_path("frappe_omnichannel", "..", "deploy", "asterisk")
	with open(os.path.join(base, rel)) as fh:
		return fh.read()


def read_bundle() -> dict:
	"""Return {host_dest_path: content} for every bundle file. Raises a clear
	ValidationError if the omnichannel app (or a file) is missing on this bench."""
	files = {}
	try:
		for rel in BUNDLE_FILES:
			files[f"{HOST_DIR}/{rel}"] = _read_app_file(rel)
	except (FileNotFoundError, OSError) as e:
		frappe.throw(
			frappe._("Cannot read the asterisk bundle from frappe_omnichannel ({0}). "
				"Is the app installed on this bench?").format(str(e)),
			frappe.ValidationError,
		)
	return files


def render_env(site_url: str, instance: str, public_ip: str, ami_password: str, api_token: str) -> str:
	"""The bootstrap .env consumed by entrypoint.sh + provisioner.py + listener.py.
	Secrets (ami_password, api_token) are written to the host file only; never
	returned to the caller."""
	return (
		f"AMI_PASSWORD={ami_password}\n"
		f"PUBLIC_IP={public_ip}\n"
		f"OC_SITE={(site_url or '').rstrip('/')}\n"
		f"OC_INSTANCE={instance}\n"
		f"OC_API_TOKEN={api_token}\n"
		"AMI_USER=oc-listener\n"
		"AMI_PORT=5038\n"
		"AMI_HOST=127.0.0.1\n"
		"REC_DIR=/recordings\n"
	)
