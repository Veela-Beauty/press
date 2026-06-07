<template>
  <div class="flex h-full flex-col">
    <!-- Sticky topbar -->
    <div class="sticky top-0 z-10 shrink-0">
      <Header>
        <Breadcrumbs :items="[{ label: 'Notifications', route: { name: 'NotificationsFeed' } }]" />
        <template #actions>
          <Button
            variant="subtle"
            :loading="markingAll"
            :disabled="counts.unread === 0"
            @click="markAll"
          >Mark all as read</Button>
        </template>
      </Header>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-auto p-5">
      <div class="mx-auto max-w-3xl">
        <!-- Summary chips (also act as quick filters) -->
        <div class="mb-4 flex flex-wrap gap-2">
          <button
            class="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm transition-colors"
            :class="tab === 'unread' ? 'border-gray-900 bg-gray-100 text-gray-900' : 'border-gray-200 text-gray-700 hover:border-gray-400'"
            :aria-pressed="tab === 'unread'"
            @click="setTab(tab === 'unread' ? 'all' : 'unread')"
          >
            <span class="font-semibold">{{ counts.unread }}</span> unread
          </button>
          <button
            class="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm transition-colors"
            :class="tab === 'attention' ? 'border-gray-900 bg-gray-100 text-gray-900' : 'border-gray-200 text-gray-700 hover:border-gray-400'"
            :aria-pressed="tab === 'attention'"
            @click="setTab(tab === 'attention' ? 'all' : 'attention')"
          >
            <span class="h-[7px] w-[7px] rounded-full bg-red-500" />
            <span class="font-semibold">{{ counts.attention }}</span> need attention
          </button>
          <button
            class="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm transition-colors"
            :class="sevFilter === 'Error' ? 'border-gray-900 bg-gray-100 text-gray-900' : 'border-gray-200 text-gray-700 hover:border-gray-400'"
            :aria-pressed="sevFilter === 'Error'"
            @click="toggleErrorFilter"
          >
            <span class="h-[7px] w-[7px] rounded-full bg-red-500" />
            <span class="font-semibold">{{ counts.errors }}</span> errors
          </button>
        </div>

        <!-- Filter bar: tabs + type + severity -->
        <div class="mb-4 flex flex-wrap items-center gap-3">
          <div class="inline-flex rounded-md bg-gray-100 p-0.5 text-sm">
            <button
              v-for="t in tabs"
              :key="t.value"
              class="rounded px-3 py-1 transition-colors"
              :class="tab === t.value ? 'bg-white font-medium text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
              @click="setTab(t.value)"
            >{{ t.label }}</button>
          </div>

          <select
            v-model="typeFilter"
            class="rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-sm text-gray-700"
            aria-label="Filter by type"
          >
            <option value="">All types</option>
            <option v-for="t in typeOptions" :key="t" :value="t">{{ t }}</option>
          </select>

          <select
            v-model="sevFilter"
            class="rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-sm text-gray-700"
            aria-label="Filter by severity"
          >
            <option value="">All severities</option>
            <option value="Error">Error</option>
            <option value="Warning">Warning</option>
            <option value="Success">Success</option>
            <option value="Info">Info</option>
          </select>
        </div>

        <!-- Loading skeleton -->
        <div v-if="list.loading && !list.data" class="space-y-2">
          <div v-for="i in 4" :key="i" class="h-[68px] animate-pulse rounded-lg border border-gray-200 bg-gray-50" />
        </div>

        <!-- Error -->
        <div
          v-else-if="list.error"
          class="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        >
          {{ list.error.messages?.join(', ') || list.error.message }}
        </div>

        <!-- Empty -->
        <div v-else-if="!groups.length" class="py-16 text-center">
          <div class="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-full bg-gray-100 text-gray-400">
            <FeatherIcon name="bell" class="h-5 w-5" />
          </div>
          <h3 class="text-base font-semibold text-gray-900">You're all caught up</h3>
          <p class="mt-1 text-sm text-gray-500">No notifications match this filter.</p>
        </div>

        <!-- Feed grouped by time bucket -->
        <template v-else>
          <template v-for="g in groups" :key="g.label">
            <div class="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-gray-500 first:mt-0">
              {{ g.label }}
            </div>
            <div
              v-for="n in g.items"
              :key="n.name"
              class="mb-2 flex gap-3 rounded-lg border border-gray-200 p-3.5"
              :class="n.read ? 'bg-gray-50/60' : 'bg-white'"
            >
              <!-- Severity-tinted icon -->
              <div class="grid h-[30px] w-[30px] shrink-0 place-items-center rounded-md" :class="sevIconClass(n)">
                <FeatherIcon :name="iconName(n)" class="h-4 w-4" />
              </div>

              <div class="min-w-0 flex-1">
                <!-- Title line -->
                <div class="flex flex-wrap items-center gap-2">
                  <span v-if="!n.read" class="h-[7px] w-[7px] shrink-0 rounded-full bg-blue-500" aria-label="Unread" />
                  <span class="text-sm font-semibold" :class="n.read ? 'text-gray-500' : 'text-gray-900'">
                    {{ n.title || n.type }}
                  </span>
                  <span class="rounded-full bg-gray-100 px-1.5 py-0.5 text-[11px] font-medium text-gray-500">{{ n.type }}</span>
                  <span v-if="sevChipClass(n)" class="rounded-full px-2 py-0.5 text-[11px] font-semibold" :class="sevChipClass(n)">
                    {{ severityOf(n) }}
                  </span>
                </div>

                <!-- Message -->
                <div
                  class="mt-1 text-[13.5px] leading-relaxed text-gray-600"
                  :class="expanded.has(n.name) ? '' : 'line-clamp-2'"
                  v-html="cleanMessage(n.message)"
                />
                <button
                  v-if="plainLength(n.message) > MSG_EXPAND_CHARS"
                  class="mt-1 text-[12.5px] font-medium text-blue-600 hover:underline"
                  @click="toggleExpand(n.name)"
                >{{ expanded.has(n.name) ? 'Show less' : 'Show more' }}</button>

                <!-- Meta + actions -->
                <div class="mt-2.5 flex flex-wrap items-center gap-4">
                  <span class="text-[12.5px] text-gray-500">{{ timeAgo(n.creation) }}</span>
                  <div class="flex items-center gap-3">
                    <Button
                      v-if="needsAttention(n) && n.route"
                      variant="outline"
                      @click="open(n)"
                    >Review</Button>
                    <button
                      v-else-if="n.route"
                      class="text-[12.5px] font-medium text-blue-600 hover:underline"
                      @click="open(n)"
                    >View</button>
                    <button
                      v-if="!n.read"
                      class="inline-flex items-center gap-1 text-[12.5px] font-medium text-gray-500 hover:text-gray-900"
                      @click="markRead(n)"
                    >
                      <FeatherIcon name="check" class="h-3.5 w-3.5" /> Mark read
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue';
import Header from '../../components/Header.vue';
import { Button, FeatherIcon, createResource, frappeRequest } from 'frappe-ui';
import { toast } from 'vue-sonner';
import router from '../../router';
import { getDocResource } from '../../utils/resource';
import { unreadNotificationsCount } from '../../data/notifications';
import {
  severityOf, needsAttention, cleanMessage, plainLength, timeAgo,
  summarize, applyFilters, groupByBucket, distinctTypes,
} from './notifications-derive';

// Data
const PAGE_LENGTH = 100;       // recent-feed cap; a "load older" control is a T10 follow-up
const MSG_EXPAND_CHARS = 140;  // plain-text length past which the "Show more" toggle appears

const list = createResource({
  url: 'press.api.notifications.get_notifications',
  params: { limit_page_length: PAGE_LENGTH },
  auto: true,
  cache: ['Notifications', 'feed'],
});

// Filter state
const tab        = ref('all');           // 'all' | 'unread' | 'attention'
const typeFilter = ref('');
const sevFilter  = ref('');
const tabs = [
  { label: 'All',             value: 'all'       },
  { label: 'Unread',          value: 'unread'    },
  { label: 'Needs attention', value: 'attention' },
];

function setTab(t) { tab.value = t; }
function toggleErrorFilter() {
  sevFilter.value = sevFilter.value === 'Error' ? '' : 'Error';
  tab.value = 'all';
}

// Derived
const items       = computed(() => list.data || []);
const counts      = computed(() => summarize(items.value));
const typeOptions = computed(() => distinctTypes(items.value));
const visible     = computed(() => applyFilters(items.value, {
  tab: tab.value, type: typeFilter.value, severity: sevFilter.value,
}));
const groups      = computed(() => groupByBucket(visible.value));

// Expand state
const expanded = reactive(new Set());
function toggleExpand(name) {
  if (expanded.has(name)) expanded.delete(name);
  else expanded.add(name);
}

// Icon + severity styling
function iconName(n) {
  const t = `${n.type || ''}`.toLowerCase();
  if (/fail|error/.test(t)) return 'alert-circle';
  if (/deploy|build/.test(t)) return 'upload-cloud';
  if (/site|migrate/.test(t)) return 'globe';
  if (/scale/.test(t)) return 'activity';
  if (/upgrade|version/.test(t)) return 'trending-up';
  if (/perf|down|slow/.test(t)) return 'activity';
  if (/support|access/.test(t)) return 'key';
  if (/complete|success|recover|online/.test(t)) return 'check-circle';
  return 'bell';
}
const SEV_ICON = {
  Error:   'bg-red-50 text-red-600',
  Warning: 'bg-amber-50 text-amber-600',
  Success: 'bg-green-50 text-green-600',
  Info:    'bg-gray-100 text-gray-500',
};
const SEV_CHIP = {
  Error:   'bg-red-50 text-red-700',
  Warning: 'bg-amber-50 text-amber-700',
};
function sevIconClass(n) { return SEV_ICON[severityOf(n)] || SEV_ICON.Info; }
function sevChipClass(n) { return SEV_CHIP[severityOf(n)] || ''; }

// Actions
function markRead(n) {
  if (n.read) return;
  const res = getDocResource({
    doctype: 'Press Notification',
    name: n.name,
    whitelistedMethods: { markRead: 'mark_as_read' },
  });
  res.markRead.submit().then(() => {
    unreadNotificationsCount.setData((c) => Math.max(0, (c || 0) - 1));
    list.reload(); // refetch so the read state is authoritative, not an optimistic guess
  }).catch(() => {});
}

function open(n) {
  markRead(n);
  if (n.route) router.push('/' + String(n.route).replace(/^\//, ''));
}

const markingAll = ref(false);
function markAll() {
  if (counts.value.unread === 0) return;
  markingAll.value = true;
  frappeRequest({ url: '/api/method/press.api.notifications.mark_all_notifications_as_read' })
    .then(() => {
      unreadNotificationsCount.setData(0);
      list.reload(); // refetch so read state is authoritative
      toast.success('All notifications marked as read');
    })
    .catch((e) => toast.error(e?.messages?.length ? e.messages.join('\n') : e?.message || 'Failed to mark all as read'))
    .finally(() => { markingAll.value = false; });
}
</script>
