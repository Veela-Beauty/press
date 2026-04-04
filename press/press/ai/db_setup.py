"""Press AI DB setup — creates Custom Fields for AI session tracking.

Uses Custom Fields on existing DocTypes rather than new DocTypes
(avoids upstream conflicts, easier to deploy on self-hosted Press).

Tables:
  - press_ai_session: AI chat sessions with provider, tokens, cost
  - press_ai_action_log: Every AI action (file write, DB op) with rollback data
  - press_ai_milestone: Rollback snapshots taken every 60 minutes

All stored as Custom DocType records via frappe.get_doc().insert().
Run setup_ai_tables() once during deployment.
"""

import frappe

# --- Table definitions ---

AI_SESSION_FIELDS = [
    {"fieldname": "session_id", "fieldtype": "Data", "label": "Session ID",
     "reqd": 1, "unique": 1, "in_list_view": 1},
    {"fieldname": "user", "fieldtype": "Data", "label": "User",
     "reqd": 1, "in_list_view": 1},
    {"fieldname": "team", "fieldtype": "Link", "label": "Team",
     "options": "Team"},
    {"fieldname": "site_name", "fieldtype": "Data", "label": "Site"},
    {"fieldname": "bench_name", "fieldtype": "Data", "label": "Bench"},
    {"fieldname": "branch", "fieldtype": "Data", "label": "Branch"},
    {"fieldname": "provider", "fieldtype": "Select", "label": "Provider",
     "options": "\nAnthropic\nOpenAI\nZ.AI\nCustom"},
    {"fieldname": "model", "fieldtype": "Data", "label": "Model"},
    {"fieldname": "api_key_source", "fieldtype": "Select", "label": "Key Source",
     "options": "\nPersonal\nCompany"},
    {"fieldname": "section_tokens", "fieldtype": "Section Break", "label": "Usage"},
    {"fieldname": "input_tokens", "fieldtype": "Int", "label": "Input Tokens", "default": "0"},
    {"fieldname": "output_tokens", "fieldtype": "Int", "label": "Output Tokens", "default": "0"},
    {"fieldname": "total_tokens", "fieldtype": "Int", "label": "Total Tokens",
     "default": "0", "in_list_view": 1},
    {"fieldname": "column_break_cost", "fieldtype": "Column Break"},
    {"fieldname": "estimated_cost", "fieldtype": "Float", "label": "Est. Cost ($)",
     "precision": "4", "default": "0"},
    {"fieldname": "message_count", "fieldtype": "Int", "label": "Messages", "default": "0"},
    {"fieldname": "section_time", "fieldtype": "Section Break", "label": "Timing"},
    {"fieldname": "started_at", "fieldtype": "Datetime", "label": "Started"},
    {"fieldname": "ended_at", "fieldtype": "Datetime", "label": "Ended"},
    {"fieldname": "status", "fieldtype": "Select", "label": "Status",
     "options": "\nActive\nCompleted\nExpired", "default": "Active", "in_list_view": 1},
]

AI_ACTION_LOG_FIELDS = [
    {"fieldname": "session_id", "fieldtype": "Data", "label": "Session ID", "reqd": 1},
    {"fieldname": "action_type", "fieldtype": "Select", "label": "Action Type",
     "options": "\nwrite_file\ndemo_data\nbench_execute\nconfig_change\ngit_commit\nmodule_install",
     "reqd": 1, "in_list_view": 1},
    {"fieldname": "site_name", "fieldtype": "Data", "label": "Site"},
    {"fieldname": "branch", "fieldtype": "Data", "label": "Branch"},
    {"fieldname": "user", "fieldtype": "Data", "label": "User", "in_list_view": 1},
    {"fieldname": "section_detail", "fieldtype": "Section Break", "label": "Details"},
    {"fieldname": "command", "fieldtype": "Small Text", "label": "Command"},
    {"fieldname": "file_path", "fieldtype": "Data", "label": "File Path"},
    {"fieldname": "payload_json", "fieldtype": "Code", "label": "Payload (JSON)",
     "options": "JSON"},
    {"fieldname": "section_rollback", "fieldtype": "Section Break", "label": "Rollback"},
    {"fieldname": "rollback_snapshot", "fieldtype": "Code", "label": "Rollback Snapshot (JSON)",
     "options": "JSON"},
    {"fieldname": "status", "fieldtype": "Select", "label": "Status",
     "options": "\nPending\nExecuted\nRolled Back\nFailed",
     "default": "Pending", "in_list_view": 1},
    {"fieldname": "milestone_id", "fieldtype": "Data", "label": "Milestone ID"},
    {"fieldname": "executed_at", "fieldtype": "Datetime", "label": "Executed At",
     "in_list_view": 1},
]

AI_MILESTONE_FIELDS = [
    {"fieldname": "milestone_id", "fieldtype": "Data", "label": "Milestone ID",
     "reqd": 1, "unique": 1, "in_list_view": 1},
    {"fieldname": "site_name", "fieldtype": "Data", "label": "Site", "in_list_view": 1},
    {"fieldname": "bench_name", "fieldtype": "Data", "label": "Bench"},
    {"fieldname": "branch", "fieldtype": "Data", "label": "Branch", "in_list_view": 1},
    {"fieldname": "user", "fieldtype": "Data", "label": "User"},
    {"fieldname": "session_id", "fieldtype": "Data", "label": "Session ID"},
    {"fieldname": "section_snapshot", "fieldtype": "Section Break", "label": "Snapshot"},
    {"fieldname": "snapshot_json", "fieldtype": "Code", "label": "Snapshot Data (JSON)",
     "options": "JSON"},
    {"fieldname": "action_count", "fieldtype": "Int", "label": "Actions in Milestone",
     "default": "0"},
    {"fieldname": "section_lifecycle", "fieldtype": "Section Break", "label": "Lifecycle"},
    {"fieldname": "created_at", "fieldtype": "Datetime", "label": "Created"},
    {"fieldname": "expires_at", "fieldtype": "Datetime", "label": "Expires"},
    {"fieldname": "status", "fieldtype": "Select", "label": "Status",
     "options": "\nActive\nRolled Back\nExpired\nCleaned",
     "default": "Active", "in_list_view": 1},
]

DOCTYPES = [
    {
        "name": "Press AI Session",
        "module": "Press",
        "fields": AI_SESSION_FIELDS,
        "autoname": "field:session_id",
        "sort_field": "started_at",
        "sort_order": "DESC",
    },
    {
        "name": "Press AI Action Log",
        "module": "Press",
        "fields": AI_ACTION_LOG_FIELDS,
        "autoname": "autoincrement",
        "sort_field": "executed_at",
        "sort_order": "DESC",
    },
    {
        "name": "Press AI Milestone",
        "module": "Press",
        "fields": AI_MILESTONE_FIELDS,
        "autoname": "field:milestone_id",
        "sort_field": "created_at",
        "sort_order": "DESC",
    },
]


def setup_ai_tables():
    """Create Press AI DocTypes if they don't exist. Idempotent."""
    for dt_def in DOCTYPES:
        dt_name = dt_def["name"]
        if frappe.db.exists("DocType", dt_name):
            print(f"  [skip] {dt_name} already exists")
            continue

        fields = []
        for i, field_def in enumerate(dt_def["fields"]):
            fields.append({**field_def, "idx": i + 1})

        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": dt_name,
            "module": dt_def["module"],
            "custom": 1,
            "is_virtual": 0,
            "istable": 0,
            "editable_grid": 0,
            "track_changes": 0,
            "autoname": dt_def.get("autoname", "autoincrement"),
            "sort_field": dt_def.get("sort_field", "modified"),
            "sort_order": dt_def.get("sort_order", "DESC"),
            "fields": fields,
            "permissions": [
                {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
            ],
        })
        doc.insert(ignore_permissions=True)
        print(f"  [created] {dt_name}")

    frappe.db.commit()
    print("Press AI tables setup complete.")


def teardown_ai_tables():
    """Remove Press AI DocTypes. For development/testing only."""
    for dt_def in reversed(DOCTYPES):
        dt_name = dt_def["name"]
        if frappe.db.exists("DocType", dt_name):
            frappe.delete_doc("DocType", dt_name, force=True)
            print(f"  [deleted] {dt_name}")
    frappe.db.commit()
