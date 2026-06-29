"""
Press Server Health Report.

Sends a rich HTML email with full server + Press platform status.
Can be called as a Watch Tower Python Method rule or directly.
"""
import os
import subprocess

import frappe
from frappe.utils import now_datetime, time_diff_in_seconds, get_datetime


def send_health_report(doc=None, rule=None):
	"""Collect server health and send report email. Always returns True."""
	report = _collect_health()
	_send_email(report)
	return True


# Friendly names for supervisor processes
PROCESS_LABELS = {
	"redis-cache": "Redis Cache",
	"redis-queue": "Redis Queue",
	"frappe-web": "Web Server",
	"node-socketio": "Socket.io",
	"frappe-build-worker-0": "Build Worker",
	"frappe-long-worker-0": "Long Worker",
	"frappe-schedule": "Scheduler",
	"frappe-short-worker-0": "Short Worker",
}


def _collect_health():
	"""Gather server resources, services, and full Press platform status."""
	# --- Server resources ---
	cpu_load = os.getloadavg()
	cpu_count = os.cpu_count()

	mem = {}
	with open("/proc/meminfo") as f:
		for line in f:
			parts = line.split()
			if parts[0] in ("MemTotal:", "MemAvailable:"):
				mem[parts[0].rstrip(":")] = int(parts[1])
	total_gb = mem.get("MemTotal", 0) / 1024 / 1024
	avail_gb = mem.get("MemAvailable", 0) / 1024 / 1024
	used_gb = total_gb - avail_gb
	used_pct = (used_gb / total_gb * 100) if total_gb > 0 else 0

	disk = os.statvfs("/")
	disk_total = disk.f_blocks * disk.f_frsize / 1024 / 1024 / 1024
	disk_free = disk.f_bavail * disk.f_frsize / 1024 / 1024 / 1024
	disk_used_pct = ((disk_total - disk_free) / disk_total * 100) if disk_total > 0 else 0

	# Uptime
	with open("/proc/uptime") as f:
		uptime_secs = float(f.read().split()[0])
	uptime_days = int(uptime_secs // 86400)
	uptime_hours = int((uptime_secs % 86400) // 3600)

	# --- Supervisor services ---
	# supervisorctl needs root or sudo -  try sudo first, fall back to direct
	sup = subprocess.run(
		["sudo", "-n", "supervisorctl", "status"],
		capture_output=True, text=True, timeout=10,
	)
	if sup.returncode != 0 or "error:" in sup.stdout.lower():
		sup = subprocess.run(
			["supervisorctl", "status"],
			capture_output=True, text=True, timeout=10,
		)
	processes = []
	all_running = True
	for line in sup.stdout.strip().split("\n"):
		if not line.strip() or "error:" in line.lower():
			continue
		parts = line.split()
		if len(parts) < 2:
			continue
		# Full name like "frappe-bench-web:frappe-bench-frappe-web"
		raw_name = parts[0]
		# Extract the short name after ":" and strip common prefix
		short = raw_name.split(":")[-1] if ":" in raw_name else raw_name
		# Remove "frappe-bench-" prefix if present
		short = short.replace("frappe-bench-", "")
		label = PROCESS_LABELS.get(short, short)
		status = parts[1]
		# Extract uptime from "uptime HH:MM:SS" or "uptime D:HH:MM:SS"
		uptime_str = ""
		if "uptime" in line:
			uptime_str = line.split("uptime")[-1].strip()
		processes.append({"name": label, "status": status, "uptime": uptime_str})
		if status != "RUNNING":
			all_running = False

	# --- Press scheduler ---
	press_jobs = frappe.db.count("Scheduled Job Type", {"method": ["like", "%press%"]})
	poll_jobs = frappe.db.count("Scheduled Job Type", {"method": ["like", "%poll_pending_jobs%"]})

	# --- Sites with usage data ---
	sites = frappe.db.sql("""
		SELECT s.name, s.status, s.host_name, s.bench, s.creation,
			s.current_database_usage, s.current_disk_usage, s.database_name,
			s.server
		FROM tabSite s
		WHERE s.status IN ('Active', 'Inactive', 'Suspended', 'Broken')
		ORDER BY s.status, s.name
	""", as_dict=True)

	# Get site backups info for disk size estimation
	# Sites run on REMOTE servers -  we can't query their DBs from press-ctrl.
	# Use Press's tracked usage, or query agent for latest if available.
	site_usage = {}
	try:
		# Get latest usage from Site Activity if available
		usage_rows = frappe.db.sql("""
			SELECT site, database_usage, disk_usage
			FROM `tabSite Activity`
			WHERE creation > NOW() - INTERVAL 7 DAY
			AND activity = 'Update Usage'
			ORDER BY creation DESC
		""", as_dict=True)
		for row in usage_rows:
			if row.site not in site_usage:
				site_usage[row.site] = {
					"db": row.database_usage or 0,
					"disk": row.disk_usage or 0,
				}
	except Exception:
		pass

	# Get press-ctrl's own DB size
	press_db_mb = 0
	try:
		result = frappe.db.sql("""
			SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 1) AS size_mb
			FROM information_schema.tables
			WHERE table_schema = DATABASE()
		""", as_dict=True)
		press_db_mb = result[0].size_mb if result else 0
	except Exception:
		pass

	# Enrich sites with usage data
	for s in sites:
		usage = site_usage.get(s.name, {})
		s["db_mb"] = usage.get("db", s.current_database_usage or 0)
		s["disk_mb"] = usage.get("disk", s.current_disk_usage or 0)

	site_counts = {}
	for s in sites:
		site_counts[s.status] = site_counts.get(s.status, 0) + 1

	# --- Benches ---
	benches = frappe.db.sql("""
		SELECT b.name, b.status, b.`group` AS release_group,
			(SELECT COUNT(*) FROM tabSite WHERE bench=b.name AND status='Active') as active_sites
		FROM tabBench b
		WHERE b.status IN ('Active', 'Updating', 'Installing', 'Broken')
		ORDER BY b.status DESC, b.name
	""", as_dict=True)

	# --- Servers ---
	servers = frappe.db.sql("""
		SELECT name, status, is_server_setup, ip
		FROM tabServer
		WHERE status != 'Archived'
		ORDER BY name
	""", as_dict=True)

	# --- Recent deploys (last 48h) ---
	recent_builds = frappe.db.sql("""
		SELECT name, status, build_start, build_end, build_error
		FROM `tabDeploy Candidate Build`
		WHERE creation > NOW() - INTERVAL 48 HOUR
		ORDER BY creation DESC
		LIMIT 10
	""", as_dict=True)

	# --- Recent agent jobs (last 24h) ---
	agent_jobs_summary = frappe.db.sql("""
		SELECT status, COUNT(*) as cnt
		FROM `tabAgent Job`
		WHERE creation > NOW() - INTERVAL 24 HOUR
		GROUP BY status
		ORDER BY cnt DESC
	""", as_dict=True)

	failed_agent_jobs = frappe.db.sql("""
		SELECT name, job_type, server, status, creation
		FROM `tabAgent Job`
		WHERE creation > NOW() - INTERVAL 24 HOUR
			AND status IN ('Failure', 'Undelivered')
		ORDER BY creation DESC
		LIMIT 5
	""", as_dict=True)

	# --- Error log (24h) ---
	error_count = frappe.db.count("Error Log", {"creation": [">", "now() - interval 24 hour"]})
	top_errors = frappe.db.sql("""
		SELECT method, COUNT(*) as cnt
		FROM `tabError Log`
		WHERE creation > NOW() - INTERVAL 24 HOUR
		GROUP BY method
		ORDER BY cnt DESC
		LIMIT 5
	""", as_dict=True)

	# Recent errors (last 5 with traceback snippet)
	recent_errors = frappe.db.sql("""
		SELECT name, method, error, creation
		FROM `tabError Log`
		WHERE creation > NOW() - INTERVAL 24 HOUR
		ORDER BY creation DESC
		LIMIT 5
	""", as_dict=True)

	# --- Watch Tower alert summary ---
	wt_alerts = frappe.db.sql("""
		SELECT rule_name, status, COUNT(*) as cnt
		FROM `tabWatch Tower Alert Log`
		WHERE alert_datetime > NOW() - INTERVAL 24 HOUR
		GROUP BY rule_name, status
		ORDER BY cnt DESC
	""", as_dict=True)

	return {
		"cpu_load": cpu_load, "cpu_count": cpu_count,
		"ram_total": total_gb, "ram_used": used_gb, "ram_pct": used_pct,
		"disk_total": disk_total, "disk_free": disk_free, "disk_pct": disk_used_pct,
		"uptime_days": uptime_days, "uptime_hours": uptime_hours,
		"processes": processes, "all_running": all_running,
		"press_jobs": press_jobs, "poll_jobs": poll_jobs,
		"sites": sites, "site_counts": site_counts, "press_db_mb": press_db_mb,
		"benches": benches, "servers": servers,
		"recent_builds": recent_builds,
		"agent_jobs_summary": agent_jobs_summary,
		"failed_agent_jobs": failed_agent_jobs,
		"error_count": error_count, "top_errors": top_errors,
		"recent_errors": recent_errors,
		"wt_alerts": wt_alerts,
	}


TABLE = 'border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;"'
TH_BG = 'style="background:#f8fafc"'


def _send_email(r):
	"""Build and send the HTML health report email."""
	ok = "\u2705"
	fail = "\u274c"
	warn = "\u26a0\ufe0f"
	# Only flag DOWN if we actually detected a down service, not if we couldn't query
	has_services = len(r["processes"]) > 0
	status_icon = ok if (r["all_running"] or not has_services) else fail
	overall = "All Green" if (r["all_running"] or not has_services) else "Issues Detected"
	ts = now_datetime().strftime("%Y-%m-%d %H:%M")
	ts_short = now_datetime().strftime("%b %d")

	from .email_branding import wrap_email, send_alert_email

	# --- Build body sections ---
	html = ""

	# --- Server Resources ---
	ram_color = _color(r["ram_pct"], 80, 90)
	disk_color = _color(r["disk_pct"], 80, 90)
	cpu_color = _color(r["cpu_load"][0] / r["cpu_count"] * 100, 70, 90)

	html += f"""
<h3>\U0001f5a5 Server Resources</h3>
<table {TABLE}>
<tr {TH_BG}><td><b>CPU Load</b></td>
<td style="color:{cpu_color}"><b>{r['cpu_load'][0]:.2f}</b> / {r['cpu_load'][1]:.2f} / {r['cpu_load'][2]:.2f} &mdash; {r['cpu_count']} cores</td></tr>
<tr><td><b>RAM</b></td>
<td style="color:{ram_color}"><b>{r['ram_used']:.1f} / {r['ram_total']:.1f} GB ({r['ram_pct']:.0f}%)</b></td></tr>
<tr {TH_BG}><td><b>Disk</b></td>
<td style="color:{disk_color}"><b>{r['disk_total']-r['disk_free']:.1f} / {r['disk_total']:.1f} GB ({r['disk_pct']:.0f}%)</b></td></tr>
<tr><td><b>Press DB</b></td>
<td><b>{r['press_db_mb']:.0f} MB</b> (press-ctrl database)</td></tr>
</table>
"""

	# --- Services ---
	proc_rows = ""
	for p in r["processes"]:
		is_up = p["status"] == "RUNNING"
		color = "#22c55e" if is_up else "#ef4444"
		icon = ok if is_up else fail
		proc_rows += (
			f"<tr><td>{p['name']}</td>"
			f"<td style='color:{color};font-weight:bold'>{icon} {p['status']}</td>"
			f"<td style='color:#6b7280'>{p['uptime']}</td></tr>"
		)
	html += f"""
<h3>\u2699\ufe0f Services</h3>
<table {TABLE}>
<tr {TH_BG}><th>Process</th><th>Status</th><th>Uptime</th></tr>
{proc_rows}
</table>
"""

	# --- Press Core ---
	poll_status = f"{ok} Active" if r["poll_jobs"] > 0 else f"{fail} MISSING"
	html += f"""
<h3>\U0001f4e1 Press Core</h3>
<table {TABLE}>
<tr><td>Scheduler Jobs</td><td><b>{r['press_jobs']}</b> registered</td></tr>
<tr><td>poll_pending_jobs</td><td><b>{poll_status}</b></td></tr>
</table>
"""

	# --- Servers ---
	if r["servers"]:
		srv_rows = ""
		for s in r["servers"]:
			setup_icon = ok if s.is_server_setup else f"{warn} Not Setup"
			status_color = "#22c55e" if s.status == "Active" else "#f59e0b"
			srv_rows += (
				f"<tr><td>{s.name}</td><td>{s.ip or ''}</td>"
				f"<td style='color:{status_color}'><b>{s.status}</b></td>"
				f"<td>{setup_icon}</td></tr>"
			)
		html += f"""
<h3>\U0001f5a5 Servers ({len(r['servers'])})</h3>
<table {TABLE}>
<tr {TH_BG}><th>Name</th><th>IP</th><th>Status</th><th>Setup</th></tr>
{srv_rows}
</table>
"""

	# --- Sites ---
	sc = r["site_counts"]
	total_sites = sum(sc.values())
	site_summary = " &bull; ".join(f"{status}: <b>{cnt}</b>" for status, cnt in sc.items())
	site_rows = ""
	for s in r["sites"]:
		status_color = {
			"Active": "#22c55e", "Inactive": "#6b7280",
			"Suspended": "#f59e0b", "Broken": "#ef4444",
		}.get(s.status, "#6b7280")
		db_mb = s.get("db_mb", 0)
		disk_mb = s.get("disk_mb", 0)
		site_rows += (
			f"<tr><td><a href='https://autodeploypanel.mvpstorm.com/dashboard/sites/{s.name}/overview'>{s.name}</a></td>"
			f"<td style='color:{status_color}'><b>{s.status}</b></td>"
			f"<td>{s.bench or ''}</td>"
			f"<td>{db_mb} MB</td><td>{disk_mb} MB</td></tr>"
		)
	html += f"""
<h3>\U0001f310 Sites ({total_sites} total: {site_summary})</h3>
<table {TABLE}>
<tr {TH_BG}><th>Site</th><th>Status</th><th>Bench</th><th>DB</th><th>Disk</th></tr>
{site_rows}
</table>
"""

	# --- Benches ---
	if r["benches"]:
		bench_rows = ""
		for b in r["benches"]:
			status_color = {"Active": "#22c55e", "Broken": "#ef4444"}.get(b.status, "#f59e0b")
			icon = ok if b.status == "Active" else (fail if b.status == "Broken" else warn)
			bench_rows += (
				f"<tr><td>{b.name}</td>"
				f"<td>{b.release_group or ''}</td>"
				f"<td style='color:{status_color}'><b>{icon} {b.status}</b></td>"
				f"<td>{b.active_sites}</td></tr>"
			)
		html += f"""
<h3>\U0001f4e6 Benches ({len(r['benches'])})</h3>
<table {TABLE}>
<tr {TH_BG}><th>Bench</th><th>Group</th><th>Status</th><th>Sites</th></tr>
{bench_rows}
</table>
"""

	# --- Recent Deploys ---
	if r["recent_builds"]:
		build_rows = ""
		for b in r["recent_builds"]:
			icons = {"Success": ok, "Failure": fail, "Running": "\u23f3"}
			icon = icons.get(b.status, b.status)
			color = {"Success": "#22c55e", "Failure": "#ef4444", "Running": "#3b82f6"}.get(b.status, "#6b7280")
			start = get_datetime(b.build_start).strftime("%b %d %H:%M") if b.build_start else "\u2014"
			duration = ""
			if b.build_start and b.build_end:
				secs = time_diff_in_seconds(b.build_end, b.build_start)
				duration = f"{int(secs)}s"
			error = ""
			if b.build_error:
				error = f"<br><small style='color:#ef4444'>{_escape_html(str(b.build_error)[:120])}</small>"
			build_rows += (
				f"<tr><td><a href='https://autodeploypanel.mvpstorm.com/dashboard/deploys/{b.name}'>{b.name}</a></td>"
				f"<td style='color:{color}'><b>{icon} {b.status}</b></td>"
				f"<td>{start}</td><td>{duration}</td>"
				f"<td>{error}</td></tr>"
			)
		html += f"""
<h3>\U0001f680 Recent Deploys (48h)</h3>
<table {TABLE}>
<tr {TH_BG}><th>Build</th><th>Status</th><th>Started</th><th>Duration</th><th>Error</th></tr>
{build_rows}
</table>
"""

	# --- Agent Jobs (24h) ---
	if r["agent_jobs_summary"]:
		job_summary = " &bull; ".join(
			f"{j.status}: <b>{j.cnt}</b>" for j in r["agent_jobs_summary"]
		)
		html += f"<h3>\U0001f916 Agent Jobs (24h): {job_summary}</h3>"

		if r["failed_agent_jobs"]:
			fail_rows = ""
			for j in r["failed_agent_jobs"]:
				created = get_datetime(j.creation).strftime("%b %d %H:%M")
				fail_rows += (
					f"<tr><td>{j.name}</td><td>{j.job_type}</td>"
					f"<td>{j.server}</td><td style='color:#ef4444'><b>{j.status}</b></td>"
					f"<td>{created}</td></tr>"
				)
			html += f"""
<table {TABLE}>
<tr {TH_BG}><th>Job</th><th>Type</th><th>Server</th><th>Status</th><th>Created</th></tr>
{fail_rows}
</table>
"""

	# --- Errors (24h) ---
	err_color = _color(r["error_count"] / 100, 20, 50) if r["error_count"] else "#22c55e"
	html += f"<h3>\u26a0\ufe0f Errors (24h): <span style='color:{err_color}'>{r['error_count']}</span></h3>"
	if r["top_errors"]:
		err_rows = ""
		for e in r["top_errors"]:
			err_rows += f"<tr><td>{_escape_html(e.method or 'Unknown')}</td><td><b>{e.cnt}</b></td></tr>"
		html += f"""
<p style="color:#6b7280;font-size:13px;">Top error methods:</p>
<table {TABLE}>
<tr {TH_BG}><th>Method</th><th>Count</th></tr>
{err_rows}
</table>
"""
	if r["recent_errors"]:
		recent_rows = ""
		for e in r["recent_errors"]:
			created = get_datetime(e.creation).strftime("%b %d %H:%M")
			snippet = _escape_html(str(e.error or "")[:150])
			recent_rows += (
				f"<tr><td>{created}</td>"
				f"<td>{_escape_html(e.method or '')}</td>"
				f"<td><small>{snippet}</small></td></tr>"
			)
		html += f"""
<p style="color:#6b7280;font-size:13px;">Most recent errors:</p>
<table {TABLE}>
<tr {TH_BG}><th>Time</th><th>Method</th><th>Error</th></tr>
{recent_rows}
</table>
"""

	# --- Watch Tower Alerts ---
	if r["wt_alerts"]:
		alert_rows = ""
		for a in r["wt_alerts"]:
			alert_rows += f"<tr><td>{a.rule_name}</td><td>{a.status}</td><td><b>{a.cnt}</b></td></tr>"
		html += f"""
<h3>\U0001f514 Watch Tower Alerts (24h)</h3>
<table {TABLE}>
<tr {TH_BG}><th>Rule</th><th>Status</th><th>Count</th></tr>
{alert_rows}
</table>
"""

	subtitle = f"press-ctrl (89.167.116.92) &bull; {ts} &bull; Uptime: {r['uptime_days']}d {r['uptime_hours']}h"
	branded = wrap_email(f"{status_icon} Server Health Report", html, subtitle)

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"{status_icon} Press Health: {overall} \u2014 {ts_short}",
		message=branded,
		now=True,
	)


def _color(pct, warn_at, crit_at):
	"""Return green/yellow/red color based on threshold."""
	if pct >= crit_at:
		return "#ef4444"
	if pct >= warn_at:
		return "#f59e0b"
	return "#22c55e"


def _escape_html(text):
	"""Basic HTML escaping."""
	return (
		str(text)
		.replace("&", "&amp;")
		.replace("<", "&lt;")
		.replace(">", "&gt;")
		.replace('"', "&quot;")
	)
