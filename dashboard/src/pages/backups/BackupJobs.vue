<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[{ label: 'Backup Jobs', route: '/backups/jobs' }]"
				/>
			</Header>
		</div>
		<div class="p-5">
			<ObjectList :options="listOptions" />
		</div>
	</div>
</template>

<script>
import ObjectList from '../../components/ObjectList.vue';
import { date } from '../../utils/format';

export default {
	name: 'BackupJobs',
	components: {
		ObjectList,
	},
	computed: {
		listOptions() {
			return {
				doctype: 'Backup Job Queue',
				orderBy: 'queued_at desc',
				fields: [
					'name',
					'job_id',
					'client',
					'mode',
					'priority',
					'status',
					'progress_percent',
					'queued_at',
					'started_at',
					'finished_at',
					'duration_seconds',
					'error_message',
				],
				columns: [
					{
						label: 'Job ID',
						fieldname: 'job_id',
						width: 0.6,
					},
					{
						label: 'Client',
						fieldname: 'client',
						width: 0.8,
					},
					{
						label: 'Mode',
						fieldname: 'mode',
						width: '100px',
						align: 'center',
					},
					{
						label: 'Status',
						fieldname: 'status',
						width: '120px',
						align: 'center',
						type: 'Badge',
					},
					{
						label: 'Progress',
						fieldname: 'progress_percent',
						width: '100px',
						align: 'center',
						format(value) {
							return value ? Math.round(value) + '%' : '-';
						},
					},
					{
						label: 'Priority',
						fieldname: 'priority',
						width: '100px',
						align: 'center',
					},
					{
						label: 'Queued At',
						fieldname: 'queued_at',
						width: 0.8,
						align: 'right',
						format(value) {
							return value ? date(value, 'llll') : '';
						},
					},
				],
				filterControls() {
					return [
						{
							type: 'link',
							label: 'Client',
							fieldname: 'client',
							options: {
								doctype: 'Backup Client',
							},
						},
						{
							type: 'select',
							label: 'Status',
							fieldname: 'status',
							options: ['', 'Queued', 'Running', 'Success', 'Failed', 'Cancelled'],
						},
						{
							type: 'select',
							label: 'Mode',
							fieldname: 'mode',
							options: ['', 'run', 'dry-run', 'check'],
						},
						{
							type: 'select',
							label: 'Priority',
							fieldname: 'priority',
							options: ['', 'Critical', 'High', 'Normal', 'Low'],
						},
					];
				},
			};
		},
	},
};
</script>
