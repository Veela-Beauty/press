import { createApp, h, ref, nextTick } from 'vue';
import 'frappe-ui/style.css';
import './tw.css';
import IssueTokenDialog from './mcp/IssueTokenDialog.vue';

const open = ref(false);
createApp({
	render: () => h(IssueTokenDialog, { modelValue: open.value, 'onUpdate:modelValue': (v) => (open.value = v) }),
}).mount('#app');
// The dialog loads its site options on the false -> true transition, like the real page.
nextTick(() => (open.value = true));
