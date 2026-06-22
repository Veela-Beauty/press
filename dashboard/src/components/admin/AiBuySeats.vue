<template>
	<div class="space-y-4">
		<div>
			<h2 class="text-lg font-semibold">Buy seats</h2>
			<p class="text-xs text-gray-500">Pick a plan. On approval the seat allotment is raised for the site.</p>
		</div>
		<div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
			<div v-for="plan in plans" :key="plan.name" class="rounded-lg border bg-white p-5" :class="plan.featured ? 'border-blue-500 ring-1 ring-blue-500' : 'border-gray-200'">
				<div class="flex items-center gap-2">
					<h3 class="text-sm font-semibold">{{ plan.name }}</h3>
					<span v-if="plan.featured" class="rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-medium text-green-700">popular</span>
				</div>
				<div class="mt-1 text-2xl font-bold">${{ plan.price }} <span class="text-xs font-normal text-gray-400">/ seat · mo</span></div>
				<ul class="my-3 space-y-1 text-xs text-gray-500">
					<li v-for="f in plan.features" :key="f">{{ f }}</li>
				</ul>
				<Button class="w-full" :variant="plan.featured ? 'solid' : 'subtle'" @click="choose(plan)">{{ plan.cta }}</Button>
			</div>
		</div>
		<p class="text-xs text-gray-400">Maps to an ERPNext Quotation → approve → seat allotment raised on the client’s AI Seat Policy.</p>
	</div>
</template>

<script>
import { Button } from 'frappe-ui';
import { toast } from 'vue-sonner';

export default {
	name: 'AiBuySeats',
	components: { Button },
	data() {
		return {
			plans: [
				{ name: 'Starter', price: 9, cta: 'Choose', features: ['smart + fast tiers', '$5 budget / seat', 'up to 5 seats'] },
				{ name: 'Team', price: 7, featured: true, cta: 'Choose Team', features: ['all tiers', '$10 budget / seat', 'up to 20 seats', 'usage analytics'] },
				{ name: 'Business', price: 5, cta: 'Contact us', features: ['all tiers + priority', 'custom budget', 'unlimited seats', 'SSO + audit'] },
			],
		};
	},
	methods: {
		choose(plan) {
			// Order-to-cash (Quotation → Invoice) is the next build (roadmap P0).
			toast.success(`Plan "${plan.name}" selected — checkout is on the roadmap (Quotation → Invoice).`);
		},
	},
};
</script>
