<template>
	<Dialog v-model="show" :options="dialogOptions">
		<template #body-content>
			<div class="space-y-4">
				<p class="text-sm text-gray-600">
					Move this site to a different Release Group on the same server. The target RG
					must have an Active Bench and include every app this site uses. The site will
					be briefly deactivated during the move.
				</p>

				<!-- Empty-state CTA: no eligible RGs found -->
				<div
					v-if="!loading && eligibleRGs.length === 0"
					class="rounded border border-blue-200 bg-blue-50 p-3 space-y-2"
				>
					<div class="text-sm font-medium text-blue-900">
						No eligible Release Groups for this site yet.
					</div>
					<div class="text-xs text-blue-800">
						To move this site, you need another RG on the same server with all this site's apps.
						Pick a path below — both end with you coming back here to do the actual move.
					</div>
					<div class="flex flex-wrap gap-2 pt-1">
						<Button
							variant="solid"
							:loading="cloning"
							@click="onCloneCurrentBench"
						>
							<template #prefix>
								<FeatherIcon name="copy" class="h-4 w-4" />
							</template>
							Clone this site's bench (recommended)
						</Button>
						<Button @click="onOpenNewBench">
							<template #prefix>
								<FeatherIcon name="plus" class="h-4 w-4" />
							</template>
							Create a new bench
						</Button>
					</div>
					<div class="text-[11px] text-blue-700 pt-1">
						<strong>Clone</strong>: copies the current bench's apps into a new RG (instant).<br />
						<strong>New bench</strong>: opens the New Bench wizard in a new tab (start from scratch).<br />
						After either, deploy the new RG, then reopen this dialog.
					</div>
				</div>

				<!-- Searchable RG picker (only when there ARE eligible RGs) -->
				<div v-if="eligibleRGs.length > 0">
					<label class="block text-sm font-medium text-gray-700 mb-1">
						Target Release Group
					</label>
					<div
						class="relative rounded border border-gray-300 bg-white p-2 focus-within:border-blue-500"
						:class="{ 'opacity-60 pointer-events-none': loading }"
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
						<div v-else-if="open && !filtered.length && !loading" class="absolute left-0 right-0 z-50 mt-1 rounded border border-gray-200 bg-white p-3 text-xs text-gray-500 shadow-lg">
							{{ query ? `No matches for "${query}"` : 'Type to search...' }}
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

				<!-- Skip failing patches (only show when picker is usable) -->
				<label
					v-if="eligibleRGs.length > 0"
					class="flex items-start gap-2 cursor-pointer rounded border border-amber-200 bg-amber-50 p-3"
				>
					<input
						type="checkbox"
						v-model="skipPatches"
						class="mt-0.5"
					/>
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
import { ref, computed, onMounted } from 'vue';
import { Dialog, ErrorMessage, Button, FeatherIcon, call, toast } from 'frappe-ui';

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
const cloning = ref(false);
const errorMsg = ref('');
const inputRef = ref(null);

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
	return eligibleRGs.value
		.filter(
			(rg) =>
				rg.name.toLowerCase().includes(q) ||
				(rg.title || '').toLowerCase().includes(q),
		)
		.slice(0, 50);
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

function onBlur() {
	setTimeout(() => { open.value = false; }, 150);
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

async function onCloneCurrentBench() {
	if (!currentReleaseGroup.value) {
		toast.error("Couldn't determine the site's current Release Group.");
		return;
	}
	// Use the human-readable RG title for the default (e.g. "AccuBuild Demo (copy)"),
	// not the technical RG name (e.g. "bench-0005 (copy)").
	const sourceLabel = currentReleaseGroupTitle.value || currentReleaseGroup.value;
	const newTitle = prompt(
		`Name for the new Release Group (apps will be copied from "${sourceLabel}"):`,
		`${sourceLabel} (copy)`,
	);
	if (!newTitle) return;
	cloning.value = true;
	try {
		const newName = await call(
			'press.press.doctype.release_group.release_group_clone.clone_release_group',
			{
				release_group: currentReleaseGroup.value,
				new_title: newTitle,
				lifetime: 'persistent',
			},
		);
		toast.success(`Cloned: ${newName}. Deploy it, then reopen this dialog to move the site.`);
		// Open the new bench in a new tab so user can deploy it
		window.open(`/dashboard/groups/${newName}`, '_blank');
		show.value = false;
	} catch (e) {
		toast.error('Clone failed: ' + (e?.messages?.[0] || e?.message || e));
	} finally {
		cloning.value = false;
	}
}

function onOpenNewBench() {
	window.open('/dashboard/groups/new', '_blank');
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
