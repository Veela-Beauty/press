"""
Site Lifecycle Manager for Watch Tower.

3-stage lifecycle for inactive sites:
1. Warning (14 days no activity) → email: "will archive in 7 days"
2. Auto-archive (21 days no activity) → backup + archive + email
3. Auto-delete (90 days archived) → backup taken at archive time, safe to drop

Uses Site Activity `action` field + Site `modified` date to track activity.
Runs daily via Watch Tower scheduler.
"""
import frappe
from frappe.utils import now_datetime, get_datetime, add_days, date_diff

# Sites that should NEVER be auto-archived (e.g., the Press site itself)
PROTECTED_SITES = (
	"demo.mvpstorm.com",
)

WARN_AFTER_DAYS = 14      # Days inactive before warning email
ARCHIVE_AFTER_DAYS = 21   # Days inactive before auto-archive
DELETE_AFTER_DAYS = 90     # Days after archive before deletion

EMAIL_TO = "eng.elgogary@gmail.com"
SITE_URL = "https://autodeploypanel.mvpstorm.com"
TABLE = 'border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;"'
TH_BG = 'style="background:#f8fafc"'

def _brand(title, body, subtitle=""):
	from .email_branding import wrap_email
	return wrap_email(title, body, subtitle)

def send_alert_email(*args, **kwargs):
	from .email_branding import send_alert_email as _send
	return _send(*args, **kwargs)


def run_site_lifecycle():
	"""Daily job: warn → archive → delete inactive sites."""
	if not frappe.db.exists("DocType", "Site"):
		return
	warned = _warn_inactive_sites()
	archived = _archive_inactive_sites()
	deleted = _delete_old_archived_sites()

	if warned or archived or deleted:
		frappe.logger().info(
			f"Site Lifecycle: warned={len(warned)}, "
			f"archived={len(archived)}, deleted={len(deleted)}"
		)


def _get_last_activity_date(site_name):
	"""Get the most recent activity date for a site.

	Checks multiple signals since self-hosted Press doesn't track
	actual user logins on the site itself:
	1. Site Activity table (dashboard logins, deploys, config changes)
	2. Site.modified (any Press-side update)
	3. Deploy Candidate Build (recent deploy to the site's bench)

	The most recent of all signals is used as "last activity".
	"""
	dates = []

	# 1. ACTUAL user login on the site (synced daily by site_activity_sync)
	site_data = frappe.db.get_value(
		"Site", site_name,
		["modified", "bench", "last_user_login"], as_dict=True,
	)
	if site_data and site_data.get("last_user_login"):
		dates.append(get_datetime(site_data.last_user_login))

	# 2. Latest Site Activity in Press (dashboard logins, deploys, etc.)
	last_activity = frappe.db.sql("""
		SELECT MAX(creation) FROM `tabSite Activity`
		WHERE site = %s
	""", site_name)
	if last_activity and last_activity[0][0]:
		dates.append(get_datetime(last_activity[0][0]))

	# 3. Site modified date
	if site_data and site_data.modified:
		dates.append(get_datetime(site_data.modified))

	# 4. Last deploy to this site's bench (means code was updated)
	if site_data and site_data.bench:
		last_deploy = frappe.db.sql("""
			SELECT MAX(build_end) FROM `tabDeploy Candidate Build`
			WHERE status = 'Success'
				AND name IN (
					SELECT candidate FROM tabDeploy
					WHERE bench = %s
				)
		""", site_data.bench)
		if last_deploy and last_deploy[0][0]:
			dates.append(get_datetime(last_deploy[0][0]))

	return max(dates) if dates else now_datetime()


def _warn_inactive_sites():
	"""Find Active sites with no activity for WARN_AFTER_DAYS, send warning."""
	sites = frappe.db.sql("""
		SELECT name, modified, bench, team
		FROM tabSite
		WHERE status = 'Active'
			AND modified < NOW() - INTERVAL %s DAY
		ORDER BY modified
	""", WARN_AFTER_DAYS, as_dict=True)

	warned = []
	for s in sites:
		if s.name in PROTECTED_SITES:
			continue

		last_activity = _get_last_activity_date(s.name)
		inactive_days = date_diff(now_datetime(), last_activity)

		if inactive_days < WARN_AFTER_DAYS:
			continue

		# Don't warn if already warned in last 7 days
		already_warned = frappe.db.exists("Watch Tower Alert Log", {
			"rule_name": "Site Inactivity Warning",
			"target_document": s.name,
			"alert_datetime": [">", add_days(now_datetime(), -7)],
		})
		if already_warned:
			continue

		warned.append({
			"name": s.name,
			"inactive_days": inactive_days,
			"last_activity": last_activity,
			"bench": s.bench,
		})

		# Create alert log
		frappe.get_doc({
			"doctype": "Watch Tower Alert Log",
			"rule_name": "Site Inactivity Warning",
			"status": "Success",
			"alert_datetime": now_datetime(),
			"triggered_by": "Scheduler",
			"target_doctype": "Site",
			"target_document": s.name,
			"action_summary": f"Inactive for {inactive_days} days. Will archive after {ARCHIVE_AFTER_DAYS} days.",
		}).insert(ignore_permissions=True)

	if warned:
		_send_warning_email(warned)
		frappe.db.commit()

	return warned


def _archive_inactive_sites():
	"""Archive Active sites with no activity for ARCHIVE_AFTER_DAYS."""
	sites = frappe.db.sql("""
		SELECT name, modified, bench, team
		FROM tabSite
		WHERE status = 'Active'
			AND modified < NOW() - INTERVAL %s DAY
		ORDER BY modified
	""", ARCHIVE_AFTER_DAYS, as_dict=True)

	archived = []
	for s in sites:
		if s.name in PROTECTED_SITES:
			continue

		last_activity = _get_last_activity_date(s.name)
		inactive_days = date_diff(now_datetime(), last_activity)

		if inactive_days < ARCHIVE_AFTER_DAYS:
			continue

		try:
			site_doc = frappe.get_doc("Site", s.name)
			site_doc.archive(
				reason=f"Auto-archived by Watch Tower: {inactive_days} days inactive",
				create_offsite_backup=True,
			)
			archived.append({
				"name": s.name,
				"inactive_days": inactive_days,
				"bench": s.bench,
			})

			frappe.get_doc({
				"doctype": "Watch Tower Alert Log",
				"rule_name": "Site Auto-Archived",
				"status": "Success",
				"alert_datetime": now_datetime(),
				"triggered_by": "Scheduler",
				"target_doctype": "Site",
				"target_document": s.name,
				"action_summary": f"Archived after {inactive_days} days inactive. Backup created.",
			}).insert(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(
				title=f"Site Lifecycle: Failed to archive {s.name}",
				message=frappe.get_traceback(),
			)

	if archived:
		_send_archive_email(archived)
		frappe.db.commit()

	return archived


def _delete_old_archived_sites():
	"""Delete archived sites older than DELETE_AFTER_DAYS."""
	sites = frappe.db.sql("""
		SELECT name, modified, bench
		FROM tabSite
		WHERE status = 'Archived'
			AND modified < NOW() - INTERVAL %s DAY
		ORDER BY modified
	""", DELETE_AFTER_DAYS, as_dict=True)

	deleted = []
	for s in sites:
		if s.name in PROTECTED_SITES:
			continue

		archived_days = date_diff(now_datetime(), get_datetime(s.modified))

		try:
			# Press archive already created offsite backup -  safe to drop
			site_doc = frappe.get_doc("Site", s.name)
			site_doc.flags.ignore_permissions = True
			# Drop the site database and remove from Press
			if hasattr(site_doc, "drop_site"):
				site_doc.drop_site()
			else:
				# Fallback: just delete the doc if drop_site doesn't exist
				site_doc.delete(ignore_permissions=True)

			deleted.append({
				"name": s.name,
				"archived_days": archived_days,
			})

			frappe.get_doc({
				"doctype": "Watch Tower Alert Log",
				"rule_name": "Site Auto-Deleted",
				"status": "Success",
				"alert_datetime": now_datetime(),
				"triggered_by": "Scheduler",
				"target_doctype": "Site",
				"target_document": s.name,
				"action_summary": f"Deleted after {archived_days} days archived. Backup was taken at archive time.",
			}).insert(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(
				title=f"Site Lifecycle: Failed to delete {s.name}",
				message=frappe.get_traceback(),
			)

	if deleted:
		_send_delete_email(deleted)
		frappe.db.commit()

	return deleted


# --- Emails ---

def _send_warning_email(sites):
	ts = now_datetime().strftime("%Y-%m-%d %H:%M")
	rows = ""
	for s in sites:
		days_left = ARCHIVE_AFTER_DAYS - s["inactive_days"]
		rows += (
			f"<tr><td><a href='{SITE_URL}/dashboard/sites/{s['name']}/overview'>{s['name']}</a></td>"
			f"<td><b>{s['inactive_days']} days</b></td>"
			f"<td>{get_datetime(s['last_activity']).strftime('%b %d, %Y')}</td>"
			f"<td style='color:#f59e0b'><b>{days_left} days</b></td></tr>"
		)

	body = f"""
<table {TABLE}>
<tr {TH_BG}><th>Site</th><th>Inactive</th><th>Last Activity</th><th>Archive In</th></tr>
{rows}
</table>

<h3>What happens next?</h3>
<ul>
<li>After <b>{ARCHIVE_AFTER_DAYS} days</b> inactive \u2192 site is archived (backup taken first)</li>
<li>After <b>{DELETE_AFTER_DAYS} days</b> archived \u2192 site is permanently deleted</li>
<li>To prevent archiving: just log into the site or trigger any activity</li>
<li>Archived sites can be restored from the dashboard</li>
</ul>"""

	send_alert_email(
		recipients=[EMAIL_TO],
		subject=f"\u26a0\ufe0f {len(sites)} site(s) will be archived soon",
		message=_brand(f"\u26a0\ufe0f Inactive Sites -  {len(sites)} site(s)", body, ts),
		now=True,
	)


def _send_archive_email(sites):
	ts = now_datetime().strftime("%Y-%m-%d %H:%M")
	rows = ""
	for s in sites:
		rows += (
			f"<tr><td>{s['name']}</td>"
			f"<td>{s['inactive_days']} days</td>"
			f"<td>{s['bench']}</td></tr>"
		)

	body = f"""
<p>Backups were created before archiving.</p>
<table {TABLE}>
<tr {TH_BG}><th>Site</th><th>Inactive Days</th><th>Bench</th></tr>
{rows}
</table>

<h3>Need to restore?</h3>
<p>Go to <a href="{SITE_URL}/app/site?status=Archived">Archived Sites</a> and click <b>Restore</b>.
Sites will be permanently deleted after <b>{DELETE_AFTER_DAYS} days</b> in archive.</p>"""

	send_alert_email(
		recipients=[EMAIL_TO],
		subject=f"\U0001f4e6 {len(sites)} site(s) archived (inactive)",
		message=_brand(f"\U0001f4e6 {len(sites)} site(s) auto-archived", body, ts),
		now=True,
	)


def _send_delete_email(sites):
	ts = now_datetime().strftime("%Y-%m-%d %H:%M")
	rows = ""
	for s in sites:
		rows += (
			f"<tr><td>{s['name']}</td>"
			f"<td>{s['archived_days']} days</td></tr>"
		)

	body = f"""
<p>These sites were archived over {DELETE_AFTER_DAYS} days ago. Offsite backups were taken at archive time.</p>
<table {TABLE}>
<tr {TH_BG}><th>Site</th><th>Days in Archive</th></tr>
{rows}
</table>"""

	send_alert_email(
		recipients=[EMAIL_TO],
		subject=f"\U0001f5d1 {len(sites)} old archived site(s) deleted",
		message=_brand(f"\U0001f5d1 {len(sites)} archived site(s) deleted", body, ts),
		now=True,
	)
