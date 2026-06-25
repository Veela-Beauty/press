<template>
  <div class="flex h-full flex-col">
    <div class="sticky top-0 z-10 shrink-0">
      <Header>
        <Breadcrumbs :items="crumbs" />
        <template #actions>
          <span class="flex items-center gap-1.5 text-xs text-gray-500">
            <span class="h-1.5 w-1.5 rounded-full bg-green-500" /> updated {{ fresh }}
          </span>
        </template>
      </Header>
    </div>

    <div class="flex-1 overflow-auto p-5">
      <div v-if="tree.loading && !tree.data" class="text-base text-gray-600">Loading telephony…</div>
      <div v-else-if="tree.error" class="rounded-lg border border-red-200 bg-red-50 p-4 text-base text-red-700">
        {{ tree.error.messages?.join(', ') || tree.error.message }}
      </div>
      <template v-else>
        <div class="mb-3">
          <h1 class="text-lg font-semibold text-gray-900">Telephony</h1>
          <p class="mt-0.5 text-sm text-gray-500">
            Self-hosted Asterisk PBX hosts behind the omnichannel app. Provision, start/stop, and watch trunk
            registration without SSH. One host can serve several companies; per-company trunks and agents are
            configured in the ERPNext OC Channel Instance form, not here.
          </p>
        </div>
        <TeleAttention :hosts="hosts" class="mb-4" @view="onOpen" />
        <PbxHostList :hosts="hosts" @open="onOpen" @provision="wizardOpen = true" @restart="onRestart" />
      </template>
    </div>

    <HostDrawer :host="drawerHost" @close="drawerHost = null" @reload="tree.reload()" />
    <ProvisionWizard :open="wizardOpen" @close="wizardOpen = false" @provisioning="onProvisioning" />
    <ProvisionProgress
      :open="progress.open"
      :host="progress.host"
      :status="progress.status"
      @close="closeProgress"
      @open-host="(h) => { closeProgress(); onOpen(h); }"
      @view-log="(h) => { closeProgress(); onOpen(h, 'logs'); }"
      @retry="retryProvision"
      @rollback="rollbackProvision"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue';
import { toast } from 'vue-sonner';
import Header from '../../components/Header.vue';
import { usePbxTree, provisionStatus, provisionPbx, hostAction, decommissionPbx } from './tele-api';
import TeleAttention from './TeleAttention.vue';
import PbxHostList from './PbxHostList.vue';
import HostDrawer from './HostDrawer.vue';
import ProvisionWizard from './ProvisionWizard.vue';
import ProvisionProgress from './ProvisionProgress.vue';

const tree = usePbxTree();
const fresh = ref('just now');
const drawerHost = ref(null);
const wizardOpen = ref(false);

const hosts = computed(() => tree.data?.hosts || []);
const crumbs = computed(() => [
  { label: 'Infrastructure', route: { name: 'Infrastructure' } },
  { label: 'Telephony', route: { name: 'Telephony' } },
]);

// 15s poll (same cadence as the infra dashboard)
let timer = null;
onMounted(() => { timer = setInterval(() => { tree.reload(); fresh.value = 'just now'; }, 15000); });
onUnmounted(() => { clearInterval(timer); if (provTimer) clearInterval(provTimer); });

function onOpen(name, tab) {
  const h = hosts.value.find((x) => x.name === name);
  if (h) drawerHost.value = tab ? { ...h, _initialTab: tab } : h;
}

async function onRestart(name) {
  try { await hostAction(name, 'restart'); toast.success(`Restart on ${name} started`); tree.reload(); }
  catch (e) { toast.error(e?.messages?.join(', ') || e?.message || 'Restart failed'); }
}

// ─── Provision job polling ──────────────────────────────────────────────────
// The wizard hands the parent the full param set; the parent owns the provision
// call so a Retry can re-run it. telephony_provision is synchronous today
// (returns { ok }); when the infra-telephony backend adds async jobs it returns
// { job_id } and we poll provision_status. Both shapes are handled here.
const PROVISION_STEPS = [
  { key: 'env', label: 'Write the generated .env on the host' },
  { key: 'firewall', label: 'Open the firewall to the trunk IP' },
  { key: 'compose', label: 'docker compose up -d (oc-asterisk + oc-listener)' },
  { key: 'register', label: 'Wait for trunk registration + first heartbeat' },
];
const progress = reactive({ open: false, host: '', jobId: '', status: null, lastParams: null, lastInstance: '' });
let provTimer = null;

async function onProvisioning({ params, host }) {
  progress.open = true;
  progress.host = host;
  progress.lastParams = params;
  progress.lastInstance = params.instance || '';
  await startProvision();
}

async function startProvision() {
  progress.jobId = '';
  progress.status = { state: 'running', steps: PROVISION_STEPS.map((s) => ({ ...s, state: 'running' })), failure: null };
  try {
    const res = await provisionPbx(progress.lastParams);
    if (res && res.job_id) {            // async backend (Plan-3): poll provision_status
      progress.jobId = res.job_id;
      startPoll();
      return;
    }
    // synchronous backend (telephony_provision): { ok, host, instance, public_ip }
    progress.status = { state: 'done', steps: PROVISION_STEPS.map((s) => ({ ...s, state: 'done' })), failure: null };
    tree.reload();
  } catch (e) {
    progress.status = {
      state: 'failed',
      steps: PROVISION_STEPS.map((s, idx) => ({ ...s, state: idx === PROVISION_STEPS.length - 1 ? 'failed' : 'done' })),
      failure: { reason: 'provision', detail: e?.messages?.join(', ') || e?.message || 'Provision failed' },
    };
  }
}

function startPoll() {
  if (provTimer) clearInterval(provTimer);
  pollOnce();
  provTimer = setInterval(pollOnce, 2000);
}
async function pollOnce() {
  try {
    progress.status = await provisionStatus(progress.jobId);
    if (progress.status.state !== 'running') { clearInterval(provTimer); provTimer = null; tree.reload(); }
  } catch (e) {
    clearInterval(provTimer); provTimer = null;
    progress.status = { state: 'failed', steps: [], failure: { reason: 'poll', detail: e?.message || 'Lost contact with the provision job' } };
  }
}
function closeProgress() { progress.open = false; if (provTimer) { clearInterval(provTimer); provTimer = null; } }

async function retryProvision() {
  if (!progress.lastParams) { progress.open = false; wizardOpen.value = true; return; }
  await startProvision();
}
async function rollbackProvision() {
  try {
    await decommissionPbx(progress.host, progress.lastInstance);
    toast.success('Rolled back - firewall closed, token revoked');
    closeProgress();
    tree.reload();
  } catch (e) {
    toast.error(e?.messages?.join(', ') || e?.message || 'Rollback failed');
  }
}
</script>
