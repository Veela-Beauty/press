<template>
	<!-- desk look (ACM-SP-05): in a page's Header the trail moves up into the top bar; the page's actions stay here -->
	<Teleport :to="topbarCrumbsEl || 'body'" :disabled="!toTopbar">
	<div class="flex min-w-0 items-center">
		<div
			class="flex min-w-0 items-center overflow-hidden text-ellipsis whitespace-nowrap"
		>
			<template v-for="(item, i) in linkItems" :key="item.label">
				<router-link
					class="flex items-center rounded px-0.5 py-1 text-lg font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400"
					:class="[
						i == linkItems.length - 1
							? 'text-gray-900'
							: 'text-gray-600 hover:text-gray-700'
					]"
					:to="item.route"
				>
					<slot name="prefix" :item="item" />
					<span>
						{{ item.label }}
					</span>
				</router-link>
				<span
					v-if="i != linkItems.length - 1"
					class="mx-0.5 text-base text-gray-500"
				>
					/
				</span>
			</template>
		</div>
	</div>
	</Teleport>
	<slot name="actions" />
</template>
<script setup>
import { computed, inject } from 'vue';
import { IN_PAGE_HEADER, topbarCrumbsEl } from '../topbar';

const inPageHeader = inject(IN_PAGE_HEADER, false);
const toTopbar = computed(() => inPageHeader && !!topbarCrumbsEl.value);

const props = defineProps({
	items: {
		type: Array,
		required: true
	}
});

const items = computed(() => {
	return (props.items || []).filter(Boolean);
});

const linkItems = computed(() => {
	let lastTwo = items.value.slice(-2);
	return lastTwo;
});
</script>
