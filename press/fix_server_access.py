import frappe

def fix():
    frappe.set_user("Administrator")
    team = "sqkn1globp"

    # Add credits to the team
    team_doc = frappe.get_doc("Team", team)
    print(f"Team: {team}")
    print(f"  enabled: {team_doc.enabled}")
    print(f"  free_account: {getattr(team_doc, 'free_account', 'N/A')}")
    print(f"  is_saas_user: {getattr(team_doc, 'is_saas_user', 'N/A')}")
    print(f"  billing_team: {getattr(team_doc, 'billing_team', 'N/A')}")

    # Check balance
    balance = frappe.get_all("Balance Transaction",
        filters={"team": team},
        fields=["sum(amount) as total"],
    )
    print(f"  Current balance: {balance[0].total if balance else 0}")

    # Add $500 credit
    bt = frappe.get_doc({
        "doctype": "Balance Transaction",
        "team": team,
        "amount": 500,
        "currency": "USD",
        "type": "Adjustment",
        "description": "Self-hosted credits",
    })
    bt.insert(ignore_permissions=True)
    bt.submit()
    frappe.db.commit()
    print(f"  Added $500 credit")

    # Check new balance
    balance = frappe.get_all("Balance Transaction",
        filters={"team": team, "docstatus": 1},
        fields=["sum(amount) as total"],
    )
    print(f"  New balance: {balance[0].total if balance else 0}")

    # Also enable server feature if there's a flag
    if hasattr(team_doc, "server_access_enabled"):
        team_doc.server_access_enabled = 1
        team_doc.save(ignore_permissions=True)
        frappe.db.commit()
        print(f"  server_access_enabled: set to 1")
