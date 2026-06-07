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
        v-else-if="tree.error"
        class="rounded-lg border border-red-200 bg-red-50 p-4 text-base text-red-700"
      >
        {{ tree.error.messages?.join(', ') || tree.error.message }}
      </div>

      <template v-else>
        <!-- Gate-0 preflight banner: only relevant while managed hosts exist -->
        <div
          v-if="hasManaged && gate0.data && !gate0.data.ready"
          class="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3.5 text-sm"
        >
          <div class="flex items-start gap-2">
            <span class="mt-1 h-2 w-2 shrink-0 rounded-full bg-amber-500" />
            <div>
              <p class="font-medium text-amber-900">Gate 0 is not provisioned, so managed hosts cannot connect yet.</p>
              <ul class="mt-1.5 space-y-1 text-amber-800">
                <li v-for="c in gate0.data.checks.filter((x) => !x.ok)" :key="c.name">
                  <span class="font-medium">{{ c.name }}:</span> {{ c.hint }}
                </li>
              </ul>
            </div>
          </div>
        </div>

        <NeedsAttention :nodes="allNodes" class="mb-4" @view="onOpen" />
        <ServerList
          :nodes="allNodes"
          :view="view"
          @open="onOpen"
          @add="onAdd"
        />
      </template>
    </div>

    <!-- Host detail drawer (type-aware: managed control vs Press read-only) -->
    <HostDrawer
      :node="detailNode"
      @close="detailNode = null"
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
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import Header from '../../components/Header.vue';
import { useInfraTree, useGate0Status } from './infra-api';
import { isManaged } from './infra-derive';
import ServerList from './ServerList.vue';
import NeedsAttention from './NeedsAttention.vue';
import HostDrawer from './HostDrawer.vue';
import AddHostWizard from './AddHostWizard.vue';

// --- Data ---
const tree = useInfraTree();
const gate0 = useGate0Status();
const router = useRouter();

// --- UI state ---
const view       = ref('list');   // 'list' | 'cards'
const fresh      = ref('just now');
const detailNode = ref(null);      // the node shown in the drawer, or null

// --- 15-second polling ---
let timer = null;
onMounted(() => {
  timer = setInterval(() => { tree.reload(); fresh.value = 'just now'; }, 15000);
});
onUnmounted(() => clearInterval(timer));

// --- Derived nodes ---
const allNodes   = computed(() => tree.data?.servers || []);
const hasManaged = computed(() => allNodes.value.some(isManaged));

// --- Breadcrumbs ---
const crumbs = computed(() => [{ label: 'Infrastructure', route: { name: 'Infrastructure' } }]);

// --- Open a node: managed hosts open the container drawer, Press servers go to the native server page ---
function onOpen(name) {
  const node = allNodes.value.find((n) => n.name === name);
  if (!node) return;
  if (isManaged(node)) detailNode.value = node;
  else router.push('/servers/' + node.name);
}

// --- Add-host wizard ---
const wizardOpen = ref(false);
function onAdd() { wizardOpen.value = true; }
</script>
