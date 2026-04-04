<template>
	<div class="space-y-4">
		<div class="rounded-lg bg-blue-50 px-4 py-2 text-xs text-blue-700">
			<i class="fa fa-lightbulb-o mr-1"></i>
			<strong>Team overrides</strong> — these settings override role defaults for this team only.
		</div>

		<!-- Token & Access Overrides -->
		<div class="text-xs font-semibold text-gray-700">
			<i class="fa fa-sliders mr-1"></i> Token & Access Overrides
		</div>
		<div class="grid grid-cols-2 gap-3">
			<div class="rounded-lg border border-gray-200 p-3">
				<label class="text-[10px] font-medium text-gray-500">Team Token Cap / Day</label>
				<input
					v-model.number="settings.token_cap"
					type="number"
					class="mt-1 w-full rounded border border-gray-200 px-2 py-1 text-sm"
					placeholder="Use role default"
				>
				<p class="mt-1 text-[10px] text-gray-400">0 = use role default</p>
			</div>
			<div class="rounded-lg border border-gray-200 p-3">
				<label class="text-[10px] font-medium text-gray-500">AI on Production Sites</label>
				<select v-model="settings.prod_access" class="mt-1 w-full rounded border border-gray-200 px-2 py-1 text-sm">
					<option value="role_default">Use role default</option>
					<option value="blocked">Blocked</option>
					<option value="read_only">Read-only</option>
				</select>
			</div>
		</div>

		<!-- Team-level toggles -->
		<div class="rounded-lg border border-gray-200 p-3">
			<div class="flex items-center justify-between">
				<div>
					<p class="text-xs font-medium text-gray-700">Block AI on production sites</p>
					<p class="text-[10px] text-gray-400">Override: all team members blocked from AI on prod</p>
				</div>
				<label class="relative inline-flex cursor-pointer items-center">
					<input v-model="settings.block_prod" type="checkbox" class="peer sr-only">
					<div class="h-5 w-9 rounded-full bg-gray-200 after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:bg-blue-600 peer-checked:after:translate-x-full"></div>
				</label>
			</div>
			<div class="mt-3 flex items-center justify-between">
				<div>
					<p class="text-xs font-medium text-gray-700">Block app install/uninstall via AI</p>
					<p class="text-[10px] text-gray-400">Prevent AI from suggesting app management commands</p>
				</div>
				<label class="relative inline-flex cursor-pointer items-center">
					<input v-model="settings.block_app_mgmt" type="checkbox" class="peer sr-only">
					<div class="h-5 w-9 rounded-full bg-gray-200 after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:bg-blue-600 peer-checked:after:translate-x-full"></div>
				</label>
			</div>
		</div>

		<!-- Team Leader for escalations -->
		<div class="rounded-lg border border-gray-200 p-3">
			<label class="text-[10px] font-medium text-gray-500">Team Leader for AI Escalations</label>
			<select v-model="settings.escalation_tl" class="mt-1 w-full rounded border border-gray-200 px-2 py-1 text-sm">
				<option value="">Team owner (default)</option>
				<option v-for="m in members" :key="m.user" :value="m.user">{{ m.full_name || m.user }}</option>
			</select>
		</div>

		<!-- Save -->
		<div class="flex justify-end">
			<button
				class="rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:bg-gray-300"
				:disabled="saving"
				@click="save"
			>
				<i v-if="saving" class="fa fa-spinner fa-spin mr-1"></i>
				<i v-else class="fa fa-save mr-1"></i>
				Save AI Overrides
			</button>
		</div>
	</div>
</template>

<script>
export default {
	name: 'AiTeamRules',
	props: {
		team: { type: String, required: true },
		members: { type: Array, default: () => [] },
	},
	emits: ['saved'],
	data() {
		return {
			saving: false,
			settings: {
				token_cap: 0,
				prod_access: 'role_default',
				block_prod: true,
				block_app_mgmt: false,
				escalation_tl: '',
			},
		};
	},
	methods: {
		async save() {
			this.saving = true;
			try {
				if (window.call) {
					await window.call('press.press.ai.api.update_team_ai_rules', {
						team: this.team,
						settings: JSON.stringify(this.settings),
					});
				}
				this.$emit('saved');
			} finally {
				this.saving = false;
			}
		},
	},
};
</script>
