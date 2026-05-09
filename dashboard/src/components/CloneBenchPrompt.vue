<template>
	<Dialog v-model="show" :options="dialogOptions">
		<template #body-content>
			<div class="space-y-4">
				<p class="text-sm text-gray-600">
					Apps will be copied from
					<span class="font-medium">{{ sourceLabel }}</span>.
					Pick how you want the new Release Group set up.
				</p>

				<FormControl
					label="Name for the new Release Group"
					v-model="newTitle"
					required
					autocomplete="off"
				/>

				<!-- Two mode options -->
				<div class="space-y-2">
					<label
						v-for="opt in modeOptions"
						:key="opt.value"
						class="flex items-start gap-2 cursor-pointer rounded border p-3"
						:class="mode === opt.value ? 'border-blue-400 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'"
					>
						<input
							type="radio"
							name="clone-mode"
							:value="opt.value"
							v-model="mode"
							class="mt-1"
						/>
						<div class="flex-1">
							<div class="text-sm font-medium text-gray-900">
								{{ opt.label }}
								<span v-if="opt.recommended" class="ml-1 inline-flex items-center rounded-full bg-green-100 px-1.5 py-0.5 text-[10px] font-medium text-green-800">
									recommended
								</span>
							</div>
							<div class="mt-0.5 text-xs text-gray-600">{{ opt.description }}</div>
						</div>
					</label>
				</div>

				<ErrorMessage :message="errorMsg" />
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { ref, computed } from 'vue';
import { Dialog, FormControl, ErrorMessage, call, toast } from 'frappe-ui';

const props = defineProps({
	sourceReleaseGroup: { type: String, required: true },
	sourceLabel: { type: String, required: true },
});
const emit = defineEmits(['cloned']);

const show = ref(true);
const newTitle = ref(`${props.sourceLabel} (copy)`);
const mode = ref('full');
const submitting = ref(false);
const errorMsg = ref('');

const modeOptions = [
	{
		value: 'full',
		label: 'Clone + auto-deploy',
		description:
			'Create the new Release Group AND deploy a bench inside it. Ready to receive sites in 5–10 minutes. Best when you want the same versions as the source.',
		recommended: true,
	},
	{
		value: 'rg_only',
		label: 'Clone Release Group only (deploy manually)',
		description:
			'Create the new RG with the same apps but skip auto-deploy. Use when you want to tweak versions, branches, or dependencies before deploying.',
		recommended: false,
	},
];

const dialogOptions = computed(() => ({
	title: 'Clone Bench / Release Group',
	size: 'lg',
	actions: [
		{
			label: mode.value === 'full' ? 'Clone + Deploy' : 'Clone RG only',
			variant: 'solid',
			loading: submitting.value,
			onClick: submit,
		},
	],
}));

async function submit() {
	errorMsg.value = '';
	if (!newTitle.value?.trim()) {
		errorMsg.value = 'Title is required.';
		return;
	}
	const method = mode.value === 'full'
		? 'press.press.doctype.release_group.release_group_clone.clone_release_group'
		: 'press.press.doctype.release_group.release_group_clone.clone_release_group_only';
	submitting.value = true;
	try {
		const newName = await call(method, {
			release_group: props.sourceReleaseGroup,
			new_title: newTitle.value.trim(),
			lifetime: 'persistent',
		});
		const successMsg = mode.value === 'full'
			? `Cloned: ${newName}. Deploy in progress — check the bench page in a few minutes, then move the site.`
			: `Cloned: ${newName}. Open the new bench, set versions/branches as needed, then click Deploy.`;
		toast.success(successMsg);
		window.open(`/dashboard/groups/${newName}`, '_blank');
		show.value = false;
		emit('cloned', { name: newName, mode: mode.value });
	} catch (e) {
		errorMsg.value = e?.messages?.[0] || e?.message || String(e);
	} finally {
		submitting.value = false;
	}
}
</script>
