# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class DemoInviteCode(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		code: DF.Data
		email: DF.Data | None
		enabled: DF.Check
		expires_on: DF.Date | None
		max_uses: DF.Int
		notes: DF.SmallText | None
		used_count: DF.Int
	# end: auto-generated types
	pass
