"""Add admin panel custom fields to Database Server DocType.

Mirrors press/press/doctype/server/server_admin_setup.py — same pattern,
same field names. The is_decommissioned flag was previously only on
tabServer, forcing every cron that filters DB servers to walk to the
linked app Server to check its flag (see press/utils/decom.py and the
2026-05-21 incident).

After this is installed, Database Server has its own flag and crons can
filter directly: `frappe.get_all('Database Server',
{'status': 'Active', 'is_decommissioned': 0}, ...)`.

Backfill: `add_is_decommissioned_to_database_server` patch populates the
flag from the linked app Server's flag on first run.

Sync: a Server.on_update hook propagates the flag to linked Database
and Proxy Servers, so future decommission actions on the app Server
stay in sync.
"""
import frappe

DATABASE_SERVER_ADMIN_FIELDS = [
    {"fieldname": "is_decommissioned", "label": "Decommissioned",
     "fieldtype": "Check", "default": "0",
     "description": "Soft-archive: excluded from scheduled crons "
                    "(binlog sync, MariaDB stalks, etc.). Auto-set when "
                    "the linked app Server is decommissioned.",
     "insert_after": "is_self_hosted"},
]


def setup_database_server_admin_fields():
    """Idempotent: add admin custom fields to Database Server if missing."""
    for field_def in DATABASE_SERVER_ADMIN_FIELDS:
        cf_name = f"Database Server-{field_def['fieldname']}"
        if frappe.db.exists("Custom Field", cf_name):
            continue
        doc = {**field_def, "doctype": "Custom Field", "dt": "Database Server"}
        frappe.get_doc(doc).insert(ignore_permissions=True)
    frappe.db.commit()
