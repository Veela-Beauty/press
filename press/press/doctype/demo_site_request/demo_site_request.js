// Copyright (c) 2026, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on("Demo Site Request", {
	refresh(frm) {
		// Approve button — only for Pending requests
		if (frm.doc.request_status === "Pending") {
			frm.add_custom_button(__("Approve & Send Invite"), function () {
				frappe.confirm(
					__("Approve this request and send invite code to <b>{0}</b>?", [frm.doc.email]),
					function () {
						frappe.call({
							method: "press.api.demo.approve_request",
							args: { request_name: frm.doc.name },
							freeze: true,
							freeze_message: __("Approving and sending invite code..."),
							callback: function (r) {
								if (r.message) {
									frappe.msgprint({
										title: __("Approved"),
										message: r.message.message || __("Invite code sent successfully"),
										indicator: "green",
									});
									frm.reload_doc();
								}
							},
						});
					}
				);
			}, __("Actions")).addClass("btn-primary-dark");

			frm.add_custom_button(__("Reject"), function () {
				var d = new frappe.ui.Dialog({
					title: __("Reject Demo Request"),
					fields: [
						{
							fieldname: "reason",
							fieldtype: "Small Text",
							label: __("Rejection Reason (sent to client)"),
							reqd: 1,
							default: "Thank you for your interest. Unfortunately, we are unable to process your demo request at this time.",
						},
					],
					primary_action_label: __("Reject & Notify"),
					primary_action: function (values) {
						d.hide();
						frappe.call({
							method: "press.api.demo.reject_request",
							args: {
								request_name: frm.doc.name,
								reason: values.reason,
							},
							freeze: true,
							freeze_message: __("Rejecting and sending notification..."),
							callback: function (r) {
								if (r.message) {
									frappe.msgprint({
										title: __("Rejected"),
										message: r.message.message || __("Rejection email sent"),
										indicator: "orange",
									});
									frm.reload_doc();
								}
							},
						});
					},
				});
				d.show();
			}, __("Actions"));
		}

		// Status indicator
		if (frm.doc.request_status === "Approved") {
			frm.dashboard.set_headline(
				__('<span style="color:#059669;">Approved — Invite code sent to {0}</span>', [frm.doc.email])
			);
		} else if (frm.doc.request_status === "Rejected") {
			frm.dashboard.set_headline(
				__('<span style="color:#dc2626;">Rejected</span>')
			);
		} else if (frm.doc.request_status === "Pending") {
			frm.dashboard.set_headline(
				__('<span style="color:#d97706;">Pending Review</span>')
			);
		}

		// Requirements summary
		if (frm.doc.requirements_submitted && frm.doc.requirements && frm.doc.requirements.length) {
			frm.dashboard.add_comment(
				__("{0} requirements submitted", [frm.doc.requirements.length]),
				"blue",
				true
			);
		}
	},
});
