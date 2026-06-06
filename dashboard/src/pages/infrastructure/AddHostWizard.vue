<template>
  <Dialog
    :modelValue="open"
    @update:modelValue="(v) => { if (!v) close() }"
    :options="{ title: 'Add managed host', size: 'lg' }"
  >
    <template #body-content>
      <!-- ─── Step 1: form ──────────────────────────────────────────────── -->
      <div v-if="step === 1" class="space-y-4">
        <p class="text-xs font-medium uppercase tracking-wide text-gray-500">Step 1 of 3</p>
        <div class="grid grid-cols-2 gap-3">
          <FormControl
            class="col-span-2"
            label="Host name"
            v-model="form.host_name"
            placeholder="my-host"
          />
          <FormControl
            label="Type"
            type="select"
            :options="serverTypeOptions"
            v-model="form.server_type"
          />
          <FormControl label="SSH host" v-model="form.ssh_host" placeholder="10.0.0.5" />
          <FormControl label="SSH user" v-model="form.ssh_user" />
          <FormControl label="SSH port" type="number" v-model="form.ssh_port" />
          <FormControl label="Proxy port" type="number" v-model="form.proxy_port" />
        </div>
      </div>

      <!-- ─── Step 2: test ──────────────────────────────────────────────── -->
      <div v-else-if="step === 2" class="space-y-4">
        <p class="text-xs font-medium uppercase tracking-wide text-gray-500">Step 2 of 3</p>

        <!-- Probing -->
        <div
          v-if="busy"
          class="flex items-center gap-3 rounded-md border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600"
        >
          <LoadingIndicator class="h-4 w-4 text-gray-500" />
          <span>Signing a short-TTL SSH cert and probing the host&hellip;</span>
        </div>

        <!-- Error -->
        <div
          v-else-if="err"
          class="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        >
          {{ err }}
        </div>

        <!-- Result -->
        <div
          v-else-if="result"
          class="divide-y divide-gray-100 rounded-md border border-gray-200"
        >
          <div class="flex items-center justify-between px-4 py-2.5 text-sm">
            <span class="text-gray-500">SSH</span>
            <span :class="result.ssh_ok ? 'text-green-700' : 'text-red-700'">
              {{ result.ssh_ok ? 'ok' : 'failed' }}
            </span>
          </div>
          <div class="flex items-center justify-between px-4 py-2.5 text-sm">
            <span class="text-gray-500">Docker API</span>
            <span :class="result.docker_ok ? 'text-green-700' : 'text-gray-500'">
              {{ result.docker_ok ? 'ok' : 'n/a' }}
            </span>
          </div>
          <div class="flex items-center justify-between px-4 py-2.5 text-sm">
            <span class="text-gray-500">Containers</span>
            <span class="font-mono text-gray-900">{{ result.containers }}</span>
          </div>
        </div>
      </div>

      <!-- ─── Step 3: success ───────────────────────────────────────────── -->
      <div v-else class="space-y-3">
        <p class="text-xs font-medium uppercase tracking-wide text-gray-500">Step 3 of 3</p>
        <div class="flex items-center gap-2 text-sm text-gray-900">
          <span class="h-2 w-2 rounded-full bg-green-500" />
          <span><span class="font-mono">{{ form.host_name }}</span> is now managed.</span>
        </div>
        <p class="text-xs text-gray-500">It appears under Infrastructure within ~15s.</p>
      </div>
    </template>

    <template #actions>
      <!-- Step 1 footer -->
      <Button
        v-if="step === 1"
        variant="solid"
        :disabled="!form.host_name || !form.ssh_host"
        @click="goTest"
      >Next: test</Button>

      <!-- Step 2 footer -->
      <template v-else-if="step === 2">
        <div class="flex items-center justify-end gap-2">
          <Button :disabled="busy" @click="step = 1">Back</Button>
          <Button
            v-if="result && !err"
            variant="solid"
            @click="step = 3"
          >Finish</Button>
        </div>
      </template>

      <!-- Step 3 footer -->
      <Button v-else variant="solid" @click="done">Done</Button>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, reactive, watch } from 'vue';
import { Dialog, Button, FormControl, LoadingIndicator } from 'frappe-ui';
import { addHost, testConnection } from './infra-api';

const props = defineProps({ open: Boolean });
const emit = defineEmits(['close', 'added']);

const serverTypeOptions = [
  { label: 'docker', value: 'docker' },
  { label: 'plain', value: 'plain' },
];

const step = ref(1);
const form = reactive({
  host_name: '',
  server_type: 'docker',
  ssh_host: '',
  ssh_user: 'sanad',
  ssh_port: 22,
  proxy_port: 2375,
});
const busy = ref(false);
const result = ref(null);
const err = ref('');

function reset() {
  step.value = 1;
  result.value = null;
  err.value = '';
}

watch(() => props.open, (v) => { if (v) reset(); });

async function goTest() {
  step.value = 2;
  busy.value = true;
  err.value = '';
  result.value = null;
  try {
    await addHost({
      ...form,
      ssh_port: Number(form.ssh_port),
      proxy_port: Number(form.proxy_port),
    });
    result.value = await testConnection(form.host_name);
  } catch (e) {
    err.value = e.messages?.join(', ') || e.message || 'Connection failed';
  } finally {
    busy.value = false;
  }
}

function close() {
  emit('close');
}

function done() {
  emit('added');
  close();
}
</script>
