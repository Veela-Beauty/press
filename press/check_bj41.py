import frappe

def run():
    logs = frappe.get_all("Backup Run Log",
        filters={"backup_job": "BJ-00041"},
        fields=["name", "mode", "status", "exit_code", "raw_tail", "error_json", "creation"],
        order_by="creation desc", limit=5)
    if not logs:
        print("No run logs for BJ-00041")
    for l in logs:
        print("---", l.name, l.mode, l.status, l.exit_code, l.creation)
        if l.raw_tail:
            print("  raw_tail:", l.raw_tail[:300])
        if l.error_json:
            print("  error:", l.error_json[:300])
