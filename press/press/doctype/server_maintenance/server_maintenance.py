# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
import subprocess

import frappe
from frappe.model.document import Document

MAINT = "/opt/sanad/maintenance.sh"


def _run_maint(action, *args):
	"""Invoke the root-owned maintenance script via the fixed sudoers grant and
	return its single RESULT line (the script validates all input)."""
	cmd = ["sudo", "-n", MAINT, action, *[str(a) for a in args]]
	r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
	out = f"{r.stdout}\n{r.stderr}".strip()
	for line in out.splitlines():
		if line.startswith("RESULT"):
			return line.replace("RESULT", "", 1).strip()
	return (out[-200:] or "no output").strip()


class ServerMaintenance(Document):
	@frappe.whitelist()
	def run_registry_gc(self):
		frappe.only_for("System Manager")
		res = _run_maint("registry-gc")
		self.db_set("registry_gc_last_run", frappe.utils.now_datetime())
		self.db_set("registry_gc_last_result", res)
		return res

	@frappe.whitelist()
	def run_backup_retention(self, apply=0):
		frappe.only_for("System Manager")
		args = [int(self.backup_retention_keep_days or 7)]
		if frappe.utils.cint(apply):
			args.append("--apply")
		res = _run_maint("backup-retention", *args)
		self.db_set("backup_retention_last_run", frappe.utils.now_datetime())
		self.db_set("backup_retention_last_result", res)
		return res


def run_scheduled_registry_gc():
	doc = frappe.get_single("Server Maintenance")
	if not doc.registry_gc_enabled:
		return
	interval = int(doc.registry_gc_interval_days or 7)
	last = doc.registry_gc_last_run
	if last and (frappe.utils.now_datetime() - last).days < interval:
		return
	doc.run_registry_gc()


def run_scheduled_backup_retention():
	doc = frappe.get_single("Server Maintenance")
	if not doc.backup_retention_enabled:
		return
	doc.run_backup_retention(apply=1)
