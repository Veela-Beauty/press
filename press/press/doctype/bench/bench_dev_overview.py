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

	# ── undeployed gap: one batch SQL instead of N COUNT queries (2A perf fix) ──
	# Build (app, deployed_timestamp) pairs, then one query with GROUP BY.
	app_ts_pairs = []
	app_to_benches: dict[str, list[str]] = {}
	for app_entry in bench_apps:
		deployed_rel = releases_map.get(app_entry.hash) if app_entry.hash else None
		ts = deployed_rel.timestamp if deployed_rel else None
		if not ts:
			continue
		app_ts_pairs.append((app_entry.app, ts))
		app_to_benches.setdefault(app_entry.app, []).append(app_entry.parent)

	undeployed_by_bench: dict = {}
	if app_ts_pairs:
		or_clauses = " OR ".join(["(app = %s AND timestamp > %s)"] * len(app_ts_pairs))
		params = [v for pair in app_ts_pairs for v in pair]
		rows = frappe.db.sql(
			f"SELECT app, COUNT(*) as cnt FROM `tabApp Release` WHERE {or_clauses} GROUP BY app",
			params,
			as_dict=True,
		)
		for row in rows:
			for bench_name in app_to_benches.get(row.app, []):
				undeployed_by_bench[bench_name] = (
					undeployed_by_bench.get(bench_name, 0) + row.cnt
				)

	# ── assemble ─────────────────────────────────────────────────────────────
	result = []
	for bench in benches:
		b = dict(bench)

		bench_sites = sites_by_bench.get(bench.name, [])
		b["site_count"] = len(bench_sites)
		b["pending_update_count"] = sum(
			1 for s in bench_sites if s.status == "Pending"
		)
		b["undeployed_count"] = undeployed_by_bench.get(bench.name, 0)

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
			# bool("0") == True, so use explicit truthy check
		scheduler_map[cfg.parent] = cfg.value in (True, 1, "1", "true", True)

	for s in sites:
		s["migrated"] = bool(activities.get(s.name))
		s["scheduler_enabled"] = not scheduler_map.get(s.name, False)

	# ── recent commits from bench apps — batched (1A perf fix) ───────────────
	app_hashes = {ae.hash: ae for ae in bench_doc.apps if ae.hash}
	panel_releases_map = {}
	if app_hashes:
		for rel in frappe.get_all(
			"App Release",
			filters={"hash": ["in", list(app_hashes.keys())]},
			fields=["hash", "message", "author", "timestamp"],
		):
			panel_releases_map[rel.hash] = rel

	recent_commits = []
	for app_entry in bench_doc.apps:
		rel = panel_releases_map.get(app_entry.hash)
		if rel and rel.message:
			recent_commits.append(
				{
					"app": app_entry.app,
					"hash": (app_entry.hash or "")[:7],
					"message": (rel.message or "").split("\n")[0][:80],
					"author": rel.author or "",
					"timestamp": str(rel.timestamp) if rel.timestamp else "",
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
