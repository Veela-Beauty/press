<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs :items="[{ label: 'Infrastructure', route: { name: 'Infrastructure' } }]" />
			</Header>
		</div>
		<div class="p-5">
			<div v-if="tree.loading" class="text-base text-gray-600">Loading infrastructure...</div>
			<div v-else-if="tree.error" class="text-base text-red-600">{{ tree.error.messages?.join(', ') || tree.error.message }}</div>
			<div v-else>
				<h1 class="text-lg font-semibold mb-3">Infrastructure</h1>
				<ul class="text-sm">
					<li v-for="s in (tree.data?.servers || [])" :key="s.name" class="py-1 font-mono">
						{{ s.name }} <span class="text-gray-500">{{ s.kind === 'managed' ? '(managed ' + s.server_type + ')' : '(press server)' }}</span>
					</li>
				</ul>
			</div>
		</div>
	</div>
</template>
<script setup>
import { createResource } from 'frappe-ui';
import Header from '../../components/Header.vue';
const tree = createResource({ url: 'press.api.infra_board.get_infra_tree', auto: true });
</script>
