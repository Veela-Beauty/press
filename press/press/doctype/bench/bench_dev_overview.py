"""
Dev Overview API — data for the Watch Tower-style DevOverview dashboard page.
Kept in a separate file because bench.py is already >700 lines.
"""
import frappe
from frappe import _


@frappe.whitelist()
def get_dev_overview_benches():
	"""Return all non-archived benches enriched with commit, build, sites, and gap data."""
	frappe.only_for("System Manager")

	benches = frappe.get_all(
		"Bench",
		fields=[
			"name",
			"status",
			"group",
			"group.title as group_title",
			"server",
			"server.title as server_title",
			"cluster.title as cluster_title",
			"is_development_bench",
			"creation",
			"candidate",
		],
		filters={"status": ["not in", ["Archived"]]},
		order_by="is_development_bench desc, name asc",
		limit=200,
	)

	if not benches:
		return []

	bench_names = [b.name for b in benches]

	# ── sites per bench ──────────────────────────────────────────────────────
	all_sites = frappe.get_all(
		"Site",
		filters={"bench": ["in", bench_names]},
		fields=["name", "bench", "status"],
	)
	sites_by_bench = {}
	for s in all_sites:
		sites_by_bench.setdefault(s.bench, []).append(s)

	# ── apps (hashes) per bench ───────────────────────────────────────────────
	bench_apps = frappe.get_all(
		"Bench App",
		filters={"parent": ["in", bench_names]},
		fields=["parent", "app", "hash"],
	)
	apps_by_bench = {}
	for a in bench_apps:
		apps_by_bench.setdefault(a.parent, []).append(a)

	# ── app releases for all hashes (batch) ──────────────────────────────────
	all_hashes = list({a.hash for a in bench_apps if a.hash})[:100]
	releases_map = {}
	if all_hashes:
		for rel in frappe.get_all(
			"App Release",
			filters={"hash": ["in", all_hashes]},
			fields=["hash", "message", "author", "timestamp"],
		):
			releases_map[rel.hash] = rel

	# ── assemble ─────────────────────────────────────────────────────────────
	result = []
	for bench in benches:
		b = dict(bench)

		bench_sites = sites_by_bench.get(bench.name, [])
		b["site_count"] = len(bench_sites)
		b["pending_update_count"] = sum(
			1 for s in bench_sites if s.status == "Pending"
		)

		# last commit: first app with a known release message
		b["last_commit"] = None
		for app_entry in apps_by_bench.get(bench.name, []):
			rel = releases_map.get(app_entry.hash)
			if rel and rel.message:
				b["last_commit"] = {
					"app": app_entry.app,
					"hash": (app_entry.hash or "")[:7],
					"message": (rel.message or "").split("\n")[0][:80],
					"author": rel.author or "",
					"timestamp": str(rel.timestamp) if rel.timestamp else "",
				}
				break

		result.append(b)

	return result


@frappe.whitelist()
def get_dev_panel_data(bench_name):
	"""
	Return data for the expanded DevOverview panel for a specific bench.
	Called directly (not as a doc method) to avoid touching bench.py.
	"""
	frappe.only_for("System Manager")
	bench_doc = frappe.get_doc("Bench", bench_name)
	# ── sites ─────────────────────────────────────────────────────────────────
	sites = frappe.get_all(
		"Site",
		filters={"bench": bench_doc.name},
		fields=["name", "status", "host_name", "is_development_site"],
	)

	site_names = [s.name for s in sites]

	# migration status per site (batch)
	activities = {}
	if site_names:
		for act in frappe.get_all(
			"Site Activity",
			filters={"site": ["in", site_names], "action": ["in", ["Migrate", "Update"]]},
			fields=["site", "action", "creation"],
			order_by="creation desc",
		):
			# only keep the most recent per site
			if act.site not in activities:
				activities[act.site] = act

	# scheduler status per site via site config key
	scheduler_map = {}
	if site_names:
		for cfg in frappe.get_all(
			"Site Config",
			filters={"parent": ["in", site_names], "key": "pause_scheduler"},
			fields=["parent", "value"],
		):
			scheduler_map[cfg.parent] = bool(cfg.value)

	for s in sites:
		s["migrated"] = bool(activities.get(s.name))
		s["scheduler_enabled"] = not scheduler_map.get(s.name, False)

	# ── recent commits from bench apps ────────────────────────────────────────
	recent_commits = []
	for app_entry in bench_doc.apps:
		if not app_entry.hash:
			continue
		rels = frappe.get_all(
			"App Release",
			filters={"hash": app_entry.hash},
			fields=["hash", "message", "author", "timestamp"],
			limit=1,
		)
		if rels and rels[0].message:
			r = rels[0]
			recent_commits.append(
				{
					"app": app_entry.app,
					"hash": (app_entry.hash or "")[:7],
					"message": (r.message or "").split("\n")[0][:80],
					"author": r.author or "",
					"timestamp": str(r.timestamp) if r.timestamp else "",
				}
			)

	# ── build history (last 5 deploy candidates for this group) ───────────────
	build_history = frappe.get_all(
		"Deploy Candidate",
		filters={"group": bench_doc.group},
		fields=["name", "status", "creation"],
		order_by="creation desc",
		limit=5,
	)

	# ── recent errors (failed agent jobs for bench sites) ─────────────────────
	error_list = []
	if site_names:
		error_list = frappe.get_all(
			"Agent Job",
			filters={"site": ["in", site_names], "status": "Failure"},
			fields=["name", "job_type", "creation", "site"],
			order_by="creation desc",
			limit=10,
		)

	return {
		"sites": sites,
		"recent_commits": recent_commits,
		"build_history": [dict(b) for b in build_history],
		"errors": {
			"count": len(error_list),
			"errors": [dict(e) for e in error_list],
		},
	}
