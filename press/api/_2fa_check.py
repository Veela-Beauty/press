"""Quick admin probe: check 2FA state for a user."""
import frappe


def check(user="eng.elgogary@gmail.com"):
	exists = frappe.db.exists("User 2FA", user)
	if not exists:
		return f"NO_2FA_RECORD for {user}"
	row = frappe.db.get_value(
		"User 2FA", user, ["enabled", "last_verified_at"], as_dict=True
	)
	return f"USER_2FA: enabled={row.enabled} last_verified={row.last_verified_at}"


def disable(user="eng.elgogary@gmail.com"):
	if not frappe.db.exists("User 2FA", user):
		return f"NO_2FA_RECORD for {user} — already off"
	frappe.db.set_value("User 2FA", user, "enabled", 0)
	frappe.db.commit()
	return f"DISABLED_2FA for {user}"


def list_all():
	rows = frappe.get_all("User 2FA", fields=["name", "user", "enabled"])
	return rows
