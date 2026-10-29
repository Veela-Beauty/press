# Every path into a confidential site must hit the PIN gate, not only the dashboard button.
from unittest.mock import patch

import frappe
from frappe.model.naming import make_autoname
from frappe.tests.utils import FrappeTestCase

from press.api.site import login as desk_login
from press.press.doctype.site.site import Site
from press.press.doctype.site.test_site import create_test_site


class TestConfidentialSiteAccess(FrappeTestCase):
	def setUp(self):
		frappe.db.set_single_value("Press Settings", "admin_login_pin", "1234")
		self.site = create_test_site(make_autoname("confacc-.#####"))
		self.site.db_set("is_confidential", 1)
		self.site.reload()
		r = frappe.cache()
		for k in r.keys("confidential_pin_fail:*"):
			r.delete(k)

	def test_login_without_pin_is_refused(self):
		with patch.object(Site, "get_login_sid", return_value="SID") as sid, patch.object(
			Site, "_send_wrong_pin_alert"
		):
			with self.assertRaises(frappe.ValidationError):
				self.site.login(reason="t")
		sid.assert_not_called()

	def test_login_with_pin_passes(self):
		with patch.object(Site, "get_login_sid", return_value="SID"):
			self.assertEqual(self.site.login(reason="t", pin="1234"), "SID")

	def test_desk_api_login_needs_pin(self):
		with patch.object(Site, "get_login_sid", return_value="SID"), patch.object(
			Site, "_send_wrong_pin_alert"
		):
			with self.assertRaises(frappe.ValidationError):
				desk_login(self.site.name, reason="t")
			self.assertEqual(desk_login(self.site.name, reason="t", pin="1234")["sid"], "SID")

	def test_login_as_team_refused_without_a_strike(self):
		# Without the team user it throws "No additional system user" and proves nothing.
		self.site.db_set("additional_system_user_created", 1)
		with patch.object(Site, "get_login_sid", return_value="SID") as sid:
			with self.assertRaises(frappe.ValidationError):
				self.site.login_as_team(reason="t")
		sid.assert_not_called()
		self.assertFalse(frappe.cache().get(self._fail_key()))

	def test_login_as_admin_wrong_pin_counts_once(self):
		with patch.object(Site, "get_login_sid", return_value="SID"), patch.object(
			Site, "_send_wrong_pin_alert"
		):
			with self.assertRaises(frappe.ValidationError):
				self.site.login_as_admin(reason="t", pin="0000")
			self.assertEqual(int(frappe.cache().get(self._fail_key())), 1)
			url = self.site.login_as_admin(reason="t", pin="1234")
		self.assertTrue(url.endswith("/app?sid=SID"))

	def test_show_admin_password_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.site.show_admin_password()

	def test_form_load_does_not_send_pin(self):
		from frappe.desk.form.load import getdoc

		getdoc("Site", self.site.name)
		self.assertFalse(frappe.response.docs[-1].get("confidential_admin_pin"))

	def _fail_key(self):
		return f"confidential_pin_fail:{frappe.session.user}:{self.site.name}"

	def test_non_confidential_login_needs_no_pin(self):
		self.site.db_set("is_confidential", 0)
		self.site.reload()
		with patch.object(Site, "get_login_sid", return_value="SID"):
			self.assertEqual(self.site.login(reason="t"), "SID")
