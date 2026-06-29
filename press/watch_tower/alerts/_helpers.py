"""Shared constants and utilities for Watch Tower alert modules."""
import hashlib
import frappe
from frappe.utils import now_datetime

TABLE = 'border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;"'
TH_BG = 'style="background:#f8fafc"'
SITE_URL = "https://autodeploypanel.mvpstorm.com"

# Error methods that are noise -  CSS parsing, translation, known harmless
NOISE_PATTERNS = (
	"PropertyValue",
	"CSSStyleDeclaration",
	"SelectorList",
	"COLOR_VALUE",
	"Error in translation file",
	"cssutils",
)

ERROR_SPIKE_THRESHOLD = 100


def esc(text):
	"""HTML-escape text for email bodies."""
	return (
		str(text)
		.replace("&", "&amp;")
		.replace("<", "&lt;")
		.replace(">", "&gt;")
		.replace('"', "&quot;")
	)


def ts_now():
	"""Return formatted timestamp string."""
	return now_datetime().strftime("%Y-%m-%d %H:%M")


PRESS_CTRL_IP = "89.167.116.92"


def ssh_cmd(ip, cmd, timeout=15):
	"""
	Run a command on a remote server via SSH. Returns (success, stdout, stderr).

	Security: cmd must be a hardcoded literal string, never constructed from
	user input or DB values. This function passes cmd as a shell string.
	"""
	import subprocess
	try:
		if ip == PRESS_CTRL_IP:
			result = subprocess.run(
				["bash", "-c", cmd],
				capture_output=True, text=True, timeout=timeout,
			)
		else:
			result = subprocess.run(
				["ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
				 f"root@{ip}", cmd],
				capture_output=True, text=True, timeout=timeout,
			)
		return result.returncode == 0 or bool(result.stdout.strip()), result.stdout, result.stderr
	except subprocess.TimeoutExpired:
		return False, "", "SSH timeout"
	except Exception as e:
		return False, "", str(e)[:200]


def get_all_servers():
	"""Get all active Press servers + press-ctrl."""
	servers = frappe.db.sql("""
		SELECT name, ip
		FROM tabServer
		WHERE status = 'Active' AND ip IS NOT NULL AND ip != ''
	""", as_dict=True)
	servers.append({"name": "press-ctrl", "ip": PRESS_CTRL_IP})
	return servers


_ALERT_THROTTLE_TTL_SEC = 6 * 60 * 60  # 6h
_ALERT_THROTTLE_MAX_SENDS = 3


def should_send_alert(rule_key: str, fingerprint: str) -> bool:
	"""Returns True if we should email this alert; False if already sent 3 times.

	Stops alert spam for sustained outages (e.g. one site down for hours
	produces one email per cron tick = inbox flood). After 3 emails for the
	same (rule, fingerprint), suppress for 6h. If the failing entities change
	(different sites go down) the fingerprint changes and a new 3-email
	series begins. Backed by Frappe cache (Redis), survives worker restarts.
	"""
	signature = hashlib.sha1(f"{rule_key}|{fingerprint}".encode()).hexdigest()[:16]
	key = f"wt:alert_count:{signature}"
	cache = frappe.cache()
	raw = cache.get_value(key, expires=True)  # force redis read; local cache is stale for expiring keys
	count = int(raw) if raw else 0
	if count >= _ALERT_THROTTLE_MAX_SENDS:
		return False
	cache.set_value(key, count + 1, expires_in_sec=_ALERT_THROTTLE_TTL_SEC)
	return True


def cleanup_old_error_logs():
	"""Delete error logs older than 7 days. Called by scheduler (daily)."""
	frappe.db.sql("""
		DELETE FROM `tabError Log`
		WHERE creation < NOW() - INTERVAL 7 DAY
		LIMIT 5000
	""")
	frappe.db.commit()
	frappe.logger().info("Watch Tower: cleaned up error logs older than 7 days")
