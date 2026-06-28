"""Site-level Watch Tower alerts -  reachability, SSL, email queue, bench updates."""
import frappe
from .._hard_timeout import hard_timeout, HardTimeoutError
from frappe.utils import get_datetime
from ._helpers import TABLE, esc, ts_now, ssh_cmd, should_send_alert


def check_site_reachability(doc_dict, rule):
	"""Check that all active sites respond with HTTP 200."""
	import requests
	from ..email_branding import wrap_email, send_alert_email

	sites = frappe.db.sql("""
		SELECT name, host_name, status, bench
		FROM tabSite
		WHERE status = 'Active'
		ORDER BY name
	""", as_dict=True)

	issues = []
	ts = ts_now()

	for site in sites:
		url = f"https://{site.name}/api/method/ping"
		try:
			with hard_timeout(15):
				resp = requests.get(url, timeout=(5, 5), verify=True, allow_redirects=True)
			if resp.status_code >= 500:
				issues.append({
					"site": site.name, "bench": site.bench,
					"error": f"HTTP {resp.status_code}",
				})
		except HardTimeoutError:
			issues.append({
				"site": site.name, "bench": site.bench,
				"error": "Hard timeout >15s (server unreachable or trickling)",
			})
		except requests.exceptions.SSLError as e:
			issues.append({
				"site": site.name, "bench": site.bench,
				"error": f"SSL Error: {str(e)[:100]}",
			})
		except requests.exceptions.ConnectionError:
			issues.append({
				"site": site.name, "bench": site.bench,
				"error": "Connection refused / unreachable",
			})
		except requests.exceptions.Timeout:
			issues.append({
				"site": site.name, "bench": site.bench,
				"error": "Timeout (>10s)",
			})
		except Exception as e:
			issues.append({
				"site": site.name, "bench": site.bench,
				"error": str(e)[:100],
			})

	if not issues:
		return False

	fingerprint = "|".join(sorted(f"{i['site']}={i['error']}" for i in issues))
	if not should_send_alert("site_reachability", fingerprint):
		return True

	rows = "".join(
		f"<tr><td><a href='https://{esc(i['site'])}'>{esc(i['site'])}</a></td>"
		f"<td>{esc(i['bench'])}</td>"
		f"<td style='color:#ef4444'>{esc(i['error'])}</td></tr>"
		for i in issues
	)

	body = f"""
<p><b>{len(issues)} of {len(sites)} active sites</b> are not responding.</p>
<table {TABLE}>
<tr style="background:#f8fafc"><th>Site</th><th>Bench</th><th>Error</th></tr>
{rows}
</table>"""

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\U0001f310 Site Alert: {len(issues)} site(s) down \u2014 {ts}",
		important=True,
		message=wrap_email("0001F310 SITE REACHABILITY ALERT", body, f"Press &bull; {ts}"),
	)
	return True


def check_ssl_expiry(doc_dict, rule):
	"""Check SSL certificates for all active sites -  alert if expiring in <14 days."""
	import ssl
	import socket
	from ..email_branding import wrap_email, send_alert_email
	from datetime import datetime

	sites = frappe.db.sql("""
		SELECT name FROM tabSite WHERE status = 'Active'
	""", as_dict=True)

	issues = []
	ts = ts_now()

	for site in sites:
		hostname = site.name
		try:
			ctx = ssl.create_default_context()
			with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
				s.settimeout(5)
				s.connect((hostname, 443))
				cert = s.getpeercert()
				not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
				days_left = (not_after - datetime.utcnow()).days

				if days_left < 14:
					issues.append({
						"site": hostname,
						"expires": not_after.strftime("%Y-%m-%d"),
						"days_left": days_left,
					})
		except (ssl.SSLError, ssl.CertificateError) as e:
			issues.append({
				"site": hostname,
				"expires": "SSL ERROR",
				"days_left": 0,
				"error": str(e)[:80],
			})
		except (socket.timeout, ConnectionRefusedError, OSError):
			pass  # Site unreachable -  handled by check_site_reachability, not SSL check

	if not issues:
		return False

	fingerprint = "|".join(sorted(f"{i['site']}={i['days_left']}d" for i in issues))
	if not should_send_alert("ssl_expiry", fingerprint):
		return True

	rows = ""
	for i in issues:
		color = "#ef4444" if i["days_left"] < 7 else "#f59e0b"
		err = f" ({esc(i.get('error', ''))})" if i.get("error") else ""
		rows += (
			f"<tr><td>{esc(i['site'])}</td>"
			f"<td style='color:{color}'><b>{i['days_left']} days</b></td>"
			f"<td>{i['expires']}{err}</td></tr>"
		)

	body = f"""
<table {TABLE}>
<tr style="background:#f8fafc"><th>Site</th><th>Days Left</th><th>Expires</th></tr>
{rows}
</table>
<p>Renew with <code>certbot renew</code> or check Press TLS configuration.</p>"""

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\U0001f512 SSL Alert: {len(issues)} cert(s) expiring \u2014 {ts}",
		important=True,
		message=wrap_email("0001F512 SSL CERTIFICATE ALERT", body, f"Press &bull; {ts}"),
	)
	return True


def check_email_queue_growth(doc_dict, rule):
	"""Alert if email queue has >100 unsent emails (early warning for loops)."""
	from ..email_branding import wrap_email, send_alert_email

	unsent = frappe.db.count("Email Queue", {"status": "Not Sent"})
	error = frappe.db.count("Email Queue", {"status": "Error"})

	if unsent + error < 100:
		return False

	# Bucket the count so similar magnitudes share a fingerprint (avoids
	# every +1 email triggering a new 3-email burst).
	bucket = ((unsent + error) // 100) * 100
	if not should_send_alert("email_queue_growth", str(bucket)):
		return True

	ts = ts_now()

	# Get breakdown by sender
	senders = frappe.db.sql("""
		SELECT sender, status, COUNT(*) as cnt
		FROM `tabEmail Queue`
		WHERE status IN ('Not Sent', 'Error')
		GROUP BY sender, status
		ORDER BY cnt DESC LIMIT 10
	""", as_dict=True)

	rows = "".join(
		f"<tr><td>{esc(s.sender or 'Unknown')}</td><td>{s.status}</td><td><b>{s.cnt}</b></td></tr>"
		for s in senders
	)

	body = f"""
<p style="color:#ef4444"><b>{unsent} Not Sent + {error} Error</b> emails in queue.</p>
<p>This may indicate a sending loop or SMTP failure.</p>
<table {TABLE}>
<tr style="background:#f8fafc"><th>Sender</th><th>Status</th><th>Count</th></tr>
{rows}
</table>
<p><b>Fix:</b> Check SMTP config, or run:
<code>bench --site demo.mvpstorm.com execute frappe.email.queue.flush</code></p>"""

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\U0001f4e7 Email Queue Alert: {unsent + error} stuck \u2014 {ts}",
		message=wrap_email("\U0001f4e7 Email Queue Growth", body, f"press-ctrl &bull; {ts}"),
	)
	return True


def check_bench_updates_pending(doc_dict, rule):
	"""Alert if sites have pending updates sitting for >3 days."""
	from ..email_branding import wrap_email, send_alert_email

	# Check deploy candidates stuck in draft
	stale_deploys = frappe.db.sql("""
		SELECT name, `group`, creation,
			DATEDIFF(NOW(), creation) as days_old
		FROM `tabDeploy Candidate`
		WHERE status = 'Draft'
			AND creation < NOW() - INTERVAL 3 DAY
		ORDER BY creation DESC
		LIMIT 5
	""", as_dict=True)

	if not stale_deploys:
		return False

	fingerprint = "|".join(sorted(d.name for d in stale_deploys))
	if not should_send_alert("bench_updates_pending", fingerprint):
		return True

	ts = ts_now()

	rows = "".join(
		f"<tr><td>{esc(d.name)}</td><td>{esc(d.group)}</td>"
		f"<td><b>{d.days_old} days</b></td></tr>"
		for d in stale_deploys
	)

	body = f"""
<p><b>{len(stale_deploys)} deploy candidate(s)</b> have been in Draft for over 3 days.</p>
<table {TABLE}>
<tr style="background:#f8fafc"><th>Deploy</th><th>Group</th><th>Age</th></tr>
{rows}
</table>"""

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\U0001f4e6 Stale Deploys: {len(stale_deploys)} pending \u2014 {ts}",
		message=wrap_email("\U0001f4e6 Pending Updates", body, f"Press &bull; {ts}"),
	)
	return True
