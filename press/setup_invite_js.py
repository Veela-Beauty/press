import frappe

def run():
    # 1. Verify tables exist now
    for t in ["tabDemo Invite Code", "tabDemo Site Request"]:
        print(f"{t}: {'EXISTS' if frappe.db.table_exists(t) else 'MISSING'}")

    # 2. Re-insert the demo request that was lost when table was recreated
    if frappe.db.count("Demo Site Request") == 0:
        frappe.get_doc({
            "doctype": "Demo Site Request",
            "company": "Elixeum Test",
            "email": "eng.elgogary@gmail.com",
            "phone": "",
            "site": "elixeum-test.sandbox.mvpstorm.com",
            "invite_code": "ACCU-DEMO-2026",
        }).insert(ignore_permissions=True)
        print("Re-inserted demo request for Elixeum Test")

    # 3. Re-insert the invite code
    if frappe.db.count("Demo Invite Code") == 0:
        from frappe.utils import add_days, nowdate
        frappe.get_doc({
            "doctype": "Demo Invite Code",
            "code": "ACCU-DEMO-2026",
            "enabled": 1,
            "expires_on": add_days(nowdate(), 90),
            "max_uses": 0,
            "used_count": 1,
            "notes": "Default invite code — unlimited uses, 90 day expiry",
        }).insert(ignore_permissions=True)
        print("Re-inserted invite code ACCU-DEMO-2026")

    # 4. Write client script for Demo Invite Code to show linked sites
    js_code = """
frappe.ui.form.on("Demo Invite Code", {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Demo Site Request",
                    filters: { invite_code: frm.doc.code },
                    fields: ["company", "email", "site", "creation"],
                    order_by: "creation desc",
                    limit_page_length: 50
                },
                callback: function(r) {
                    var rows = r.message || [];
                    var html = "";
                    if (rows.length === 0) {
                        html = '<div class="text-muted">No sites created with this code yet.</div>';
                    } else {
                        html = '<table class="table table-bordered table-sm" style="margin:0">';
                        html += '<thead><tr><th>Company</th><th>Email</th><th>Site</th><th>Created</th></tr></thead><tbody>';
                        rows.forEach(function(r) {
                            var site_link = r.site ? '<a href="/app/site/' + r.site + '">' + r.site + '</a>' : '-';
                            html += '<tr><td>' + (r.company||'-') + '</td><td>' + (r.email||'-') + '</td><td>' + site_link + '</td><td>' + frappe.datetime.str_to_user(r.creation) + '</td></tr>';
                        });
                        html += '</tbody></table>';
                    }
                    frm.fields_dict.sites_html.$wrapper.html(html);
                }
            });
        }
    }
});
"""
    # Write the JS file
    js_path = "/home/frappe/frappe-bench/apps/press/press/press/doctype/demo_invite_code/demo_invite_code.js"
    with open(js_path, "w") as f:
        f.write(js_code)
    print(f"Wrote client script to {js_path}")

    frappe.db.commit()
    print("Done")
