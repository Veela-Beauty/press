<template>
  <Dialog
    :modelValue="open"
    @update:modelValue="(v) => { if (!v) $emit('close'); }"
    :options="{ title: 'Provision PBX', size: 'lg' }"
  >
    <template #body-content>
      <div class="space-y-4">
        <!-- step bar -->
        <div class="flex gap-1.5">
          <span v-for="n in 3" :key="n" class="h-0.5 flex-1 rounded-full" :class="n <= step ? 'bg-gray-900' : 'bg-gray-200'" />
        </div>

        <!-- STEP 1: site & company -->
        <div v-if="step === 1" class="space-y-4">
          <p class="text-xs font-medium uppercase tracking-wide text-gray-500">Step 1 of 3 · ERPNext site & company</p>

          <div class="flex overflow-hidden rounded-md border border-gray-200">
            <button
              v-for="m in deployModes"
              :key="m.value"
              type="button"
              class="flex-1 px-3 py-2 text-sm"
              :class="deploy === m.value ? 'bg-gray-100 font-medium text-gray-900' : 'bg-white text-gray-500 hover:text-gray-700'"
              @click="setDeploy(m.value)"
            >{{ m.label }}</button>
          </div>

          <!-- self-hosted -->
          <div v-if="deploy === 'self'" class="space-y-3">
            <FormControl type="select" label="Site" :options="siteOptions" v-model="form.site" @update:modelValue="onSiteChange" />
            <FormControl type="select" label="OC Channel Instance (VoIP)" :options="instanceOptions" v-model="form.instance" @update:modelValue="onInstanceChange" />
            <div class="rounded-md p-2.5 text-xs" :class="auth.has_auth ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-800'">
              {{ auth.detail || 'Checking trunk secret…' }}
            </div>
          </div>

          <!-- frappe cloud / external -->
          <div v-else class="space-y-3">
            <div class="rounded-md bg-amber-50 p-2.5 text-xs text-amber-800">
              Frappe Cloud runs the ERPNext site, not Asterisk. The PBX reaches the site over HTTPS (the site never needs inbound),
              so enter the site URL + an API token, and the PBX goes on a self-hosted host below.
            </div>
            <FormControl type="text" label="Site URL" v-model="form.fc_site_url" placeholder="https://acme.frappe.cloud" />
            <div class="grid grid-cols-2 gap-3">
              <FormControl type="text" label="OC Channel Instance" v-model="form.instance" placeholder="acme-voip" />
              <FormControl type="text" label="API token (key:secret)" v-model="form.fc_api_token" placeholder="generate on the site" />
            </div>
            <p class="text-xs text-gray-400">On the site: the listener user → API Access → Generate Keys. Used only to mint the container's pull token.</p>
          </div>

          <!-- host select -->
          <FormControl type="select" label="PBX host" :options="hostOptions" v-model="form.host" @update:modelValue="onHostChange" />
          <p class="text-xs text-gray-400">{{ hostHint }}</p>

          <!-- new-host sub-flow -->
          <div v-if="form.host === 'new'" class="space-y-3 rounded-md border border-gray-200 p-3">
            <div class="grid grid-cols-2 gap-3">
              <FormControl type="text" label="Host name" v-model="form.host_name" placeholder="gulfcorner-pbx" />
              <FormControl type="text" label="SSH host" v-model="form.ssh_host" placeholder="49.13.x.x" />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <FormControl type="text" label="SSH user" v-model="form.ssh_user" />
              <FormControl type="number" label="SSH port" v-model="form.ssh_port" />
            </div>
            <div class="flex items-center gap-2">
              <Button :loading="testing" @click="doTest">Test connection</Button>
              <span v-if="testRes" class="text-xs" :class="testRes.ok ? 'text-green-700' : 'text-red-700'">{{ testRes.detail }}</span>
            </div>
          </div>
        </div>

        <!-- STEP 2: network & firewall (read-only) -->
        <div v-else-if="step === 2" class="space-y-4">
          <p class="text-xs font-medium uppercase tracking-wide text-gray-500">Step 2 of 3 · Network & firewall</p>
          <div class="grid grid-cols-2 gap-3 rounded-md border border-gray-200 p-3 text-sm">
            <div><span class="text-xs text-gray-500">SIP port</span><div class="font-mono text-gray-900">5060 / udp</div></div>
            <div><span class="text-xs text-gray-500">RTP range</span><div class="font-mono text-gray-900">10000-20000 / udp</div></div>
          </div>
          <div class="rounded-md bg-gray-50 p-2.5 text-xs text-gray-600">
            The firewall opens SIP + RTP to the trunk IP only, not the public internet. Phase B also opens 443/wss for the browser softphone.
          </div>
        </div>

        <!-- STEP 3: review -->
        <div v-else class="space-y-4">
          <p class="text-xs font-medium uppercase tracking-wide text-gray-500">Step 3 of 3 · Review & provision</p>
          <div class="rounded-md bg-blue-50 p-2.5 text-xs text-blue-800">
            The AMI password and the listener API token are generated for you - nothing technical to type.
          </div>
          <pre class="overflow-x-auto rounded-md bg-gray-900 p-3 font-mono text-xs leading-relaxed text-gray-100"># deploy/asterisk/.env (generated)
OC_SITE={{ reviewSite }}
OC_INSTANCE={{ form.instance }}
AMI_PASSWORD=•••••••••••• (generated)
OC_API_TOKEN=••••:•••••• (minted for listener user)</pre>
        </div>
      </div>
    </template>

    <template #actions>
      <div class="flex items-center justify-between">
        <Button :class="step === 1 ? 'invisible' : ''" @click="step--">Back</Button>
        <Button variant="solid" :disabled="!canAdvance" @click="next">{{ step === 3 ? 'Provision' : 'Continue' }}</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue';
import { Dialog, Button, FormControl } from 'frappe-ui';
import { toast } from 'vue-sonner';
import { provisionTargets, validateAuth, testHostConnection } from './tele-api';

const props = defineProps({ open: Boolean });
const emit = defineEmits(['close', 'provisioning']);

const deployModes = [{ label: 'Self-hosted (Press)', value: 'self' }, { label: 'Frappe Cloud / external', value: 'fc' }];
const step = ref(1);
const deploy = ref('self');
const testing = ref(false);
const testRes = ref(null);
const auth = ref({ has_auth: true, detail: '' });

const form = reactive({
  site: '', instance: '', host: '',
  host_name: '', ssh_host: '', ssh_user: 'root', ssh_port: 22,
  fc_site_url: '', fc_api_token: '',
});

const targets = ref({ sites: [], hosts: [] });

watch(() => props.open, async (o) => {
  if (!o) return;
  step.value = 1;
  deploy.value = 'self';
  testRes.value = null;
  Object.assign(form, { site: '', instance: '', host: '', host_name: '', ssh_host: '', ssh_user: 'root', ssh_port: 22, fc_site_url: '', fc_api_token: '' });
  try {
    targets.value = await provisionTargets();
    if (targets.value.sites?.length) { form.site = targets.value.sites[0].site; onSiteChange(); }
    if (targets.value.hosts?.length) { form.host = targets.value.hosts[0].name; onHostChange(); }
  } catch (e) {
    toast.error(e?.messages?.join(', ') || e?.message || 'Could not load provision targets');
  }
});

const siteOptions = computed(() => (targets.value.sites || []).map((s) => ({ label: s.site, value: s.site })));
const instanceOptions = computed(() => {
  const s = (targets.value.sites || []).find((x) => x.site === form.site);
  return (s?.instances || []).map((i) => ({ label: i.instance, value: i.instance }));
});
const hostOptions = computed(() => [
  ...(targets.value.hosts || []).map((h) => ({ label: h.label || h.name, value: h.name })),
  { label: 'Register a new managed host…', value: 'new' },
]);

const hostHint = computed(() => {
  if (form.host === 'new') return 'Onboards a brand-new self-hosted host (needs a public IP for the SIP trunk): test SSH first, then provision.';
  return deploy.value === 'fc'
    ? 'Hosts this Frappe Cloud company on our Asterisk; it pulls config from the site URL over HTTPS.'
    : 'Adds this company to an existing Asterisk. No new container.';
});

function setDeploy(m) {
  deploy.value = m;
  if (m === 'fc') { form.host = 'new'; onHostChange(); } // FC: no co-located host, register a self-hosted one
}
function onSiteChange() {
  const s = (targets.value.sites || []).find((x) => x.site === form.site);
  form.instance = s?.instances?.[0]?.instance || '';
  onInstanceChange();
}
async function onInstanceChange() {
  if (deploy.value !== 'self' || !form.site || !form.instance) return;
  try { auth.value = await validateAuth(form.site, form.instance); }
  catch { auth.value = { has_auth: false, detail: 'Could not validate trunk secret' }; }
}
function onHostChange() { testRes.value = null; }

async function doTest() {
  testing.value = true;
  testRes.value = null;
  try {
    const r = await testHostConnection({ host_name: form.host_name, ssh_host: form.ssh_host, ssh_user: form.ssh_user, ssh_port: Number(form.ssh_port) });
    testRes.value = { ok: r.ok, detail: r.ok ? `connection ok${r.docker_ok ? ' · Docker reachable' : ''}` : (r.detail || 'connection failed') };
  } catch (e) {
    testRes.value = { ok: false, detail: e?.messages?.join(', ') || e?.message || 'connection failed' };
  } finally {
    testing.value = false;
  }
}

const reviewSite = computed(() => deploy.value === 'self' ? `https://${form.site}` : (form.fc_site_url || ''));

const canAdvance = computed(() => {
  if (step.value === 1) {
    if (deploy.value === 'self' && (!form.instance || !auth.value.has_auth)) return false;
    if (deploy.value === 'fc' && (!form.fc_site_url.trim() || !form.fc_api_token.trim())) return false;
    if (form.host === 'new' && (!form.host_name.trim() || !form.ssh_host.trim() || !(testRes.value && testRes.value.ok))) return false;
    return true;
  }
  return true;
});

function buildParams() {
  return {
    deploy: deploy.value,
    host: form.host,
    site: deploy.value === 'self' ? form.site : null,
    instance: form.instance,
    host_name: form.host === 'new' ? form.host_name : null,
    ssh_host: form.host === 'new' ? form.ssh_host : null,
    ssh_user: form.host === 'new' ? form.ssh_user : null,
    ssh_port: form.host === 'new' ? Number(form.ssh_port) : null,
    fc_site_url: deploy.value === 'fc' ? form.fc_site_url : null,
    fc_api_token: deploy.value === 'fc' ? form.fc_api_token : null,
  };
}

function next() {
  if (step.value < 3) { step.value++; return; }
  const params = buildParams();
  const host = form.host === 'new' ? form.host_name : form.host;
  // Parent owns the provision call + progress poll; it gets the full params so retry works.
  emit('provisioning', { params, host });
  emit('close');
}
</script>
