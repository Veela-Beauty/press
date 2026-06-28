"""
Watch Tower Email Branding -  Accurate Systems.

Shared header/footer for all Watch Tower emails.
Sends via direct SMTP -  completely bypasses Frappe's Email Queue
to prevent feedback loops when the queue itself is the problem.
"""
import smtplib
from ._hard_timeout import hard_timeout, HardTimeoutError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

LOGO_URL = "https://autodeploypanel.mvpstorm.com/files/accurate-systems-logo.png"
SITE_URL = "https://autodeploypanel.mvpstorm.com"
COMPANY = "Accurate Systems"
BRAND_COLOR = "#1e40af"  # Accurate blue
BRAND_LIGHT = "#eff6ff"

# CC for important alerts only (backup failures, site down, deploy stuck).
# NOT for noise alerts (error log spikes, worker queues, scheduler internals).
# Pass important=True to send_alert_email to include these recipients.
IMPORTANT_ALERT_CC = []  # emptied 2026-05-03 -  wosaibi+sukaina opted out, see commit

# SMTP config -  read from Email Account on first use, cached
_smtp_config = {}


def _get_smtp_config():
	"""Load SMTP config from the default outgoing Email Account."""
	if _smtp_config:
		return _smtp_config

	import frappe

	try:
		account = frappe.get_doc("Email Account", {"default_outgoing": 1})
		_smtp_config.update({
			"server": account.smtp_server,
			"port": account.smtp_port or 587,
			"login": account.email_id,
			"password": account.get_password("password") if account.password else "",
			"sender": f"{account.name} <{account.email_id}>",
			"use_tls": bool(account.use_tls),
		})
	except Exception:
		# Fallback -  hardcoded for Press
		_smtp_config.update({
			"server": "mail.acsprosys.com",
			"port": 587,
			"login": "info@optiflowsys.com",
			"password": "",
			"sender": "Watch Tower <info@optiflowsys.com>",
			"use_tls": True,
		})

	return _smtp_config


def send_alert_email(recipients, subject, message, important=False, **kwargs):
	"""
	Send email via direct SMTP -  no Frappe Email Queue involved.

	Args:
		important: If True, CC client stakeholders (IMPORTANT_ALERT_CC).
		           Use for: backup failures, site down, deploy stuck, SSL expiry.
		           Do NOT use for: error log spikes, worker queues, scheduler noise.
	"""
	import frappe

	cc_list = IMPORTANT_ALERT_CC if important else []
	all_recipients = list(set(
		(recipients if isinstance(recipients, list) else [recipients])
		+ cc_list
	))

	# Try direct SMTP first
	try:
		cfg = _get_smtp_config()
		if cfg.get("password"):
			_send_smtp(cfg, all_recipients, subject, message)
			return
	except Exception as e:
		frappe.logger("watch_tower").warning(f"Direct SMTP failed: {e}, falling back to frappe.sendmail")

	# No fallback to frappe.sendmail -  it creates Email Queue entries
	# that pile up as errors when SMTP rejects recipients (caused 104K entries, 1.17 GB).
	# If direct SMTP fails, just log and move on.
	frappe.logger("watch_tower").error(f"Alert email not sent (SMTP unavailable): {subject}")


def _send_smtp(cfg, recipients, subject, html_body):
	"""Send HTML email via direct SMTP connection.

	Wrapped in hard_timeout(15s) -  without it, smtplib.login can hang
	indefinitely on slow EHLO/AUTH responses (saw 5+ min hangs in
	prod 2026-05-02). Hard timeout releases the worker so other queued
	jobs (DR Restore, etc.) don't starve.
	"""
	import frappe
	msg = MIMEMultipart("alternative")
	msg["From"] = cfg["sender"]
	msg["To"] = ", ".join(recipients)
	msg["Subject"] = subject
	msg.attach(MIMEText(html_body, "html", "utf-8"))

	try:
		with hard_timeout(15):
			with smtplib.SMTP(cfg["server"], cfg["port"], timeout=10) as server:
				if cfg.get("use_tls"):
					server.starttls()
				if cfg.get("password"):
					server.login(cfg["login"], cfg["password"])
				server.sendmail(cfg["login"], recipients, msg.as_string())
	except HardTimeoutError:
		frappe.logger("watch_tower").error(
			f"_send_smtp hard-timeout (>15s) to " + cfg["server"] + "; alert dropped: " + subject
		)


def wrap_email(title, body_html, subtitle=""):
	"""Wrap email body in branded template with logo header and footer."""
	return f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:700px;margin:0 auto;background:#fff;">

<!-- Header -->
<div style="background:{BRAND_COLOR};padding:20px 24px;border-radius:8px 8px 0 0;">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td>
<img src="{LOGO_URL}" alt="{COMPANY}" height="36" style="height:36px;vertical-align:middle;" />
</td>
<td style="text-align:right;color:rgba(255,255,255,0.7);font-size:12px;">
Cloud Hosting Platform
</td>
</tr>
</table>
</div>

<!-- Title bar -->
<div style="background:{BRAND_LIGHT};padding:16px 24px;border-bottom:1px solid #dbeafe;">
<h2 style="margin:0;font-size:18px;color:#1e293b;">{title}</h2>
{"<p style='margin:4px 0 0;color:#64748b;font-size:13px;'>" + subtitle + "</p>" if subtitle else ""}
</div>

<!-- Body -->
<div style="padding:20px 24px;">
{body_html}
</div>

<!-- Footer -->
<div style="background:#f8fafc;padding:16px 24px;border-top:1px solid #e2e8f0;border-radius:0 0 8px 8px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td style="color:#94a3b8;font-size:11px;">
Watch Tower &bull; {COMPANY} Cloud
</td>
<td style="text-align:right;font-size:11px;">
<a href="{SITE_URL}/app/watch-tower-rules" style="color:{BRAND_COLOR};text-decoration:none;">Rules</a>
&nbsp;&bull;&nbsp;
<a href="{SITE_URL}/app/watch-tower-alert-log" style="color:{BRAND_COLOR};text-decoration:none;">Alerts</a>
&nbsp;&bull;&nbsp;
<a href="{SITE_URL}/dashboard" style="color:{BRAND_COLOR};text-decoration:none;">Dashboard</a>
</td>
</tr>
</table>
</div>

</div>"""
