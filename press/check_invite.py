import frappe

def run():
    doc = frappe.get_doc("Demo Invite Code", "ACCU-DEMO-2026")
    print(f"Code: {doc.code}, Enabled: {doc.enabled}, Used: {doc.used_count}, Expires: {doc.expires_on}")

    reqs = frappe.get_all("Demo Site Request", fields=["company", "email", "site", "invite_code"], limit=5)
    print(f"\nDemo Site Requests ({len(reqs)}):")
    for r in reqs:
        print(f"  {r.company} | {r.email} | {r.site} | code: {r.invite_code}")
