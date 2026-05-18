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
			<!-- Surface-specific leader: explains where you are and what these flows mean here -->
			<div class="border-b border-gray-200 bg-blue-50/40 px-4 py-2 text-[11.5px] leading-relaxed text-gray-700">
				{{ surfaceIntro }}
			</div>

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
				<div class="rounded border border-blue-200 bg-blue-50 px-3 py-2 text-[11.5px] leading-relaxed text-blue-900">
					<strong>Prerequisite:</strong> the app must already have a GitHub
					<code class="rounded bg-blue-100 px-1 py-0.5 text-[11px]">origin</code> remote and you must be on a
					real branch (not detached HEAD). Fresh bench containers sometimes ship with only an
					<code class="rounded bg-blue-100 px-1 py-0.5 text-[11px]">upstream</code> remote pointing at a local
					path. If Push fails with <em>"'origin' does not appear to be a git repository"</em> or
					<em>"You are not currently on a branch"</em>, fix it once via the Code Server or SSH flow
					(see the other tabs — <strong>steps 3.5 + 3.6</strong>), then come back here.
				</div>
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
				<div>
					<div class="font-medium text-gray-900">If Push fails — common fixes</div>
					<ul class="mt-0.5 list-disc space-y-1 pl-5 text-[11.5px] leading-relaxed text-gray-600">
						<li>
							<strong>"'origin' does not appear to be a git repository"</strong> — the app has no
							GitHub remote yet. Open Code Server (next tab), then run:
							<code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">git remote add origin https://github.com/&lt;org&gt;/&lt;repo&gt;.git</code>
							and <code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">git fetch origin</code>.
						</li>
						<li>
							<strong>"You are not currently on a branch"</strong> — detached HEAD. Run
							<code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">git checkout &lt;branch&gt;</code>
							or <code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">git switch -c &lt;branch&gt; origin/&lt;branch&gt;</code>.
						</li>
						<li>
							<strong>403 / Permission denied</strong> — your GitHub user (the one tied to your Press email)
							doesn't have write access to that repo. Fix on GitHub, not on the bench.
						</li>
					</ul>
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
					<div class="font-medium text-gray-900">3. Set up git auth — run inside the app folder</div>
					<pre class="mt-1 overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[11px] text-gray-100"><code>cd ~/frappe-bench/apps/&lt;app&gt;
bench-git-setup</code></pre>
					<p class="mt-1 text-xs leading-relaxed">
						Enter your <strong>Press email</strong> when prompted. Press issues a short-lived per-user
						GitHub OAuth token (<strong>~8 hours</strong>) and configures <code>git user.name</code> /
						<code>user.email</code> as you. If the app's <code>origin</code> is an SSH URL
						(<code>git@github.com:...</code>), the script auto-rewrites it to HTTPS so the OAuth token
						actually works. Re-run if the token expires.
					</p>
					<p class="mt-1 text-[11px] text-gray-500">
						First-time only: if the script says "Connect GitHub", open the link it prints, authorize once,
						then re-run.
					</p>
				</div>
				<div>
					<div class="font-medium text-gray-900">3.5. Make sure <code>origin</code> points to GitHub</div>
					<pre class="mt-1 overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[11px] text-gray-100"><code>git remote -v</code></pre>
					<p class="mt-1 text-xs leading-relaxed">
						Fresh bench containers sometimes only have an <code>upstream</code> remote pointing at
						<code>file:///home/frappe/context/apps/&lt;app&gt;</code> — not GitHub. If you see <strong>no
						<code>origin</code></strong> line, add it:
					</p>
					<pre class="mt-1 overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[11px] text-gray-100"><code>git remote add origin https://github.com/&lt;org&gt;/&lt;repo&gt;.git
git fetch origin</code></pre>
					<p class="mt-1 text-[11px] text-gray-500">
						Use the same GitHub URL the app was scaffolded from. <code>bench-git-setup</code> takes care of
						auth — you don't need to add credentials to this URL.
					</p>
				</div>
				<div>
					<div class="font-medium text-gray-900">3.6. Get on a real branch (not detached HEAD)</div>
					<pre class="mt-1 overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[11px] text-gray-100"><code>git status                                # shows "HEAD detached" if you are
git checkout &lt;branch&gt;                      # if branch exists locally
git switch -c &lt;branch&gt; origin/&lt;branch&gt;     # if you just fetched it</code></pre>
					<p class="mt-1 text-xs leading-relaxed">
						Bench containers usually start in detached HEAD. <code>git pull</code> fails until you're on
						a branch. Skip this step only if <code>git status</code> shows
						<code>On branch &lt;name&gt;</code>.
					</p>
				</div>
				<div>
					<div class="font-medium text-gray-900">4. Pull or push</div>
					<pre class="mt-1 overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[11px] text-gray-100"><code>git pull                                  # latest from origin
git checkout -b feat/my-feature           # OR keep working on the branch from 3.6
git add -A &amp;&amp; git commit -m "..."
git push -u origin feat/my-feature</code></pre>
					<p class="mt-1 text-xs leading-relaxed">
						Commits are attributed to YOU on GitHub. Open a PR from the GitHub web UI as usual.
					</p>
					<p class="mt-1 text-[11px] text-gray-500">
						<strong>Schema change?</strong> Run
						<code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">bench --site &lt;site&gt; migrate</code>
						after pulling. Python edits hot-reload — no <code>bench restart</code> needed.
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
					<div class="font-medium text-gray-900">3. Set up git auth — run inside the app folder</div>
					<pre class="mt-1 overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[11px] text-gray-100"><code>cd ~/frappe-bench/apps/&lt;app&gt;
bench-git-setup</code></pre>
					<p class="mt-1 text-xs leading-relaxed">
						Same as Code Server: prompts for your Press email, fetches a per-user GitHub OAuth token
						(<strong>~8 hours</strong>), sets <code>git user.name</code> / <code>user.email</code>,
						and auto-rewrites SSH origins (<code>git@github.com:...</code>) to HTTPS so the token works.
						Token lives in tmpfs and is wiped on logout.
					</p>
				</div>
				<div>
					<div class="font-medium text-gray-900">3.5. Make sure <code>origin</code> points to GitHub</div>
					<pre class="mt-1 overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[11px] text-gray-100"><code>git remote -v</code></pre>
					<p class="mt-1 text-xs leading-relaxed">
						Fresh bench containers sometimes only have an <code>upstream</code> remote pointing at
						<code>file:///home/frappe/context/apps/&lt;app&gt;</code> — not GitHub. If you see <strong>no
						<code>origin</code></strong> line, add it once:
					</p>
					<pre class="mt-1 overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[11px] text-gray-100"><code>git remote add origin https://github.com/&lt;org&gt;/&lt;repo&gt;.git
git fetch origin</code></pre>
				</div>
				<div>
					<div class="font-medium text-gray-900">3.6. Get on a real branch (not detached HEAD)</div>
					<pre class="mt-1 overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[11px] text-gray-100"><code>git status                                # shows "HEAD detached" if you are
git checkout &lt;branch&gt;                      # if branch exists locally
git switch -c &lt;branch&gt; origin/&lt;branch&gt;     # if you just fetched it</code></pre>
				</div>
				<div>
					<div class="font-medium text-gray-900">4. Pull or push</div>
					<pre class="mt-1 overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[11px] text-gray-100"><code>git pull
git push origin HEAD</code></pre>
					<p class="mt-1 text-[11px] text-gray-500">
						<code>bench-git-setup</code> handles auth + URL rewrite — you don't need a personal SSH key
						or PAT inside the bench. Forwarded SSH agent (<code>-A</code>) is only a fallback if you
						prefer SSH remotes.
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
						If the container is <em>rebuilt</em> (deploy, image upgrade) before you push, your work is gone.
						<strong>Push first, deploy second.</strong>
						<span class="block mt-1 text-[11px] opacity-90">
							<code class="rounded bg-yellow-100 px-1 py-0.5">bench restart</code> only recycles processes —
							your edited files survive. Only a <em>rebuild</em> wipes them.
						</span>
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
		// Where this guide is mounted: tailors the leader paragraph
		// 'site'  — Site Dev tab (focuses on "this site's bench")
		// 'bench' — Release Group Bench Actions tab (focuses on "this group")
		surface: {
			type: String,
			default: 'bench',
			validator: (v) => ['bench', 'site'].includes(v),
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
	computed: {
		surfaceIntro() {
			if (this.surface === 'site') {
				return (
					'These are the three ways to push code that affects THIS site. ' +
					'Pick the one that matches how you edit — from the dashboard, from Code Server in the browser, or from a real SSH terminal. ' +
					"Whichever you choose, the change lands in the same bench container that powers this site."
				);
			}
			// surface === 'bench'
			return (
				'Three ways to push code from a bench in this release group. ' +
				'These flows apply to every site running on the bench you choose. ' +
				'Use Dashboard for the easiest path, Code Server for browser-based editing, or SSH if you want your own terminal.'
			);
		},
	},
};
</script>
