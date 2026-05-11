
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
