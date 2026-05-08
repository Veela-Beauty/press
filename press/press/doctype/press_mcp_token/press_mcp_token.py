# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class PressMCPToken(Document):
	def is_active(self) -> bool:
		if self.revoked:
			return False
		return self.expires_at > now_datetime()
