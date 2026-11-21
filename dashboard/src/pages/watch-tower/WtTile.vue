<!-- A Watch Tower tile: the number, its comparison and a flag (the client-site board's tile, prototype ACM-SP-03). -->
<template>
	<component
		:is="link ? 'button' : 'div'"
		class="wt-tile"
		:class="{ link }"
		:type="link ? 'button' : undefined"
		@click="link && $emit('open')"
	>
		<div class="t">{{ label }}</div>
		<div class="v"><slot>{{ value }}</slot></div>
		<div class="c" :class="tone">{{ compare }}</div>
		<span v-if="flag" class="wt-flag" :class="flag.kind">{{ flag.text }}</span>
	</component>
</template>

<script setup>
defineProps({
	label: { type: String, required: true },
	value: { type: [String, Number], default: '' },
	compare: { type: String, default: '' },
	tone: { type: String, default: '' },
	flag: { type: Object, default: null },
	link: { type: Boolean, default: false },
});
defineEmits(['open']);
</script>

<style scoped>
.wt-tile {
	display: block;
	width: 100%;
	text-align: left;
	border: 1px solid #e9eaec;
	border-radius: 8px;
	padding: 12px 14px;
	background: #fff;
}
.wt-tile.link {
	cursor: pointer;
}
.wt-tile.link:hover {
	border-color: #dfe1e4;
	background: #f6f7f8;
}
.t {
	font-size: 13px;
	color: #525a64;
}
.v {
	font-size: 24px;
	font-weight: 650;
	margin-top: 2px;
	font-variant-numeric: tabular-nums;
	letter-spacing: -0.01em;
	color: #1c2024;
}
.c {
	font-size: 12.5px;
	color: #6b737b;
	margin-top: 2px;
	min-height: 18px;
}
.c.up {
	color: #c0392b;
}
.c.down {
	color: #18794e;
}
.wt-flag {
	display: inline-flex;
	align-items: center;
	gap: 5px;
	margin-top: 8px;
	font-size: 12px;
	font-weight: 550;
	border-radius: 5px;
	padding: 1px 8px;
}
.wt-flag::before {
	content: '';
	width: 6px;
	height: 6px;
	border-radius: 50%;
	background: currentColor;
}
.wt-flag.red {
	background: #fbe9e7;
	color: #c0392b;
}
.wt-flag.amber {
	background: #fdf3d6;
	color: #8a5a00;
}
.wt-flag.ok {
	background: #e7f4ec;
	color: #18794e;
}
</style>
