"""Which servers or sites an alert already emailed about (0.7.85). A disk, SSH or site-down alert emails when a server or
site joins the failing set; while the same set keeps failing the hourly repeat goes to the 08:00 digest; when nothing
fails any more the caller sends one "cleared" email. Before this a new count or error text started a new series of
three emails (62 of the 263 alerts Brevo held on 27 Nov 2026).

The caller remembers a set only after its email went out, and forgets it only after the "cleared" email went out, so
a refused send is tried again at the next check. When Redis cannot be read an alert counts as new: an alert sent twice
beats an alert lost."""

KEY = "wt:alert_set:{}"
TTL_SEC = 7 * 24 * 60 * 60


def _cache(cache):
	if cache is not None:
		return cache
	import frappe

	return frappe.cache()


def _log(err):
	try:
		import frappe

		frappe.logger("watch_tower").error(f"alert_state: {type(err).__name__}: {err}")
	except Exception:
		pass


def failing(rule_key, cache=None):
	"""The set this rule last emailed about (empty when none, or when Redis cannot be read)."""
	try:
		return set(_cache(cache).get_value(KEY.format(rule_key), expires=True) or [])
	except Exception as err:
		_log(err)
		return set()


def is_new(rule_key, entities, cache=None):
	"""True when one of `entities` is not in the failing set, or when Redis cannot be read."""
	try:
		before = set(_cache(cache).get_value(KEY.format(rule_key), expires=True) or [])
	except Exception as err:
		_log(err)
		return True
	return bool({str(x) for x in entities} - before)


def remember(rule_key, entities, cache=None):
	"""Keep `entities` as the failing set for the next check."""
	try:
		_cache(cache).set_value(
			KEY.format(rule_key), sorted({str(x) for x in entities}), expires_in_sec=TTL_SEC
		)
	except Exception as err:
		_log(err)


def forget(rule_key, cache=None):
	"""Drop the failing set once the "cleared" email went out."""
	try:
		_cache(cache).delete_value(KEY.format(rule_key))
	except Exception as err:
		_log(err)
