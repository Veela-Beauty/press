"""Add site_type custom field to Site DocType."""

import frappe


SITE_TYPE_OPTIONS = "Production\nStaging\nDev\nDemo"


def add_site_type_field():
    """Add site_type custom field to Site DocType if it doesn't exist."""
    if frappe.db.exists("Custom Field", {"dt": "Site", "fieldname": "site_type"}):
        return

    frappe.get_doc({
        "doctype": "Custom Field",
        "dt": "Site",
        "fieldname": "site_type",
        "label": "Site Type",
        "fieldtype": "Select",
        "options": SITE_TYPE_OPTIONS,
        "default": "Production",
        "insert_after": "cluster",
        "in_list_view": 1,
        "in_standard_filter": 1,
        "reqd": 0,
    }).insert(ignore_permissions=True)
    frappe.db.commit()
