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
	# Class-level counter so tokens are unique even when tests run within
	# the same millisecond on a fast box.
	_global_counter = 0

	def setUp(self):
		import time as _time
		import uuid as _uuid
		# Bump the class counter and combine with time + uuid for uniqueness.
		TestMCPRateLimit._global_counter += 1
		self._counter = 0
		self._base_token = (
			f"MCPT-test-rl-{int(_time.time() * 1000)}-"
			f"{TestMCPRateLimit._global_counter}-{_uuid.uuid4().hex[:8]}"
		)

	def _fresh_token(self) -> str:
		"""Return a unique token name for this test invocation."""
		self._counter += 1
		return f"{self._base_token}-{self._counter}"

	def tearDown(self):
		# No persistent state — Redis keys expire on their own (2× window TTL).
		pass

	def test_first_call_passes(self):
		# Should not raise
		check_rate_limit(self._fresh_token(), limit=DEFAULT_LIMIT)

	def test_under_limit_passes(self):
		token = self._fresh_token()
		for _ in range(DEFAULT_LIMIT - 1):
			check_rate_limit(token, limit=DEFAULT_LIMIT)
		# Final call still under limit
		check_rate_limit(token, limit=DEFAULT_LIMIT)

	def test_over_limit_raises(self):
		token = self._fresh_token()
		for _ in range(DEFAULT_LIMIT):
			check_rate_limit(token, limit=DEFAULT_LIMIT)
		with self.assertRaises(RateLimitError):
			check_rate_limit(token, limit=DEFAULT_LIMIT)

	def test_none_token_skips_check(self):
		# Should not raise regardless of how many calls
		for _ in range(DEFAULT_LIMIT * 2):
			check_rate_limit(None, limit=DEFAULT_LIMIT)
