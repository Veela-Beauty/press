import { ref } from 'vue';
import call from './teamCall.js';

// Run an action only after "Confirm it's you" (PRS-SP-22). A confirm holds 10 minutes on the server, so when one
// still holds the action runs at once; otherwise the dialog opens and the action runs after Verify.
export function useConfirm() {
	const confirmOpen = ref(false);
	const confirmReason = ref('');
	let pending = null;

	async function withConfirm(reason, action) {
		const status = await call('press.mcp_server.token_confirm.confirm_status');
		if (status?.unlocked_seconds > 0) return action();
		confirmReason.value = reason;
		pending = action;
		confirmOpen.value = true;
	}

	function onConfirmed() {
		confirmOpen.value = false;
		const action = pending;
		pending = null;
		return action ? action() : undefined;
	}

	return { confirmOpen, confirmReason, withConfirm, onConfirmed };
}
