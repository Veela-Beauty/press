"""
Unit tests for archiving a Code Server whose bench may already be archived (0.7.79). No site or database needed.

Run:
  python3 -m unittest press.press.doctype.code_server.test_code_server_archive -v
"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

_frappe = types.ModuleType("frappe")
_frappe.db = MagicMock()
_frappe.get_doc = MagicMock()
_frappe.logger = MagicMock()
_frappe.whitelist = lambda *a, **k: lambda f: f
_document = types.ModuleType("frappe.model.document")
_document.Document = type("Document", (), {})
_naming = types.ModuleType("frappe.model.naming")
_naming.append_number_if_name_exists = MagicMock()
_agent = types.ModuleType("press.agent")
_agent.Agent = MagicMock()
_utils = types.ModuleType("press.utils")
_utils.log_error = MagicMock()
_dns = types.ModuleType("press.utils.dns")
_dns._change_dns_record = MagicMock()
_dns.create_dns_record = MagicMock()
for _name, _mod in {
	"frappe": _frappe,
	"frappe.model": types.ModuleType("frappe.model"),
	"frappe.model.document": _document,
	"frappe.model.naming": _naming,
	"press.agent": _agent,
	"press.utils": _utils,
	"press.utils.dns": _dns,
}.items():
	sys.modules.setdefault(_name, _mod)

from press.press.doctype.code_server import code_server as cs  # noqa: E402
from press.press.doctype.code_server import code_server_archive as ca  # noqa: E402


class TestArchiveOutcome(unittest.TestCase):
	def test_bench_archived_counts_the_archive_job_as_done(self):
		self.assertEqual(ca.archive_outcome("Success", None, True), "Archived")
		self.assertEqual(ca.archive_outcome("Success", "Failure", True), "Archived")
		self.assertEqual(ca.archive_outcome("Failure", None, True), "Broken")
		self.assertEqual(ca.archive_outcome(None, None, True), "Pending")

	def test_bench_active_needs_both_jobs(self):
		self.assertEqual(ca.archive_outcome("Success", "Success", False), "Archived")
		self.assertEqual(ca.archive_outcome("Success", "Failure", False), "Broken")
		self.assertEqual(ca.archive_outcome("Failure", "Success", False), "Broken")
		self.assertEqual(ca.archive_outcome("Success", None, False), "Pending")

	def test_latest_job_status_reads_the_newest_job(self):
		with patch.object(ca, "frappe") as fr:
			fr.db.get_value.return_value = "Success"
			self.assertEqual(ca.latest_job_status(ca.ARCHIVE_JOB, "cs1"), "Success")
			kwargs = fr.db.get_value.call_args.kwargs
			self.assertEqual(kwargs["order_by"], "creation desc")
			self.assertTrue(kwargs["for_update"])

	def test_bench_is_archived_never_queries_without_a_name(self):
		with patch.object(ca, "frappe") as fr:
			self.assertFalse(ca.bench_is_archived(None))
			self.assertFalse(ca.bench_is_archived(""))
			fr.db.get_value.assert_not_called()


def _code_server():
	doc = object.__new__(cs.CodeServer)
	doc.name, doc.bench, doc.server, doc.proxy_server, doc.domain = (
		"code-b1.example.com",
		"b1",
		"srv",
		"proxy",
		"dom",
	)
	doc.status = "Archived"
	doc.save = MagicMock()
	return doc


class TestArchive(unittest.TestCase):
	def _run(self, bench_archived, dns_error=None):
		doc = _code_server()
		agent = MagicMock()
		dns = MagicMock(side_effect=dns_error)
		with (
			patch.object(cs, "Agent", return_value=agent) as agent_cls,
			patch.object(cs, "_change_dns_record", dns),
			patch.object(cs, "bench_is_archived", return_value=bench_archived),
			patch.object(cs, "log_error") as log_error,
			patch.object(cs, "frappe") as fr,
		):
			doc.archive()
		return doc, agent, agent_cls, dns, log_error, fr

	def test_archived_bench_skips_the_agent_archive(self):
		doc, agent, agent_cls, dns, log_error, _ = self._run(bench_archived=True)
		dns.assert_called_once()
		agent.remove_upstream_file.assert_called_once_with(server="srv", code_server="code-b1.example.com")
		agent.archive_code_server.assert_not_called()
		self.assertEqual(agent_cls.call_count, 1)
		doc.save.assert_called_once()
		self.assertEqual(doc.status, "Pending")
		log_error.assert_not_called()

	def test_active_bench_still_asks_the_agent(self):
		_, agent, agent_cls, _, log_error, _ = self._run(bench_archived=False)
		agent.remove_upstream_file.assert_called_once()
		agent.archive_code_server.assert_called_once_with("b1", "code-b1.example.com")
		self.assertEqual(agent_cls.call_count, 2)
		log_error.assert_not_called()



class TestArchiveJobUpdate(unittest.TestCase):
	def _run(self, job_type, status, bench_status, other_status):
		def get_value(doctype, *args, **kwargs):
			return {"Code Server": "b1", "Bench": bench_status, "Agent Job": other_status}[doctype]

		job = types.SimpleNamespace(job_type=job_type, status=status, code_server="cs1")
		with (
			patch.object(cs, "frappe") as fr,
			patch.object(ca, "frappe") as fr_ca,
			patch.object(cs, "release_name") as release,
		):
			fr.db.get_value.side_effect = get_value
			fr_ca.db.get_value.side_effect = get_value
			cs.process_archive_code_server_job_update(job)
		return fr.db.set_value, release

	def test_upstream_done_on_an_archived_bench_archives_and_frees_the_name(self):
		set_value, release = self._run(ca.UPSTREAM_JOB, "Success", "Archived", "Failure")
		set_value.assert_called_once_with("Code Server", "cs1", "status", "Archived")
		release.assert_called_once_with("cs1")

	def test_archive_job_failure_on_an_active_bench_is_broken(self):
		set_value, release = self._run(ca.ARCHIVE_JOB, "Failure", "Active", "Success")
		set_value.assert_called_once_with("Code Server", "cs1", "status", "Broken")
		release.assert_not_called()

	def test_one_job_still_running_on_an_active_bench_stays_pending(self):
		set_value, release = self._run(ca.UPSTREAM_JOB, "Success", "Active", None)
		set_value.assert_called_once_with("Code Server", "cs1", "status", "Pending")
		release.assert_not_called()

	def test_a_record_already_renamed_by_the_other_callback_is_left_alone(self):
		job = types.SimpleNamespace(job_type=ca.ARCHIVE_JOB, status="Failure", code_server="cs1")
		with patch.object(cs, "frappe") as fr, patch.object(cs, "release_name") as release:
			fr.db.get_value.return_value = None
			cs.process_archive_code_server_job_update(job)
		fr.db.set_value.assert_not_called()
		release.assert_not_called()


if __name__ == "__main__":
	unittest.main()
