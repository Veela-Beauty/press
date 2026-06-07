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
          ? `${down.length + servers.length} down, ${over.length} overloaded`
          : 'Nothing needs attention.' }}
      </span>
    </div>

    <!-- Triage list (down first, capped at 4) -->
    <div v-if="hasIssues" class="mt-3 flex flex-col gap-2">
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

      <!-- Down Press-server rows -->
      <div
        v-for="s in shownServers"
        :key="`srv-${s.name}`"
        class="flex items-center gap-2"
      >
        <span class="inline-block h-[7px] w-[7px] shrink-0 rounded-full bg-red-500" />
        <span class="font-mono text-sm text-gray-900">{{ s.name }}</span>
        <span class="text-xs text-gray-400">server {{ s.health === 'unknown' ? 'unreachable' : 'down' }}</span>
        <div class="flex-1" />
        <Button variant="subtle" @click="$emit('view', s.name)">View</Button>
      </div>

      <!-- Overflow footer -->
      <div v-if="total > 4" class="text-xs text-gray-400">
        +{{ total - 4 }} more
      </div>
    </div>

    <!-- Alerts panel: deferred until Watch Tower endpoint confirmed -->
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { Button } from 'frappe-ui';
import { issues, overloaded, downServers, loadState, stateLabel } from './infra-derive';

const props = defineProps({
  nodes: { type: Array, default: () => [] },
});
defineEmits(['view']);

const down    = computed(() => issues(props.nodes));
const over    = computed(() => overloaded(props.nodes));
const servers = computed(() => downServers(props.nodes));
const total   = computed(() => down.value.length + over.value.length + servers.value.length);
const hasIssues = computed(() => total.value > 0);

// Down units first, then overloaded hosts, then down servers; max 4 combined.
const shownDown    = computed(() => down.value.slice(0, 4));
const shownOver    = computed(() => over.value.slice(0, Math.max(0, 4 - shownDown.value.length)));
const shownServers = computed(() => servers.value.slice(0, Math.max(0, 4 - shownDown.value.length - shownOver.value.length)));
</script>
