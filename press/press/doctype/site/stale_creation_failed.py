import frappe

MIGRATE_JOBS = ("Migrate Site", "Update Site Migrate")


def clear_stale_creation_failed():
	"""Press clears Site.creation_failed only when a Restore Site job succeeds. A failed New Site or
	Restore that is finished by hand keeps the flag, and every site action stays blocked on a healthy
	site. A green migrate after the flag proves the site works, so clear it then (Active sites only)."""
	sites = frappe.get_all(
		"Site",
		filters={"status": "Active", "creation_failed": ("is", "set")},
		fields=["name", "creation_failed"],
	)
	for site in sites:
		migrated = frappe.db.exists(
			"Agent Job",
			{
				"site": site.name,
				"job_type": ("in", MIGRATE_JOBS),
				"status": "Success",
				"creation": (">", site.creation_failed),
			},
		)
		if migrated:
			# conditional: a restore that failed after the read above stamped a new flag and Broken; keep that one
			frappe.db.sql(
				"""update `tabSite` set creation_failed = null
				where name = %s and status = 'Active' and creation_failed = %s""",
				(site.name, site.creation_failed),
			)
			frappe.db.commit()
