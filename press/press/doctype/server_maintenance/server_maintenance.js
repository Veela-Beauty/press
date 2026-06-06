frappe.ui.form.on("Server Maintenance", {
	refresh(frm) {
		frm.add_custom_button(__("Registry GC Now"), () => {
			frappe.confirm(__("Run Docker registry garbage collection now? The registry restarts briefly."), () => {
				frm.call("run_registry_gc").then((r) => {
					frappe.msgprint({ title: __("Registry GC"), message: r.message, indicator: "green" });
					frm.reload_doc();
				});
			});
		}, __("Run Now"));
		frm.add_custom_button(__("Backup Retention (Dry Run)"), () => {
			frm.call("run_backup_retention", { apply: 0 }).then((r) => {
				frappe.msgprint({ title: __("Backup Retention - dry run"), message: r.message, indicator: "blue" });
				frm.reload_doc();
			});
		}, __("Run Now"));
		frm.add_custom_button(__("Backup Retention (Apply)"), () => {
			frappe.confirm(__("Permanently delete backups older than the retention window? The newest backup per site is always kept."), () => {
				frm.call("run_backup_retention", { apply: 1 }).then((r) => {
					frappe.msgprint({ title: __("Backup Retention - applied"), message: r.message, indicator: "orange" });
					frm.reload_doc();
				});
			});
		}, __("Run Now"));
	},
});
