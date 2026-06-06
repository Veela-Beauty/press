# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import frappe
from frappe.model.document import Document


class ManagedHost(Document):
	def before_insert(self):
		if not self.host_principal:
			self.host_principal = self.host_name
