<template>
	<Dialog v-model="show" :options="dialogOptions">
		<template #body-content>
			<div class="space-y-4">
				<p class="text-sm text-gray-600">
					Move this site to a different Release Group on the same server. The target RG
					must have an Active Bench and include every app this site uses. The site will
					be briefly deactivated during the move.
				</p>

				<MoveSiteEmptyState
					v-if="!loading && eligibleRGs.length === 0"
					:current-release-group="currentReleaseGroup"
					:current-release-group-title="currentReleaseGroupTitle"
					@clone-clicked="onCloneClicked"
				/>

				<!-- Searchable RG picker -->
				<div v-if="eligibleRGs.length > 0">
					<label class="block text-sm font-medium text-gray-700 mb-1">
						Target Release Group
					</label>
					<div
						class="relative rounded border border-gray-300 bg-white p-2 focus-within:border-blue-500"
					>
						<div v-if="selected" class="mb-1.5 flex flex-wrap gap-1">
							<span class="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-800">
								{{ selected.title || selected.name }}
								<span v-if="selected.title && selected.title !== selected.name" class="font-mono text-[10px] text-blue-600">
									{{ selected.name }}
								</span>
								<button
									type="button"
									class="text-blue-600 hover:text-blue-900"
									@click.stop="clearSelected"
								>
									×
								</button>
							</span>
						</div>
						<input
							ref="inputRef"
							type="text"
							v-model="query"
							:placeholder="selected ? 'Pick a different RG...' : 'Search benches by name or title...'"
							class="w-full border-0 bg-transparent p-0 text-sm focus:outline-none focus:ring-0"
							@focus="open = true"
							@blur="onBlur"
							@keydown.escape="open = false"
						/>
						<div
							v-if="open && filtered.length"
							ref="dropdownRef"
							class="absolute left-0 right-0 z-50 mt-1 max-h-64 overflow-y-auto rounded border border-gray-200 bg-white shadow-lg"
						>
							<button
								v-for="opt in filtered"
								:key="opt.name"
								type="button"
								class="block w-full text-left px-3 py-1.5 text-sm hover:bg-blue-50"
								:class="{ 'bg-blue-100': selected?.name === opt.name }"
								@mousedown.prevent="select(opt)"
							>
								<div class="flex items-baseline gap-2">
									<span class="font-medium">{{ opt.title || opt.name }}</span>
									<span v-if="opt.title && opt.title !== opt.name" class="font-mono text-xs text-gray-400">{{ opt.name }}</span>
								</div>
								<div class="text-xs text-gray-500">
									{{ opt.app_count }} app{{ opt.app_count === 1 ? '' : 's' }} · server: {{ opt.server }}
								</div>
							</button>
						</div>
					</div>
					<div class="mt-1 text-xs text-gray-500">
						{{ eligibleRGs.length }} eligible RG{{ eligibleRGs.length === 1 ? '' : 's' }} —
						only RGs on the same server, with all this site's apps and an Active Bench, are shown.
					</div>
				</div>

				<div v-if="loading" class="text-xs text-gray-500">
					Loading eligible Release Groups...
				</div>

				<label
					v-if="eligibleRGs.length > 0"
					class="flex items-start gap-2 cursor-pointer rounded border border-amber-200 bg-amber-50 p-3"
				>
					<input type="checkbox" v-model="skipPatches" class="mt-0.5" />
					<div>
						<div class="text-sm font-medium text-amber-900">Skip failing patches</div>
						<div class="text-xs text-amber-800">
							If a patch fails during the move, continue anyway instead of rolling back. Only
							check this if you've already reviewed the failing patch.
						</div>
					</div>
				</label>

				<ErrorMessage :message="errorMsg" />
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue';
import { Dialog, ErrorMessage, call, toast } from 'frappe-ui';
import MoveSiteEmptyState from './MoveSiteEmptyState.vue';
import CloneBenchPrompt from './CloneBenchPrompt.vue';
import { renderDialog } from '../utils/components';

const props = defineProps({
	siteName: { type: String, required: true },
});
const emit = defineEmits(['moved']);

const show = ref(true);

const eligibleRGs = ref([]);
const currentReleaseGroup = ref(null);
const currentReleaseGroupTitle = ref(null);
const loading = ref(false);
const selected = ref(null);
const query = ref('');
const open = ref(false);
const skipPatches = ref(false);
const submitting = ref(false);
const errorMsg = ref('');
const inputRef = ref(null);
const dropdownRef = ref(null);

const dialogOptions = computed(() => ({
	title: 'Move Site to Release Group',
	size: 'lg',
	actions:
		eligibleRGs.value.length > 0
			? [
					{
						label: 'Move',
						variant: 'solid',
						loading: submitting.value,
						onClick: submit,
					},
				]
			: [],
}));

const filtered = computed(() => {
	const q = query.value.trim().toLowerCase();
	if (!q) return eligibleRGs.value.slice(0, 50);
	const out = [];
	for (const rg of eligibleRGs.value) {
		if (out.length >= 50) break;
		if (rg.name.toLowerCase().includes(q) || (rg.title || '').toLowerCase().includes(q)) {
			out.push(rg);
		}
	}
	return out;
});

function select(rg) {
	selected.value = rg;
	query.value = '';
	open.value = false;
}

function clearSelected() {
	selected.value = null;
	inputRef.value?.focus();
}

function onBlur(e) {
	// Use relatedTarget to deterministically close only when focus moves
	// outside the dropdown. Avoids the 150ms setTimeout race condition.
	if (e.relatedTarget && dropdownRef.value?.contains(e.relatedTarget)) return;
	open.value = false;
}

async function loadContext() {
	loading.value = true;
	try {
		const ctx = await call(
			'press.api.site_move.get_site_move_context',
			{ site: props.siteName },
		);
		eligibleRGs.value = ctx?.eligible || [];
		currentReleaseGroup.value = ctx?.current_release_group || null;
		currentReleaseGroupTitle.value =
			ctx?.current_release_group_title || ctx?.current_release_group || null;
	} catch (e) {
		toast.error('Failed to load: ' + (e?.messages?.[0] || e?.message || e));
	} finally {
		loading.value = false;
	}
}

onMounted(() => {
	loadContext();
});

function onCloneClicked() {
	if (!currentReleaseGroup.value) {
		toast.error("Couldn't determine the site's current Release Group.");
		return;
	}
	// Close this dialog and open the clone-mode chooser in its place.
	show.value = false;
	renderDialog(
		h(CloneBenchPrompt, {
			sourceReleaseGroup: currentReleaseGroup.value,
			sourceLabel: currentReleaseGroupTitle.value || currentReleaseGroup.value,
		}),
	);
}

async function submit() {
	errorMsg.value = '';
	if (!selected.value) {
		errorMsg.value = 'Pick a target Release Group first.';
		return;
	}
	submitting.value = true;
	try {
		const result = await call('press.api.site_move.move_to_release_group', {
			site: props.siteName,
			target_release_group: selected.value.name,
			skip_failing_patches: skipPatches.value ? 1 : 0,
		});
		toast.success(`Move queued (job: ${result.job || 'pending'})`);
		show.value = false;
		emit('moved', result);
	} catch (e) {
		errorMsg.value = e?.messages?.[0] || e?.message || String(e);
	} finally {
		submitting.value = false;
	}
}
</script>
