<template>
  <div>
    <!-- Overview -->
    <div v-if="tab === 'overview'" class="space-y-4">
      <dl class="grid grid-cols-2 gap-x-6 gap-y-1.5 rounded-md border border-gray-200 p-3 text-sm">
        <dt class="text-gray-500">Container</dt><dd class="font-mono text-gray-900">{{ host.container }}</dd>
        <dt class="text-gray-500">Listener</dt><dd class="font-mono text-gray-900">{{ host.listener }}</dd>
        <dt class="text-gray-500">Active calls</dt><dd class="font-mono text-gray-900">{{ host.active_calls }}</dd>
        <dt class="text-gray-500">CPU</dt><dd class="font-mono text-gray-900">{{ host.cpu_pct != null ? host.cpu_pct + '%' : 'n/a' }}</dd>
        <dt class="text-gray-500">Uptime</dt><dd class="font-mono text-gray-900">{{ host.uptime }}</dd>
        <dt class="text-gray-500">Recordings</dt><dd class="font-mono text-gray-900">{{ host.recordings || '—' }}</dd>
      </dl>
      <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-500">Companies served on this host</h3>
      <CompaniesTable :instances="host.instances || []" />
      <p class="rounded-md bg-gray-50 p-2.5 text-xs text-gray-500">
        One Asterisk serves several companies. Each company's trunk + agents are edited in ERPNext
        (its OC Channel Instance); this host pulls them and reloads within ~30s. You do not edit trunk config here.
      </p>
    </div>

    <!-- Listener log -->
    <ListenerLog v-else-if="tab === 'logs'" :host="host.name" :active="tab === 'logs'" />

    <!-- Config & secrets -->
    <ConfigSecrets v-else :host="host" @reload="$emit('reload')" />
  </div>
</template>

<script setup>
import CompaniesTable from './CompaniesTable.vue';
import ListenerLog from './ListenerLog.vue';
import ConfigSecrets from './ConfigSecrets.vue';
defineProps({ host: { type: Object, required: true }, tab: { type: String, default: 'overview' } });
defineEmits(['reload']);
</script>
