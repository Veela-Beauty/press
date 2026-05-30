import { toast } from 'vue-sonner';
import { h } from 'vue';

// Frappe server errors (e.g. permission 403s) arrive as HTML like
// "<details><summary>You are not permitted...</summary>Function ... is not
// whitelisted.</summary></details>". Rendered via innerHTML that showed raw
// markup. Flatten such blobs to readable text while keeping intentional <br>.
function sanitizeErrorHtml(msg) {
	if (!msg || typeof msg !== 'string') return msg;
	if (!/<\/?(details|summary|div|span|pre|code|p)\b/i.test(msg)) return msg;
	let text = msg
		.replace(/<\s*br\s*\/?>/gi, '\n')
		.replace(/<\/(summary|p|div)>/gi, '\n')
		.replace(/<[^>]+>/g, '')
		.replace(/\n{2,}/g, '\n')
		.trim();
	// Decode the few entities Frappe emits.
	text = text
		.replace(/&lt;/g, '<')
		.replace(/&gt;/g, '>')
		.replace(/&amp;/g, '&')
		.replace(/&quot;/g, '"');
	return text;
}

export function showErrorToast(error) {
	let errorMessage = error.messages?.length
		? error.messages.join('\n')
		: error.message;
	toast.error(sanitizeErrorHtml(errorMessage));
}

export function getToastErrorMessage(e, fallbackMessage = 'An error occurred') {
	const raw = e.messages?.length
		? e.messages.join('<br>')
		: e.message || fallbackMessage;
	const errorMessage = sanitizeErrorHtml(raw);
	// Keep innerHTML for intentional <br> from messages.join; sanitized text has
	// newlines instead of tags, so render with whitespace preserved.
	return h('div', { style: 'white-space: pre-wrap', innerHTML: errorMessage });
}
