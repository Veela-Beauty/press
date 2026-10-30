<template>
	<AlertAddPaymentMode
		class="mb-5"
		v-if="$team?.doc && !$team.doc.payment_mode && !$team.doc.parent_team"
	/>
	<AlertCardExpired
		class="mb-5"
		v-if="$team?.doc && isCardExpired && $team.doc?.payment_mode == 'Card'"
	/>
	<AlertAddressDetails
		class="mb-5"
		v-if="
			$team?.doc &&
			!$team.doc?.billing_details?.name &&
			$team.doc.payment_mode
		"
	/>
	<CustomAlerts ctx_type="List Page" />
	<AlertMandateInfo
		class="mb-5"
		v-if="
			$team?.doc &&
			isMandateNotSet &&
			$team.doc.currency === 'INR' &&
			$team.doc.payment_mode == 'Card'
		"
	/>
	<AlertUnpaidInvoices
		class="mb-5"
		v-if="
			hasUnpaidInvoices > 0 && $team.doc.payment_mode == 'Prepaid Credits'
		"
		:amount="hasUnpaidInvoices"
	/>
	<AlertBudgetThreshold
		class="mb-5"
		v-if="displayBudgetAlert > 0"
		:amount="displayBudgetAlert"
		:currency="$team.doc.currency == 'INR' ? '₹' : '$'"
	/>
</template>

<script>
// Team billing alerts shown at the top of list pages (moved out of ListPage.vue so
// custom list pages, like the benches list, show the same alerts).
import { defineAsyncComponent } from 'vue';
import dayjs from '../utils/dayjs';

export default {
	components: {
		AlertAddPaymentMode: defineAsyncComponent(
			() => import('./AlertAddPaymentMode.vue'),
		),
		AlertCardExpired: defineAsyncComponent(
			() => import('./AlertCardExpired.vue'),
		),
		AlertAddressDetails: defineAsyncComponent(
			() => import('./AlertAddressDetails.vue'),
		),
		AlertMandateInfo: defineAsyncComponent(
			() => import('./AlertMandateInfo.vue'),
		),
		AlertUnpaidInvoices: defineAsyncComponent(
			() => import('./AlertUnpaidInvoices.vue'),
		),
		AlertBudgetThreshold: defineAsyncComponent(
			() => import('./AlertBudgetThreshold.vue'),
		),
		CustomAlerts: defineAsyncComponent(() => import('./CustomAlerts.vue')),
	},
	computed: {
		isCardExpired() {
			if (this.$team.doc.payment_method?.expiry_year < dayjs().year()) {
				return true;
			} else if (
				this.$team.doc.payment_method?.expiry_year == dayjs().year() &&
				this.$team.doc.payment_method?.expiry_month < dayjs().month() + 1
			) {
				return true;
			} else {
				return false;
			}
		},
		isMandateNotSet() {
			return !this.$team.doc?.payment_method?.stripe_mandate_id;
		},
		hasUnpaidInvoices() {
			return this.$resources.getAmountDue.data;
		},
		displayBudgetAlert() {
			if (
				!this.$team.doc.receive_budget_alerts ||
				!this.$team.doc.monthly_alert_threshold ||
				this.$team.doc.monthly_alert_threshold <= 0
			) {
				return 0;
			}

			let difference =
				this.$resources.getCurrentBillingAmount.data -
				this.$team.doc.monthly_alert_threshold;

			return difference > 0 ? difference.toFixed(2) : 0;
		},
	},
	resources: {
		getAmountDue() {
			return {
				url: 'press.api.billing.total_unpaid_amount',
				auto: true,
			};
		},
		getCurrentBillingAmount() {
			return {
				url: 'press.api.billing.get_current_billing_amount',
				auto: true,
				cache: 'Current Billing Amount',
			};
		},
	},
};
</script>
