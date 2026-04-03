import frappe

def check():
    frappe.set_user("Administrator")

    # Check all recent builds
    builds = frappe.get_all("Deploy Candidate Build",
        fields=["name", "deploy_candidate", "status", "creation"],
        order_by="creation desc", limit=5)

    for b in builds:
        print(f"{b.name}: DC={b.deploy_candidate} status={b.status} created={b.creation}")
