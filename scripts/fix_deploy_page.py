"""Fix DeployCandidate.vue — remove broken frappe-ui document resource, use manual fetch."""

path = "/home/frappe/frappe-bench/apps/press/dashboard/src/pages/DeployCandidate.vue"
with open(path) as f:
    content = f.read()

# 1. Remove deploy() from resources block — this is the broken frappe-ui document resource
content = content.replace(
    """	resources: {
		deploy() {
			return {
				type: 'document',
				doctype: 'Deploy Candidate Build',
				name: this.id,
				transform: this.transformDeploy,
			};
		},
		estimate()""",
    """	resources: {
		estimate()"""
)

# 2. Fix estimate — it referenced $resources.deploy?.doc?.group, now use this.deploy?.group
content = content.replace(
    "params: { group: this.$resources.deploy?.doc?.group },",
    "params: { group: this.deploy?.group },"
)

# 3. Add deployData to data()
content = content.replace(
    """	data() {
		return {
			elapsedSeconds: 0,""",
    """	data() {
		return {
			deployDoc: null,
			deployLoading: true,
			elapsedSeconds: 0,"""
)

# 4. Fix deploy computed — use deployDoc instead of $resources.deploy.doc
content = content.replace(
    """		deploy() {
			return this.$resources.deploy?.doc;
		},
		isLoading() {
			return this.$resources.deploy?.get?.loading && !this.$resources.deploy?.get?.fetched;
		},""",
    """		deploy() {
			return this.deployDoc;
		},
		isLoading() {
			return this.deployLoading;
		},"""
)

# 5. Fix mounted — replace socket handlers that use $resources.deploy
content = content.replace(
    """	mounted() {
		this.previousBuildId = this.$route?.query?.previous || null;
		this.$socket.emit('doc_subscribe', 'Deploy Candidate Build', this.id);
		this.$socket.on(`bench_deploy:${this.id}:steps`, (data) => {
			if (data.name === this.id && this.$resources.deploy.doc) {
				this.$resources.deploy.doc.build_steps = this.transformDeploy({
					build_steps: data.steps,
				})?.build_steps;
			}
		});
		this.$socket.on(`bench_deploy:${this.id}:finished`, () => {
			const rgDoc = getCachedDocumentResource(
				'Release Group',
				this.$resources.deploy.doc?.group,
			);
			if (rgDoc) rgDoc.reload();
			this.$resources.deploy.reload();
			this.$resources.errors.reload();
			this.$resources.warnings.reload();
		});
	},""",
    """	mounted() {
		this.previousBuildId = this.$route?.query?.previous || null;
		this.fetchDeploy();
		this.$socket.emit('doc_subscribe', 'Deploy Candidate Build', this.id);
		this.$socket.on(`bench_deploy:${this.id}:steps`, (data) => {
			if (data.name === this.id && this.deployDoc) {
				const transformed = this.transformDeploy({ build_steps: data.steps });
				if (transformed?.build_steps) this.deployDoc.build_steps = transformed.build_steps;
			}
		});
		this.$socket.on(`bench_deploy:${this.id}:finished`, () => {
			const rgDoc = getCachedDocumentResource('Release Group', this.deploy?.group);
			if (rgDoc) rgDoc.reload();
			this.fetchDeploy();
			this.$resources.errors?.reload();
			this.$resources.warnings?.reload();
		});
	},"""
)

# 6. Fix watch — deploy.group watcher uses $resources.estimate
content = content.replace(
    """		'deploy.group'(group) {
			if (group && this.isBuilding) {
				this.$resources.estimate.submit({ group });
			}
		},""",
    """		'deploy.group'(group) {
			if (group && this.isBuilding) {
				this.$resources.estimate?.submit({ group });
			}
		},"""
)

# 7. Fix watch handler for deploy.status — references $resources.estimate
content = content.replace(
    "this.$resources.estimate.submit({ group: this.deploy?.group });",
    "this.$resources.estimate?.submit({ group: this.deploy?.group });"
)

# 8. Add fetchDeploy method at the top of methods block
content = content.replace(
    "	methods: {",
    """	methods: {
		async fetchDeploy() {
			this.deployLoading = true;
			try {
				const team = localStorage.getItem('current_team') || window.default_team || '';
				const res = await fetch('/api/method/press.api.client.get', {
					method: 'POST',
					headers: {
						'Content-Type': 'application/json',
						'X-Frappe-CSRF-Token': window.csrf_token || '',
						'X-Press-Team': team,
					},
					body: JSON.stringify({ doctype: 'Deploy Candidate Build', name: this.id }),
				});
				const data = await res.json();
				if (data.message) {
					this.deployDoc = this.transformDeploy ? this.transformDeploy(data.message) : data.message;
				}
			} catch (e) {
				console.error('Deploy fetch failed:', e);
			} finally {
				this.deployLoading = false;
			}
		},"""
)

# 9. Fix reload button in template — was $resources.deploy.reload()
content = content.replace(
    '@click="$resources.deploy.reload()"',
    '@click="fetchDeploy()"'
)
content = content.replace(
    ':loading="$resources.deploy.get.loading"',
    ':loading="deployLoading"'
)

# 10. Fix autoRefresh — was $resources.deploy.reload()
content = content.replace(
    "this.autoRefreshTimer = setInterval(() => { this.$resources.deploy.reload(); }, 5000);",
    "this.autoRefreshTimer = setInterval(() => { this.fetchDeploy(); }, 5000);"
)

with open(path, "w") as f:
    f.write(content)

# Verify no more $resources.deploy references remain (except in comments)
import re
remaining = re.findall(r'\$resources\.deploy', content)
print(f"Fix applied. Remaining $resources.deploy references: {len(remaining)}")
for r in remaining:
    pass  # All should be gone
