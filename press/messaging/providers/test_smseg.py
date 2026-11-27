"""The smseg adapter (owner 2026-11-27). Network mocked: python3 -m unittest press.messaging.providers.test_smseg -v"""

import unittest
from unittest.mock import MagicMock, patch

from press.messaging import providers

SETTINGS = {"username": "u", "password": "p", "sender_name": "Basher"}


class TestSmseg(unittest.TestCase):
	def test_the_request_smseg_expects(self):
		reply = MagicMock(ok=True, status_code=200, text='{"type":"success"}')
		with patch("requests.post", return_value=reply) as post:
			ok, _detail = providers.send("smseg", SETTINGS, "+201012345678", "code 1")
		self.assertTrue(ok)
		self.assertEqual(post.call_args.args[0], "https://smssmartegypt.com/sms/api/json/")
		self.assertEqual(
			post.call_args.kwargs["json"],
			{
				"username": "u",
				"password": "p",
				"sendername": "Basher",
				"mobiles": "201012345678",
				"message": "code 1",
			},
		)
		self.assertEqual(post.call_args.kwargs["timeout"], 8)

	def test_an_http_error_is_not_ok(self):
		with patch("requests.post", return_value=MagicMock(ok=False, status_code=401, text="bad login")):
			ok, detail = providers.send("smseg", SETTINGS, "+201012345678", "x")
		self.assertFalse(ok)
		self.assertIn("401", detail)

	def test_an_error_body_is_not_ok(self):
		with patch(
			"requests.post",
			return_value=MagicMock(
				ok=True, status_code=200, text='{"type":"error","error":{"msg":"Invalid"}}'
			),
		):
			ok, _detail = providers.send("smseg", SETTINGS, "+201012345678", "x")
		self.assertFalse(ok)

	def test_no_network_is_not_ok(self):
		import requests

		with patch("requests.post", side_effect=requests.ConnectionError("down")):
			ok, _detail = providers.send("smseg", SETTINGS, "+201012345678", "x")
		self.assertFalse(ok)

	def test_an_unknown_type(self):
		ok, detail = providers.send("pigeon", SETTINGS, "+201012345678", "x")
		self.assertFalse(ok)
		self.assertIn("pigeon", detail)
