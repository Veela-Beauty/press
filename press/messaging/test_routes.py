"""Routes per country for SMS codes (owner 2026-11-27). No site needed: python3 -m unittest press.messaging.test_routes -v"""

import unittest

from press.messaging import routes


class TestRouteFor(unittest.TestCase):
	def test_a_listed_country(self):
		self.assertEqual(
			routes.route_for("SA", routes.DEFAULT_ROUTES), {"provider": "Google Firebase", "price": 0.18}
		)

	def test_an_unlisted_country_takes_the_default(self):
		self.assertEqual(routes.route_for("FR", routes.DEFAULT_ROUTES)["price"], 0.20)

	def test_lower_case_and_none(self):
		self.assertEqual(routes.route_for("eg", routes.DEFAULT_ROUTES)["price"], 0.13)
		self.assertEqual(routes.route_for(None, routes.DEFAULT_ROUTES)["price"], 0.20)

	def test_mode(self):
		self.assertEqual(routes.mode_of("Google Firebase"), "firebase")
		self.assertEqual(routes.mode_of("smseg Egypt"), "server")


class TestParse(unittest.TestCase):
	def test_empty_or_broken_gives_the_defaults(self):
		self.assertEqual(routes.parse(None), routes.DEFAULT_ROUTES)
		self.assertEqual(routes.parse("{not json"), routes.DEFAULT_ROUTES)

	def test_a_json_string(self):
		self.assertEqual(
			routes.parse('{"default": {"provider": "Google Firebase", "price": 0.3}}')["default"]["price"],
			0.3,
		)


class TestClean(unittest.TestCase):
	def test_rows_become_a_route_table(self):
		table = routes.clean(
			[
				{"country": "sa", "provider": "Google Firebase", "price": "0.18"},
				{"country": "default", "provider": "Google Firebase", "price": 0.2},
			]
		)
		self.assertEqual(
			table,
			{
				"SA": {"provider": "Google Firebase", "price": 0.18},
				"default": {"provider": "Google Firebase", "price": 0.2},
			},
		)

	def test_a_negative_or_missing_price_is_refused(self):
		with self.assertRaises(ValueError):
			routes.clean([{"country": "default", "provider": "Google Firebase", "price": -1}])
		with self.assertRaises(ValueError):
			routes.clean([{"country": "default", "provider": "Google Firebase", "price": ""}])

	def test_a_table_without_default_is_refused(self):
		with self.assertRaises(ValueError):
			routes.clean([{"country": "SA", "provider": "Google Firebase", "price": 0.18}])
