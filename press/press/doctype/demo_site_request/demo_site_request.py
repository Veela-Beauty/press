# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class DemoSiteRequest(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from press.press.doctype.demo_requirement_answer.demo_requirement_answer import DemoRequirementAnswer

		admin_password: DF.Password | None
		company: DF.Data | None
		email: DF.Data | None
		email_sent: DF.Check
		industry: DF.Data | None
		invite_code: DF.Link | None
		phone: DF.Data | None
		request_message: DF.SmallText | None
		request_status: DF.Literal["", "Pending", "Approved", "Site Created", "Rejected"]
		requirements: DF.Table[DemoRequirementAnswer]
		requirements_submitted: DF.Check
		site: DF.Link | None
	# end: auto-generated types
	pass
