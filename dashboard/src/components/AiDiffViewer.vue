<template>
	<div v-if="localFiles.length > 0" class="rounded-lg border border-gray-200 bg-white">
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
			<div class="flex items-center gap-2">
				<i class="fa fa-code-fork text-sm text-blue-600"></i>
				<span class="text-sm font-semibold">Code Changes</span>
				<span class="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600">
					{{ localFiles.length }} file{{ localFiles.length > 1 ? 's' : '' }}
				</span>
			</div>
			<div class="flex items-center gap-2">
				<button
					class="rounded px-2 py-1 text-xs font-medium text-green-700 transition-colors hover:bg-green-50"
					:disabled="applying"
					@click="approveAll"
				>
					<i class="fa fa-check mr-1"></i>Approve All
				</button>
				<button
					class="rounded px-2 py-1 text-xs font-medium text-red-700 transition-colors hover:bg-red-50"
					@click="rejectAll"
				>
					<i class="fa fa-times mr-1"></i>Reject All
				</button>
			</div>
		</div>

		<!-- File tabs -->
		<div class="flex overflow-x-auto border-b border-gray-100 bg-gray-50 px-2">
			<button
				v-for="(file, i) in localFiles"
				:key="file.path"
				class="flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-xs font-medium transition-colors"
				:class="activeTab === i
					? 'border-blue-500 text-blue-700 bg-white'
					: 'border-transparent text-gray-500 hover:text-gray-700'"
				@click="activeTab = i"
			>
				<i :class="fileIcon(file)" class="text-[10px]"></i>
				<span>{{ fileName(file.path) }}</span>
				<span
					v-if="file.decision"
					:class="{
						'text-green-600': file.decision === 'approved',
						'text-red-600': file.decision === 'rejected',
					}"
				>
					<i :class="file.decision === 'approved' ? 'fa fa-check' : 'fa fa-times'"></i>
				</span>
			</button>
		</div>

		<!-- Active file diff -->
		<div v-if="activeFile" class="relative">
			<!-- File path + per-file actions -->
			<div class="flex items-center justify-between bg-gray-50 px-4 py-2">
				<span class="font-mono text-xs text-gray-600">{{ activeFile.path }}</span>
				<div class="flex items-center gap-2">
					<span class="text-[10px] text-gray-400">
						+{{ activeFile.additions || 0 }} / -{{ activeFile.deletions || 0 }}
					</span>
					<button
						aria-label="Approve this file"
						class="rounded px-2 py-0.5 text-xs font-medium text-green-700 hover:bg-green-50"
						:class="activeFile.decision === 'approved' ? 'bg-green-100' : ''"
						@click="setDecision(activeTab, 'approved')"
					>
						<i class="fa fa-check"></i>
					</button>
					<button
						aria-label="Reject this file"
						class="rounded px-2 py-0.5 text-xs font-medium text-red-700 hover:bg-red-50"
						:class="activeFile.decision === 'rejected' ? 'bg-red-100' : ''"
						@click="setDecision(activeTab, 'rejected')"
					>
						<i class="fa fa-times"></i>
					</button>
				</div>
			</div>

			<!-- Diff content -->
			<div class="max-h-[400px] overflow-auto">
				<table class="w-full font-mono text-xs">
					<tbody>
						<tr
							v-for="(line, li) in activeFile.lines"
							:key="li"
							:class="{
								'bg-green-50': line.type === 'add',
								'bg-red-50': line.type === 'remove',
								'bg-white': line.type === 'context',
								'bg-blue-50': line.type === 'header',
							}"
						>
							<td class="w-10 select-none px-2 text-right text-gray-400">
								{{ line.oldNum || '' }}
							</td>
							<td class="w-10 select-none px-2 text-right text-gray-400">
								{{ line.newNum || '' }}
							</td>
							<td class="w-4 select-none text-center"
								:class="{
									'text-green-600': line.type === 'add',
									'text-red-600': line.type === 'remove',
								}"
							>
								{{ line.type === 'add' ? '+' : line.type === 'remove' ? '-' : '' }}
							</td>
							<td class="whitespace-pre-wrap px-2 py-0.5">{{ line.text }}</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<!-- Apply button -->
		<div class="flex items-center justify-between border-t border-gray-100 px-4 py-3">
			<div class="text-xs text-gray-500">
				{{ approvedCount }} approved, {{ rejectedCount }} rejected, {{ pendingCount }} pending
			</div>
			<button
				class="rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700 disabled:bg-gray-300"
				:disabled="approvedCount === 0 || applying"
				@click="applyApproved"
			>
				<i v-if="applying" class="fa fa-spinner fa-spin mr-1"></i>
				<i v-else class="fa fa-check mr-1"></i>
				Apply {{ approvedCount }} file{{ approvedCount !== 1 ? 's' : '' }}
			</button>
		</div>
	</div>
</template>

<script>
export default {
	name: 'AiDiffViewer',
	props: {
		files: {
			type: Array,
			default: () => [],
			// Each file: { path, lines: [{type, text, oldNum, newNum}], additions, deletions, decision }
		},
		benchName: { type: String, default: '' },
		branch: { type: String, default: '' },
		sessionId: { type: String, default: '' },
	},
	emits: ['apply', 'applied'],
	data() {
		return {
			localFiles: [],
			activeTab: 0,
			applying: false,
		};
	},
	watch: {
		files: {
			immediate: true,
			handler(val) {
				this.localFiles = val.map(f => ({ ...f }));
			},
		},
	},
	computed: {
		activeFile() {
			return this.localFiles[this.activeTab] || null;
		},
		approvedCount() {
			return this.localFiles.filter(f => f.decision === 'approved').length;
		},
		rejectedCount() {
			return this.localFiles.filter(f => f.decision === 'rejected').length;
		},
		pendingCount() {
			return this.localFiles.filter(f => !f.decision).length;
		},
	},
	methods: {
		setDecision(index, decision) {
			if (this.localFiles[index]) {
				this.localFiles[index].decision = decision;
			}
		},
		approveAll() {
			this.localFiles.forEach(f => { f.decision = 'approved'; });
		},
		rejectAll() {
			this.localFiles.forEach(f => { f.decision = 'rejected'; });
		},
		fileName(path) {
			return path.split('/').pop();
		},
		fileIcon(file) {
			const ext = file.path.split('.').pop();
			const icons = { py: 'fa fa-file-code-o', js: 'fa fa-file-code-o', vue: 'fa fa-file-code-o', json: 'fa fa-file-text-o', csv: 'fa fa-file-excel-o' };
			return icons[ext] || 'fa fa-file-o';
		},
		async applyApproved() {
			const approved = this.localFiles.filter(f => f.decision === 'approved');
			if (approved.length === 0) return;

			this.applying = true;
			this.$emit('apply', {
				files: approved.map(f => f.path),
				bench_name: this.benchName,
				branch: this.branch,
				session_id: this.sessionId,
			});
			// Reset after emit — parent handles completion
			setTimeout(() => { this.applying = false; }, 5000);
		},
	},
};
</script>
