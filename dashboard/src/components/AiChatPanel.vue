<template>
	<div
		v-if="visible"
		class="flex h-full flex-col border-l border-gray-200 bg-white"
		:style="{ width: panelWidth + 'px' }"
	>
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
			<div class="flex items-center gap-2">
				<div class="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-50">
					<i class="fa fa-magic text-xs text-blue-600"></i>
				</div>
				<span class="text-sm font-semibold text-gray-900">AI Assistant</span>
				<span
					v-if="sessionActive"
					class="rounded-full bg-green-100 px-1.5 py-0.5 text-[10px] font-medium text-green-700"
				>Active</span>
			</div>
			<div class="flex items-center gap-1">
				<button
					class="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
					title="New session"
					@click="resetSession"
				>
					<i class="fa fa-plus text-xs"></i>
				</button>
				<button
					class="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
					title="Close"
					@click="$emit('close')"
				>
					<i class="fa fa-times text-xs"></i>
				</button>
			</div>
		</div>

		<!-- Token budget bar -->
		<div v-if="budgetInfo" class="border-b border-gray-100 px-4 py-2">
			<div class="flex items-center justify-between text-[10px] text-gray-500">
				<span>{{ budgetInfo.used.toLocaleString() }} / {{ budgetInfo.cap.toLocaleString() }} tokens</span>
				<span :class="budgetPct >= 80 ? 'text-orange-600 font-semibold' : ''">
					{{ budgetPct }}%
				</span>
			</div>
			<div class="mt-1 h-1 rounded-full bg-gray-100">
				<div
					class="h-full rounded-full transition-all"
					:class="budgetPct >= 80 ? 'bg-orange-500' : 'bg-blue-500'"
					:style="{ width: Math.min(budgetPct, 100) + '%' }"
				></div>
			</div>
		</div>

		<!-- Quick prompts (shown when no messages) -->
		<div v-if="messages.length === 0" class="flex-1 overflow-y-auto p-4">
			<p class="mb-3 text-xs text-gray-500">Quick actions:</p>
			<div class="flex flex-col gap-2">
				<button
					v-for="qp in quickPrompts"
					:key="qp.id"
					class="rounded-lg border border-gray-200 px-3 py-2 text-left text-xs text-gray-700 transition-colors hover:border-blue-300 hover:bg-blue-50"
					@click="sendQuickPrompt(qp)"
				>
					<i :class="qp.icon" class="mr-1.5 text-gray-400"></i>
					{{ qp.label }}
				</button>
			</div>
		</div>

		<!-- Message list -->
		<div v-else ref="messagesContainer" class="flex-1 overflow-y-auto p-4 space-y-3">
			<div
				v-for="(msg, i) in messages"
				:key="i"
				:class="msg.role === 'user' ? 'ml-8' : 'mr-4'"
			>
				<!-- User message -->
				<div v-if="msg.role === 'user'" class="rounded-lg bg-blue-50 px-3 py-2 text-sm text-gray-800">
					{{ msg.text }}
				</div>

				<!-- AI message -->
				<div v-else class="space-y-2">
					<div class="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-sm text-gray-800">
						<div v-html="renderMarkdown(msg.text)"></div>
					</div>

					<!-- Violation banner -->
					<div
						v-if="msg.violations && msg.violations.length > 0"
						class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700"
					>
						<i class="fa fa-exclamation-triangle mr-1"></i>
						<strong>{{ msg.violations.length }} violation(s) detected</strong>
						<span v-if="msg.violations.some(v => v.category === 1)">
							— dangerous code was removed from this response
						</span>
						<ul class="mt-1 space-y-0.5 pl-4">
							<li v-for="v in msg.violations" :key="v.pattern">
								<span
									:class="{
										'text-red-700': v.category === 1,
										'text-orange-700': v.category === 2,
										'text-yellow-700': v.category === 3,
									}"
								>
									[Cat {{ v.category }}] {{ v.pattern }}: {{ v.description }}
								</span>
							</li>
						</ul>
					</div>

					<!-- Token count -->
					<div v-if="msg.tokens" class="text-[10px] text-gray-400">
						{{ msg.tokens.toLocaleString() }} tokens
					</div>
				</div>
			</div>

			<!-- Loading indicator -->
			<div v-if="loading" class="flex items-center gap-2 text-xs text-gray-400">
				<div class="h-4 w-4 animate-spin rounded-full border-2 border-blue-400 border-t-transparent"></div>
				Thinking...
			</div>
		</div>

		<!-- Staging confirm banner -->
		<div
			v-if="needsConfirm"
			class="border-t border-orange-200 bg-orange-50 px-4 py-2 text-xs text-orange-700"
		>
			<i class="fa fa-exclamation-triangle mr-1"></i>
			Staging site — confirm before applying changes.
		</div>

		<!-- Input area -->
		<div class="border-t border-gray-200 p-3">
			<div class="flex items-end gap-2">
				<textarea
					ref="inputArea"
					v-model="inputText"
					class="flex-1 resize-none rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 placeholder-gray-400 outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
					placeholder="Ask AI to debug, scaffold, or extend..."
					rows="2"
					:disabled="loading || !hasApiKey"
					@keydown.enter.exact.prevent="sendMessage"
				></textarea>
				<button
					class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white transition-colors hover:bg-blue-700 disabled:bg-gray-300"
					:disabled="!inputText.trim() || loading || !hasApiKey"
					@click="sendMessage"
				>
					<i class="fa fa-arrow-up text-xs"></i>
				</button>
			</div>
			<div v-if="!hasApiKey" class="mt-2 text-[10px] text-red-500">
				<i class="fa fa-key mr-1"></i>
				No API key configured. Go to Settings to add your provider key.
			</div>
		</div>
	</div>
</template>

<script>
export default {
	name: 'AiChatPanel',
	props: {
		visible: { type: Boolean, default: false },
		siteName: { type: String, default: '' },
		benchName: { type: String, default: '' },
		siteType: { type: String, default: 'Dev' },
		branch: { type: String, default: '' },
		panelWidth: { type: Number, default: 380 },
	},
	emits: ['close'],
	data() {
		return {
			messages: [],
			inputText: '',
			loading: false,
			sessionId: null,
			hasApiKey: true,
			needsConfirm: false,
			budgetInfo: null,
			quickPrompts: [
				{ id: 'debug', label: 'Debug last error', icon: 'fa fa-bug', prompt: 'Load the latest error log and explain the traceback. Suggest a fix.' },
				{ id: 'scaffold', label: 'Scaffold a new module', icon: 'fa fa-cube', prompt: 'I want to create a new Frappe module. Ask me what it should do.' },
				{ id: 'field', label: 'Add a field to DocType', icon: 'fa fa-plus-square', prompt: 'I want to add a new field to an existing DocType. Ask me which DocType and what field.' },
				{ id: 'script', label: 'Write a server script', icon: 'fa fa-file-code-o', prompt: 'I need a server script. Ask me what it should do and which DocType it targets.' },
			],
		};
	},
	computed: {
		budgetPct() {
			if (!this.budgetInfo || !this.budgetInfo.cap) return 0;
			return Math.round((this.budgetInfo.used / this.budgetInfo.cap) * 100);
		},
		sessionActive() {
			return !!this.sessionId;
		},
	},
	methods: {
		async sendMessage() {
			const text = this.inputText.trim();
			if (!text || this.loading) return;

			this.messages.push({ role: 'user', text });
			this.inputText = '';
			this.loading = true;

			try {
				const response = await this.$call(
					'press.press.ai.api.chat',
					{
						prompt: text,
						site_name: this.siteName,
						bench_name: this.benchName,
						site_type: this.siteType,
						branch: this.branch,
						session_id: this.sessionId,
					}
				);

				if (response.success) {
					this.sessionId = response.session_id;
					this.messages.push({
						role: 'assistant',
						text: response.response_text,
						violations: response.violations || [],
						tokens: response.tokens_used || 0,
					});
					if (response.budget) {
						this.budgetInfo = response.budget;
					}
					this.needsConfirm = response.needs_confirm || false;
				} else {
					this.messages.push({
						role: 'assistant',
						text: `**Error:** ${response.error}`,
						violations: [],
					});
					if (response.error && response.error.toLowerCase().includes('key')) {
						this.hasApiKey = false;
					}
				}
			} catch (err) {
				this.messages.push({
					role: 'assistant',
					text: `**Error:** ${err.message || 'Request failed'}`,
					violations: [],
				});
			} finally {
				this.loading = false;
				this.$nextTick(() => this.scrollToBottom());
			}
		},

		sendQuickPrompt(qp) {
			this.inputText = qp.prompt;
			this.sendMessage();
		},

		resetSession() {
			this.messages = [];
			this.sessionId = null;
			this.needsConfirm = false;
		},

		scrollToBottom() {
			const container = this.$refs.messagesContainer;
			if (container) {
				container.scrollTop = container.scrollHeight;
			}
		},

		renderMarkdown(text) {
			// Basic markdown rendering — code blocks and bold
			return text
				.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="my-2 rounded bg-gray-900 p-2 text-xs text-green-400 overflow-x-auto"><code>$2</code></pre>')
				.replace(/`([^`]+)`/g, '<code class="rounded bg-gray-200 px-1 text-xs">$1</code>')
				.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
				.replace(/\n/g, '<br>');
		},

		$call(method, args) {
			// Wrapper for frappe-ui call — works with Press dashboard
			return new Promise((resolve, reject) => {
				if (window.call) {
					window.call(method, args).then(resolve).catch(reject);
				} else {
					// Fallback for testing without frappe-ui
					fetch(`/api/method/${method}`, {
						method: 'POST',
						headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': window.csrf_token || '' },
						body: JSON.stringify(args),
					})
					.then(r => r.json())
					.then(d => resolve(d.message))
					.catch(reject);
				}
			});
		},
	},
};
</script>
