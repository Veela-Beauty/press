<template>
	<div class="flex h-full flex-col">
		<Header :sticky="true">
			<Breadcrumbs
				:items="[{ label: object.list.title, route: object.list.route }]"
			/>
		</Header>
		<div class="p-5 pb-0">
			<ListPageAlerts />
			<ObjectList :options="listOptions" />
		</div>
	</div>
</template>

<script>
import Header from '../components/Header.vue';
import ObjectList from '../components/ObjectList.vue';
import { Breadcrumbs, Button, Dropdown, TextInput } from 'frappe-ui';
import { getObject } from '../objects';
import ListPageAlerts from '../components/ListPageAlerts.vue';

export default {
	components: {
		Header,
		Breadcrumbs,
		ObjectList,
		Button,
		Dropdown,
		TextInput,
		ListPageAlerts,
	},
	props: {
		objectType: {
			type: String,
			required: true,
		},
	},
	methods: {
		getRoute(row) {
			return {
				name: `${this.object.doctype} Detail`,
				params: {
					name: row.name,
				},
			};
		},
	},
	computed: {
		object() {
			return getObject(this.objectType);
		},
		listOptions() {
			return {
				...this.object.list,
				doctype: this.object.doctype,
				route: this.object.detail ? this.getRoute : null,
			};
		},
	},
};
</script>
