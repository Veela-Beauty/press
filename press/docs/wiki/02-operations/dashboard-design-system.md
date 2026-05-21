# Dashboard Design System

Single source of truth for repeated UI patterns on the Press dashboard. Whenever you add a tab or a stat card to a page, you MUST use one of the primitives listed here. Forking the style — copying a class string from another page and tweaking it — is what causes the drift that bit us in May 2026.

Authored 2026-05-21 after a live audit found:
- **7 different tab patterns** across the dashboard (4 active-state styles, 3 font sizes, 3 padding sizes)
- **31 stat cards across 7 files** with drifting font-weight (bold vs semibold), label transform (UPPERCASE vs none), and label sizes

This page documents the primitives that replaced them.

---

## Tabs

### Where the source lives

| File | Purpose |
|---|---|
| `dashboard/src/components/_shared/tabClasses.js` | CSS class constants — for pages whose tab markup is too entangled to swap to the component. |
| `dashboard/src/components/_shared/UnifiedTabs.vue` | Reusable Vue component — for new pages. Uses the same constants internally. |

### Active-tab styling

- **Active**: `font-bold text-gray-900`
- **Inactive**: `font-medium text-gray-500 hover:text-gray-900`
- **No underline.** No pill background. No shape change. Only weight + color change between active and inactive.

### Container

- **Standalone tab strip** (not in a card): `TAB_STRIP_BASE` → `flex items-center bg-gray-50 rounded-lg border border-gray-200 px-1`
- **Tab strip inside a card** (panel pattern): `TAB_STRIP_PANEL_TOP` + `TAB_STRIP_DIVIDER` underneath when a body is rendered

### Inline (for existing pages)

```vue
<template>
  <div :class="TAB_STRIP_BASE" class="mb-4 gap-1">
    <button
      v-for="t in tabs"
      :key="t.id"
      :class="tabClass(activeTab === t.id)"
      @click="activeTab = t.id"
    >
      {{ t.label }}
    </button>
  </div>
</template>

<script setup>
import { TAB_STRIP_BASE, tabClass } from '@/components/_shared/tabClasses.js';
const activeTab = ref('overview');
const tabs = [{ id: 'overview', label: 'Overview' }, { id: 'logs', label: 'Logs' }];
</script>
```

For Options API pages, expose the constants via `setup()`:
```js
setup() {
  return { TAB_STRIP_BASE, tabClass };
}
```

### Component (for new pages)

```vue
<UnifiedTabs
  v-model="active"
  :tabs="[
    { id: 'tokens', label: 'Tokens', icon: 'key' },
    { id: 'guide', label: 'Guide', icon: 'book' },
  ]"
>
  <template #tokens><TokensPanel /></template>
  <template #guide><GuidePanel /></template>
</UnifiedTabs>
```

### Retrofitted pages (as of 2026-05-21)

`AdminPanel.vue`, `BackupRunLog.vue`, `BenchCodeHealth.vue`, `UnifiedTabs.vue`, `MCPTopTabs.vue`. Five implementations, one source.

### Deferred (intentionally on their own style — for now)

- Sidebar tabs (`AutoScaleTabs.vue`, `SiteInsights.vue`) — left-column router-link pattern needs its own constants file.
- `TabsWithRouter.vue` consumers (`Settings.vue`, `Billing.vue`, `Partners.vue`) — wrap frappe-ui `<FTabs>`. Restyling without losing router integration is a separate refactor.
- `DevFlowsGuide.vue` — pill+ring pattern is intentionally different (decorative on a dev surface).

---

## Stat cards (number tiles)

### Where the source lives

| File | Purpose |
|---|---|
| `dashboard/src/components/_shared/statCardClasses.js` | CSS class constants + color tokens — for custom layouts (progress bars, sub-stats). |
| `dashboard/src/components/_shared/StatCard.vue` | Reusable Vue component — for the common case (label + number). |

### Anatomy

- **Card container**: `STAT_CARD_BASE` → `rounded-lg border border-gray-200 bg-white p-4`
- **Label**: `STAT_LABEL` → `text-xs font-medium uppercase tracking-wide text-gray-500`
- **Number**: `text-2xl font-bold` + color token
- **Subline (optional)**: `text-xs text-gray-400`

### Color tokens

Use intent tokens, not raw colors:

| Token | Use for | Class |
|---|---|---|
| `default` | Neutral counts (most cards) | `text-gray-900` |
| `good` | Healthy / success counts | `text-green-600` |
| `warn` | Borderline / attention | `text-amber-600` |
| `bad` | Failures / critical | `text-red-600` |
| `info` | Monetary, "of N" metrics | `text-blue-600` |
| `muted` | Greyed-out / zero state | `text-gray-500` |

### Component (preferred for the common case)

```vue
<div class="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
  <StatCard label="Teams" :number="stats.teams" />
  <StatCard label="Healthy" :number="stats.healthy" color="good" />
  <StatCard label="Failed" :number="stats.failed" color="bad" />
  <StatCard label="Monthly Cost" color="info">
    <template #number>&euro;{{ stats.cost }}</template>
  </StatCard>
  <StatCard
    label="Servers"
    :number="serverCount"
    :subline="serverNames.join(', ')"
    class="sm:col-span-2"
  />
</div>
```

### Inline classes (for cards with custom layout — progress bars, etc.)

```vue
<div :class="STAT_CARD_BASE">
  <div :class="STAT_LABEL">Storage</div>
  <div :class="statNumberClass('info')">{{ used }} / {{ total }} GB</div>
  <ProgressBar :value="used / total * 100" class="mt-2" />
</div>
```

### Anti-patterns (what NOT to do)

The audit found these patterns drifting. NEVER add:

- **Left-padding icon** inside the card (e.g. `<i class="fa fa-users text-blue-500 mr-2">`). Per user feedback: "too many number cards have same icon in left padding — don't repeat that pattern." Keep cards clean.
- **Left-border-color accent** (e.g. `border-l-4 border-blue-500`). Use the `color` token on the number text instead.
- **Custom font sizes** (text-xl, text-3xl). Use the default `text-2xl` from STAT_NUMBER.
- **Custom label transforms** (capitalize, none). Always UPPERCASE via STAT_LABEL.
- **font-semibold for the number**. Always font-bold via STAT_NUMBER.

### Retrofitted pages (as of 2026-05-21)

`AdminPanel.vue` (5 cards), `ServerBackups.vue` (4 cards), `BackupServers.vue` (4 cards), `BackupClients.vue` (4 cards), `BackupRunLog.vue` (4 cards). Five files, one source.

### Deferred

- `CodeHealth.vue` — has 5 health-score cards with color-coded ranges + sub-stats. Needs a small extension (multi-line variant) before retrofit. Auditor flagged for Phase 2.
- `BackupClientDetail.vue` — has 5 cards including a storage-with-progress-bar variant. Use inline `STAT_CARD_BASE` + classes; component refactor not worth the per-card slot complexity.

---

## How to add a new shared primitive

If you find yourself building a 3rd visual pattern (button group? badge? chip?), add it to `_shared/`:

1. Build the constants file first (e.g. `_shared/chipClasses.js`).
2. Optionally build a component on top.
3. Document it on this page in a new section.
4. Add a memory rule (`feedback_dashboard-<pattern>-style-shared-source.md`) so future agents see it before adding a 4th forked pattern.

## Memory rules pointing at this page

- `feedback_dashboard-tab-style-shared-source.md` — tabs always import from `tabClasses.js`
- `feedback_dashboard-card-style-shared-source.md` — stat cards always import from `statCardClasses.js` or use `<StatCard>`
- `feedback_no-user-facing-ai-marker.md` — never expose AI authorship in UI

## Why this matters

Without shared primitives, every new tab or card becomes a one-off styling decision. Five engineers ship five different paddings, four different active states, three different font sizes — and the dashboard slowly becomes a museum of design fashion across the months it was built. Single source of truth + a memory rule on every primitive = the dashboard stays coherent without a design review on every commit.
