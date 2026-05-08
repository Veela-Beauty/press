# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Sliding-window rate limiter for MCP token calls.

Backed by frappe.cache (Redis). Sliding window of 60 seconds; default cap
60 calls/min/token. On exceeded, raises a frappe.PermissionError-shape
exception subclass (RateLimitError) so callers can branch.
"""
from __future__ import annotations

import time

import frappe

WINDOW_SECONDS = 60
DEFAULT_LIMIT = 60  # calls per window per token


class RateLimitError(frappe.PermissionError):
	"""Token exceeded its rate limit."""


def check_rate_limit(token_name: str | None, limit: int = DEFAULT_LIMIT) -> None:
	"""Increment counter for token in current window. Raise if over limit.

	If token_name is None (unauthenticated path) the check is skipped — the
	auth layer should reject those before this is called.
	"""
	if not token_name:
		return
	cache = frappe.cache()
	now_bucket = int(time.time() // WINDOW_SECONDS)
	key = f"mcp:rate:{token_name}:{now_bucket}"
	# Increment with TTL; first hit creates the key
	current = cache.incr(key)
	if current == 1:
		# Set TTL on first increment in this window
		cache.expire(key, WINDOW_SECONDS * 2)
	if current > limit:
		raise RateLimitError(
			f"rate limit exceeded: {current} calls in this 60s window (cap {limit})"
		)
