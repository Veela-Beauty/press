<template>
	<div v-if="!acknowledged" class="mx-auto max-w-lg rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
		<div class="mb-4 text-center">
			<div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-blue-50">
				<i class="fa fa-shield text-xl text-blue-600"></i>
			</div>
			<h2 class="text-lg font-semibold text-gray-900">AI Usage Policy</h2>
			<p class="mt-1 text-sm text-gray-500">You must agree to this policy before using the AI Developer Assistant.</p>
		</div>

		<!-- Technical Rules -->
		<div class="mb-4 rounded-lg border border-gray-100 p-3">
			<p class="mb-2 text-xs font-semibold uppercase text-gray-500">Technical Rules</p>
			<div v-for="rule in technicalRules" :key="rule.text" class="flex items-start gap-2 py-1">
				<span class="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded text-[9px] font-bold text-white"
					:class="rule.level === 'block' ? 'bg-red-500' : 'bg-orange-500'">
					{{ rule.level === 'block' ? 'X' : '!' }}
				</span>
				<span class="text-xs text-gray-700">{{ rule.text }}</span>
			</div>
		</div>

		<!-- Behavioral Rules -->
		<div class="mb-4 rounded-lg border border-gray-100 p-3">
			<p class="mb-2 text-xs font-semibold uppercase text-gray-500">Behavioral Rules</p>
			<div v-for="rule in behavioralRules" :key="rule.text" class="flex items-start gap-2 py-1">
				<span class="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded text-[9px] font-bold text-white bg-orange-500">!</span>
				<span class="text-xs text-gray-700">{{ rule.text }}</span>
			</div>
		</div>

		<!-- Compliance Rules -->
		<div class="mb-4 rounded-lg border border-gray-100 p-3">
			<p class="mb-2 text-xs font-semibold uppercase text-gray-500">Compliance Rules</p>
			<div v-for="rule in complianceRules" :key="rule.text" class="flex items-start gap-2 py-1">
				<span class="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded text-[9px] font-bold text-white bg-red-500">X</span>
				<span class="text-xs text-gray-700">{{ rule.text }}</span>
			</div>
		</div>

		<!-- Acknowledgment checkbox -->
		<div class="mb-4 rounded-lg border border-blue-100 bg-blue-50 p-3">
			<label class="flex items-start gap-2 text-xs text-blue-800">
				<input v-model="agreed" type="checkbox" class="mt-0.5 rounded border-blue-300">
				<span>I have read and agree to the <strong>AI Usage Policy — v1.0 — April 2026</strong>. I understand that violations may result in access revocation.</span>
			</label>
		</div>

		<button
			class="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:bg-gray-300"
			:disabled="!agreed || submitting"
			@click="acknowledge"
		>
			<i v-if="submitting" class="fa fa-spinner fa-spin mr-1"></i>
			Continue to AI Assistant
		</button>
	</div>
</template>

<script>
import { call } from 'frappe-ui';

export default {
	name: 'AiPolicyGate',
	emits: ['acknowledged'],
	data() {
		return {
			acknowledged: false,
			agreed: false,
			submitting: false,
			technicalRules: [
				{ text: 'Block Raw SQL (DELETE/DROP/TRUNCATE) — hard block, cannot override', level: 'block' },
				{ text: 'Block uninstall app / destroy / rm -rf via AI', level: 'block' },
				{ text: 'Block AI modifications on Production sites — read-only panel', level: 'block' },
				{ text: 'Max 100K tokens/day — warning at 80%, block at 100%', level: 'warn' },
			],
			behavioralRules: [
				{ text: 'AI output must be reviewed before apply — mandatory for implementors' },
				{ text: 'Do not share AI sessions or API keys with others' },
			],
			complianceRules: [
				{ text: 'Client code sent via company key only — personal key on client data blocked' },
				{ text: 'Real production data (PII) blocked from any prompt or context' },
				{ text: 'Escalation requests require a written reason — logged in audit' },
			],
		};
	},
	methods: {
		async acknowledge() {
			this.submitting = true;
			try {
				await call('press.press.ai.api.acknowledge_policy', {});
				this.acknowledged = true;
				this.$emit('acknowledged');
			} catch (e) {
				console.error('Policy acknowledge failed:', e);
			} finally {
				this.submitting = false;
			}
		},
	},
};
</script>
