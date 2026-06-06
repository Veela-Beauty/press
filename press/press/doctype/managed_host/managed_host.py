# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import frappe
from frappe.model.document import Document


class ManagedHost(Document):
	def validate(self):
		import re

		if not re.match(r"^[a-zA-Z0-9._-]+$", self.host_name or ""):
			frappe.throw("Host Name must match ^[a-zA-Z0-9._-]+$ (it becomes the SSH cert principal)")
		if self.ssh_user and not re.match(r"^(?!-)[a-zA-Z0-9._-]+$", self.ssh_user):
			frappe.throw("ssh_user may contain only letters, digits, dot, underscore, hyphen, and must not start with '-'")
		if self.ssh_host and not re.match(r"^(?!-)[a-zA-Z0-9._:-]+$", self.ssh_host):
			frappe.throw("ssh_host may contain only letters, digits, dot, colon, underscore, hyphen, and must not start with '-'")
		for _port, _label in ((self.ssh_port, "SSH Port"), (self.proxy_port, "Socket-Proxy Port")):
			if _port and not (1 <= frappe.utils.cint(_port) <= 65535):
				frappe.throw(f"{_label} must be between 1 and 65535")

	def before_insert(self):
		if not self.host_principal:
			self.host_principal = self.host_name
