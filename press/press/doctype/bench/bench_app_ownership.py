"""
Determine whether the current team owns an app on a bench (i.e. has push access
to the App Source's GitHub repo). Used by the dashboard to decide whether to
show the Push to GitHub button on the Site Dev tab and to refuse push attempts
on upstream apps before they fail at GitHub auth.
"""
import frappe


def is_app_owned_by_current_team(bench_name: str, app: str) -> bool:
	"""
	True iff the App Source for (bench, app) belongs to the current team
	AND is not marked public. Public app sources (frappe, erpnext, hrms,
	upstream payments) are read-only from any team's perspective.
	"""
	source = frappe.db.get_value(
		"Bench App",
		{"parent": bench_name, "app": app},
		"source",
	)
	if not source:
		return False
	src_team, src_public = frappe.db.get_value(
		"App Source",
		source,
		["team", "public"],
	) or (None, None)
	if src_public:
		return False
	try:
		from press.utils import get_current_team
		current_team = get_current_team()
	except Exception:
		return False
	return src_team == current_team
