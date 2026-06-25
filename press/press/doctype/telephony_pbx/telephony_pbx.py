# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import re

import frappe
from frappe.model.document import Document


class TelephonyPBX(Document):
	def validate(self):
		# instance becomes part of the on-host dir + .env; keep it shell-safe.
		if self.instance and not re.match(r"^[a-zA-Z0-9._-]+$", self.instance):
			frappe.throw("OC Channel Instance must match ^[a-zA-Z0-9._-]+$")
		if not self.pbx_id:
			self.pbx_id = f"{self.host}:{self.instance}"
