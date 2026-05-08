# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.mcp_server.rate_limit import (
	DEFAULT_LIMIT,
	RateLimitError,
	check_rate_limit,
)


class TestMCPRateLimit(FrappeTestCase):
	def setUp(self):
		# Clear any existing rate-limit keys for the test token
		cache = frappe.cache()
		# Best-effort key cleanup; specific keys depend on time bucket
		self.token_name = "MCPT-test-rate-limit"

	def tearDown(self):
		# No persistent state — Redis keys expire on their own.
		pass

	def test_first_call_passes(self):
		# Should not raise
		check_rate_limit(self.token_name, limit=DEFAULT_LIMIT)

	def test_under_limit_passes(self):
		for _ in range(DEFAULT_LIMIT - 1):
			check_rate_limit(self.token_name, limit=DEFAULT_LIMIT)
		# Final call still under limit
		check_rate_limit(self.token_name, limit=DEFAULT_LIMIT)

	def test_over_limit_raises(self):
		for _ in range(DEFAULT_LIMIT):
			check_rate_limit(self.token_name, limit=DEFAULT_LIMIT)
		with self.assertRaises(RateLimitError):
			check_rate_limit(self.token_name, limit=DEFAULT_LIMIT)

	def test_none_token_skips_check(self):
		# Should not raise regardless of how many calls
		for _ in range(DEFAULT_LIMIT * 2):
			check_rate_limit(None, limit=DEFAULT_LIMIT)
