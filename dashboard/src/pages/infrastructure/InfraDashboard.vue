<template>
  <div class="flex h-full flex-col">
    <!-- Sticky topbar -->
    <div class="sticky top-0 z-10 shrink-0">
      <Header>
        <Breadcrumbs :items="crumbs" />
        <template #actions>
          <div class="flex items-center gap-3">
            <!-- Nav toggle: Servers | Infrastructure -->
            <div class="flex rounded-md bg-gray-100 p-0.5 text-sm">
              <button
                class="rounded px-3 py-1 transition-colors"
                :class="nav === 'servers' ? 'bg-white shadow-sm font-medium text-gray-900' : 'text-gray-500 hover:text-gray-700'"
                @click="setNav('servers')"
              >Servers</button>
              <button
                class="rounded px-3 py-1 transition-colors"
                :class="nav === 'infra' ? 'bg-white shadow-sm font-medium text-gray-900' : 'text-gray-500 hover:text-gray-700'"
                @click="setNav('infra')"
              >Infrastructure</button>
            </div>

            <!-- List / Cards toggle (hidden when drilled into a group) -->
            <div v-if="!path.group" class="flex rounded-md bg-gray-100 p-0.5 text-sm">
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
        <!-- LEVEL 1: server/host list -->
        <ServerList
          v-if="!path.server"
          :nav="nav"
          :nodes="navNodes"
          :view="view"
          @drill="drill"
          @add="onAdd"
        />

        <!-- LEVEL 2: server / host detail (HostDetail lands in Task 6) -->
        <div v-else-if="!path.group" class="space-y-3">
          <button
            class="text-sm text-blue-600 hover:underline"
            @click="go(null, null)"
          >&larr; Back</button>
          <div class="rounded-lg border border-gray-200 p-6 text-gray-600">
            Detail for <span class="font-mono font-medium">{{ path.server }}</span>
            &mdash; host/unit views land in Task 6 / 7.
          </div>
        </div>

        <!-- LEVEL 3: group unit table (UnitTable lands in Task 6) -->
        <div v-else class="space-y-3">
          <button
            class="text-sm text-blue-600 hover:underline"
            @click="go(path.server, null)"
          >&larr; Back</button>
          <div class="rounded-lg border border-gray-200 p-6 text-gray-600">
            Units for group <span class="font-mono font-medium">{{ path.group }}</span>
            &mdash; Task 6.
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue';
import Header from '../../components/Header.vue';
import { Button } from 'frappe-ui';
import { useInfraTree } from './infra-api';
import { partition } from './infra-derive';
import ServerList from './ServerList.vue';

// ─── Data ─────────────────────────────────────────────────────────────────────
const tree = useInfraTree();

// ─── UI state ─────────────────────────────────────────────────────────────────
const nav   = ref('infra');       // 'servers' | 'infra'
const path  = reactive({ server: null, group: null });
const view  = ref('list');        // 'list' | 'cards'
const fresh = ref('just now');

// ─── 15-second polling ────────────────────────────────────────────────────────
let timer = null;
onMounted(() => {
  timer = setInterval(() => {
    tree.reload();
    fresh.value = 'just now';
  }, 15000);
});
onUnmounted(() => clearInterval(timer));

// ─── Derived nodes ────────────────────────────────────────────────────────────
const allNodes  = computed(() => tree.data?.servers || []);
const navNodes  = computed(() => {
  const { servers, infra } = partition(allNodes.value);
  return nav.value === 'infra' ? infra : servers;
});
const current   = computed(() => allNodes.value.find((n) => n.name === path.server) || null);

// ─── Breadcrumbs ──────────────────────────────────────────────────────────────
const crumbs = computed(() => {
  const base = [{
    label: nav.value === 'infra' ? 'Infrastructure' : 'Servers',
    route: { name: 'Infrastructure' },
  }];
  if (path.server) base.push({ label: path.server });
  if (path.group)  base.push({ label: path.group });
  return base;
});

// ─── Navigation helpers ───────────────────────────────────────────────────────
function setNav(n) {
  nav.value = n;
  path.server = null;
  path.group  = null;
}

function drill(name) {
  path.server = name;
  path.group  = null;
}

function openGroup(gid) {
  path.group = gid;
}

function go(server, group) {
  path.server = server;
  path.group  = group;
}

// ─── Stubs (wired in later tasks) ─────────────────────────────────────────────
function onAdd() {
  // Task 9: Add host wizard
}
</script>
