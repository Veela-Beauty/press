"""Add admin panel custom fields to Proxy Server DocType.

Mirrors press/press/doctype/server/server_admin_setup.py — same pattern.
See database_server_admin_setup.py for the full rationale.
"""
import frappe

PROXY_SERVER_ADMIN_FIELDS = [
    {"fieldname": "is_decommissioned", "label": "Decommissioned",
     "fieldtype": "Check", "default": "0",
     "description": "Soft-archive: excluded from scheduled crons. "
                    "Auto-set when ALL linked app Servers are decommissioned.",
     "insert_after": "is_self_hosted"},
]


def setup_proxy_server_admin_fields():
    """Idempotent: add admin custom fields to Proxy Server if missing."""
    for field_def in PROXY_SERVER_ADMIN_FIELDS:
        cf_name = f"Proxy Server-{field_def['fieldname']}"
        if frappe.db.exists("Custom Field", cf_name):
            continue
        doc = {**field_def, "doctype": "Custom Field", "dt": "Proxy Server"}
        frappe.get_doc(doc).insert(ignore_permissions=True)
    frappe.db.commit()
