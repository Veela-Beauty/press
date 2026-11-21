<!-- Stacked bars per day with a hover tooltip, drawn in SVG exactly like the approved prototype (ACM-SP-03): one axis
from zero, a 1px surface gap between segments, rounded top, whole-number ticks. A click on a segment emits its layer. -->
<template>
	<div ref="host" class="relative px-3 pb-1 pt-2.5" @mouseleave="hover = null">
		<svg v-if="width" :width="width" :height="height" role="img" :aria-label="label" @mousemove="move">
			<g v-for="t in ticks" :key="`t${t}`">
				<line :x1="L" :x2="width - R" :y1="y(t)" :y2="y(t)" stroke="#eceef0" />
				<text :x="L - 8" :y="y(t) + 4" text-anchor="end" font-size="11.5" fill="#7c838b">{{ t }}</text>
			</g>
			<g v-for="(day, i) in days" :key="day">
				<rect
					v-for="seg in segments[i]"
					:key="seg.k"
					:x="seg.x"
					:y="seg.y"
					:width="barWidth"
					:height="seg.h"
					:rx="seg.top ? 2.5 : 0"
					:fill="seg.color"
					:class="{ 'cursor-pointer': pickable(seg.k) }"
					@click="pickable(seg.k) && $emit('pick', seg.k)"
				/>
				<text
					v-if="i % labelEvery === 0 || i === days.length - 1"
					:x="L + slot * i + slot / 2"
					:y="height - 8"
					text-anchor="middle"
					font-size="11.5"
					fill="#7c838b"
				>
					{{ shortDay(day) }}
				</text>
			</g>
		</svg>
		<div v-if="hover" class="wt-tip" :style="{ left: `${hover.left}px`, top: `${hover.top}px` }">
			<div class="d">{{ shortDay(days[hover.i]) }}</div>
			<div v-for="layer in layers" :key="layer.name" class="r">
				<i :style="{ background: layer.color }" />{{ layer.name }}<b>{{ layer.values[hover.i] ?? '-' }}</b>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { shortDay } from './shared';

const props = defineProps({
	days: { type: Array, required: true },
	layers: { type: Array, required: true }, // [{ name, color, values: [number | null per day] }]
	height: { type: Number, default: 230 },
	label: { type: String, default: '' },
	pickableLayers: { type: Number, default: 0 }, // the first n layers emit 'pick' when clicked
});
defineEmits(['pick']);

const L = 38, R = 8, T = 10, B = 26;
const host = ref(null);
const width = ref(0);
const hover = ref(null);
let observer;
onMounted(() => {
	observer = new ResizeObserver(() => (width.value = Math.max(280, host.value.clientWidth - 24)));
	observer.observe(host.value);
});
onBeforeUnmount(() => observer?.disconnect());

const slot = computed(() => (width.value - L - R) / props.days.length);
const barWidth = computed(() => Math.max(3, Math.min(18, slot.value * 0.62)));
const labelEvery = computed(() => (slot.value < 12 ? 10 : 5));
const totals = computed(() => props.days.map((_, i) => props.layers.reduce((a, l) => a + (l.values[i] || 0), 0)));
const step = computed(() => {
	const raw = Math.max(4, ...totals.value) / 4;
	const pow = 10 ** Math.floor(Math.log10(raw));
	const n = raw / pow;
	return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * pow;
});
const top = computed(() => Math.ceil(Math.max(4, ...totals.value) / step.value) * step.value);
const ticks = computed(() => Array.from({ length: Math.round(top.value / step.value) + 1 }, (_, i) => i * step.value));
const y = (v) => T + (props.height - T - B) * (1 - v / top.value);
const segments = computed(() =>
	props.days.map((_, i) => {
		const drawn = props.layers.map((l, k) => ({ k, l })).filter(({ l }) => (l.values[i] || 0) > 0);
		let base = 0;
		return drawn.map(({ k, l }, n) => {
			const v = l.values[i];
			const gap = n < drawn.length - 1 ? 1 : 0;
			const seg = {
				k,
				color: l.color,
				x: L + slot.value * i + (slot.value - barWidth.value) / 2,
				y: y(base + v) + gap,
				h: Math.max(1, y(base) - y(base + v) - gap),
				top: n === drawn.length - 1,
			};
			base += v;
			return seg;
		});
	}),
);
const pickable = (k) => k < props.pickableLayers;

function move(event) {
	const box = host.value.getBoundingClientRect();
	const x = event.clientX - box.left - 12; // the host's left padding
	const i = Math.max(0, Math.min(props.days.length - 1, Math.floor((x - L) / slot.value)));
	hover.value = { i, left: Math.min(event.clientX - box.left + 14, box.width - 190), top: Math.max(6, event.clientY - box.top - 40) };
}
</script>

<style scoped>
.wt-tip {
	position: absolute;
	pointer-events: none;
	background: #fff;
	border: 1px solid #dfe1e4;
	border-radius: 8px;
	box-shadow: 0 6px 20px rgba(16, 24, 40, 0.12);
	padding: 8px 10px;
	font-size: 12.5px;
	min-width: 170px;
	z-index: 5;
}
.wt-tip .d {
	color: #7c838b;
	margin-bottom: 4px;
}
.wt-tip .r {
	display: flex;
	align-items: center;
	gap: 7px;
	line-height: 1.7;
}
.wt-tip .r i {
	width: 9px;
	height: 9px;
	border-radius: 50%;
	display: inline-block;
}
.wt-tip .r b {
	margin-left: auto;
	font-variant-numeric: tabular-nums;
}
</style>
