<template>
  <div class="overflow-hidden rounded-lg border border-gray-200">
    <table v-if="instances.length" class="w-full text-sm">
      <thead>
        <tr class="border-b border-gray-200 bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
          <th class="px-3 py-2">Company / instance</th>
          <th class="px-3 py-2">Trunk</th>
          <th class="px-3 py-2">DID</th>
          <th class="px-3 py-2">Status</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-100">
        <tr v-for="i in instances" :key="i.instance">
          <td class="px-3 py-2.5">
            <div class="font-medium text-gray-900">{{ i.instance }}</div>
            <div class="text-xs text-gray-400">{{ i.site }}</div>
          </td>
          <td class="px-3 py-2.5">
            {{ i.trunk }} <span class="ml-1 font-mono text-xs text-gray-400">{{ i.trunk_ip }}</span>
          </td>
          <td class="px-3 py-2.5 font-mono text-xs text-gray-700">{{ i.did }}</td>
          <td class="px-3 py-2.5"><Badge :label="regLabel(i.reg)" :theme="regTheme(i.reg)" /></td>
        </tr>
      </tbody>
    </table>
    <p v-else class="px-3 py-4 text-sm text-gray-400">No companies served on this host yet.</p>
  </div>
</template>

<script setup>
import { Badge } from 'frappe-ui';
defineProps({ instances: { type: Array, default: () => [] } });
const LABEL = { reg: 'Registered', unreg: 'Unregistered', prov: 'Provisioning' };
const THEME = { reg: 'green', unreg: 'orange', prov: 'blue' };
const regLabel = (r) => LABEL[r] || r;
const regTheme = (r) => THEME[r] || 'gray';
</script>
