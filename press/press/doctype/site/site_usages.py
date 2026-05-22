import functools
from typing import TYPE_CHECKING

import frappe
import rq

from press.api.analytics import get_current_cpu_usage_for_sites_on_server
from press.press.doctype.site_plan.site_plan import get_plan_config
from press.utils import log_error

if TYPE_CHECKING:
	from press.press.doctype.site.site import Site


@functools.lru_cache(maxsize=128)
def get_cpu_limit(plan):
	return frappe.db.get_value("Site Plan", plan, "cpu_time_per_day") * 3600 * 1000_000


@functools.lru_cache(maxsize=128)
def get_cpu_limits(plan):
	return get_config(plan).get("rate_limit", {}).get("limit", 1) * 1000_000


@functools.lru_cache(maxsize=128)
def get_disk_limits(plan):
	return frappe.db.get_value("Site Plan", plan, ["max_database_usage", "max_storage_usage"])


@functools.lru_cache(maxsize=128)
def get_config(plan):
	return get_plan_config(plan)


def update_cpu_usages():
	"""Update CPU Usages field Site.current_cpu_usage across all Active sites from Site Request Log"""
	# Skip decommissioned servers (2026-05-21 cluster-decom rule).
	servers = frappe.get_all(
		"Server",
		filters={"status": "Active", "is_primary": True, "is_decommissioned": 0},
		pluck="name",
	)
	for server in servers:
		frappe.enqueue(
			"press.press.doctype.site.site_usages.update_cpu_usage_server",
			server=server,
			queue="long",
			deduplicate=True,
			job_id=f"update_cpu_usages:{server}",
		)


def update_cpu_usage_server(server):
	usage = get_current_cpu_usage_for_sites_on_server(server)
	sites = frappe.get_all(
		"Site",
		filters={"status": "Active", "server": server},
		fields=["name", "plan", "current_cpu_usage"],
	)

	for site in sites:
		if site.name not in usage:
			continue
		try:
			cpu_usage = usage[site.name]
			cpu_limit = get_cpu_limits(site.plan)
			latest_cpu_usage = int((cpu_usage / cpu_limit) * 100)

			if site.current_cpu_usage != latest_cpu_usage:
				site_doc = frappe.get_doc("Site", site.name)
				site_doc.current_cpu_usage = latest_cpu_usage
				site_doc.save()
				frappe.db.commit()
		except rq.timeouts.JobTimeoutException:
			frappe.db.rollback()
			return
		except Exception:
			log_error("Site CPU Usage Update Error", site=site, cpu_usage=cpu_usage, cpu_limit=cpu_limit)
			frappe.db.rollback()


def update_disk_usages():
	"""Update Storage and Database Usages fields Site.current_database_usage and Site.current_disk_usage for sites that have Site Usage documents"""

	latest_disk_usages = frappe.db.sql(
		"""WITH disk_usage AS (
			SELECT
				`site`,
				`database`,
				`public` + `private` as disk,
				ROW_NUMBER() OVER (PARTITION BY `site` ORDER BY `creation` DESC) AS 'rank'
			FROM
				`tabSite Usage`
			WHERE
				`creation` > %s
		),
		joined AS (
			SELECT
				u.site,
				site.current_database_usage,
				site.current_disk_usage,
				CAST(u.database / plan.max_database_usage * 100 AS INTEGER) AS latest_database_usage,
				CAST(u.disk / plan.max_storage_usage * 100 AS INTEGER) AS latest_disk_usage
			FROM
				disk_usage u
			INNER JOIN
				`tabSubscription` s
			ON
				u.site = s.document_name
			LEFT JOIN
				`tabSite` site
			ON
				u.site = site.name
			LEFT JOIN
				`tabSite Plan` plan
			ON
				s.plan = plan.name
			WHERE
				`rank` = 1 AND
				s.`document_type` = 'Site' AND
				site.`status` != "Archived"
		)
		SELECT
			j.site,
			j.latest_database_usage,
			j.latest_disk_usage
		FROM
			joined j
		WHERE
			ABS(j.latest_database_usage - j.current_database_usage ) > 1 OR
			ABS(j.latest_disk_usage - j.current_disk_usage) > 1
	""",
		values=(frappe.utils.add_to_date(frappe.utils.now(), hours=-12),),
		as_dict=True,
	)

	for usage in latest_disk_usages:
		try:
			site: Site = frappe.get_doc("Site", usage.site, for_update=True)
			site.current_database_usage = usage.latest_database_usage
			site.current_disk_usage = usage.latest_disk_usage
			site.check_if_disk_usage_exceeded(save=False)
			site.save()
			frappe.db.commit()
		except frappe.DoesNotExistError:
			frappe.db.rollback()
		except Exception:
			log_error("Site Disk Usage Update Error", usage=usage)
			frappe.db.rollback()


def audit_site_usage_freshness():
	"""Daily defensive check that the sync_benches → Site Usage pipeline is alive.

	`sync_benches` runs hourly_long and is supposed to insert a Site Usage row per
	active site each cycle. If the agent fails silently (the function wraps each
	bench's sync in try/except + log_error), Site Usage stops refreshing and the
	dashboard's Storage/Database panels drift to stale values.

	This check finds active sites whose latest Site Usage record is >24h old (or
	missing entirely) and logs a warning to Error Log so operators can investigate.

	Discovered as a real-world failure mode on 2026-04-29: tabSite Usage was empty
	install-wide for weeks. Manual backfill via site.sync_info() per site fixed it
	immediately. This audit catches that pattern early.
	"""
	stale = frappe.db.sql(
		"""
		SELECT s.name, COALESCE(MAX(u.creation), 'never') AS last_usage
		FROM `tabSite` s
		LEFT JOIN `tabSite Usage` u ON u.site = s.name
		WHERE s.status = 'Active'
		GROUP BY s.name
		HAVING last_usage = 'never' OR MAX(u.creation) < NOW() - INTERVAL 24 HOUR
		""",
		as_dict=True,
	)
	if not stale:
		return

	stale_names = [r["name"] for r in stale]
	frappe.log_error(
		title="Site Usage data is stale",
		message=(
			f"{len(stale_names)} active sites have no Site Usage record in the last 24h.\n"
			f"This usually means the hourly_long `sync_benches` scheduler is failing silently.\n\n"
			f"Affected sites: {stale_names[:20]}{'...' if len(stale_names) > 20 else ''}\n\n"
			f"Recovery: run the manual backfill recipe in docs/runbook/log-server.md "
			f"(loop site.sync_info() across active sites + update_disk_usages())."
		),
	)
