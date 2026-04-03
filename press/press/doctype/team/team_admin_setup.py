"""Add admin panel custom fields to Team DocType."""
import frappe

TEAM_QUOTA_FIELDS = [
    {"fieldname": "admin_section", "label": "Admin Controls", "fieldtype": "Section Break",
     "insert_after": "billing_tab", "collapsible": 1},
    {"fieldname": "max_sites", "label": "Max Sites", "fieldtype": "Int",
     "default": "0", "description": "0 = unlimited", "insert_after": "admin_section"},
    {"fieldname": "max_benches", "label": "Max Benches", "fieldtype": "Int",
     "default": "0", "description": "0 = unlimited", "insert_after": "max_sites"},
    {"fieldname": "max_disk_gb", "label": "Max Disk (GB)", "fieldtype": "Float",
     "default": "0", "description": "0 = unlimited", "insert_after": "max_benches"},
    {"fieldname": "column_break_admin", "fieldtype": "Column Break",
     "insert_after": "max_disk_gb"},
    {"fieldname": "allowed_site_types", "label": "Allowed Site Types", "fieldtype": "Small Text",
     "default": "Production\nStaging\nDev\nDemo",
     "description": "One type per line. Leave empty for all types.",
     "insert_after": "column_break_admin"},
    {"fieldname": "enabled_features", "label": "Enabled Features", "fieldtype": "JSON",
     "default": "{}",
     "description": "JSON map of feature_id: true/false",
     "insert_after": "allowed_site_types", "hidden": 1},
]


def setup_admin_fields():
    """Idempotent: add custom fields to Team if missing."""
    for field_def in TEAM_QUOTA_FIELDS:
        cf_name = f"Team-{field_def['fieldname']}"
        if frappe.db.exists("Custom Field", cf_name):
            continue
        doc = {**field_def, "doctype": "Custom Field", "dt": "Team"}
        frappe.get_doc(doc).insert(ignore_permissions=True)
    frappe.db.commit()
