// Copyright (c) 2022, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('ERPNext Site Settings', {
	refresh: function (frm) {
		frm.add_custom_button(__('Open Site'), () => {
			window.open(`https://accuratesystems.com.sa/dashboard/sites/${frm.doc.site}`);
		});
	},
});
