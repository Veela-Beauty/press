<template>
	<div class="space-y-4">
		<div class="flex items-center justify-between">
			<div>
				<h2 class="text-lg font-semibold">{{ isNew ? 'New policy' : form.policy_name }}</h2>
				<p class="text-xs text-gray-500">Pushed to every PC of a person on this policy by Basher.</p>
			</div>
			<div class="flex items-center gap-2">
				<Button @click="$emit('back')">Back to policies</Button>
				<Button variant="solid" :loading="saving" :disabled="loading" @click="save">Save policy</Button>
			</div>
		</div>

		<div v-if="loading" class="space-y-3">
			<div v-for="n in 3" :key="n" class="h-28 animate-pulse rounded-lg bg-gray-100"></div>
		</div>

		<template v-else>
			<div class="space-y-3 rounded-lg border border-gray-200 bg-white p-4">
				<h3 class="text-sm font-semibold">How it runs <span class="font-normal text-gray-400">(permission mode, route and previews)</span></h3>
				<div v-if="isNew" class="max-w-md">
					<FormControl
						label="Policy name" v-model="form.policy_name" placeholder="Example: Standard"
						data-err="name" :aria-invalid="errors.name ? 'true' : null" :aria-describedby="errors.name ? 'policy-err-name' : null"
					/>
					<p v-if="errors.name" id="policy-err-name" role="alert" class="mt-1 text-[11px] text-red-600">{{ errors.name }}</p>
				</div>
				<div class="grid grid-cols-2 gap-4">
					<FormControl
						type="select" label="Permission mode" v-model="form.permission_mode" :options="modes"
						description="Bypass lets Claude act without asking. Blocked actions below still apply."
					/>
					<FormControl
						type="select" label="Route" v-model="form.route" :options="routes"
						description="Own Max goes straight to Anthropic with the person's own login, outside our budget."
					/>
					<FormControl
						type="select" label="Web page previews" v-model="form.preview_mode" :options="previews"
						description="Sealed hides Open preview in Basher for web pages Claude makes. A guard rail, not a lock."
					/>
				</div>
			</div>

			<div class="space-y-3 rounded-lg border border-gray-200 bg-white p-4">
				<h3 class="text-sm font-semibold">Models <span class="font-normal text-gray-400">(each picks a Serves as name from the Gateway pool)</span></h3>
				<div class="grid grid-cols-2 gap-4">
					<div v-for="slot in slots" :key="slot.key">
						<FormControl
							type="select" :label="slot.label" v-model="form[slot.key]" :options="modelChoices(slot.key)"
							placeholder="Pick a model" :disabled="own" :description="slot.hint"
							data-err="models" :aria-invalid="slotInvalid(slot.key) ? 'true' : null" :aria-describedby="slotInvalid(slot.key) ? 'policy-err-models' : null"
						/>
						<p v-if="isUnserved(slot.key)" class="mt-1 text-[11px] text-red-600">No enabled account serves this name now. Pick another.</p>
					</div>
					<div>
						<FormControl
							type="select" label="Rules and skills release" v-model="form.rules_release" :options="releaseChoices"
							placeholder="Pick a release" description="From the skills git repo. Basher refreshes every PC when this changes."
							data-err="release" :aria-invalid="errors.release ? 'true' : null" :aria-describedby="errors.release ? 'policy-err-release' : null"
						/>
						<p v-if="releaseListFailed && !form.rules_release" class="mt-1 text-[11px] text-red-600">No skills releases available yet. Ask the control center admin to configure the skills release token.</p>
						<p v-if="releaseListFailed" class="mt-1 text-[11px] text-gray-500">{{ releaseError }}</p>
						<p v-if="errors.release" id="policy-err-release" role="alert" class="mt-1 text-[11px] text-red-600">{{ errors.release }}</p>
					</div>
				</div>
				<p v-if="errors.models" id="policy-err-models" role="alert" class="mt-1 text-[11px] text-red-600">{{ errors.models }}</p>
				<p v-if="own" class="text-xs text-gray-500">Route is Own Claude Max: the three model fields are greyed, the models come from the person's Max.</p>
			</div>

			<div class="space-y-3 rounded-lg border border-gray-200 bg-white p-4">
				<h3 class="text-sm font-semibold">What Claude Code may do <span class="font-normal text-gray-400">(Claude Code permission syntax, one per line)</span></h3>
				<div class="grid grid-cols-2 gap-4">
					<FormControl
						type="textarea" :rows="7" label="Allowed actions" v-model="form.allowed_actions"
						placeholder="Bash(git status:*)" description="Claude does these without asking."
					/>
					<FormControl
						type="textarea" :rows="7" label="Blocked actions" v-model="form.blocked_actions"
						placeholder="Bash(rm -rf:*)" description="Always enforced against standard users and user-level processes, also with bypass on. A local administrator can still change them."
					/>
				</div>
			</div>
		</template>
	</div>
</template>

<script>
import { Button, FormControl, call } from 'frappe-ui';
import { toast } from 'vue-sonner';
import {
	PERMISSION_MODES, ROUTES, PREVIEW_MODES, MODEL_SLOTS, emptyPolicy, fromServer, isOwnMax, modelOptions,
	releaseOptions, defaultRelease, validatePolicy, policyErrors, savePayload, savedMessage,
} from './policies-derive.js';

const API = 'sanad_ai_control_center.policies';

export default {
	name: 'AiPolicyForm',
	components: { Button, FormControl },
	props: { name: { type: String, default: null } },
	emits: ['back', 'saved'],
	data() {
		return {
			form: emptyPolicy(), errors: {}, serving: [], releases: [], unserved: [], releaseError: '',
			loading: true, saving: false, modes: PERMISSION_MODES, routes: ROUTES, previews: PREVIEW_MODES, slots: MODEL_SLOTS,
		};
	},
	computed: {
		isNew() { return !this.name; },
		own() { return isOwnMax(this.form); },
		validatedFields() {
			const f = this.form;
			return [f.policy_name, f.rules_release, f.route, f.model_light, f.model_normal, f.model_hard];
		},
		releaseListFailed() { return !!this.releaseError && !this.releases.length; },
		releaseChoices() { return releaseOptions(this.releases, this.form.rules_release); },
	},
	watch: {
		validatedFields() { if (Object.keys(this.errors).length) this.errors = policyErrors(this.form, this.isNew); },
	},
	mounted() { this.load(); },
	methods: {
		async load() {
			this.loading = true;
			try { this.serving = (await call(`${API}.list_serving_models`)).models || []; }
			catch (e) { toast.error(e.messages?.[0] || 'Could not load the models'); }
			try { this.releases = (await call(`${API}.list_releases`)).releases || []; }
			catch (e) { this.releaseError = e.messages?.[0] || 'Could not read releases from the skills repo.'; }
			if (this.name) {
				try {
					const p = await call(`${API}.get_policy`, { name: this.name });
					this.form = fromServer(p);
					this.unserved = p.models_unserved || [];
				} catch (e) {
					toast.error(e.messages?.[0] || 'Could not load the policy');
					this.$emit('back');
					return;
				}
			} else {
				this.form.rules_release = defaultRelease(this.releases);
			}
			this.loading = false;
		},
		modelChoices(key) { return modelOptions(this.serving, this.form[key]); },
		slotInvalid(key) { return !!this.errors.models && !this.own && !this.form[key]; },
		isUnserved(key) { return !this.own && !!this.form[key] && this.unserved.includes(this.form[key]); },
		async save() {
			this.errors = policyErrors(this.form, this.isNew);
			const problem = validatePolicy(this.form, this.isNew);
			if (problem) {
				toast.error(problem);
				const first = ['name', 'release', 'models'].find((k) => this.errors[k]);
				this.$nextTick(() => {
					const el = this.$el.querySelector(`[data-err="${first}"][aria-invalid="true"]`);
					el?.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
					el?.focus?.();
				});
				return;
			}
			this.saving = true;
			try {
				const r = await call(`${API}.save_policy`, savePayload(this.form, this.isNew));
				toast.success(savedMessage(r));
				(r.warnings || []).forEach((w) => toast.warning(w));
				this.$emit('saved');
			} catch (e) { toast.error(e.messages?.[0] || 'Could not save the policy'); }
			this.saving = false;
		},
	},
};
</script>
