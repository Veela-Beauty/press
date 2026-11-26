<template>
  <div class="rounded-lg border border-gray-200 p-4">
    <!-- Header -->
    <div class="flex items-center gap-2">
      <span
        class="inline-block h-[7px] w-[7px] shrink-0 rounded-full"
        :class="hasIssues ? 'bg-red-500' : 'bg-green-500'"
      />
      <h2 class="text-sm font-semibold text-gray-900">
        {{ hasIssues ? 'Needs attention' : 'All clear' }}
      </h2>
      <span class="text-xs text-gray-500">
        {{ hasIssues
          ? `${security.length} security risks, ${down.length} down, ${servers.length} unreachable, ${over.length} overloaded`
          : `Nothing needs attention.${checkedAt ? ` Security checked from outside ${checkedTime}.` : ''}` }}
      </span>
    </div>

    <!-- Security (prototype PRS-SP-11): first, never cut by the 4-row cap below -->
    <div v-if="security.length" class="mt-3 flex flex-col gap-2">
      <div class="text-xs font-semibold text-gray-700">
        Security <span class="font-normal text-gray-400">checked from outside {{ checkedTime }}, hourly</span>
      </div>
      <template v-for="(f, i) in security" :key="`sec-${f.where}-${f.what}`">
        <div class="flex items-center gap-2">
          <span class="inline-block h-[7px] w-[7px] shrink-0 rounded-full" :class="SEV[f.severity].dot" />
          <span class="w-[62px] shrink-0 rounded-md py-px text-center text-xs font-semibold" :class="SEV[f.severity].chip">
            {{ f.severity }}
          </span>
          <span class="w-[190px] shrink-0 truncate font-mono text-sm text-gray-900" :title="f.where">{{ f.where }}</span>
          <span class="text-sm text-gray-700">{{ f.what }}</span>
          <div class="flex-1" />
          <Button variant="subtle" :aria-expanded="openFix === i" @click="openFix = openFix === i ? null : i">
            {{ openFix === i ? 'Hide' : 'Fix' }}
          </Button>
        </div>
        <div
          v-if="openFix === i"
          class="ml-[15px] rounded-md border border-gray-200 bg-gray-50 px-2.5 py-2 text-sm text-gray-700"
        >
          {{ f.fix }}
          <span class="mt-1 block text-xs text-gray-400">
            It leaves this list on the first hourly check that no longer finds it.
          </span>
        </div>
      </template>
      <div v-if="down.length || over.length || servers.length" class="my-1 h-px bg-gray-200" />
    </div>

    <!-- Triage list (down first, capped at 4) -->
    <div v-if="down.length || over.length || servers.length" class="mt-3 flex flex-col gap-2">
      <!-- Down-unit rows -->
      <div
        v-for="d in shownDown"
        :key="`down-${d.server}-${d.unit}`"
        class="flex items-center gap-2"
      >
        <span class="inline-block h-[7px] w-[7px] shrink-0 rounded-full bg-red-500" />
        <span class="font-mono text-sm text-gray-900">{{ d.unit }}</span>
        <span class="text-xs text-gray-400">on {{ d.server }}</span>
        <span class="text-xs text-red-700">{{ stateLabel(d.state) }}</span>
        <div class="flex-1" />
        <Button variant="subtle" @click="$emit('view', d.server)">View</Button>
      </div>

      <!-- Overloaded-host rows -->
      <div
        v-for="o in shownOver"
        :key="`over-${o.name}`"
        class="flex items-center gap-2"
      >
        <span class="inline-block h-[7px] w-[7px] shrink-0 rounded-full bg-amber-500" />
        <span class="font-mono text-sm text-gray-900">{{ o.name }}</span>
        <span class="text-xs text-gray-400">
          overloaded {{ loadState(o)?.which }} {{ loadState(o)?.val }}%
        </span>
        <div class="flex-1" />
        <Button variant="subtle" @click="$emit('view', o.name)">View</Button>
      </div>

      <!-- Unreachable Press-server rows -->
      <div
        v-for="s in shownServers"
        :key="`srv-${s.name}`"
        class="flex items-center gap-2"
      >
        <span class="inline-block h-[7px] w-[7px] shrink-0 rounded-full bg-red-500" />
        <span class="font-mono text-sm text-gray-900">{{ s.name }}</span>
        <span class="text-xs text-gray-400">server unreachable</span>
        <div class="flex-1" />
        <Button variant="subtle" @click="$emit('view', s.name)">View</Button>
      </div>

      <!-- Overflow footer -->
      <div v-if="triage > 4" class="text-xs text-gray-400">
        +{{ triage - 4 }} more
      </div>
    </div>

  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { Button } from 'frappe-ui';
import { issues, overloaded, unreachableServers, loadState, stateLabel } from './infra-derive';

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  // Exposure Watch rows: { severity: High|Medium|Low, where, what, fix }, worst first
  security: { type: Array, default: () => [] },
  checkedAt: { type: String, default: null },
});
defineEmits(['view']);

const down    = computed(() => issues(props.nodes));
const over    = computed(() => overloaded(props.nodes));
const servers = computed(() => unreachableServers(props.nodes));
const triage  = computed(() => down.value.length + over.value.length + servers.value.length);
const hasIssues = computed(() => triage.value + props.security.length > 0);

// Severity is written as text (the chip); the dot repeats it for a quick scan.
const SEV = {
  High:   { dot: 'bg-red-500',   chip: 'bg-red-50 text-red-700' },
  Medium: { dot: 'bg-amber-500', chip: 'bg-amber-50 text-amber-700' },
  Low:    { dot: 'bg-gray-400',  chip: 'bg-gray-100 text-gray-700' },
};
const openFix = ref(null);
// "2026-11-26 09:12" -> "09:12" today, the date and time otherwise
const checkedTime = computed(() => {
  if (!props.checkedAt) return '';
  const [day, time] = props.checkedAt.split(' ');
  return day === new Date().toISOString().slice(0, 10) ? time : props.checkedAt;
});

// Down units first, then overloaded hosts, then unreachable servers; max 4 combined.
const shownDown    = computed(() => down.value.slice(0, 4));
const shownOver    = computed(() => over.value.slice(0, Math.max(0, 4 - shownDown.value.length)));
const shownServers = computed(() => servers.value.slice(0, Math.max(0, 4 - shownDown.value.length - shownOver.value.length)));
</script>
