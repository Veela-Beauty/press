"""press.overrides.get_password never reads back an SMS provider's login (0.7.81): the developers are System Managers on
Press, and a System Manager can otherwise decrypt any Password field. No site needed:
  /home/eslam/.venvs/press-tests/bin/python -m unittest press.messaging.test_provider_login_guard -v

The stubs live only while press.overrides is imported, so other stubbed test modules in the same run keep their own.
"""

import importlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


def _module(name, **attrs):
	mod = types.ModuleType(name)
	for key, value in attrs.items():
		setattr(mod, key, value)
	return mod


def _raise(msg, exc=Exception):
	raise exc(msg)


PermissionError_ = type("PermissionError", (Exception,), {})
CLIENT = _module("frappe.client", get_password=MagicMock(return_value="ok"))
STUBS = {
	"frappe": _module(
		"frappe",
		whitelist=lambda *a, **k: lambda f: f,
		PermissionError=PermissionError_,
		throw=MagicMock(side_effect=_raise),
	),
	"frappe.core": _module("frappe.core"),
	"frappe.core.doctype": _module("frappe.core.doctype"),
	"frappe.core.doctype.user": _module("frappe.core.doctype.user"),
	"frappe.core.doctype.user.user": _module("frappe.core.doctype.user.user", User=type("User", (), {})),
	"frappe.handler": _module("frappe.handler", is_whitelisted=MagicMock()),
	"frappe.utils": _module("frappe.utils", cint=int),
	"frappe.client": CLIENT,
	"press.access": _module("press.access"),
	"press.access.support_access": _module("press.access.support_access", has_support_access=MagicMock()),
	"press.runner": _module("press.runner", constants=MagicMock()),
	"press.utils": _module("press.utils", _get_current_team=MagicMock(), _system_user=MagicMock()),
}


class TestProviderLoginGuard(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		with patch.dict(sys.modules, STUBS):
			sys.modules.pop("press.overrides", None)
			cls.overrides = importlib.import_module("press.overrides")
		sys.modules.pop("press.overrides", None)

	def call(self, doctype):
		with patch.dict(sys.modules, {"frappe.client": CLIENT}):
			return self.overrides.get_password(doctype, "X-1", "password")

	def test_an_sms_provider_password_is_refused(self):
		with self.assertRaises(PermissionError_):
			self.call("SMS Provider")

	def test_an_mcp_token_is_still_refused(self):
		with self.assertRaises(PermissionError_):
			self.call("Press MCP Token")

	def test_other_doctypes_pass_through(self):
		self.assertEqual(self.call("Server"), "ok")
