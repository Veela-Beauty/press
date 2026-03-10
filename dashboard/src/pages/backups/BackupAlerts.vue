<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[{ label: 'Backup Alerts', route: '/backups/alerts' }]"
				/>
				<template #actions>
					<Button variant="solid" @click="showCreateDialog">
						New Alert Rule
					</Button>
				</template>
			</Header>
		</div>
		<div class="p-5">
			<ObjectList :options="listOptions" />
		</div>

		<!-- Create/Edit Dialog -->
		<Dialog v-model="dialogOpen" :options="{ title: editingAlert ? 'Edit Alert Rule' : 'New Alert Rule', size: 'lg' }">
			<template #body-content>
				<div class="space-y-4">
					<FormControl label="Alert Name" v-model="form.alert_name" :required="true" />
					<div class="grid grid-cols-2 gap-4">
						<FormControl label="Priority" type="select" v-model="form.priority"
							:options="[
								{ label: 'Critical', value: 'Critical' },
								{ label: 'High', value: 'High' },
								{ label: 'Medium', value: 'Medium' },
								{ label: 'Low', value: 'Low' },
							]" />
						<FormControl label="Rule Type" type="select" v-model="form.rule_type"
							:options="[
								{ label: 'General Rule', value: 'General Rule' },
								{ label: 'Client Rule', value: 'Client Rule' },
							]" />
					</div>
					<div class="grid grid-cols-2 gap-4">
						<FormControl label="Notification Method" type="select" v-model="form.alert_type"
							:options="[
								{ label: 'Email Only', value: 'Email Only' },
								{ label: 'Webhook Only', value: 'Webhook Only' },
								{ label: 'Both', value: 'Both' },
							]" />
						<FormControl label="Check Frequency" type="select" v-model="form.check_frequency"
							:options="[
								{ label: 'Hourly', value: 'Hourly' },
								{ label: 'Every 6 Hours', value: 'Every 6 Hours' },
								{ label: 'Daily', value: 'Daily' },
								{ label: 'Weekly', value: 'Weekly' },
							]" />
					</div>
					<FormControl v-if="form.alert_type !== 'Webhook Only'"
						label="Email Recipients (comma-separated)" v-model="form.email_recipients" />
					<FormControl v-if="form.alert_type !== 'Email Only'"
						label="Webhook URL" v-model="form.webhook_url" />
					<div class="grid grid-cols-2 gap-4">
						<FormControl label="Max Days Without Backup" type="number" v-model="form.max_days_without_backup" />
						<FormControl label="Max Repo Size (GB)" type="number" v-model="form.max_repo_size_gb" />
					</div>
					<div class="flex gap-4">
						<label class="flex items-center gap-2">
							<input type="checkbox" v-model="form.alert_on_failure" /> Alert on Failure
						</label>
						<label class="flex items-center gap-2">
							<input type="checkbox" v-model="form.alert_on_warning" /> Alert on Warning
						</label>
						<label class="flex items-center gap-2">
							<input type="checkbox" v-model="form.enabled" /> Enabled
						</label>
					</div>
				</div>
			</template>
			<template #actions>
				<Button variant="solid" @click="saveAlert" :loading="saving">
					{{ editingAlert ? 'Update' : 'Create' }}
				</Button>
			</template>
		</Dialog>
	</div>
</template>

<script>
import ObjectList from '../../components/ObjectList.vue';
import { Button, Dialog, FormControl } from 'frappe-ui';
import { date } from '../../utils/format';

const emptyForm = () => ({
	alert_name: '',
	priority: 'Medium',
	rule_type: 'General Rule',
	alert_type: 'Email Only',
	check_frequency: 'Daily',
	email_recipients: '',
	webhook_url: '',
	max_days_without_backup: 3,
	max_repo_size_gb: 100,
	alert_on_failure: true,
	alert_on_warning: false,
	enabled: true,
});

export default {
	name: 'BackupAlerts',
	components: { ObjectList, Button, Dialog, FormControl },
	data() {
		return {
			dialogOpen: false,
			editingAlert: null,
			form: emptyForm(),
			saving: false,
		};
	},
	methods: {
		showCreateDialog() {
			this.editingAlert = null;
			this.form = emptyForm();
			this.dialogOpen = true;
		},
		async showEditDialog(alertName) {
			try {
				const res = await fetch(`/api/method/daman_backup.daman_backup.press_api.get_alert_detail?alert_name=${encodeURIComponent(alertName)}`, {
					headers: { 'X-Frappe-CSRF-Token': window.csrf_token },
				});
				const data = await res.json();
				if (data.message) {
					this.editingAlert = alertName;
					this.form = { ...emptyForm(), ...data.message };
					this.dialogOpen = true;
				}
			} catch (e) {
				this.$toast({ title: 'Failed to load alert', variant: 'error' });
			}
		},
		async saveAlert() {
			this.saving = true;
			try {
				const method = this.editingAlert
					? 'daman_backup.daman_backup.press_api.update_alert'
					: 'daman_backup.daman_backup.press_api.create_alert';
				const args = { ...this.form };
				if (this.editingAlert) args.alert_name_id = this.editingAlert;

				const res = await fetch(`/api/method/${method}`, {
					method: 'POST',
					headers: {
						'Content-Type': 'application/json',
						'X-Frappe-CSRF-Token': window.csrf_token,
					},
					body: JSON.stringify(args),
				});
				const data = await res.json();
				if (data.message) {
					this.$toast({ title: this.editingAlert ? 'Alert updated' : 'Alert created', variant: 'success' });
					this.dialogOpen = false;
					this.$forceUpdate();
				}
			} catch (e) {
				this.$toast({ title: 'Failed to save alert', variant: 'error' });
			} finally {
				this.saving = false;
			}
		},
		async toggleAlert(alertName, enabled) {
			try {
				await fetch('/api/method/daman_backup.daman_backup.press_api.toggle_alert', {
					method: 'POST',
					headers: {
						'Content-Type': 'application/json',
						'X-Frappe-CSRF-Token': window.csrf_token,
					},
					body: JSON.stringify({ alert_name: alertName, enabled: enabled ? 0 : 1 }),
				});
				this.$toast({ title: enabled ? 'Alert disabled' : 'Alert enabled', variant: 'success' });
			} catch (e) {
				this.$toast({ title: 'Failed to toggle alert', variant: 'error' });
			}
		},
		async deleteAlert(alertName) {
			if (!confirm(`Delete alert "${alertName}"?`)) return;
			try {
				await fetch('/api/method/daman_backup.daman_backup.press_api.delete_alert', {
					method: 'POST',
					headers: {
						'Content-Type': 'application/json',
						'X-Frappe-CSRF-Token': window.csrf_token,
					},
					body: JSON.stringify({ alert_name: alertName }),
				});
				this.$toast({ title: 'Alert deleted', variant: 'success' });
				this.$forceUpdate();
			} catch (e) {
				this.$toast({ title: 'Failed to delete alert', variant: 'error' });
			}
		},
	},
	computed: {
		listOptions() {
			const self = this;
			return {
				doctype: 'Backup Alert Rule',
				orderBy: 'modified desc',
				fields: [
					'name', 'alert_name', 'priority', 'alert_type',
					'check_frequency', 'enabled', 'last_triggered',
					'trigger_count',
				],
				columns: [
					{
						label: 'Alert Name',
						fieldname: 'alert_name',
						width: 1,
					},
					{
						label: 'Priority',
						fieldname: 'priority',
						width: '120px',
						align: 'center',
						type: 'Badge',
					},
					{
						label: 'Method',
						fieldname: 'alert_type',
						width: '120px',
						align: 'center',
					},
					{
						label: 'Frequency',
						fieldname: 'check_frequency',
						width: '120px',
						align: 'center',
					},
					{
						label: 'Enabled',
						fieldname: 'enabled',
						width: '80px',
						type: 'Icon',
						Icon(value) {
							return value ? 'check' : '';
						},
					},
					{
						label: 'Last Triggered',
						fieldname: 'last_triggered',
						width: 0.8,
						format(value) {
							return value ? date(value, 'lll') : 'Never';
						},
					},
					{
						label: 'Count',
						fieldname: 'trigger_count',
						width: '80px',
						align: 'center',
					},
				],
				filterControls() {
					return [
						{
							type: 'select',
							label: 'Priority',
							fieldname: 'priority',
							options: ['', 'Critical', 'High', 'Medium', 'Low'],
						},
						{
							type: 'checkbox',
							label: 'Enabled',
							fieldname: 'enabled',
						},
					];
				},
				rowActions({ row }) {
					return [
						{
							label: 'Edit',
							onClick() { self.showEditDialog(row.name); },
						},
						{
							label: row.enabled ? 'Disable' : 'Enable',
							onClick() { self.toggleAlert(row.name, row.enabled); },
						},
						{
							label: 'Delete',
							onClick() { self.deleteAlert(row.name); },
						},
					];
				},
			};
		},
	},
};
</script>
