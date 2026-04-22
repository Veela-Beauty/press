"""Add admin panel custom fields to Server DocType."""
import frappe

SERVER_ADMIN_FIELDS = [
    {"fieldname": "admin_panel_section", "label": "Admin Panel", "fieldtype": "Section Break",
     "insert_after": "ip", "collapsible": 1},
    {"fieldname": "monthly_cost_override", "label": "Monthly Cost Override (€)",
     "fieldtype": "Currency", "default": "0",
     "description": "0 = use hardcoded SERVER_COSTS baseline. Non-zero overrides it.",
     "insert_after": "admin_panel_section"},
    {"fieldname": "is_decommissioned", "label": "Decommissioned", "fieldtype": "Check",
     "default": "0",
     "description": "Soft-archive: excluded from cost rollup and from new site provisioning.",
     "insert_after": "monthly_cost_override"},
    {"fieldname": "column_break_admin_server", "fieldtype": "Column Break",
     "insert_after": "is_decommissioned"},
    {"fieldname": "admin_notes", "label": "Admin Notes", "fieldtype": "Small Text",
     "description": "Free-form notes for ops team (e.g. contract end date, vendor ticket).",
     "insert_after": "column_break_admin_server"},
]


def setup_server_admin_fields():
    """Idempotent: add admin custom fields to Server if missing."""
    for field_def in SERVER_ADMIN_FIELDS:
        cf_name = f"Server-{field_def['fieldname']}"
        if frappe.db.exists("Custom Field", cf_name):
            continue
        doc = {**field_def, "doctype": "Custom Field", "dt": "Server"}
        frappe.get_doc(doc).insert(ignore_permissions=True)
    frappe.db.commit()
