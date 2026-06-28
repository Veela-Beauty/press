"""Infrastructure Watch Tower alerts -  disk, Docker, SSH, Redis, MariaDB."""
import frappe
from ._helpers import TABLE, esc, ts_now, ssh_cmd, get_all_servers, PRESS_CTRL_IP, should_send_alert


def check_server_disk_usage(doc_dict, rule):
	"""
	Check disk usage on ALL managed servers via SSH.
	Fires if any server is above 85% disk usage.
	For servers above threshold: collects detailed space recovery suggestions.
	NEVER takes any action -  only reports what CAN be cleaned.
	"""
	from ..email_branding import wrap_email, send_alert_email

	servers = get_all_servers()
	issues = []
	all_results = []
	ts = ts_now()

	SCAN_CMD = " && ".join([
		"df -h /",
		"echo '---RECLAIMABLE---'",
		"echo 'TEMP:' $(du -sh /tmp 2>/dev/null | cut -f1)",
		"echo 'APT_CACHE:' $(du -sh /var/cache/apt 2>/dev/null | cut -f1 || echo '0')",
		"echo 'OLD_LOGS:' $(find /var/log -name '*.gz' -o -name '*.old' -o -name '*.1' "
		"2>/dev/null | xargs du -sh 2>/dev/null | awk '{s+=$1} END {printf \"%.0fM\", s}' || echo '0')",
		"echo 'JOURNAL:' $(journalctl --disk-usage 2>/dev/null | grep -oP '[\\d.]+[GMK]' || echo '0')",
		"echo '---DOCKER---'",
		"docker system df 2>/dev/null || echo 'NO_DOCKER'",
		"echo '---DOCKER_DETAIL---'",
		"echo 'DANGLING_IMAGES:' $(docker images -f dangling=true -q 2>/dev/null | wc -l) 'images'",
		"echo 'BUILD_CACHE:' $(docker builder du 2>/dev/null | tail -1 || echo '0')",
		"echo 'STOPPED_CONTAINERS:' $(docker ps -a -f status=exited --format '{{.Names}} {{.Size}}' "
		"2>/dev/null | head -5 || echo 'none')",
		"echo 'UNUSED_VOLUMES:' $(docker volume ls -f dangling=true -q 2>/dev/null | wc -l) 'volumes'",
	])

	for server in servers:
		ok, stdout, stderr = ssh_cmd(server["ip"], SCAN_CMD, timeout=30)

		if not ok and not stdout.strip():
			all_results.append({
				"server": server["name"], "ip": server["ip"],
				"status": "unreachable", "pct": 0, "detail": stderr[:100],
			})
			continue

		entry = {"server": server["name"], "ip": server["ip"], "reclaimable": []}

		# Parse df
		for line in stdout.split("\n"):
			if line.startswith("/") or line.startswith("overlay"):
				parts = line.split()
				if len(parts) >= 5:
					try:
						pct = int(parts[4].replace("%", ""))
					except ValueError:
						continue
					entry.update({
						"status": "ok" if pct < 85 else "warning" if pct < 95 else "critical",
						"pct": pct, "size": parts[1], "used": parts[2], "avail": parts[3],
					})
					break

		# Parse reclaimable section
		if "---RECLAIMABLE---" in stdout:
			reclaim = stdout.split("---RECLAIMABLE---")[1].split("---DOCKER---")[0]
			for line in reclaim.strip().split("\n"):
				line = line.strip()
				if ":" in line and not line.startswith("echo"):
					key, _, val = line.partition(":")
					val = val.strip()
					if val and val != "0" and val != "0M":
						entry["reclaimable"].append((key.strip(), val))

		# Parse Docker section
		if "---DOCKER---" in stdout and "NO_DOCKER" not in stdout:
			docker_section = stdout.split("---DOCKER---")[1]
			docker_main = docker_section.split("---DOCKER_DETAIL---")[0] if "---DOCKER_DETAIL---" in docker_section else docker_section
			docker_detail = docker_section.split("---DOCKER_DETAIL---")[1] if "---DOCKER_DETAIL---" in docker_section else ""

			for dline in docker_main.strip().split("\n"):
				parts = dline.split()
				if len(parts) >= 5 and parts[0] in ("Images", "Containers", "Local", "Build"):
					label = {"Local": "Volumes", "Build": "Build Cache"}.get(parts[0], parts[0])
					reclaim_val = next((p for p in reversed(parts) if "%" in p), "")
					size = parts[3] if len(parts) > 3 else ""
					if size and size != "0B":
						entry["reclaimable"].append((f"Docker {label}", f"{size} (reclaimable: {reclaim_val})"))

			for dline in docker_detail.strip().split("\n"):
				dline = dline.strip()
				if ":" in dline and not dline.startswith("echo"):
					key, _, val = dline.partition(":")
					val = val.strip()
					if val and val != "0" and val != "none" and "0 images" not in val and "0 volumes" not in val:
						entry["reclaimable"].append((key.strip(), val))

		all_results.append(entry)
		if entry.get("pct", 0) >= 85:
			issues.append(entry)

	if not issues:
		return False

	fingerprint = "|".join(sorted(f"{i.get('name')}={(i.get('pct', 0) // 5) * 5}" for i in issues))
	if not should_send_alert("server_disk", fingerprint):
		return True

	# Build email
	summary_rows = ""
	for r in all_results:
		pct = r.get("pct", 0)
		color = "#22c55e" if pct < 85 else "#f59e0b" if pct < 95 else "#ef4444"
		status = r.get("status", "unknown")
		if status in ("unreachable", "timeout", "error"):
			summary_rows += (
				f"<tr><td>{esc(r['server'])}</td><td>{r['ip']}</td>"
				f"<td style='color:#6b7280'><b>{status}</b></td>"
				f"<td colspan='2'>{esc(r.get('detail', ''))}</td></tr>"
			)
		else:
			icon = "\u2705" if pct < 85 else "\u26a0\ufe0f" if pct < 95 else "\u274c"
			summary_rows += (
				f"<tr><td>{esc(r['server'])}</td><td>{r['ip']}</td>"
				f"<td style='color:{color}'><b>{icon} {pct}%</b></td>"
				f"<td>{r.get('used', '?')} / {r.get('size', '?')}</td>"
				f"<td>{r.get('avail', '?')} free</td></tr>"
			)

	body = f"""
<h3>All Servers</h3>
<table {TABLE}>
<tr style="background:#f8fafc"><th>Server</th><th>IP</th><th>Usage</th><th>Used/Total</th><th>Free</th></tr>
{summary_rows}
</table>"""

	for entry in issues:
		reclaim_rows = "".join(
			f"<tr><td>{esc(label)}</td><td><b>{esc(val)}</b></td></tr>"
			for label, val in entry.get("reclaimable", [])
		)
		if reclaim_rows:
			body += f"""
<h3 style="color:#ef4444;margin-top:20px;">{esc(entry['server'])} \u2014 Space Recovery Options</h3>
<p style="color:#64748b;font-size:13px;">These items can potentially be cleaned. <b>No action was taken</b> \u2014 review and decide.</p>
<table {TABLE}>
<tr style="background:#f8fafc"><th>Item</th><th>Size / Details</th></tr>
{reclaim_rows}
</table>
<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:6px;padding:12px;margin-top:8px;">
<b>Suggested commands (run manually):</b><br>
<code style="font-size:12px;">
docker image prune -a --filter until=48h -f<br>
docker builder prune -a -f<br>
docker container prune -f<br>
apt-get clean<br>
journalctl --vacuum-time=3d<br>
find /tmp -type f -mtime +7 -delete
</code>
</div>"""

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\U0001f4bf Disk Alert: {len(issues)} server(s) above 85% \u2014 {ts}",
		message=wrap_email("\U0001f4bf Server Disk Usage Alert", body, f"Press Infrastructure &bull; {ts}"),
	)
	return True


def check_docker_container_health(doc_dict, rule):
	"""Check Docker containers on all servers -  alert on crashed/restarting/exited."""
	from ..email_branding import wrap_email, send_alert_email

	servers = get_all_servers()
	issues = []
	ts = ts_now()

	for server in servers:
		ok, stdout, stderr = ssh_cmd(
			server["ip"],
			"docker ps -a --format '{{.Names}}\\t{{.Status}}\\t{{.State}}' 2>/dev/null || echo 'NO_DOCKER'",
		)
		if not ok or "NO_DOCKER" in stdout:
			continue

		for line in stdout.strip().split("\n"):
			parts = line.split("\t")
			if len(parts) < 3:
				continue
			name, status, state = parts[0], parts[1], parts[2]
			if state in ("exited", "dead", "restarting"):
				issues.append({
					"server": server["name"], "container": name,
					"state": state, "status": status,
				})

	if not issues:
		return False

	fingerprint = "|".join(sorted(f"{i['server']}:{i['container']}={i['state']}" for i in issues))
	if not should_send_alert("docker_health", fingerprint):
		return True

	rows = "".join(
		f"<tr><td>{esc(i['server'])}</td><td>{esc(i['container'])}</td>"
		f"<td style='color:#ef4444'><b>{i['state']}</b></td>"
		f"<td>{esc(i['status'])}</td></tr>"
		for i in issues
	)

	body = f"""
<table {TABLE}>
<tr style="background:#f8fafc"><th>Server</th><th>Container</th><th>State</th><th>Status</th></tr>
{rows}
</table>
<p style="margin-top:12px">Check with <code>docker logs &lt;container&gt;</code> on the server.</p>"""

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\U0001f4e6 Docker Alert: {len(issues)} container(s) down \u2014 {ts}",
		message=wrap_email("\U0001f4e6 Docker Container Health", body, f"Press Infrastructure &bull; {ts}"),
	)
	return True


def check_ssh_connectivity(doc_dict, rule):
	"""Check that press-ctrl can SSH into all managed servers."""
	from ..email_branding import wrap_email, send_alert_email

	servers = frappe.db.sql("""
		SELECT name, ip
		FROM tabServer
		WHERE status = 'Active' AND ip IS NOT NULL AND ip != ''
	""", as_dict=True)

	issues = []
	ts = ts_now()

	for server in servers:
		ok, stdout, stderr = ssh_cmd(server["ip"], "echo OK", timeout=10)
		if not ok or "OK" not in stdout:
			issues.append({
				"server": server["name"], "ip": server["ip"],
				"error": stderr[:150] or "No response",
			})

	if not issues:
		return False

	fingerprint = "|".join(sorted(f"{i['server']}={i['error']}" for i in issues))
	if not should_send_alert("ssh_connectivity", fingerprint):
		return True

	rows = "".join(
		f"<tr><td>{esc(i['server'])}</td><td>{i['ip']}</td>"
		f"<td style='color:#ef4444'>{esc(i['error'])}</td></tr>"
		for i in issues
	)

	body = f"""
<p style="color:#ef4444"><b>Press-ctrl cannot reach {len(issues)} server(s) via SSH.</b>
Deploys, agent jobs, and monitoring will fail.</p>
<table {TABLE}>
<tr style="background:#f8fafc"><th>Server</th><th>IP</th><th>Error</th></tr>
{rows}
</table>"""

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\U0001f6a8 SSH Alert: {len(issues)} server(s) unreachable \u2014 {ts}",
		message=wrap_email("\U0001f6a8 SSH Connectivity Alert", body, f"Press Infrastructure &bull; {ts}"),
	)
	return True


def check_redis_health(doc_dict, rule):
	"""Check Redis is responsive and not in error state."""
	from ..email_branding import wrap_email, send_alert_email
	import subprocess

	issues = []
	ts = ts_now()

	# Check redis-cache (11000) and redis-queue (12000)
	for port, name in [(11000, "Redis Cache"), (12000, "Redis Queue"), (13000, "Redis Socketio")]:
		try:
			result = subprocess.run(
				["redis-cli", "-p", str(port), "ping"],
				capture_output=True, text=True, timeout=5,
			)
			if "PONG" not in result.stdout:
				issues.append(f"{name} (port {port}): not responding")
				continue

			# Check for MISCONF error (stop-writes-on-bgsave-error)
			result = subprocess.run(
				["redis-cli", "-p", str(port), "set", "_wt_health_check", "1"],
				capture_output=True, text=True, timeout=5,
			)
			if "MISCONF" in result.stdout:
				issues.append(f"{name} (port {port}): <b>MISCONF \u2014 writes blocked</b> (bgsave error)")

			# Check memory usage
			result = subprocess.run(
				["redis-cli", "-p", str(port), "info", "memory"],
				capture_output=True, text=True, timeout=5,
			)
			for line in result.stdout.split("\n"):
				if line.startswith("used_memory_human:"):
					mem = line.split(":")[1].strip()
					pass  # Memory info collected but not an issue
		except Exception:
			issues.append(f"{name} (port {port}): connection failed")

	if not issues:
		return False

	if not should_send_alert("redis_health", "|".join(sorted(issues))):
		return True

	body = "<ul>" + "".join(f"<li style='color:#ef4444'>{i}</li>" for i in issues) + "</ul>"
	body += "<p>Check with <code>redis-cli -p PORT info</code> on press-ctrl.</p>"

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\U0001f534 Redis Alert: {len(issues)} issue(s) \u2014 {ts}",
		message=wrap_email("\U0001f534 Redis Health Alert", body, f"press-ctrl &bull; {ts}"),
	)
	return True


def check_mariadb_health(doc_dict, rule):
	"""Check MariaDB connection pool and slow queries."""
	from ..email_branding import wrap_email, send_alert_email

	issues = []
	ts = ts_now()

	# 1. Check active connections vs max
	try:
		result = frappe.db.sql("""
			SELECT
				(SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS
				 WHERE VARIABLE_NAME = 'Threads_connected') as active,
				(SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_VARIABLES
				 WHERE VARIABLE_NAME = 'max_connections') as max_conn
		""", as_dict=True)
		if result:
			active = int(result[0].active or 0)
			max_conn = int(result[0].max_conn or 151)
			pct = (active / max_conn * 100) if max_conn > 0 else 0
			if pct > 80:
				issues.append(f"Connections: <b>{active}/{max_conn}</b> ({pct:.0f}%) \u2014 nearing limit")
	except Exception:
		pass

	# 2. Check for long-running queries (>60s)
	try:
		long_queries = frappe.db.sql("""
			SELECT ID, USER, TIME, STATE, SUBSTRING(INFO, 1, 100) as query
			FROM information_schema.PROCESSLIST
			WHERE COMMAND != 'Sleep' AND TIME > 60
			ORDER BY TIME DESC LIMIT 5
		""", as_dict=True)
		for q in long_queries:
			issues.append(
				f"Long query ({q.TIME}s) by {q.USER}: <code>{esc(q.query or '')}</code>"
			)
	except Exception:
		pass

	# 3. Check if MariaDB is responding at all
	try:
		frappe.db.sql("SELECT 1")
	except Exception as e:
		issues.append(f"MariaDB not responding: {esc(str(e)[:100])}")

	if not issues:
		return False

	if not should_send_alert("mariadb_health", "|".join(sorted(issues))):
		return True

	body = "<ul>" + "".join(f"<li>{i}</li>" for i in issues) + "</ul>"

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\U0001f5c4 MariaDB Alert: {len(issues)} issue(s) \u2014 {ts}",
		message=wrap_email("\U0001f5c4 MariaDB Health Alert", body, f"press-ctrl &bull; {ts}"),
	)
	return True


def check_microservice_health(doc_dict, rule):
	"""Check HTTP health endpoints of internal microservices (code-analysis, etc.)."""
	from ..email_branding import wrap_email, send_alert_email
	import json

	ts = ts_now()
	services = [
		{"name": "Code Analysis", "url": "http://localhost:8200/health", "server": PRESS_CTRL_IP},
	]

	issues = []
	for svc in services:
		ok, stdout, stderr = ssh_cmd(
			svc["server"],
			f"curl -sf --max-time 5 {svc['url']} 2>/dev/null || echo FAIL",
		)
		if not ok or "FAIL" in stdout or '"status":"ok"' not in stdout:
			issues.append({"name": svc["name"], "url": svc["url"], "response": stdout[:200]})

	if not issues:
		return False

	fingerprint = "|".join(sorted(i["name"] for i in issues))
	if not should_send_alert("microservice_health", fingerprint):
		return True

	rows = "".join(
		f"<tr><td>{esc(i['name'])}</td><td>{esc(i['url'])}</td>"
		f"<td style='color:#ef4444'><b>DOWN</b></td>"
		f"<td style='font-size:11px'>{esc(i['response'][:100])}</td></tr>"
		for i in issues
	)

	body = f"""
<table {TABLE}>
<tr style="background:#f8fafc"><th>Service</th><th>URL</th><th>Status</th><th>Response</th></tr>
{rows}
</table>
<p style="margin-top:12px">Restart with <code>docker compose up -d</code> in the service directory.</p>"""

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\U0001f6a8 Microservice Down: {len(issues)} service(s) unreachable \u2014 {ts}",
		message=wrap_email("\U0001f6a8 Microservice Health Check", body, f"Press Infrastructure &bull; {ts}"),
	)
	return True