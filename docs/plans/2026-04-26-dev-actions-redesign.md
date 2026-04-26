# Dev Actions Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the Press dashboard's Release Group Actions panel so each bench has a single, organized section: Code Server panel + 4 action tiles (Open in VS Code, Mark as Dev Bench, Generate SSH Certificate, Restart Bench). Fix the password copy bug. Add an "Open in VS Code" flow that launches the user's local VS Code Desktop over Remote-SSH.

**Architecture:** One Vue component restructure (`ReleaseGroupActions.vue`) + one new dialog (`VSCodeLaunchDialog.vue`) that reuses the existing SSH certificate generation API (`press.api.client.run_doc_method` on Release Group). One small backend whitelisted method to compose the `vscode://` URL from a bench. No schema changes, no permission changes.

**Tech Stack:** Vue 3 Options API (matches existing component style), frappe-ui (`Dialog`, `Button`, `FeatherIcon`), Tailwind CSS (slate palette via frappe-ui preset), Python whitelisted methods.

**Reference:** Approved prototype at [docs/prototypes/dev-actions-redesign.html](../prototypes/dev-actions-redesign.html). Open it before implementing — the tile sizing, KV row layout, and modal step format are all locked there.

**Working directory:** `/home/eslam/data/erpnext-app-repos/press_local`. Branch off `cloudflare-dns`.

---

## File Structure

**Create:**
- `dashboard/src/components/group/VSCodeLaunchDialog.vue` (~220 lines) — modal that reuses SSH cert generation API and ends with a `Launch VS Code` button firing a `vscode://` URI.
- `press/docs/wiki/03-bench-management/dev-actions.md` — user-facing wiki page documenting the Dev Actions panel.

**Modify:**
- `dashboard/src/components/group/ReleaseGroupActions.vue` (currently 326 lines → ~480 lines) — full template restructure. New per-bench section with status pill, full-width Code Server KV panel, and 4-tile action grid.
- `press/press/doctype/bench/bench_dev_overview.py` — add `get_vscode_remote_url(bench_name)` whitelisted method that returns the `vscode://vscode-remote/...` URL for a bench.

**Test:**
- `press/press/doctype/bench/test_bench_dev_overview.py` (create or extend) — Python unit test for the new method.

**No changes:**
- `dashboard/src/components/group/SSHCertificateDialog.vue` (kept untouched — VSCodeLaunchDialog is a sibling, not a fork).
- `press/press/doctype/release_group/release_group.json` (the standard `actions` child table is bypassed in the new layout, not deleted; existing data is harmless).

---

### Task 0: Branch and worktree setup

**Files:** none (git only)

- [ ] **Step 1: Create feature branch off `cloudflare-dns`**

```bash
cd /home/eslam/data/erpnext-app-repos/press_local
git fetch origin
git checkout cloudflare-dns
git pull origin cloudflare-dns
git checkout -b feat/dev-actions-redesign
```

- [ ] **Step 2: Confirm clean state**

```bash
git status
```

Expected: `On branch feat/dev-actions-redesign` and `nothing to commit, working tree clean`. If untracked files exist, stash or commit before proceeding.

- [ ] **Step 3: Pre-edit backup**

```bash
bash ~/.claude/hooks/pre-edit-backup.sh \
  dashboard/src/components/group/ReleaseGroupActions.vue \
  press/press/doctype/bench/bench_dev_overview.py
```

Expected: `Saved backup to .tmp/backups/...`. Required by Gate 1c per project pipeline rules.

---

### Task 1: Backend — `get_vscode_remote_url` API

**Files:**
- Modify: `press/press/doctype/bench/bench_dev_overview.py`
- Create or extend: `press/press/doctype/bench/test_bench_dev_overview.py`

- [ ] **Step 1: Read the existing module to match style**

```bash
head -40 press/press/doctype/bench/bench_dev_overview.py
```

Note the existing whitelist decorator pattern, frappe imports, and how `bench_name` is validated in other methods (typically `frappe.get_doc("Bench", bench_name)` early to enforce permissions).

- [ ] **Step 2: Write the failing test**

Create `press/press/doctype/bench/test_bench_dev_overview.py` if missing:

```python
import frappe
import unittest
from press.press.doctype.bench.bench_dev_overview import get_vscode_remote_url


class TestBenchDevOverview(unittest.TestCase):
    def setUp(self):
        # Pick any existing Active bench from the test fixtures
        self.bench = frappe.db.get_value(
            "Bench", {"status": "Active"}, ["name", "group"], as_dict=True
        )
        if not self.bench:
            self.skipTest("No active bench in test DB")

    def test_returns_vscode_uri_with_bench_user_proxy_and_bench_path(self):
        url = get_vscode_remote_url(self.bench.name)
        self.assertTrue(url.startswith("vscode://vscode-remote/ssh-remote+"))
        self.assertIn(f"+{self.bench.name}@", url)
        self.assertIn(":2222", url)
        self.assertTrue(url.endswith("/home/frappe/frappe-bench"))

    def test_raises_for_nonexistent_bench(self):
        with self.assertRaises(frappe.DoesNotExistError):
            get_vscode_remote_url("nonexistent-bench-zzz-9999")
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd /home/frappe/frappe-bench  # or your local bench root
bench --site demo.mvpstorm.com run-tests --module press.press.doctype.bench.test_bench_dev_overview
```

Expected: `ImportError: cannot import name 'get_vscode_remote_url'` or similar.

- [ ] **Step 4: Implement the method**

Append to `press/press/doctype/bench/bench_dev_overview.py`:

```python
@frappe.whitelist()
def get_vscode_remote_url(bench_name: str) -> str:
    """
    Compose a `vscode://vscode-remote/ssh-remote+<bench>@<proxy>:2222/home/frappe/frappe-bench`
    URI for launching local VS Code Desktop against a Press-managed bench over SSH.

    Permission: caller must have read access to the Bench. frappe.get_doc enforces this.
    """
    bench = frappe.get_doc("Bench", bench_name)  # raises DoesNotExistError + checks read perm
    release_group = frappe.get_doc("Release Group", bench.group)
    proxy_server = bench.proxy_server or release_group.proxy_server
    if not proxy_server:
        frappe.throw(
            "This bench has no proxy server configured. Run Generate SSH Certificate first."
        )
    return (
        f"vscode://vscode-remote/ssh-remote+{bench.name}@{proxy_server}:2222"
        f"/home/frappe/frappe-bench"
    )
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
bench --site demo.mvpstorm.com run-tests --module press.press.doctype.bench.test_bench_dev_overview
```

Expected: `2 tests passed`.

- [ ] **Step 6: Commit**

```bash
git add press/press/doctype/bench/bench_dev_overview.py press/press/doctype/bench/test_bench_dev_overview.py
git commit -m "feat(bench): add get_vscode_remote_url for VS Code Remote-SSH launcher"
```

---

### Task 2: Create `VSCodeLaunchDialog.vue`

**Files:**
- Create: `dashboard/src/components/group/VSCodeLaunchDialog.vue`

The new dialog matches the existing `SSHCertificateDialog.vue` flow (key selection → certificate generation → step list) but ends with a `Launch VS Code` button that opens the `vscode://` URI returned by Task 1.

- [ ] **Step 1: Read the existing SSHCertificateDialog for the cert-generation pattern**

```bash
cat dashboard/src/components/group/SSHCertificateDialog.vue
```

Confirm the API shape: `releaseGroup.generateCertificate.submit({ ssh_key_name })`, `releaseGroup.getCertificate.submit({ ssh_key_name })`, `press.api.account.get_user_ssh_keys`.

- [ ] **Step 2: Create the new component**

Create `dashboard/src/components/group/VSCodeLaunchDialog.vue`:

```vue
<template>
	<Dialog :options="{ title: 'Open in VS Code', size: 'xl' }" v-model="show">
		<template #body-content v-if="$bench.doc">
			<div v-if="certificate && vscodeUrl" class="space-y-4">
				<p class="text-base text-gray-700">
					Connect to <strong>{{ bench }}</strong> with your local VS Code Desktop over SSH.
					Run the commands below once, then click <strong>Launch VS Code</strong>.
				</p>

				<div v-if="isWindows" class="space-y-2">
					<h4 class="text-base font-semibold text-gray-700">Step 1</h4>
					<p class="text-base">Set the PowerShell encoding to UTF-8.</p>
					<ClickToCopyField
						textContent="$PSDefaultParameterValues['*: Encoding'] = 'utf8'"
						:breakLines="false"
					/>
				</div>

				<div class="space-y-2">
					<h4 class="text-base font-semibold text-gray-700">
						Step {{ isWindows ? '2' : '1' }}
					</h4>
					<p class="text-base">Store the SSH certificate locally.</p>
					<ClickToCopyField :textContent="certificateCommand" :breakLines="false" />
				</div>

				<div class="space-y-2">
					<h4 class="text-base font-semibold text-gray-700">
						Step {{ isWindows ? '3' : '2' }}
					</h4>
					<p class="text-base">Launch VS Code Desktop. It opens the bench over Remote-SSH.</p>
					<a :href="vscodeUrl" class="block">
						<Button variant="solid" class="w-full">Launch VS Code</Button>
					</a>
					<p class="mt-2 text-xs text-gray-500">
						Doesn't open automatically? Copy and paste this URL in your browser:
					</p>
					<ClickToCopyField :textContent="vscodeUrl" :breakLines="true" />
				</div>

				<div class="flex items-start gap-2 rounded bg-gray-100 p-3 text-sm text-gray-700">
					<FeatherIcon name="info" class="mt-0.5 h-4 w-4 flex-shrink-0" />
					<p>
						The certificate is valid for <strong>6 hours</strong>. Reopen this dialog after it expires.
						Your local SSH key authenticates you — no Code Server password is needed.
					</p>
				</div>
			</div>

			<div v-else class="space-y-3 text-p-base text-gray-700">
				<p v-if="!$bench.doc.user_ssh_key">
					Add an SSH public key in
					<router-link :to="{ name: 'SettingsDeveloper' }" class="underline" @click="show = false">
						Developer Settings
					</router-link>
					before opening this bench in VS Code.
				</p>
				<p v-else-if="!$bench.doc.is_ssh_proxy_setup">
					SSH access is not enabled for this bench. Please contact support.
				</p>
				<template v-else>
					<p>
						You will need an SSH certificate to connect VS Code over Remote-SSH. The certificate
						is signed for your registered SSH key and is valid for 6 hours.
					</p>
					<div v-if="sshKeys.length > 1" class="space-y-2">
						<label class="block text-sm font-semibold text-gray-700">
							Sign certificate for which key?
						</label>
						<div class="space-y-1.5">
							<label
								v-for="key in sshKeys"
								:key="key.name"
								class="flex cursor-pointer items-center gap-2 rounded border p-2 hover:bg-gray-50"
								:class="selectedSshKey === key.name ? 'border-blue-400 bg-blue-50' : 'border-gray-200'"
							>
								<input
									type="radio"
									:value="key.name"
									v-model="selectedSshKey"
									class="accent-blue-600"
									:disabled="key.is_disabled"
								/>
								<div class="flex-1 truncate">
									<div class="text-sm font-medium text-gray-900">
										{{ key.label || '(no label)' }}
									</div>
									<code class="block truncate text-xs text-gray-500">
										{{ key.ssh_fingerprint }}
									</code>
								</div>
							</label>
						</div>
					</div>
					<ErrorMessage class="mt-3" :message="$releaseGroup.generateCertificate.error" />
				</template>
			</div>
		</template>

		<template
			#actions
			v-if="!certificate && $bench.doc?.is_ssh_proxy_setup && $bench.doc?.user_ssh_key"
		>
			<Button
				:loading="$releaseGroup.generateCertificate.loading"
				:disabled="!selectedSshKey"
				@click="handleGenerate"
				variant="solid"
				class="w-full"
			>
				Generate SSH Certificate
			</Button>
		</template>
	</Dialog>
</template>

<script>
import { getCachedDocumentResource, call, FeatherIcon } from 'frappe-ui';

export default {
	props: ['bench', 'releaseGroup'],
	components: { FeatherIcon },
	data() {
		return {
			show: true,
			sshKeys: [],
			selectedSshKey: null,
			vscodeUrl: null,
		};
	},
	resources: {
		bench() {
			return {
				type: 'document',
				doctype: 'Bench',
				name: this.bench,
				onSuccess: (doc) => {
					if (doc.is_ssh_proxy_setup && doc.user_ssh_key) {
						this.loadSshKeys();
					}
				},
			};
		},
	},
	computed: {
		$bench() {
			return this.$resources.bench;
		},
		$releaseGroup() {
			return getCachedDocumentResource('Release Group', this.releaseGroup);
		},
		certificate() {
			return this.$releaseGroup.getCertificate.data;
		},
		certificateCommand() {
			if (!this.certificate) return null;
			return `echo '${this.certificate.ssh_certificate?.trim()}' > ~/.ssh/id_${this.certificate.key_type}-cert.pub`;
		},
		isWindows() {
			return navigator.userAgent.includes('Windows');
		},
	},
	methods: {
		async loadSshKeys() {
			try {
				this.sshKeys = await call('press.api.account.get_user_ssh_keys');
				const activeDefault = this.sshKeys.find((k) => k.is_default && !k.is_disabled);
				const firstActive = this.sshKeys.find((k) => !k.is_disabled);
				this.selectedSshKey = (activeDefault || firstActive || this.sshKeys[0])?.name;
				if (this.selectedSshKey) {
					await this.$releaseGroup.getCertificate.submit({ ssh_key_name: this.selectedSshKey });
					await this.loadVscodeUrl();
				}
			} catch (e) {
				this.sshKeys = [];
			}
		},
		async loadVscodeUrl() {
			try {
				this.vscodeUrl = await call(
					'press.press.doctype.bench.bench_dev_overview.get_vscode_remote_url',
					{ bench_name: this.bench },
				);
			} catch (e) {
				this.vscodeUrl = null;
			}
		},
		async handleGenerate() {
			await this.$releaseGroup.generateCertificate.submit({ ssh_key_name: this.selectedSshKey });
			await this.$releaseGroup.getCertificate.submit({ ssh_key_name: this.selectedSshKey });
			await this.loadVscodeUrl();
		},
	},
};
</script>
```

- [ ] **Step 3: Build the dashboard to surface compile errors**

```bash
ssh press-ctrl 'sudo -u frappe bash -c "cd /home/frappe/frappe-bench && bench build --app press"'
```

Expected: `Build complete.` with no Vue errors. If a SyntaxError or template error appears, fix and retry before moving on.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/components/group/VSCodeLaunchDialog.vue
git commit -m "feat(dashboard): add VSCodeLaunchDialog for Open in VS Code flow"
```

---

### Task 3: Restructure `ReleaseGroupActions.vue` template

**Files:**
- Modify: `dashboard/src/components/group/ReleaseGroupActions.vue`

This is the largest change. The component goes from one custom Dev Actions block + one fixture-driven actions block to a single per-bench section card. The bottom standard `actions` block is removed entirely (the 3 actions it rendered — Open Code Server, Generate SSH Certificate, Restart Bench — are now per-bench tiles).

- [ ] **Step 1: Replace the entire `<template>` block**

Replace the contents of the `<template>` in `dashboard/src/components/group/ReleaseGroupActions.vue` with:

```vue
<template>
	<div class="mx-auto max-w-3xl space-y-4">
		<div v-if="benches.data?.length" class="rounded border border-gray-200">
			<div class="border-b border-gray-200 p-5 text-lg font-semibold">Dev Actions</div>

			<div
				v-for="bench in benches.data"
				:key="bench.name"
				class="border-b border-gray-200 p-5 last:border-b-0"
			>
				<!-- Bench head: name + helper + status pill -->
				<div class="mb-4 flex items-start justify-between gap-4">
					<div>
						<h3 class="font-mono text-base font-semibold text-gray-900">{{ bench.name }}</h3>
						<p class="mt-0.5 text-sm text-gray-500">
							{{
								bench.is_development_bench
									? 'This bench is marked as a development bench'
									: 'Mark this bench for development use only'
							}}
						</p>
					</div>
					<span
						class="inline-flex flex-shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
						:class="codeServerStatusClass(bench)"
					>
						<span class="h-1.5 w-1.5 rounded-full" :class="codeServerDotClass(bench)"></span>
						{{ codeServerStatusLabel(bench) }}
					</span>
				</div>

				<!-- Code Server KV panel -->
				<div class="mb-3 overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
					<div class="border-b border-gray-200 bg-white px-4 py-2.5">
						<span class="text-xs font-semibold text-gray-900">Code Server</span>
					</div>

					<template v-if="codeServerStatus[bench.name]?.status === 'Running' && codeServerStatus[bench.name]?.url">
						<div class="grid grid-cols-[90px_1fr] items-center gap-3 px-4 py-2.5">
							<div class="text-[11px] font-medium uppercase tracking-wider text-gray-500">URL</div>
							<div class="flex min-w-0 items-center gap-1.5 font-mono text-[12.5px] text-gray-900">
								<span class="flex-1 truncate">{{ codeServerStatus[bench.name].url }}</span>
								<button
									class="inline-flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-gray-200 hover:text-gray-900"
									@click="copyToClipboard(codeServerStatus[bench.name].url, 'URL copied')"
									title="Copy URL"
								>
									<FeatherIcon name="copy" class="h-3.5 w-3.5" />
								</button>
								<a
									:href="codeServerStatus[bench.name].url"
									target="_blank"
									class="inline-flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-gray-200 hover:text-gray-900"
									title="Open in new tab"
								>
									<FeatherIcon name="external-link" class="h-3.5 w-3.5" />
								</a>
							</div>
						</div>
						<div class="grid grid-cols-[90px_1fr] items-center gap-3 border-t border-gray-200 px-4 py-2.5">
							<div class="text-[11px] font-medium uppercase tracking-wider text-gray-500">Password</div>
							<div class="flex min-w-0 items-center gap-1.5 font-mono text-[12.5px]">
								<span
									class="flex-1 truncate select-none"
									:class="revealedPasswords[bench.name] ? 'select-text font-medium text-gray-900' : 'tracking-widest text-gray-500'"
								>
									{{ revealedPasswords[bench.name] ? codeServerStatus[bench.name].password : '••••••••••••' }}
								</span>
								<button
									class="inline-flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-gray-200 hover:text-gray-900"
									:class="revealedPasswords[bench.name] && 'text-blue-600'"
									@click="togglePasswordReveal(bench)"
									:title="revealedPasswords[bench.name] ? 'Hide password' : 'Show password'"
								>
									<FeatherIcon :name="revealedPasswords[bench.name] ? 'eye-off' : 'eye'" class="h-3.5 w-3.5" />
								</button>
								<button
									class="inline-flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-gray-200 hover:text-gray-900"
									@click="copyCodeServerPassword(bench)"
									title="Copy password"
								>
									<FeatherIcon name="copy" class="h-3.5 w-3.5" />
								</button>
							</div>
						</div>
						<div class="space-y-1.5 border-t border-gray-200 bg-white px-4 py-2.5 text-xs text-gray-500">
							<div class="flex items-center gap-2">
								<span :class="codeServerStatus[bench.name]?.password_is_expired ? 'font-medium text-red-600' : ''">
									{{ formatExpiry(codeServerStatus[bench.name].password_expires_at) }}
								</span>
								<span class="text-gray-300">·</span>
								<button
									:disabled="rotateLoading[bench.name]"
									@click="rotateCodeServerPassword(bench)"
									class="font-medium text-gray-700 hover:text-gray-900 hover:underline"
								>
									{{ rotateLoading[bench.name] ? 'Rotating…' : 'Rotate now' }}
								</button>
								<span class="text-gray-300">·</span>
								<button
									:disabled="restartLoading[bench.name]"
									@click="restartCodeServer(bench)"
									class="font-medium text-gray-700 hover:text-gray-900 hover:underline"
								>
									{{ restartLoading[bench.name] ? 'Restarting…' : 'Restart' }}
								</button>
							</div>
							<div class="flex items-center gap-1.5">
								<span>Auto-rotate every</span>
								<input
									type="number"
									min="0"
									class="w-9 rounded border border-gray-200 px-1 py-0 text-right text-xs focus:border-blue-500 focus:outline-none"
									v-model.number="durationEdits[bench.name]"
									@blur="saveDuration(bench)"
									@keyup.enter="saveDuration(bench)"
								/>
								<span>days</span>
							</div>
						</div>
					</template>

					<template v-else-if="codeServerStatus[bench.name]?.exists && codeServerStatus[bench.name]?.status !== 'Running'">
						<div class="flex flex-col items-center gap-2 px-4 py-6 text-center text-sm text-gray-500">
							<span>Code Server {{ codeServerStatus[bench.name].status === 'Pending' ? 'starting…' : codeServerStatus[bench.name].status.toLowerCase() }}</span>
							<Button
								:loading="restartLoading[bench.name]"
								@click="restartCodeServer(bench)"
								class="mt-1"
							>
								Restart Code Server
							</Button>
						</div>
					</template>

					<template v-else>
						<div class="flex flex-col items-center gap-2 px-4 py-6 text-center text-sm text-gray-500">
							<span>Code Server is not running for this bench.</span>
							<Button
								:loading="codeServerLoading[bench.name]"
								variant="solid"
								@click="launchCodeServer(bench)"
								class="mt-1"
							>
								Launch Code Server
							</Button>
						</div>
					</template>
				</div>

				<!-- 4-tile action grid -->
				<div class="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
					<button
						type="button"
						class="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-3.5 text-left transition hover:border-gray-300 hover:shadow-sm"
						@click="openVscodeDialog(bench)"
					>
						<div class="flex h-7 w-7 items-center justify-center rounded-md bg-blue-50 text-blue-600">
							<FeatherIcon name="code" class="h-4 w-4" />
						</div>
						<div>
							<h4 class="text-[13px] font-semibold text-gray-900">Open in VS Code</h4>
							<p class="mt-0.5 text-[11.5px] leading-snug text-gray-500">
								Local VS Code Desktop via Remote-SSH.
							</p>
						</div>
					</button>

					<button
						type="button"
						class="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-3.5 text-left transition hover:border-gray-300 hover:shadow-sm"
						:disabled="devLoading[bench.name]"
						@click="toggleDevBench(bench)"
					>
						<div class="flex h-7 w-7 items-center justify-center rounded-md bg-gray-100 text-gray-700">
							<FeatherIcon name="tag" class="h-4 w-4" />
						</div>
						<div>
							<h4 class="text-[13px] font-semibold text-gray-900">
								{{ bench.is_development_bench ? 'Unset Dev Bench' : 'Mark as Dev Bench' }}
							</h4>
							<p class="mt-0.5 text-[11.5px] leading-snug text-gray-500">
								Tag this bench for development use only.
							</p>
						</div>
					</button>

					<button
						type="button"
						class="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-3.5 text-left transition hover:border-gray-300 hover:shadow-sm"
						@click="openSshDialog(bench)"
					>
						<div class="flex h-7 w-7 items-center justify-center rounded-md bg-gray-100 text-gray-700">
							<FeatherIcon name="lock" class="h-4 w-4" />
						</div>
						<div>
							<h4 class="text-[13px] font-semibold text-gray-900">Generate SSH Certificate</h4>
							<p class="mt-0.5 text-[11.5px] leading-snug text-gray-500">
								Required for "Open in VS Code". Valid 6 hours.
							</p>
						</div>
					</button>

					<button
						type="button"
						class="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-3.5 text-left transition hover:border-gray-300 hover:shadow-sm"
						@click="confirmRestartBench(bench)"
					>
						<div class="flex h-7 w-7 items-center justify-center rounded-md bg-gray-100 text-gray-700">
							<FeatherIcon name="refresh-cw" class="h-4 w-4" />
						</div>
						<div>
							<h4 class="text-[13px] font-semibold text-gray-900">Restart Bench</h4>
							<p class="mt-0.5 text-[11.5px] leading-snug text-gray-500">
								Restart all bench workers (web, scheduler, queues).
							</p>
						</div>
					</button>
				</div>
			</div>
		</div>
	</div>
</template>
```

- [ ] **Step 2: Verify template parses**

```bash
ssh press-ctrl 'sudo -u frappe bash -c "cd /home/frappe/frappe-bench && bench build --app press"'
```

Expected: clean build. If template errors appear, fix and retry. The component is broken at runtime until Task 4 wires the new methods, but the template must compile.

- [ ] **Step 3: Commit (template only — methods come next)**

```bash
git add dashboard/src/components/group/ReleaseGroupActions.vue
git commit -m "refactor(dashboard): restructure Dev Actions to per-bench section template"
```

---

### Task 4: Wire `<script>` block of `ReleaseGroupActions.vue`

**Files:**
- Modify: `dashboard/src/components/group/ReleaseGroupActions.vue`

Add the new methods used by the template (`copyToClipboard`, `togglePasswordReveal`, `openVscodeDialog`, `openSshDialog`, `confirmRestartBench`, `codeServerStatusClass`, `codeServerStatusLabel`, `codeServerDotClass`). Remove the now-unused `actions` computed property and `ReleaseGroupActionCell` import.

- [ ] **Step 1: Replace the entire `<script>` block**

Replace the contents of the `<script>` block in `dashboard/src/components/group/ReleaseGroupActions.vue` with:

```vue
<script>
import {
	call,
	createListResource,
	getCachedDocumentResource,
	FeatherIcon,
	Button,
} from 'frappe-ui';
import { h, defineAsyncComponent } from 'vue';
import { toast } from 'vue-sonner';
import { renderDialog, confirmDialog } from '../../utils/components';
import SSHCertificateDialog from './SSHCertificateDialog.vue';

const VSCodeLaunchDialog = defineAsyncComponent(
	() => import('./VSCodeLaunchDialog.vue'),
);

export default {
	props: ['releaseGroup'],
	components: { FeatherIcon, Button },
	data() {
		return {
			devLoading: {},
			codeServerLoading: {},
			codeServerStatus: {},
			revealedPasswords: {},
			rotateLoading: {},
			restartLoading: {},
			durationEdits: {},
			benches: createListResource({
				doctype: 'Bench',
				fields: ['name', 'status', 'is_development_bench', 'group'],
				filters: { group: this.releaseGroup, status: ['not in', ['Archived']] },
				orderBy: 'creation desc',
				auto: true,
				onSuccess: (data) => this.loadCodeServerStatuses(data),
			}),
		};
	},
	computed: {
		$releaseGroup() {
			return getCachedDocumentResource('Release Group', this.releaseGroup);
		},
	},
	methods: {
		async toggleDevBench(bench) {
			const enabling = !bench.is_development_bench;
			this.devLoading = { ...this.devLoading, [bench.name]: true };
			try {
				await call('press.api.client.run_doc_method', {
					dt: 'Bench',
					dn: bench.name,
					method: 'set_development_bench',
					args: JSON.stringify({ enable: enabling ? 1 : 0 }),
				});
				toast.success(
					enabling
						? `${bench.name} marked as development bench`
						: `${bench.name} unset from development bench`,
				);
				this.benches.reload();
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to update bench');
			} finally {
				this.devLoading = { ...this.devLoading, [bench.name]: false };
			}
		},

		async loadCodeServerStatuses(benches) {
			const statuses = {};
			const durations = { ...this.durationEdits };
			for (const b of benches) {
				try {
					statuses[b.name] = await call(
						'press.press.doctype.bench.bench_dev_overview.get_code_server_status',
						{ bench_name: b.name },
					);
					if (statuses[b.name]?.password_expiry_days != null) {
						durations[b.name] = statuses[b.name].password_expiry_days;
					}
				} catch (e) {
					statuses[b.name] = { enabled: false, exists: false, status: null };
				}
			}
			this.codeServerStatus = statuses;
			this.durationEdits = durations;
		},

		async launchCodeServer(bench) {
			this.codeServerLoading = { ...this.codeServerLoading, [bench.name]: true };
			const subdomain = `code-${bench.name.replace(/[^a-z0-9]/g, '-').slice(0, 30)}`;
			try {
				const res = await call(
					'press.press.doctype.bench.bench_dev_overview.setup_code_server',
					{ bench_name: bench.name, subdomain },
				);
				if (res?.error) {
					toast.error(res.error);
				} else {
					toast.success('Code Server setup started');
					this.loadCodeServerStatuses(this.benches.data || []);
				}
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to launch Code Server');
			} finally {
				this.codeServerLoading = { ...this.codeServerLoading, [bench.name]: false };
			}
		},

		togglePasswordReveal(bench) {
			this.revealedPasswords = {
				...this.revealedPasswords,
				[bench.name]: !this.revealedPasswords[bench.name],
			};
		},

		async copyCodeServerPassword(bench) {
			const pwd = this.codeServerStatus[bench.name]?.password;
			if (!pwd) return;
			await this.copyToClipboard(pwd, 'Code Server password copied');
		},

		async copyToClipboard(text, message = 'Copied') {
			try {
				await navigator.clipboard.writeText(text);
				toast.success(message);
			} catch (e) {
				toast.error('Could not copy — your browser may be blocking clipboard access');
			}
		},

		formatExpiry(ts) {
			if (!ts) return 'no expiry';
			const target = new Date(ts);
			const diff = target - new Date();
			if (diff <= 0) return 'expired — rotating on next check';
			const days = Math.floor(diff / 86400000);
			const hours = Math.floor((diff % 86400000) / 3600000);
			const minutes = Math.floor((diff % 3600000) / 60000);
			if (days > 0) return `Expires in ${days}d ${hours}h`;
			if (hours > 0) return `Expires in ${hours}h ${minutes}m`;
			return `Expires in ${minutes}m`;
		},

		async rotateCodeServerPassword(bench) {
			if (
				!confirm(
					'Rotate the Code Server password now?\nAny active browser session will be disconnected.',
				)
			)
				return;
			this.rotateLoading = { ...this.rotateLoading, [bench.name]: true };
			try {
				await call(
					'press.press.doctype.bench.bench_dev_overview.rotate_code_server_password',
					{ bench_name: bench.name },
				);
				toast.success('Password rotated');
				await this.loadCodeServerStatuses(this.benches.data || []);
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to rotate password');
			} finally {
				this.rotateLoading = { ...this.rotateLoading, [bench.name]: false };
			}
		},

		async saveDuration(bench) {
			const cur = this.codeServerStatus[bench.name]?.password_expiry_days;
			const newVal = Number(this.durationEdits[bench.name]);
			if (Number.isNaN(newVal) || newVal < 0 || newVal === cur) return;
			try {
				await call(
					'press.press.doctype.bench.bench_dev_overview.set_code_server_password_expiry_days',
					{ bench_name: bench.name, days: newVal },
				);
				toast.success(`Auto-rotate set to ${newVal} day${newVal === 1 ? '' : 's'}`);
				await this.loadCodeServerStatuses(this.benches.data || []);
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to update duration');
			}
		},

		async restartCodeServer(bench) {
			this.restartLoading = { ...this.restartLoading, [bench.name]: true };
			try {
				await call(
					'press.press.doctype.bench.bench_dev_overview.restart_code_server',
					{ bench_name: bench.name },
				);
				toast.success('Code Server restart queued — should be back in 10–30 s');
				setTimeout(() => this.loadCodeServerStatuses(this.benches.data || []), 8000);
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to restart Code Server');
			} finally {
				this.restartLoading = { ...this.restartLoading, [bench.name]: false };
			}
		},

		openVscodeDialog(bench) {
			renderDialog(
				h(VSCodeLaunchDialog, {
					bench: bench.name,
					releaseGroup: this.releaseGroup,
				}),
			);
		},

		openSshDialog(bench) {
			renderDialog(
				h(SSHCertificateDialog, {
					bench: bench.name,
					releaseGroup: this.releaseGroup,
				}),
			);
		},

		confirmRestartBench(bench) {
			confirmDialog({
				title: 'Restart Bench',
				message: `Are you sure you want to restart the bench <b>${bench.name}</b>?`,
				primaryAction: {
					label: 'Restart',
					variant: 'solid',
					theme: 'red',
					onClick: ({ hide }) => {
						toast.promise(
							call('press.api.client.run_doc_method', {
								dt: 'Bench',
								dn: bench.name,
								method: 'restart',
							}),
							{
								loading: 'Restarting bench...',
								success: () => {
									hide();
									return 'Bench will restart shortly';
								},
								error: (e) =>
									e?.messages?.join('\n') || 'Failed to restart bench',
							},
						);
					},
				},
			});
		},

		codeServerStatusClass(bench) {
			const s = this.codeServerStatus[bench.name];
			if (s?.status === 'Running') return 'bg-green-50 text-green-700';
			if (s?.exists) return 'bg-yellow-50 text-yellow-700';
			return 'bg-gray-100 text-gray-600';
		},
		codeServerDotClass(bench) {
			const s = this.codeServerStatus[bench.name];
			if (s?.status === 'Running') return 'bg-green-500';
			if (s?.exists) return 'bg-yellow-500';
			return 'bg-gray-400';
		},
		codeServerStatusLabel(bench) {
			const s = this.codeServerStatus[bench.name];
			if (s?.status === 'Running') return 'Code Server running';
			if (s?.status === 'Pending') return 'Code Server starting';
			if (s?.exists) return `Code Server ${String(s.status || '').toLowerCase()}`;
			return 'Code Server stopped';
		},
	},
};
</script>
```

- [ ] **Step 2: Build and verify in browser**

```bash
ssh press-ctrl 'sudo -u frappe bash -c "cd /home/frappe/frappe-bench && bench build --app press && bench clear-cache"'
ssh press-ctrl 'supervisorctl restart frappe-bench-web:frappe-bench-frappe-web'
```

Then open `https://demo.mvpstorm.com/dashboard/groups/<some-group>/actions` in your browser. Expected:
- One per-bench section with name + helper + status pill on the right.
- Code Server panel with URL row, Password row (masked dots), expiry/rotate/restart links, auto-rotate input.
- 4 tiles below the panel.
- Bottom standalone "Bench Actions" card is **gone**.

- [ ] **Step 3: Manual test the password show/hide**

In the browser:
1. Click the eye icon next to the masked password.
2. Confirm the actual password text appears and is selectable.
3. Click the eye icon again.
4. Confirm the dots return and selecting them does nothing.
5. Click the copy icon.
6. Confirm the toast says "Code Server password copied" and pasting elsewhere yields the real password (NOT the dots).

- [ ] **Step 4: Manual test the 4 tiles**

1. Click "Mark as Dev Bench" — toast says "marked as development bench", label changes to "Unset Dev Bench".
2. Click "Generate SSH Certificate" — SSH dialog opens (existing component).
3. Click "Restart Bench" — confirm dialog appears, no errors.
4. Click "Open in VS Code" — VSCodeLaunchDialog opens (Task 5 verifies the rest).

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/components/group/ReleaseGroupActions.vue
git commit -m "refactor(dashboard): wire ReleaseGroupActions methods to new layout"
```

---

### Task 5: End-to-end test of "Open in VS Code"

**Files:** none (manual verification)

- [ ] **Step 1: Launch flow with no SSH key**

Sign in as a user without an SSH public key configured. Click "Open in VS Code" tile. Expected: dialog says "Add an SSH public key in Developer Settings" with a router link.

- [ ] **Step 2: Launch flow with valid SSH key**

Sign in as `eslam@accuratesystems.io` (or any user with `~/.ssh/id_ed25519.pub` registered). Click "Open in VS Code". Expected:
- Dialog opens, shows "You will need an SSH certificate..." text.
- A `Generate SSH Certificate` button at the bottom.
- Clicking generates a cert, then dialog updates to show 3 steps (or 2 on macOS) ending in a `Launch VS Code` button.

- [ ] **Step 3: Click `Launch VS Code` and confirm browser handoff**

Click the button. Expected: browser prompts "Open Visual Studio Code?" → click Open → VS Code Desktop launches → Remote-SSH connection to the bench succeeds → bench's `/home/frappe/frappe-bench` opens in the editor.

- [ ] **Step 4: Confirm copy button on the URL still works**

Below the launch button there's a `vscode://...` URL. Click its copy icon, then paste in the address bar. Expected: same VS Code launch as the button.

If any of these fail, file the failure (which step, what happened, error messages), fix it, then re-run all 4 steps.

---

### Task 6: Add wiki page

**Files:**
- Create: `press/docs/wiki/03-bench-management/dev-actions.md`

- [ ] **Step 1: Create the wiki page**

```bash
mkdir -p press/docs/wiki/03-bench-management
```

Create `press/docs/wiki/03-bench-management/dev-actions.md`:

```markdown
# Dev Actions Panel

The Dev Actions panel appears at `/dashboard/groups/<release-group>/actions` and gives developers per-bench tools for editing code on a Press-managed bench.

## What's in each bench section

For every bench in the release group, you see:

1. **Bench identity** — bench name (mono), helper text, and a status pill on the right showing whether Code Server is running.
2. **Code Server panel** — full bench code-server URL, current password (masked by default), expiry countdown, rotate / restart links, and an auto-rotate days input.
3. **Action tiles** — four per-bench actions:
   - **Open in VS Code** — launches your local VS Code Desktop over Remote-SSH.
   - **Mark as Dev Bench** — tags the bench as `is_development_bench`, used by other dashboards as a filter.
   - **Generate SSH Certificate** — opens the SSH cert dialog (PowerShell / bash one-liner).
   - **Restart Bench** — restarts all bench workers (web, scheduler, queues).

## Working with the Code Server password

The masked password row has two icon buttons:

- **Eye icon (👁 / 🚫👁)** — toggles between masked dots and the real password text. When revealed, the text is selectable; when masked, selecting the dots does nothing.
- **Copy icon (📋)** — copies the actual password to your clipboard regardless of mask state, with a "Code Server password copied" confirmation toast.

The Code Server password rotates automatically based on the **Auto-rotate every N days** setting (default 3 days). You can rotate manually with **Rotate now**.

## "Open in VS Code" — first-time setup

Clicking the tile opens a dialog that walks through three steps:

1. (Windows only) Set PowerShell encoding to UTF-8.
2. Install the SSH certificate locally (`echo '...' > ~/.ssh/id_ed25519-cert.pub`).
3. Click **Launch VS Code** — your browser asks to open VS Code Desktop, which then connects to the bench over Remote-SSH and opens `/home/frappe/frappe-bench`.

Certificates are valid for 6 hours. Reopen the dialog when one expires.

## Backend method

The dialog calls `press.press.doctype.bench.bench_dev_overview.get_vscode_remote_url` which returns:

```
vscode://vscode-remote/ssh-remote+<bench>@<proxy_server>:2222/home/frappe/frappe-bench
```

The `proxy_server` is read from the `Bench` document or its `Release Group` if the bench-level field is empty.

## Related files

- Component: `dashboard/src/components/group/ReleaseGroupActions.vue`
- VS Code dialog: `dashboard/src/components/group/VSCodeLaunchDialog.vue`
- SSH cert dialog: `dashboard/src/components/group/SSHCertificateDialog.vue`
- Backend APIs: `press/press/doctype/bench/bench_dev_overview.py`
```

- [ ] **Step 2: Commit**

```bash
git add press/docs/wiki/03-bench-management/dev-actions.md
git commit -m "docs(wiki): document Dev Actions panel and Open in VS Code flow"
```

---

### Task 7: Quality gates and final commit

**Files:** none (process)

- [ ] **Step 1: Run `/clean-code` on changed files**

In Claude Code, invoke:

```
/clean-code dashboard/src/components/group/ReleaseGroupActions.vue dashboard/src/components/group/VSCodeLaunchDialog.vue press/press/doctype/bench/bench_dev_overview.py
```

Address any MUST-FIX findings. Note SHOULD-FIX / NICE-TO-HAVE in the next commit message.

- [ ] **Step 2: Run `/code-review` on changed files**

```
/code-review dashboard/src/components/group/ReleaseGroupActions.vue dashboard/src/components/group/VSCodeLaunchDialog.vue press/press/doctype/bench/bench_dev_overview.py
```

Address Critical / High issues. Lower-severity issues go in the commit message.

- [ ] **Step 3: Bump press version (only if hooks/Python behaviour changed)**

```bash
grep -rn "__version__\|version =" press/__init__.py press/hooks.py | head -4
```

If the patch version needs to bump (a new whitelisted method was added — yes), bump it in BOTH `press/__init__.py` and `press/hooks.py` to match.

- [ ] **Step 4: Final commit and push**

```bash
git status
git add -A
git commit -m "chore: clean-code + code-review fixes for dev-actions-redesign"
```

Push via the press-ctrl bundle method per `~/.claude/CLAUDE.md` (Claude Code terminal cannot push directly):

```bash
git bundle create /tmp/dev-actions.bundle cloudflare-dns..feat/dev-actions-redesign
scp -i "E:/.ssh/new_id_ed25519" /tmp/dev-actions.bundle root@89.167.116.92:/tmp/dev-actions.bundle
ssh -i "E:/.ssh/new_id_ed25519" root@89.167.116.92 "cd /home/frappe/frappe-bench/apps/press && \
  git fetch /tmp/dev-actions.bundle 'feat/dev-actions-redesign:refs/remotes/local/dev-actions' && \
  git checkout cloudflare-dns && \
  git merge --no-ff refs/remotes/local/dev-actions -m 'Merge dev-actions-redesign' && \
  git push upstream cloudflare-dns"
```

- [ ] **Step 5: Deploy to demo.mvpstorm.com**

```bash
ssh press-ctrl 'sudo -u frappe bash -c "cd /home/frappe/frappe-bench && \
  git -C apps/press pull upstream cloudflare-dns && \
  bench build --app press --force && \
  bench clear-cache"'
ssh press-ctrl 'supervisorctl restart frappe-bench-web:frappe-bench-frappe-web'
```

Open `https://demo.mvpstorm.com/dashboard/groups/<group>/actions` in an incognito window. Run through the manual tests from Task 5 once more.

- [ ] **Step 6: Update DEVLOG**

Add a Session Archive entry to `DEVLOG.md` in `press_local`:

```markdown
### Session N — 2026-04-26: Dev Actions redesign
**What we did:** Restructured Release Group Actions panel into per-bench sections with a Code Server KV panel and 4 action tiles (Open in VS Code, Mark Dev Bench, Generate SSH Cert, Restart Bench). Fixed password copy bug (eye + copy icon buttons replace clickable label). Added Open in VS Code flow that mints SSH cert and fires `vscode://` URI.
**Files:** `ReleaseGroupActions.vue`, `VSCodeLaunchDialog.vue` (new), `bench_dev_overview.py`, `dev-actions.md` (wiki)
**Decisions:** Used a sibling dialog (not extension of `SSHCertificateDialog`) for the VS Code flow to keep concerns isolated. `Restart Bench` reuses the same `restart` doc method as the standalone bench page. `proxy_server` resolved from bench-level field with release-group fallback.
```

---

## Self-Review

**Spec coverage:** Each prototype-mandated change has at least one task:
- Per-bench section + Code Server KV panel → Task 3 (template) + Task 4 (script).
- Eye / copy buttons replacing clickable label → Task 4 (`togglePasswordReveal`, `copyCodeServerPassword`, `copyToClipboard`).
- 4-tile action grid (VS Code, Dev Bench, SSH Cert, Restart Bench) → Task 3 (template) + Task 4 (handlers).
- "Open in VS Code" dialog → Task 2 (`VSCodeLaunchDialog.vue`) + Task 1 (backend URL).
- Deduplicated bottom card → Task 3 (the `<div v-for="group in actions">` block is removed; nothing renders the duplicate "Open Code Server" any more).
- Production palette → Task 3 uses Tailwind utility classes (`bg-gray-50`, `text-gray-700`, `bg-blue-50`, `text-blue-600`) which compile to the production frappe-ui slate palette automatically.

**Placeholder scan:** No "TBD", "TODO", "implement later" remain. Every code step contains the actual code. Every command has expected output.

**Type consistency:**
- `bench.name` is used consistently as the lookup key (matches `Bench` doctype primary key).
- `releaseGroup` prop in `VSCodeLaunchDialog` matches the prop name in `SSHCertificateDialog` (both pass it down to `getCachedDocumentResource`).
- `get_vscode_remote_url` parameter name `bench_name` matches the call signature in `VSCodeLaunchDialog.loadVscodeUrl`.
- `formatExpiry` returns `"Expires in N…"` — capital "E" matches the prototype text.
- Reactive maps (`devLoading`, `revealedPasswords`, etc.) are mutated via spread (`{ ...this.X, [k]: v }`) consistently for Vue 3 reactivity.

**Risks not yet addressed:**
- If a Release Group has dozens of benches, rendering N Code Server KV panels could be heavy. Acceptable for MVP — typical groups have 1-5 benches.
- `vscode://` URI handlers require VS Code Desktop installed locally. Documented in Task 5 manual test and the wiki page.
