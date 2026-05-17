<template>
	<Dialog v-model="show" :options="{ title: 'Clone Site', size: 'lg' }">
		<template #body-content>
			<div class="space-y-4">
				<p class="text-p-base text-gray-700">
					Create a copy of <b>{{ site }}</b> onto a target bench. Only benches
					that have every app this site needs are listed.
				</p>

				<!-- Target Bench picker -->
				<FormControl
					label="Target Bench"
					type="combobox"
					:options="benchOptions"
					v-model="targetBench"
					:disabled="benchesResource.loading"
					placeholder="Search or pick a bench…"
				/>
				<p v-if="benchesResource.loading" class="-mt-2 text-xs text-gray-500">
					Loading compatible benches…
				</p>
				<p
					v-else-if="!compatibleBenches.length"
					class="-mt-2 text-xs text-amber-700"
				>
					No existing bench matches this site's apps. Pick
					<b>Create a new bench</b> above to clone this site's release group.
				</p>

				<!-- New subdomain with live availability check -->
				<div>
					<FormControl
						label="New subdomain (without the root domain)"
						v-model="newSubdomain"
						@blur="checkSubdomain"
						autocomplete="off"
					/>
					<p
						v-if="subdomainStatus === 'checking'"
						class="mt-1 text-xs text-gray-500"
					>
						Checking availability…
					</p>
					<p
						v-else-if="subdomainStatus === 'taken'"
						class="mt-1 text-xs text-red-600"
					>
						✗ {{ newSubdomain }}.{{ rootDomain }} is already taken.
					</p>
					<p
						v-else-if="subdomainStatus === 'available'"
						class="mt-1 text-xs text-green-700"
					>
						✓ {{ newSubdomain }}.{{ rootDomain }} is available.
					</p>
					<p
						v-else-if="subdomainStatus === 'invalid'"
						class="mt-1 text-xs text-red-600"
					>
						✗ Subdomain may only contain lowercase letters, numbers, and
						hyphens.
					</p>
				</div>

				<!-- Data mode -->
				<FormControl
					label="Data mode"
					type="select"
					:options="modeOptions"
					v-model="mode"
				/>
				<p class="-mt-2 text-xs text-gray-500">{{ modeHint }}</p>

				<ErrorMessage :message="errorMsg" />
			</div>
		</template>
		<template #actions>
			<Button
				class="w-full"
				:label="primaryLabel"
				variant="solid"
				:loading="submitting"
				:disabled="!canSubmit"
				@click="onPrimary"
			/>
		</template>
	</Dialog>
</template>

<script setup>
import { ref, computed, h, defineAsyncComponent } from 'vue';
import {
	Dialog,
	FormControl,
	Button,
	ErrorMessage,
	call,
	createResource,
	getCachedDocumentResource,
} from 'frappe-ui';
import { toast } from 'vue-sonner';
import { useRouter } from 'vue-router';
import { renderDialog } from '../../utils/components';

const props = defineProps({
	site: { type: String, required: true },
});

const router = useRouter();
const siteDoc = getCachedDocumentResource('Site', props.site);

const NEW_BENCH_SENTINEL = '__new_bench__';

const show = ref(true);
const targetBench = ref(null);
const newSubdomain = ref('');
const mode = ref('latest_backup');
const submitting = ref(false);
const errorMsg = ref('');
const subdomainStatus = ref('');

const modeOptions = [
	{
		label: 'Latest backup (fast — uses most recent offsite backup)',
		value: 'latest_backup',
	},
	{
		label: 'Fresh backup (slow — triggers a new backup first)',
		value: 'fresh_backup',
	},
	{ label: 'Empty (no data — just install apps)', value: 'empty' },
];

const modeHints = {
	latest_backup:
		'Restores from the most recent offsite backup. Fast (a few minutes). Recommended.',
	fresh_backup:
		'Triggers a fresh offsite backup first, then re-run this clone after the backup completes. Slowest path.',
	empty:
		'Spins up an empty site with the same apps installed. No customer data is copied.',
};
const modeHint = computed(() => modeHints[mode.value] || '');

const rootDomain = computed(() => siteDoc?.doc?.domain || '');

const benchesResource = createResource({
	url: 'press.press.doctype.site.site_clone.list_compatible_benches',
	params: { site: props.site },
	auto: true,
});

const compatibleBenches = computed(() => benchesResource.data || []);

const benchOptions = computed(() => {
	const opts = compatibleBenches.value.map((b) => ({
		label: b.label,
		value: b.value,
	}));
	return [
		{
			label: '➕ Create a new bench (clone this site’s release group)',
			value: NEW_BENCH_SENTINEL,
		},
		...opts,
	];
});

const canSubmit = computed(() => {
	if (submitting.value) return false;
	const benchValue = unwrap(targetBench.value);
	if (!benchValue) return false;
	if (benchValue === NEW_BENCH_SENTINEL) return true;
	if (!newSubdomain.value?.trim()) return false;
	if (subdomainStatus.value === 'taken' || subdomainStatus.value === 'invalid')
		return false;
	return true;
});

const primaryLabel = computed(() => {
	const benchValue = unwrap(targetBench.value);
	return benchValue === NEW_BENCH_SENTINEL ? 'Create new bench…' : 'Clone';
});

function unwrap(option) {
	return option && typeof option === 'object' && 'value' in option
		? option.value
		: option;
}

const SUBDOMAIN_REGEX = /^[a-z0-9][a-z0-9-]{1,62}$/;

async function checkSubdomain() {
	const sd = newSubdomain.value?.trim().toLowerCase();
	if (!sd) {
		subdomainStatus.value = '';
		return;
	}
	if (!SUBDOMAIN_REGEX.test(sd)) {
		subdomainStatus.value = 'invalid';
		return;
	}
	if (!rootDomain.value) return;
	subdomainStatus.value = 'checking';
	try {
		const taken = await call('press.api.site.exists', {
			subdomain: sd,
			domain: rootDomain.value,
		});
		subdomainStatus.value = taken ? 'taken' : 'available';
	} catch (e) {
		subdomainStatus.value = '';
	}
}

function onPrimary() {
	const benchValue = unwrap(targetBench.value);
	if (benchValue === NEW_BENCH_SENTINEL) {
		openCloneBenchPrompt();
		return;
	}
	submit(benchValue);
}

function openCloneBenchPrompt() {
	if (!siteDoc?.doc?.group) {
		errorMsg.value =
			'Cannot open Clone Bench — the source site has no release group loaded.';
		return;
	}
	const CloneBenchPrompt = defineAsyncComponent(
		() => import('../CloneBenchPrompt.vue'),
	);
	show.value = false;
	renderDialog(
		h(CloneBenchPrompt, {
			sourceReleaseGroup: siteDoc.doc.group,
			sourceLabel: siteDoc.doc.group_title || siteDoc.doc.group,
		}),
	);
	toast.info(
		'Reopen "Clone Site" once the new bench finishes deploying (5–10 min).',
	);
}

async function submit(benchValue) {
	errorMsg.value = '';
	submitting.value = true;
	try {
		const response = await call(
			'press.press.doctype.site.site_clone.clone_site',
			{
				site: props.site,
				target_bench: benchValue,
				new_subdomain: newSubdomain.value.trim().toLowerCase(),
				mode: mode.value,
			},
		);
		// clone_site mirrors press.api.site._new, which returns {site, job}.
		// Match NewSite.vue's pattern: route to the Site Job progress page when
		// the provisioning job exists, otherwise the site overview.
		const newSite = response?.site || response;
		toast.success(`Cloned site created: ${newSite}`);
		show.value = false;
		if (response?.job) {
			router.push({
				name: 'Site Job',
				params: { name: newSite, id: response.job },
			});
		} else {
			router.push(`/sites/${newSite}`);
		}
	} catch (e) {
		errorMsg.value = e?.messages?.[0] || e?.message || String(e);
	} finally {
		submitting.value = false;
	}
}
</script>
