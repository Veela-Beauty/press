# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import frappe


def log_infra_action(host: str, unit: str, action: str, outcome: str, detail: str = "") -> None:
	"""Append an immutable audit row for every control action (R5)."""
	frappe.get_doc(
		{
			"doctype": "Infra Action Log",
			"actor": frappe.session.user,
			"host": host,
			"unit": unit,
			"action": action,
			"outcome": outcome,
			"detail": detail,
		}
	).insert(ignore_permissions=True)
	# Durability (R5): commit the audit row in its own right so a later rollback
	# of the control request cannot erase the record of the attempt. Control
	# actions are external (Docker API / SSH), so there is no pending DB write
	# this would wrongly commit.
	frappe.db.commit()


class Adapter:
	"""Normalized host adapter. Every adapter returns the same shapes so the
	aggregator and UI never care how a host is read.
	  enumerate(host) -> {"units": [unit...], "metrics": {"cpu","mem","disk","req"}}
	  control(host, unit_id, action) -> {"ok": bool, ...}
	  logs(host, unit_id, tail) -> list[str]
	A `unit` is {"name","kind"('service'|'container'),"state","sub","uptime","restarts","ports","health","pid"}.
	"""

	def enumerate(self, host) -> dict:  # pragma: no cover - interface
		raise NotImplementedError

	def control(self, host, unit_id: str, action: str) -> dict:  # pragma: no cover
		raise NotImplementedError

	def logs(self, host, unit_id: str, tail: int = 200) -> list:  # pragma: no cover
		raise NotImplementedError


def get_adapter(host) -> "Adapter":
	"""Return the adapter for a MANAGED host (docker/plain). Press benches are
	NOT routed here - they are read directly via get_dev_overview_benches /
	get_processes. This factory is managed-hosts-only by design.
	"""
	from press.infra.adapters.ssh_docker import SshDockerAdapter
	from press.infra.adapters.ssh_plain import SshPlainAdapter

	t = host.get("server_type")
	if t == "docker":
		return SshDockerAdapter()
	if t == "plain":
		return SshPlainAdapter()
	frappe.throw(f"No adapter for server_type {t!r}", frappe.ValidationError)
