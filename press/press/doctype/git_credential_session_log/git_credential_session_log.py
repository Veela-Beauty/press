# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import TYPE_CHECKING

import frappe
from frappe.model.document import Document

if TYPE_CHECKING:
	from frappe.types import DF


class GitCredentialSessionLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		bench: DF.Data | None
		error_message: DF.SmallText | None
		name: DF.Int | None
		success: DF.Check
		timestamp: DF.Datetime
		user: DF.Link
	# end: auto-generated types
	pass


def log_credential_request(user: str, bench: str, success: bool, error_message: str | None = None):
	"""Fire-and-forget audit event. Swallows errors to avoid blocking git-setup."""
	try:
		doc = frappe.new_doc("Git Credential Session Log")
		doc.user = user
		doc.bench = bench
		doc.success = 1 if success else 0
		doc.timestamp = frappe.utils.now()
		if error_message:
			doc.error_message = str(error_message)[:1000]
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.log_error(title="GitCredentialSessionLog insert failed")
