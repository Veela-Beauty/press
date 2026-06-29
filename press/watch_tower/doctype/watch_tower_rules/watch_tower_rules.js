// Copyright (c) 2026, Lipton and contributors
// For license information, please see license.txt

frappe.ui.form.on('Watch Tower Rules', {
	refresh(frm) {
		// Populate Python Method dropdown
		if (frm.doc.evaluation_mode === 'Python Method') {
			populate_method_options(frm);
		}
		// "Evaluate Now" button -  always visible for saved, enabled rules
		if (!frm.is_new() && frm.doc.enabled) {
			frm.add_custom_button(__('Evaluate Now'), function () {
				frappe.confirm(
					__('Run this rule against all matching documents now? This will be queued as a background job.'),
					function () {
						frm.call('evaluate_now').then(() => {
							frm.reload_doc();
						});
					}
				);
			}, __('Actions'));
		}

		// "Dry Run" button -  test rule without writing
		if (!frm.is_new()) {
			frm.add_custom_button(__('Dry Run'), function () {
				frappe.call({
					method: 'tamkeen_suite_app.watch_tower.engine.dry_run_rule',
					args: { rule_name: frm.doc.name, limit: 100 },
					freeze: true,
					freeze_message: __('Evaluating rule (read-only)...'),
					callback(r) {
						if (!r.message) return;
						let data = r.message;
						let html = `<div style="margin-bottom:12px;">
							<strong>${data.total_candidates}</strong> candidates,
							<strong>${data.evaluated}</strong> evaluated,
							<strong>${data.matched}</strong> matched.
							${data.truncated ? '<span class="text-warning">(truncated to 100)</span>': ''}
						</div>`;

						if (!data.results.length) {
							html += '<p class="text-muted">No documents matched this rule.</p>';
						} else {
							html += `<table class="table table-bordered table-sm" style="font-size:12px;">
							<thead><tr><th>#</th><th>Document</th><th>Why Matched</th><th>Would Do</th></tr></thead><tbody>`;
							data.results.forEach(function (row, i) {
								let link = `<a href="/app/${frappe.router.slug(frm.doc.target_doctype)}/${row.name}">${row.display_name}</a>`;
								html += `<tr><td>${i + 1}</td><td>${link}</td><td>${row.details || ''}</td><td>${row.actions}</td></tr>`;
							});
							html += '</tbody></table>';
						}

						frappe.msgprint({
							title: __('Dry Run Results'),
							message: html,
							wide: true
						});
					}
				});
			}, __('Actions'));
		}

		// "View Alert Logs" button
		if (!frm.is_new()) {
			frm.add_custom_button(__('View Alert Logs'), function () {
				frappe.set_route('List', 'Watch Tower Alert Log', {
					rule: frm.doc.name
				});
			}, __('Actions'));
		}

		// "Preview Audit Scores" -  dry-run for audit_critical_customers rule
		if (!frm.is_new() && (frm.doc.condition_method || "").includes("audit_critical_customers")) {
			frm.add_custom_button(__('Preview Audit Scores'), function () {
				let d = new frappe.ui.Dialog({
					title: __("Preview Audit Scores"),
					fields: [
						{
							fieldname: "source",
							label: __("Data Source"),
							fieldtype: "Select",
							options: "YP (synced data)\nData Lake (Supabase direct)",
							default: "YP (synced data)",
							reqd: 1,
							description: __("YP uses already-synced Customer fields. Data Lake queries Supabase directly -  useful when sync hasn't run yet.")
						},
						{
							fieldname: "limit",
							label: __("Max Results"),
							fieldtype: "Int",
							default: 30
						}
					],
					primary_action_label: __("Run Preview"),
					primary_action(values) {
						d.hide();
						let is_datalake = values.source.includes("Data Lake");
						let method = is_datalake
							? "tamkeen_suite_app.watch_tower.rules.audit_critical.preview_audit_scores_datalake": "tamkeen_suite_app.watch_tower.rules.audit_critical.preview_audit_scores";

						frappe.call({
							method: method,
							args: { limit: values.limit || 30 },
							freeze: true,
							freeze_message: is_datalake
								? __("Fetching from Data Lake and scoring..."): __("Scoring from YP data..."),
							callback(r) {
								if (!r.message) return;
								let data = r.message;
								let html = `<div style="margin-bottom:12px;">
									<span class="badge badge-info">${data.source || "Unknown"}</span>
									<strong>${data.total_evaluated}</strong> customers evaluated,
									<strong>${data.total_with_score}</strong> with score &gt; 0.
									Showing top ${data.results.length}:
								</div>`;

								html += `<table class="table table-bordered table-sm" style="font-size:12px;">
								<thead><tr>
									<th>#</th><th>Customer</th><th>Score</th>
									<th>C1 Overdue</th><th>C2 Credit</th>
									<th>C3 Discount</th><th>C4 Volume</th>
									<th>Outstanding</th><th>Credit Limit</th>
								</tr></thead><tbody>`;

								data.results.forEach(function (row, i) {
									let link = is_datalake
										? row.customer_name || row.customer: `<a href="/app/customer/${row.customer}">${row.customer_name || row.customer}</a>`;
									html += `<tr>
										<td>${i + 1}</td>
										<td>${link}</td>
										<td><strong>${row.score}</strong>/100</td>
										<td>${row.c1_overdue}/25</td>
										<td>${row.c2_credit}/25</td>
										<td>${row.c3_discount}/25</td>
										<td>${row.c4_volume}/25</td>
										<td>${format_currency(row.outstanding)}</td>
										<td>${format_currency(row.credit_limit)}</td>
									</tr>`;
								});
								html += "</tbody></table>";

								frappe.msgprint({
									title: __("Audit Score Preview -  {0}", [data.source]),
									message: html,
									wide: true
								});
							}
						});
					}
				});
				d.show();
			}, __('Actions'));
		}

		// Dashboard status indicator
		if (frm.doc.last_run_status) {
			let color_map = {
				'Success': 'green',
				'Partial Success': 'orange',
				'Failed': 'red',
				'No Matches': 'blue',
				'Running': 'yellow'
			};
			frm.dashboard.add_indicator(
				__('Last Run: {0}', [frm.doc.last_run_status]),
				color_map[frm.doc.last_run_status] || 'grey'
			);
		}

		// Show last run summary as a comment
		if (frm.doc.last_result_summary && frm.doc.last_evaluated_at) {
			frm.set_intro(
				__('Last evaluated: {0} -  {1}', [
					frappe.datetime.str_to_user(frm.doc.last_evaluated_at),
					frm.doc.last_result_summary
				]),
				frm.doc.last_run_status === 'Success' ? 'green': frm.doc.last_run_status === 'Failed' ? 'red': 'blue'
			);
		}

		// Listen for realtime progress updates
		if (frm.doc.last_run_status === 'Running') {
			// Clean up previous listener before binding new one
			if (frm._wt_progress_handler) {
				frappe.realtime.off('watch_tower_progress', frm._wt_progress_handler);
			}
			frm._wt_progress_handler = (data) => {
				if (data.rule === frm.doc.name) {
					frappe.show_progress(
						__('Evaluating Rule'),
						data.evaluated,
						data.total,
						__('{0} of {1} docs evaluated, {2} matched', [
							data.evaluated, data.total, data.matched
						])
					);
					if (data.evaluated >= data.total) {
						setTimeout(() => frm.reload_doc(), 2000);
					}
				}
			};
			frappe.realtime.on('watch_tower_progress', frm._wt_progress_handler);
		}
	},

	before_unload(frm) {
		if (frm._wt_progress_handler) {
			frappe.realtime.off('watch_tower_progress', frm._wt_progress_handler);
			delete frm._wt_progress_handler;
		}
	},

	evaluation_mode(frm) {
		if (frm.doc.evaluation_mode === 'Python Method') {
			populate_method_options(frm);
		} else {
			frm.set_value('script_description', '');
		}
	},

	condition_method(frm) {
		fetch_method_description(frm);
		apply_method_defaults(frm);
	},

	target_doctype(frm) {
		// Clear condition fields when DocType changes
		frm.set_value('condition_field', '');
		frm.set_value('condition_expression', '');
		frm.set_value('condition_script', '');
		frm.set_value('condition_method', '');
		frm.set_value('target_filters_json', '');
	}
});

function populate_method_options(frm) {
	frappe.call({
		method: 'tamkeen_suite_app.watch_tower.doctype.watch_tower_rules.watch_tower_rules.get_available_methods',
		callback(r) {
			if (r.message) {
				frm.set_df_property('condition_method', 'options', '\n' + r.message);
				if (frm.doc.condition_method) {
					fetch_method_description(frm);
				}
			}
		}
	});
}

function fetch_method_description(frm) {
	if (!frm.doc.condition_method) {
		frm.set_value('script_description', '');
		return;
	}
	frappe.call({
		method: 'tamkeen_suite_app.watch_tower.doctype.watch_tower_rules.watch_tower_rules.get_method_description',
		args: { method_path: frm.doc.condition_method },
		callback(r) {
			frm.set_value('script_description', r.message || '');
		}
	});
}

function apply_method_defaults(frm) {
	if (!frm.doc.condition_method) return;
	frappe.call({
		method: 'tamkeen_suite_app.watch_tower.doctype.watch_tower_rules.watch_tower_rules.get_method_defaults',
		args: { method_path: frm.doc.condition_method },
		callback(r) {
			let defaults = r.message;
			if (!defaults || !Object.keys(defaults).length) return;

			// Auto-set target DocType
			if (defaults.target_doctype && !frm.doc.target_doctype) {
				frm.set_value('target_doctype', defaults.target_doctype);
			}

			// Auto-set filters
			if (defaults.target_filters_json && !frm.doc.target_filters_json) {
				frm.set_value('target_filters_json', defaults.target_filters_json);
			}

			// Auto-populate actions child table
			if (defaults.actions && defaults.actions.length && !frm.doc.actions.length) {
				defaults.actions.forEach(function (action) {
					let row = frm.add_child('actions');
					row.action_type = action.action_type || 'Set Field Value';
					row.target_field = action.target_field || '';
					row.field_value = action.field_value || '';
					row.overwrite_existing = action.overwrite_existing || 0;
				});
				frm.refresh_field('actions');
			}

			// Clear actions if method handles writes and user has stale actions
			if (defaults.method_handles_writes && frm.doc.actions.length) {
				frappe.show_alert({
					message: __('This method writes fields directly. Actions table can be left empty.'),
					indicator: 'blue'
				}, 7);
			}

			// Show note about what this method does
			if (defaults.note) {
				frappe.show_alert({
					message: defaults.note,
					indicator: 'blue'
				}, 10);
			}
		}
	});
}
