<template>
  <div class="flex h-full flex-col">
    <!-- Sticky topbar -->
    <div class="sticky top-0 z-10 shrink-0">
      <Header>
        <Breadcrumbs :items="crumbs" />
        <template #actions>
          <div class="flex items-center gap-3">
            <!-- List / Cards toggle -->
            <div class="flex rounded-md bg-gray-100 p-0.5 text-sm">
              <button
                class="rounded px-2.5 py-1 transition-colors"
                :class="view === 'list' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'"
                @click="view = 'list'"
              >List</button>
              <button
                class="rounded px-2.5 py-1 transition-colors"
                :class="view === 'cards' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'"
                @click="view = 'cards'"
              >Cards</button>
            </div>

            <!-- Freshness indicator -->
            <span class="flex items-center gap-1.5 text-xs text-gray-500">
              <span class="h-1.5 w-1.5 rounded-full bg-green-500" />
              updated {{ fresh }}
            </span>
          </div>
        </template>
      </Header>
    </div>

    <!-- Content area -->
    <div class="flex-1 overflow-auto p-5">
      <!-- Initial load -->
      <div v-if="tree.loading && !tree.data" class="text-base text-gray-600">
        Loading infrastructure...
      </div>

      <!-- Error state -->
      <div
        v-else-if="tree.error && !tree.data"
        class="rounded-lg border border-red-200 bg-red-50 p-4 text-base text-red-700"
      >
        {{ tree.error.messages?.join(', ') || tree.error.message }}
      </div>

      <template v-else>
        <!-- A failed poll keeps the last data on screen (and what is expanded) -->
        <div v-if="tree.error" class="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          Refresh failed, showing the last data: {{ tree.error.messages?.join(', ') || tree.error.message }}
        </div>
        <NeedsAttention
          :nodes="allNodes"
          :security="security.data?.findings || []"
          :checked-at="security.data?.checked_at"
          :skipped="security.data?.skipped || []"
          :setup="setupChecks"
          class="mb-4"
          @view="onOpen"
        />
        <ServerList
          ref="serverList"
          :nodes="allNodes"
          :view="view"
          @open="onOpen"
          @add="onAdd"
          @openUnit="onOpenUnit"
          @reload="tree.reload()"
        />
      </template>
    </div>

    <!-- One container's logs and controls (servers themselves open in place in ServerList) -->
    <UnitDrawer
      :host="logHost"
      :unit="logUnit"
      @close="logUnitKey = null"
      @reload="tree.reload()"
    />

    <!-- Add-host wizard (Task 9) -->
    <AddHostWizard
      :open="wizardOpen"
      @close="wizardOpen = false"
      @added="tree.reload()"
    />
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue';
import Header from '../../components/Header.vue';
import { useInfraTree, useGate0Status, useSecurityFindings } from './infra-api';
import { isManaged } from './infra-derive';
import ServerList from './ServerList.vue';
import NeedsAttention from './NeedsAttention.vue';
import UnitDrawer from './UnitDrawer.vue';
import AddHostWizard from './AddHostWizard.vue';

// --- Data ---
const tree = useInfraTree();
const security = useSecurityFindings();
const gate0 = useGate0Status();

// --- UI state ---
const view       = ref('list');   // 'list' | 'cards'
const fresh      = ref('just now');
const serverList = ref(null);
const logHost    = ref('');
const logUnitKey = ref(null);      // _id (or name) of the unit whose drawer is open
// Resolved from the live tree so the drawer follows each 15 s poll instead of a snapshot.
const logUnit = computed(() => {
  if (!logUnitKey.value) return null;
  const units = allNodes.value.find((n) => n.name === logHost.value)?.units || [];
  return units.find((u) => (u._id || u.name) === logUnitKey.value) || null;
});

// --- 15-second polling ---
let timer = null;
let securityTimer = null;
onMounted(() => {
  timer = setInterval(() => { tree.reload(); fresh.value = 'just now'; }, 15000);
  // the security check runs hourly, so every 5 minutes is plenty
  securityTimer = setInterval(() => security.reload(), 5 * 60 * 1000);
});
onUnmounted(() => { clearInterval(timer); clearInterval(securityTimer); });

// --- Derived nodes ---
const allNodes   = computed(() => tree.data?.servers || []);
const hasManaged = computed(() => allNodes.value.some(isManaged));
// Gate-0 checks that failed, shown as a Setup row in Needs attention while managed hosts exist
const setupChecks = computed(() => (hasManaged.value && gate0.data && !gate0.data.ready
  ? (gate0.data.checks || []).filter((c) => !c.ok) : []));

// --- Breadcrumbs ---
const crumbs = computed(() => [{ label: 'Infrastructure', route: { name: 'Infrastructure' } }]);

// --- Open a server: show it expanded in the list (Needs attention "View", a click in Cards view) ---
async function onOpen(name) {
  view.value = 'list';
  await nextTick();
  serverList.value?.expand(name);
}

function onOpenUnit(host, unit) {
  logHost.value = host;
  logUnitKey.value = unit._id || unit.name;
}

// --- Add-host wizard ---
const wizardOpen = ref(false);
function onAdd() { wizardOpen.value = true; }
</script>
