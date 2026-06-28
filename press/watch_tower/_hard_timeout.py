"""Hard wall-clock timeout helpers -  used by Watch Tower to prevent
network-bound jobs from hanging the worker queue.

The standard library's `requests.get(timeout=N)` and `smtplib.SMTP(timeout=N)`
apply per-recv() timeouts: a server trickling bytes can keep the timer
resetting, so a "10s timeout" can hang for minutes. signal.SIGALRM gives
a true wall-clock cap.

USAGE:
    with hard_timeout(15):
        requests.get("https://slow-site.com/api")
    # If still inside after 15s -> raises HardTimeoutError, releases worker.

LIMITATIONS:
   - Only works in the main thread of a process (signal handlers are
      process-wide). RQ workers run jobs in the main thread of a forked
      child process, so this is fine for our use case.
   - Nesting is intentionally NOT supported -  each call replaces any
      prior alarm. Don't nest hard_timeout blocks.
"""
from __future__ import annotations

import signal
from contextlib import contextmanager


class HardTimeoutError(Exception):
	"""Raised when a hard_timeout block exceeds its wall-clock limit."""


def _alarm_handler(signum, frame):
	raise HardTimeoutError(f"Hard timeout exceeded (SIGALRM after seconds)")


@contextmanager
def hard_timeout(seconds: int):
	"""Context manager that raises HardTimeoutError if body runs > N seconds.

	No-op when seconds is 0 or negative. Restores any previous SIGALRM
	handler on exit (whether body completes, returns, or raises).
	"""
	if seconds <= 0:
		yield
		return

	previous_handler = signal.signal(signal.SIGALRM, _alarm_handler)
	previous_remaining = signal.alarm(seconds)
	try:
		yield
	finally:
		signal.alarm(0)
		signal.signal(signal.SIGALRM, previous_handler)
		# Restore any prior alarm that was running before we entered
		if previous_remaining > 0:
			signal.alarm(previous_remaining)
