import { ref } from 'vue';
import { toast } from 'vue-sonner';
import call from './teamCall.js';

// Run an action only after "Confirm it's you" (PRS-SP-22). A confirm holds 10 minutes for this browser session on the
// server; the page remembers it too, so while it holds the action runs inside the click itself (Safari and Firefox
// refuse a clipboard write that comes after a network wait).
const HOLD_MS = 590 * 1000;
let confirmedUntil = 0;

export function useConfirm() {
	const confirmOpen = ref(false);
	const confirmReason = ref('');
	let pending = null;

	async function withConfirm(reason, action) {
		if (Date.now() < confirmedUntil) return action();
		let status;
		try {
			status = await call('press.mcp_server.token_confirm.confirm_status');
		} catch (e) {
			toast.error(e?.messages?.[0] || e?.message || "Could not check Confirm it's you");
			return;
		}
		if (status?.unlocked_seconds > 0) {
			confirmedUntil = Date.now() + Math.min(status.unlocked_seconds * 1000, HOLD_MS);
			return action();
		}
		confirmReason.value = reason;
		pending = action;
		confirmOpen.value = true;
	}

	function onConfirmed() {
		confirmedUntil = Date.now() + HOLD_MS;
		confirmOpen.value = false;
		const action = pending;
		pending = null;
		return action ? action() : undefined;
	}

	return { confirmOpen, confirmReason, withConfirm, onConfirmed };
}
