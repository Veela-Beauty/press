<template>
	<div class="space-y-4">
		<div class="mb-2 text-sm font-semibold">
			<i class="fa fa-exclamation-circle mr-1 text-blue-600"></i>
			Escalation Requests
		</div>

		<!-- Active escalation -->
		<div v-for="esc in escalations" :key="esc.id" class="rounded-lg border border-gray-200 bg-white p-4">
			<div v-if="esc.status === 'pending'" class="mb-3 rounded-lg bg-orange-50 px-3 py-2 text-xs text-orange-700">
				<i class="fa fa-clock-o mr-1"></i>
				<strong>{{ esc.id }}</strong> — Escalation from {{ esc.user }} / Pending {{ esc.pending_for }}
			</div>

			<!-- Step 1: User Request -->
			<div class="mb-3 flex gap-3">
				<div class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
					:class="esc.step >= 1 ? 'bg-green-500' : 'bg-gray-300'">
					{{ esc.step >= 1 ? '✓' : '1' }}
				</div>
				<div class="flex-1 text-xs">
					<p class="font-semibold">User Request</p>
					<p class="text-gray-600">
						<strong>{{ esc.user }}</strong> — {{ esc.requested_at }}<br>
						Requested: <code class="rounded bg-gray-100 px-1 text-[10px]">{{ esc.blocked_code }}</code><br>
						Reason: "{{ esc.reason }}"<br>
						<span class="text-red-600">Linter: {{ esc.linter_message }}</span>
					</p>
				</div>
			</div>

			<!-- Step 2: TL Review -->
			<div class="mb-3 flex gap-3">
				<div class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
					:class="esc.step >= 2 ? 'bg-green-500' : esc.step === 1 ? 'bg-orange-500' : 'bg-gray-300'">
					{{ esc.step >= 2 ? '✓' : '2' }}
				</div>
				<div class="flex-1 text-xs">
					<p class="font-semibold">Team Leader Review — {{ esc.step >= 2 ? (esc.tl_approved ? 'Approved' : 'Rejected') : 'Pending' }}</p>
					<div v-if="esc.step === 1 && isTeamLeader" class="mt-2 flex gap-2">
						<button class="rounded bg-green-600 px-3 py-1 text-xs text-white hover:bg-green-700" @click="$emit('approve-esc', esc.id)">
							<i class="fa fa-check mr-1"></i>Approve
						</button>
						<button class="rounded bg-red-600 px-3 py-1 text-xs text-white hover:bg-red-700" @click="$emit('reject-esc', esc.id)">
							<i class="fa fa-times mr-1"></i>Reject
						</button>
					</div>
					<p v-if="esc.tl_comment" class="mt-1 text-gray-500">{{ esc.tl_comment }}</p>
				</div>
			</div>

			<!-- Step 3: Admin Decision -->
			<div class="flex gap-3">
				<div class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
					:class="esc.step >= 3 ? 'bg-green-500' : esc.step === 2 && esc.tl_approved ? 'bg-orange-500' : 'bg-gray-300'">
					{{ esc.step >= 3 ? '✓' : '3' }}
				</div>
				<div class="flex-1 text-xs">
					<p class="font-semibold">Admin Final Decision</p>
					<p class="text-gray-500">AI will NOT execute this action — execution is always manual.</p>
					<div v-if="esc.step === 2 && esc.tl_approved && isAdmin" class="mt-2 flex gap-2">
						<button class="rounded bg-green-600 px-3 py-1 text-xs text-white hover:bg-green-700" @click="$emit('admin-approve-esc', esc.id)">
							<i class="fa fa-check mr-1"></i>Log manual execution
						</button>
						<button class="rounded bg-red-600 px-3 py-1 text-xs text-white hover:bg-red-700" @click="$emit('admin-reject-esc', esc.id)">
							<i class="fa fa-times mr-1"></i>Reject
						</button>
					</div>
				</div>
			</div>
		</div>

		<!-- Empty state -->
		<div v-if="escalations.length === 0" class="rounded-lg border border-gray-200 bg-white p-8 text-center text-sm text-gray-400">
			<i class="fa fa-check-circle mb-2 text-2xl text-green-400"></i>
			<p>No open escalations</p>
		</div>
	</div>
</template>

<script>
export default {
	name: 'AiEscalations',
	props: {
		isTeamLeader: { type: Boolean, default: false },
		isAdmin: { type: Boolean, default: false },
	},
	emits: ['approve-esc', 'reject-esc', 'admin-approve-esc', 'admin-reject-esc'],
	data() {
		return {
			escalations: [],
		};
	},
};
</script>
