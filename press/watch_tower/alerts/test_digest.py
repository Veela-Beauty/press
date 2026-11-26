"""Daily alert digest (0.7.77), pinned on a fake Redis list: no bench, no network. Runs without a bench:
python3 -m unittest test_digest (from this folder)."""

import html as _html
import importlib.util
import pathlib
import unittest

_spec = importlib.util.spec_from_file_location("digest", pathlib.Path(__file__).with_name("digest.py"))
dg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dg)


class FakeList:
	"""The three list calls digest.py makes on frappe.cache(), with Redis index rules."""

	def __init__(self):
		self.items = []

	def rpush(self, key, value):
		self.items.append(value)

	def lrange(self, key, start, stop):
		return list(self.items[start : None if stop == -1 else stop + 1])

	def ltrim(self, key, start, stop):
		n = len(self.items)
		start = max(n + start, 0) if start < 0 else start
		self.items = self.items[start : None if stop == -1 else stop + 1]


class TestDigest(unittest.TestCase):
	def test_counts_dates_and_times_do_not_split_one_alert_type(self):
		a = dg.kind_of("⚠️ 17 scheduled job failure(s) - 2026-11-24 21:00")
		b = dg.kind_of("⚠️ 16 scheduled job failure(s) - 2026-11-25 05:01")
		self.assertEqual(a, b)
		self.assertEqual(
			dg.kind_of("\U0001f511 GitHub Token Alert — 2026-11-25 00:04"), "\U0001f511 GitHub Token Alert"
		)

	def test_group_counts_and_keeps_the_latest_subject_most_frequent_first(self):
		items = [
			{"subject": "17 scheduled job failure(s) - 2026-11-24 21:00", "at": "2026-11-24 21:00"},
			{"subject": "Disk Alert: 2 server(s) above 85%", "at": "2026-11-24 22:01"},
			{"subject": "18 scheduled job failure(s) - 2026-11-24 20:00", "at": "2026-11-24 20:00"},
			{"subject": "16 scheduled job failure(s) - 2026-11-25 05:00", "at": "2026-11-25 05:00"},
		]
		rows = dg.group(items)
		self.assertEqual([r["times"] for r in rows], [3, 1])
		self.assertEqual(rows[0]["first"], "2026-11-24 20:00")
		self.assertEqual(rows[0]["last"], "2026-11-25 05:00")
		self.assertEqual(rows[0]["subject"], "16 scheduled job failure(s) - 2026-11-25 05:00")

	def test_clear_drops_only_what_the_report_showed(self):
		c = FakeList()
		dg.add("A 1", "2026-11-26 07:00", cache=c)
		dg.add("A 2", "2026-11-26 07:30", cache=c)
		shown = dg.peek(cache=c)
		dg.add("B late", "2026-11-26 08:00", cache=c)  # arrives while the report is being sent
		dg.clear(len(shown), cache=c)
		self.assertEqual([x["subject"] for x in dg.peek(cache=c)], ["B late"])

	def test_the_list_is_capped_newest_kept(self):
		c = FakeList()
		for i in range(dg.MAX_KEPT + 5):
			dg.add(f"alert {i}", "2026-11-26 07:00", cache=c)
		kept = dg.peek(cache=c)
		self.assertEqual(len(kept), dg.MAX_KEPT)
		self.assertEqual(kept[-1]["subject"], f"alert {dg.MAX_KEPT + 4}")

	def test_section_is_empty_when_nothing_was_kept_and_escapes_subjects(self):
		self.assertEqual(dg.html([], "", "", _html.escape), "")
		out = dg.html([{"subject": "<b>x</b> site down", "at": "2026-11-26 07:00"}], "", "", _html.escape)
		self.assertIn("&lt;b&gt;x&lt;/b&gt;", out)
		self.assertIn("11-26 07:00", out)

	def test_a_broken_entry_is_skipped(self):
		c = FakeList()
		c.items = ["not json", '{"subject": "ok", "at": "2026-11-26 07:00"}']
		self.assertEqual([x["subject"] for x in dg.peek(cache=c)], ["ok"])


if __name__ == "__main__":
	unittest.main()
