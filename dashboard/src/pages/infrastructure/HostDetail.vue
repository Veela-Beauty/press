<template>
  <div>
    <!-- MANAGED HOST -->
    <template v-if="node.kind === 'managed'">
      <!-- Unreachable callout -->
      <div
        v-if="node.health === 'unknown'"
        class="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
      >
        This host is unreachable — check the SSH cert / socket-proxy.
      </div>

      <!-- Plain host callout -->
      <div
        v-if="node.server_type === 'plain'"
        class="mb-4 rounded-lg border bg-gray-50 p-3 text-sm text-gray-600"
      >
        Plain host — watch-only in v1 (systemd status, no control).
      </div>

      <UnitTable
        :host="node.name"
        :units="node.units || []"
        @openUnit="$emit('openUnit', $event)"
        @reload="$emit('reload')"
      />
    </template>

    <!-- PRESS SERVER NODE -->
    <template v-else>
      <div class="space-y-2">
        <template v-if="node.benches && node.benches.length">
          <div
            v-for="b in node.benches"
            :key="b.name"
            class="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-3"
          >
            <div class="flex items-center gap-3">
              <!-- health dot -->
              <span
                class="inline-block h-[7px] w-[7px] shrink-0 rounded-full"
                :class="b.health === 'healthy' ? 'bg-green-500' : b.health === 'unknown' ? 'bg-gray-400' : 'bg-red-500'"
              />
              <span class="font-mono text-sm font-medium text-gray-900">{{ b.name }}</span>
              <span class="text-xs text-gray-500">
                {{ b.services_up ?? 0 }} up / {{ b.services_down ?? 0 }} down
                <template v-if="b.site_count != null"> &middot; {{ b.site_count }} sites</template>
              </span>
            </div>
            <Button variant="subtle" @click="goServer(node.name)">Open server page</Button>
          </div>
        </template>
        <p v-else class="py-4 text-sm text-gray-400">No benches.</p>
        <p class="text-xs text-gray-400">Bench service control lives on the server page.</p>
      </div>
    </template>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router';
import { Button } from 'frappe-ui';
import UnitTable from './UnitTable.vue';

defineProps({
  node: { type: Object, required: true },
});

defineEmits(['openUnit', 'reload']);

const router = useRouter();

function goServer(name) {
  router.push(`/servers/${name}`);
}
</script>
