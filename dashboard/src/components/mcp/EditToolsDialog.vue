<template>
	<!-- PRS-SP-22: change which tools a token can call. Same token, nothing to copy again; adding a tool needs
	     Confirm it's you, removing only does not (press.mcp_server.token_edit.update_token_tools). -->
	<Dialog v-model="show" :options="{ title: 'Edit tools', size: '4xl', actions }">
		<template #body-content>
			<div class="space-y-4">
				<p class="-mt-2 text-sm text-gray-600">
					{{ token?.label }} · {{ token?.token_prefix }}… · same token, nothing to copy again
				</p>
				<ToolScopePicker v-model="scope" :baseline="baseline" label="Tools this token can call" />
				<div class="flex flex-wrap items-center gap-2 text-sm text-gray-700">
					<span>Changes:</span>
					<span v-for="t in added" :key="'a' + t" class="rounded bg-green-100 px-2 py-0.5 text-xs text-green-800">
						+ {{ TOOL_CATALOG[t]?.label || t }}
					</span>
					<span v-for="t in removed" :key="'r' + t" class="rounded bg-gray-200 px-2 py-0.5 text-xs text-gray-700">
						− {{ TOOL_CATALOG[t]?.label || t }}
					</span>
					<span v-if="!added.length && !removed.length" class="text-gray-500">none yet</span>
				</div>
				<p v-if="addsHighRisk" class="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
					A high-risk tool turns on risky tools for this token. A token of a user who is not a System User waits
					for approval again, as when it was issued.
				</p>
				<ErrorMessage :message="error" />
			</div>
		</template>
	</Dialog>
	<ConfirmItsYouDialog v-model="confirmOpen" :reason="confirmReason" @confirmed="onConfirmed" />
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { Dialog, ErrorMessage } from 'frappe-ui';
import { toast } from 'vue-sonner';
import call from './teamCall.js';
import { TOOL_CATALOG, ALL_TOOLS } from './_tool_catalog.js';
import ToolScopePicker from './ToolScopePicker.vue';
import ConfirmItsYouDialog from './ConfirmItsYouDialog.vue';
import { useConfirm } from './useConfirm.js';

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	token: { type: Object, default: null },
});
const emit = defineEmits(['update:modelValue', 'saved']);
const show = computed({
	get: () => props.modelValue,
	set: (v) => emit('update:modelValue', v),
});
const { confirmOpen, confirmReason, withConfirm, onConfirmed } = useConfirm();

const baseline = ref([]);
const scope = ref([]);
const error = ref('');
const saving = ref(false);

const added = computed(() => scope.value.filter((t) => !baseline.value.includes(t)));
const removed = computed(() => baseline.value.filter((t) => !scope.value.includes(t)));
const addsHighRisk = computed(
	() => !props.token?.risky_tools_enabled && added.value.some((t) => TOOL_CATALOG[t]?.risk === 'high'),
);
const actions = computed(() => [
	{ label: 'Cancel', variant: 'outline', onClick: () => (show.value = false) },
	{
		label: 'Save',
		variant: 'solid',
		loading: saving.value,
		disabled: !scope.value.length || (!added.value.length && !removed.value.length),
		onClick: save,
	},
]);

watch(
	() => props.modelValue,
	(open) => {
		if (!open || !props.token) return;
		const current = props.token.scope?.length ? props.token.scope : ALL_TOOLS;
		baseline.value = [...current];
		scope.value = [...current];
		error.value = '';
	},
);

async function doSave() {
	saving.value = true;
	error.value = '';
	try {
		const r = await call('press.mcp_server.token_edit.update_token_tools', {
			token_id: props.token.name,
			scope: scope.value,
		});
		toast.success(`Saved the tools of ${props.token.label}: +${r.added.length} −${r.removed.length}`);
		emit('saved');
		show.value = false;
	} catch (e) {
		error.value = e?.messages?.[0] || e?.message || String(e);
	} finally {
		saving.value = false;
	}
}

function save() {
	if (!added.value.length) return doSave();
	return withConfirm(`to save the tools of ${props.token.label}`, doSave);
}
</script>
