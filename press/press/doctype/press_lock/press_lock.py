# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from datetime import timedelta

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class PressLock(Document):
	def validate(self) -> None:
		if self.ttl_minutes is None or self.ttl_minutes < 1:
			self.ttl_minutes = 30
		if not self.expires_at:
			self.expires_at = now_datetime() + timedelta(minutes=self.ttl_minutes)
		if not self.holder:
			self.holder = frappe.session.user

	def is_active(self) -> bool:
		"""True if not revoked AND not expired."""
		if self.revoked:
			return False
		return self.expires_at > now_datetime()
