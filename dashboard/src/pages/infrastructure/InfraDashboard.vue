<template>
  <div class="flex h-full flex-col">
    <!-- Sticky topbar -->
    <div class="sticky top-0 z-10 shrink-0">
      <!-- One row: the tabs on the left, the open tab's actions on the right (owner 27 Nov: no empty band, no second
           row). On a phone the page title stays in this row, so the tabs get their own row under it.
           Servers = this page; Inventory = our NetBox (servers, clients, sites, handbooks) inside the page, signed
           in through AutoDeploy. Staff only, like the page. -->
      <Header>
        <Breadcrumbs :items="crumbs" />
        <!-- the first tab's text lines up with the page's left edge once the trail has moved to the top bar -->
        <div v-if="!$isMobile" class="mr-auto flex" :class="topbarCrumbsEl ? '-ml-4' : 'ml-2'">
          <button
            v-for="t in TABS"
            :key="t.id"
            type="button"
            :class="tabClass(tab === t.id)"
            :aria-pressed="tab === t.id"
            @click="setTab(t.id)"
          >{{ t.label }}</button>
        </div>
        <template #actions>
          <div v-if="tab === 'servers'" class="flex items-center gap-3">
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
          <a
            v-else
            :href="INVENTORY_URL"
            target="_blank"
            rel="noopener"
            class="whitespace-nowrap px-2 text-sm text-gray-500 hover:text-gray-900"
          >Open full screen</a>
        </template>
      </Header>
      <div v-if="$isMobile" :class="[TAB_STRIP_PANEL_TOP, TAB_STRIP_DIVIDER, 'px-1']">
        <button
          v-for="t in TABS"
          :key="t.id"
          type="button"
          :class="tabClass(tab === t.id)"
          :aria-pressed="tab === t.id"
          @click="setTab(t.id)"
        >{{ t.label }}</button>
      </div>
    </div>

    <!-- Inventory: loaded on first open, then kept, so NetBox stays where you left it when you switch back -->
    <iframe
      v-if="inventoryOpened"
      v-show="tab === 'inventory'"
      :src="INVENTORY_URL"
      title="Inventory"
      class="w-full flex-1 border-0"
    />

    <!-- Content area -->
    <div v-show="tab === 'servers'" class="flex-1 overflow-auto p-5">
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
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import Header from '../../components/Header.vue';
import { TAB_STRIP_PANEL_TOP, TAB_STRIP_DIVIDER, tabClass } from '../../components/_shared/tabClasses.js';
import { topbarCrumbsEl } from '../../components/topbar';
import { useInfraTree, useGate0Status, useSecurityFindings } from './infra-api';
import { isManaged } from './infra-derive';
import ServerList from './ServerList.vue';
import NeedsAttention from './NeedsAttention.vue';
import UnitDrawer from './UnitDrawer.vue';
import AddHostWizard from './AddHostWizard.vue';

// Accurate Systems Infrastructure (NetBox on press-ctrl): sanadeoi-infra/press-ctrl/netbox. ?sso=autodeploy signs in
// through AutoDeploy with no login screen; NetBox lets only this page frame it (frame-ancestors in its nginx).
const INVENTORY_URL = 'https://netbox.mvpstorm.com/?sso=autodeploy';
const TABS = [{ id: 'servers', label: 'Servers' }, { id: 'inventory', label: 'Inventory' }];

// --- Tab, kept in the address (?tab=inventory) so a link or a reload opens the same tab ---
const route = useRoute();
const router = useRouter();
const tab = computed(() => (route.query.tab === 'inventory' ? 'inventory' : 'servers'));
const inventoryOpened = ref(tab.value === 'inventory');
watch(tab, (t) => { if (t === 'inventory') inventoryOpened.value = true; });
function setTab(id) {
  router.replace({ query: { ...route.query, tab: id === 'servers' ? undefined : id } });
}

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
