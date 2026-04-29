<template>
	<!-- Collapsible guide card with 3 tabs: Dashboard / Code Server / SSH -->
	<div class="rounded-lg border border-gray-200 bg-white shadow-sm">
		<button
			type="button"
			class="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-gray-50"
			@click="open = !open"
		>
			<div class="flex items-center gap-2">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" class="h-4 w-4 text-blue-600" stroke-width="2">
					<circle cx="12" cy="12" r="10"></circle>
					<path d="M12 16v-4"></path>
					<circle cx="12" cy="8" r=".5" fill="currentColor"></circle>
				</svg>
				<span class="text-sm font-semibold text-gray-900">How to pull and push code</span>
				<span class="hidden text-xs text-gray-500 sm:inline">— three flows: Dashboard, Code Server, SSH</span>
			</div>
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" class="h-4 w-4 text-gray-400" stroke-width="2">
				<path :d="open ? 'M18 15l-6-6-6 6' : 'M6 9l6 6 6-6'"></path>
			</svg>
		</button>

		<div v-if="open" class="border-t border-gray-200">
			<!-- Tab switcher -->
			<div class="flex gap-1 border-b border-gray-200 bg-gray-50 px-2 pt-2">
				<button
					v-for="t in tabs"
					:key="t.id"
					type="button"
					@click="active = t.id"
					:class="[
						'rounded-t px-3 py-1.5 text-xs font-medium transition',
						active === t.id
							? 'bg-white text-blue-700 shadow-sm ring-1 ring-gray-200'
							: 'text-gray-600 hover:bg-white/60 hover:text-gray-900',
					]"
				>
					{{ t.label }}
				</button>
			</div>

			<!-- DASHBOARD tab -->
			<div v-if="active === 'dashboard'" class="space-y-3 px-4 py-4 text-sm text-gray-700">
				<p class="text-xs leading-relaxed text-gray-500">
					Push from this dashboard — no SSH, no terminal. Easiest for most edits.
				</p>
				<div>
					<div class="font-medium text-gray-900">1. Find what's dirty</div>
					<p class="mt-0.5 text-xs leading-relaxed">
						The <strong>App Status</strong> table shows every app on this bench. Apps with
						<span class="rounded-full bg-orange-100 px-1.5 text-[11px] font-semibold text-orange-600">● N dirty</span>
						have uncommitted changes. Apps tagged
						<span class="rounded-full bg-gray-100 px-1.5 text-[11px] font-medium text-gray-600">upstream</span>
						(like <code>frappe</code>, <code>erpnext</code>, <code>hrms</code>) are read-only — no Push button.
					</p>
				</div>
				<div>
					<div class="font-medium text-gray-900">2. Click <strong>Push ↓</strong> on the dirty row</div>
					<p class="mt-0.5 text-xs leading-relaxed">
						An inline form opens with a <strong>Commit message</strong> and a <strong>Branch</strong> field.
					</p>
				</div>
				<div>
					<div class="font-medium text-gray-900">3. Pick a branch (recommended for team work)</div>
					<ul class="mt-0.5 list-disc space-y-1 pl-5 text-xs leading-relaxed">
						<li>Leave Branch blank to push to the current branch.</li>
						<li>
							Click <strong>✨ new feature</strong> to auto-fill
							<code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">dev/&lt;your-username&gt;/&lt;date&gt;</code>
							— each teammate gets their own branch.
						</li>
						<li>Or type any branch name (<code>fix/x123</code>, <code>feat/payments-refactor</code>).</li>
					</ul>
				</div>
				<div>
					<div class="font-medium text-gray-900">4. Click <strong>Push to GitHub</strong></div>
					<p class="mt-0.5 text-xs leading-relaxed">
						The dashboard runs <code>git add</code> → <code>git commit</code> → <code>git push</code> in the
						bench container with your team's GitHub token. The commit is authored as <strong>you</strong>
						(based on your dashboard login).
					</p>
				</div>
				<div>
					<div class="font-medium text-gray-900">5. Open a Pull Request</div>
					<p class="mt-0.5 text-xs leading-relaxed">
						If you pushed to a feature branch, an <strong>→ Open Pull Request</strong> link appears below
						the push output. Click it — GitHub opens compare-and-create-PR pre-filled.
					</p>
				</div>
			</div>

			<!-- CODE SERVER tab -->
			<div v-if="active === 'code-server'" class="space-y-3 px-4 py-4 text-sm text-gray-700">
				<p class="text-xs leading-relaxed text-gray-500">
					Browser-based VS Code with a built-in terminal. No install on your laptop. Best for quick edits
					from any device.
				</p>
				<div>
					<div class="font-medium text-gray-900">1. Open Code Server</div>
					<p class="mt-0.5 text-xs leading-relaxed">
						In the <strong>Dev Actions</strong> panel above, click <strong>Launch Code Server</strong>.
						A new browser tab opens with VS Code running inside the bench container.
						If the button shows <strong>Restart</strong>, click that first to revive a stuck server.
					</p>
				</div>
				<div>
					<div class="font-medium text-gray-900">2. Open the integrated terminal</div>
					<p class="mt-0.5 text-xs leading-relaxed">
						In Code Server: <strong>View → Terminal</strong> (or <kbd class="rounded border bg-gray-100 px-1 text-[11px]">Ctrl+`</kbd>).
						You're now inside <code>~/frappe-bench/</code> as user <code>frappe</code>.
					</p>
				</div>
				<div>
					<div class="font-medium text-gray-900">3. Set up git auth — once per shell session</div>
					<p class="mt-0.5 text-xs leading-relaxed">Run:</p>
					<pre class="mt-1 overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[11px] text-gray-100"><code>bench-git-setup</code></pre>
					<p class="mt-1 text-xs leading-relaxed">
						Enter your <strong>Press email</strong> when prompted. Press issues a short-lived per-user
						GitHub OAuth token (~60 min) and configures <code>git user.name</code> / <code>user.email</code>
						as you. Re-run <code>bench-git-setup</code> if the token expires.
					</p>
					<p class="mt-1 text-[11px] text-gray-500">
						First-time only: if the script says "Connect GitHub", open the link it prints, authorize once,
						then re-run.
					</p>
				</div>
				<div>
					<div class="font-medium text-gray-900">4. Pull or push from any app folder</div>
					<pre class="mt-1 overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[11px] text-gray-100"><code>cd ~/frappe-bench/apps/&lt;app&gt;
git pull                                  # latest from origin
git checkout -b feat/my-feature           # team-friendly branch
git add -A &amp;&amp; git commit -m "..."
git push -u origin feat/my-feature</code></pre>
					<p class="mt-1 text-xs leading-relaxed">
						Commits are attributed to YOU on GitHub. Open a PR from the GitHub web UI as usual.
					</p>
				</div>
			</div>

			<!-- SSH tab -->
			<div v-if="active === 'ssh'" class="space-y-3 px-4 py-4 text-sm text-gray-700">
				<p class="text-xs leading-relaxed text-gray-500">
					Connect from your local terminal or VS Code Desktop's Remote-SSH. Best when you want your own
					tooling, multiple panes, and tmux/zsh.
				</p>
				<div>
					<div class="font-medium text-gray-900">1. Generate an SSH certificate</div>
					<p class="mt-0.5 text-xs leading-relaxed">
						In the <strong>Bench Actions</strong> panel, click <strong>Generate SSH Certificate</strong>.
						One click — no key upload. The cert is signed by Press and lasts ~24 h.
					</p>
				</div>
				<div>
					<div class="font-medium text-gray-900">2. Connect with agent forwarding</div>
					<pre class="mt-1 overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[11px] text-gray-100"><code>ssh -A &lt;bench-name&gt;@&lt;proxy_server&gt; -p 2222</code></pre>
					<p class="mt-1 text-xs leading-relaxed">
						<strong>-A</strong> forwards your local SSH agent so you can also push with your personal
						SSH key if a repo is on SSH instead of HTTPS. The bench name and proxy host are shown
						on the Bench Actions card.
					</p>
				</div>
				<div>
					<div class="font-medium text-gray-900">3. Set up git auth — once per shell session</div>
					<pre class="mt-1 overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[11px] text-gray-100"><code>bench-git-setup</code></pre>
					<p class="mt-1 text-xs leading-relaxed">
						Same as Code Server: prompts for your Press email, fetches a per-user GitHub OAuth token,
						sets <code>git user.name</code> / <code>user.email</code>. Token lives in tmpfs and is
						wiped on logout.
					</p>
				</div>
				<div>
					<div class="font-medium text-gray-900">4. Pull or push</div>
					<pre class="mt-1 overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[11px] text-gray-100"><code>cd ~/frappe-bench/apps/&lt;app&gt;
git pull
git push origin HEAD</code></pre>
					<p class="mt-1 text-[11px] text-gray-500">
						Don't run <code>git remote add origin</code> manually — the existing remote is set up by
						Press, and deploy keys are read-only. Use <code>bench-git-setup</code> for auth instead.
					</p>
				</div>
			</div>

			<!-- Shared yellow callout -->
			<div class="border-t border-gray-200 bg-yellow-50 px-4 py-3">
				<div class="flex items-start gap-2 text-xs text-yellow-800">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" class="mt-0.5 h-3.5 w-3.5 flex-shrink-0" stroke-width="1.8">
						<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
						<path d="M12 9v4" />
						<circle cx="12" cy="17" r=".5" fill="currentColor" />
					</svg>
					<div>
						<strong>Edits live only in the running container.</strong>
						If the container restarts before you push, your work is gone. Push first, deploy/restart second.
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script>
export default {
	name: 'DevFlowsGuide',
	props: {
		// Which tab opens by default: 'dashboard' | 'code-server' | 'ssh'
		defaultFlow: {
			type: String,
			default: 'dashboard',
			validator: (v) => ['dashboard', 'code-server', 'ssh'].includes(v),
		},
	},
	data() {
		return {
			open: false,
			active: this.defaultFlow,
			tabs: [
				{ id: 'dashboard', label: 'Dashboard' },
				{ id: 'code-server', label: 'Code Server' },
				{ id: 'ssh', label: 'SSH' },
			],
		};
	},
};
</script>
