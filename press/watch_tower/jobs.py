"""
Watch Tower Scheduler Jobs.

Entry points for frappe scheduler_events in hooks.py.
Each job fetches enabled rules for its frequency and enqueues them.

Press-specific extensions (health_report, press_alerts, site_lifecycle,
site_activity_sync) self-skip when the `Site` doctype doesn't exist.
This lets Watch Tower run cleanly on a regular ERPNext site.
"""
import frappe

from press.watch_tower import _nolicense as licensing


def _is_press_site():
	"""True when this site has Press installed (Site doctype exists)."""
	return bool(frappe.db.exists("DocType", "Site"))


def run_hourly_watch_tower():
	"""Hourly Watch Tower rule evaluation."""
	if not licensing.is_allowed("watch_tower"):
		return
	from .engine import run_scheduled_rules
	run_scheduled_rules("Hourly")


def run_daily_watch_tower():
	"""Daily Watch Tower rule evaluation. The health report moved to run_morning_report (0.7.77)."""
	from .engine import run_scheduled_rules
	if licensing.is_allowed("watch_tower"):
		run_scheduled_rules("Daily")


def run_morning_report():
	"""08:00: the (Press-only) health report with the day's kept alerts (alerts/digest.py). It ran at midnight inside
	run_daily_watch_tower before 0.7.77."""
	if _is_press_site():
		from .health_report import send_health_report
		send_health_report()


def run_weekly_watch_tower():
	"""Weekly Watch Tower rule evaluation."""
	if not licensing.is_allowed("watch_tower"):
		return
	from .engine import run_scheduled_rules
	run_scheduled_rules("Weekly")
