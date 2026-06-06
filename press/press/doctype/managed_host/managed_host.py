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

	def before_insert(self):
		if not self.host_principal:
			self.host_principal = self.host_name
