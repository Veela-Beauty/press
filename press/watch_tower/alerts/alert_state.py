"""Which servers or sites an alert already emailed about (0.7.85). A disk, SSH or site-down alert emails when a server or
site joins the failing set; while the same set keeps failing the hourly repeat goes to the 08:00 digest; when nothing
fails any more the caller sends one "cleared" email. Before this a new count or error text started a new series of
three emails (62 of the 263 alerts Brevo held on 27 Nov 2026)."""

KEY = "wt:alert_set:{}"
TTL_SEC = 7 * 24 * 60 * 60


def _cache(cache):
	if cache is not None:
		return cache
	import frappe

	return frappe.cache()


def is_new(rule_key, entities, cache=None):
	"""True when one of `entities` was not failing at the last check. Keeps this check's set for the next one."""
	c = _cache(cache)
	key = KEY.format(rule_key)
	before = set(c.get_value(key, expires=True) or [])
	now = {str(e) for e in entities}
	c.set_value(key, sorted(now), expires_in_sec=TTL_SEC)
	return bool(now - before)


def cleared(rule_key, cache=None):
	"""What was failing when everything is fine again: returned once, then forgotten (empty when nothing was)."""
	c = _cache(cache)
	key = KEY.format(rule_key)
	before = c.get_value(key, expires=True) or []
	if before:
		c.delete_value(key)
	return sorted(before)
