"""Offline tests for get_2fa_qr_code_url (0.7.92): the 2FA secret is never handed to a session once 2FA is on.

Runs without a bench: the function is lifted out of press/api/account.py and run against a stand-in frappe and pyotp.
Run from the repo root: python3 press/api/tests/test_2fa_secret_offline.py
Inside a bench, where the real frappe is importable, these tests skip themselves so they never replace it.
"""

import ast
import pathlib
import types
import unittest

try:
	import frappe  # noqa: F401

	REAL_FRAPPE = True
except ImportError:
	REAL_FRAPPE = False

ACCOUNT = pathlib.Path(__file__).resolve().parents[1] / "account.py"
USER = "owner@example.com"


class Thrown(Exception):
	pass


class FakeFrappe:
	def __init__(self, row):
		self.row = row  # the User 2FA row: None, or {"enabled": 0|1, "totp_secret": ...}
		self.deleted = []
		self.inserted = []
		self.session = types.SimpleNamespace(user=USER)
		self.db = types.SimpleNamespace(get_value=self._get_value, exists=self._exists)

	@staticmethod
	def whitelist(*args, **kwargs):
		return lambda fn: fn

	def throw(self, message, exc=None):
		raise Thrown(message)

	def _get_value(self, doctype, name, field):
		assert doctype == "User 2FA" and name == USER
		return (self.row or {}).get(field)

	def _exists(self, doctype, name):
		return doctype == "User 2FA" and name == USER and self.row is not None

	def delete_doc(self, doctype, name, **kwargs):
		self.deleted.append((doctype, name, kwargs))
		self.row = None

	def get_doc(self, values):
		fake = self

		class Doc:
			def insert(self):
				fake.inserted.append(values)
				fake.row = {"enabled": 0, "totp_secret": values["totp_secret"]}

		return Doc()


class FakeTOTP:
	def __init__(self, secret):
		self.secret = secret

	def provisioning_uri(self, name, issuer_name):
		return f"otpauth://totp/{issuer_name}:{name}?secret={self.secret}&issuer={issuer_name}"


def load(fake_frappe):
	"""The function from account.py, as written there, bound to the stand-ins."""
	tree = ast.parse(ACCOUNT.read_text())
	fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "get_2fa_qr_code_url")
	module = ast.Module(body=[fn], type_ignores=[])
	counter = iter(range(1, 100))
	pyotp = types.SimpleNamespace(
		random_base32=lambda: f"NEWSECRET{next(counter)}",
		totp=types.SimpleNamespace(TOTP=FakeTOTP),
	)
	namespace = {"frappe": fake_frappe, "pyotp": pyotp}
	exec(compile(module, str(ACCOUNT), "exec"), namespace)
	return namespace["get_2fa_qr_code_url"]


@unittest.skipIf(REAL_FRAPPE, "inside a bench the real frappe is used; run this file offline")
class TestSecretNeverReadBack(unittest.TestCase):
	def test_with_2fa_on_the_secret_is_refused(self):
		fake = FakeFrappe({"enabled": 1, "totp_secret": "OLDSECRET"})
		with self.assertRaises(Thrown) as ctx:
			load(fake)()
		self.assertIn("already on", str(ctx.exception))
		self.assertEqual((fake.deleted, fake.inserted), ([], []))

	def test_a_switched_off_row_is_replaced_by_a_fresh_one(self):
		"""A new row, so its creation date is the date of this link (token_confirm's 'linked before this login')."""
		fake = FakeFrappe({"enabled": 0, "totp_secret": "OLDSECRET"})
		url = load(fake)()
		self.assertEqual([d[:2] for d in fake.deleted], [("User 2FA", USER)])
		self.assertEqual(len(fake.inserted), 1)
		self.assertNotIn("OLDSECRET", url)
		self.assertIn(f"secret={fake.inserted[0]['totp_secret']}", url)

	def test_no_row_yet_makes_one(self):
		fake = FakeFrappe(None)
		url = load(fake)()
		self.assertEqual(fake.deleted, [])
		self.assertEqual(fake.inserted[0]["user"], USER)
		self.assertTrue(url.startswith("otpauth://totp/"))

	def test_each_call_while_off_gives_a_new_secret(self):
		fake = FakeFrappe(None)
		get_url = load(fake)
		first = get_url()
		second = get_url()
		self.assertNotEqual(first, second)
		self.assertEqual(len(fake.deleted), 1, "the second call replaces the row the first one made")


if __name__ == "__main__":
	unittest.main()
