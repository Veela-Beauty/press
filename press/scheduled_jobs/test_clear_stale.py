"""Tests for clear_stale_agent_request_failures.execute()."""

import datetime as dt
import sys
import types
from unittest.mock import MagicMock, patch

# Inject a fake `frappe` module before importing the SUT, so the SUT's
# `import frappe` resolves to our mock and the test stays hermetic.
fake_frappe = types.ModuleType("frappe")
fake_frappe.get_all = MagicMock()
fake_frappe.db = MagicMock()
fake_frappe.delete_doc = MagicMock()
fake_frappe.utils = types.SimpleNamespace(
    add_to_date=lambda _, minutes: dt.datetime.utcnow() + dt.timedelta(minutes=minutes)
)
sys.modules["frappe"] = fake_frappe

# Same trick for press.agent.
fake_press_agent = types.ModuleType("press.agent")
fake_press_agent.Agent = MagicMock()
sys.modules["press.agent"] = fake_press_agent
sys.modules.setdefault("press", types.ModuleType("press"))

from press.scheduled_jobs import clear_stale_agent_request_failures as SUT  # noqa: E402


def _row(name="r1", server="press-f1.sandbox.mvpstorm.com", server_type="Server"):
    return types.SimpleNamespace(name=name, server=server, server_type=server_type)


def setup_function(_):
    fake_frappe.get_all.reset_mock()
    fake_frappe.delete_doc.reset_mock()
    fake_frappe.db.exists.reset_mock()


def test_no_stale_rows_does_nothing():
    fake_frappe.get_all.return_value = []
    SUT.execute()
    fake_frappe.delete_doc.assert_not_called()


def test_alive_server_clears_row():
    fake_frappe.get_all.return_value = [_row()]
    fake_frappe.db.exists.return_value = True
    with patch.object(SUT, "_is_agent_alive", return_value=True):
        SUT.execute()
    fake_frappe.delete_doc.assert_called_once_with("Agent Request Failure", "r1")


def test_dead_server_keeps_row():
    fake_frappe.get_all.return_value = [_row()]
    fake_frappe.db.exists.return_value = True
    with patch.object(SUT, "_is_agent_alive", return_value=False):
        SUT.execute()
    fake_frappe.delete_doc.assert_not_called()


def test_orphaned_row_deleted_even_if_server_gone():
    fake_frappe.get_all.return_value = [_row(server="ghost.example.com")]
    fake_frappe.db.exists.return_value = False
    SUT.execute()
    fake_frappe.delete_doc.assert_called_once_with("Agent Request Failure", "r1")
