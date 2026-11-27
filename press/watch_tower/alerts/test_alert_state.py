"""Alert on change (0.7.85), pinned on a fake Redis key store: no bench, no network. Runs without a bench:
python3 -m unittest test_alert_state (from this folder)."""

import importlib.util
import pathlib
import unittest

_spec = importlib.util.spec_from_file_location(
	"alert_state", pathlib.Path(__file__).with_name("alert_state.py")
)
st = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(st)


class FakeCache:
	"""The three key calls alert_state.py makes on frappe.cache()."""

	def __init__(self):
		self.data, self.ttl = {}, {}

	def get_value(self, key, expires=False):
		return self.data.get(key)

	def set_value(self, key, value, expires_in_sec=None):
		self.data[key], self.ttl[key] = value, expires_in_sec

	def delete_value(self, key):
		self.data.pop(key, None)


class TestAlertState(unittest.TestCase):
	def setUp(self):
		self.c = FakeCache()

	def test_first_failure_is_new_and_the_same_set_is_not(self):
		self.assertTrue(st.is_new("server_disk", ["press-ctrl:85"], self.c))
		self.assertFalse(st.is_new("server_disk", ["press-ctrl:85"], self.c))
		self.assertFalse(st.is_new("server_disk", ["press-ctrl:85"], self.c))

	def test_a_new_server_or_a_higher_band_is_new_a_shrinking_set_is_not(self):
		st.is_new("server_disk", ["a:85", "b:85"], self.c)
		self.assertFalse(st.is_new("server_disk", ["a:85"], self.c))
		self.assertTrue(st.is_new("server_disk", ["a:95"], self.c))
		self.assertTrue(st.is_new("server_disk", ["a:95", "c:85"], self.c))

	def test_an_entity_that_recovered_and_fails_again_is_new(self):
		st.is_new("site_reachability", ["x", "y"], self.c)
		st.is_new("site_reachability", ["x"], self.c)
		self.assertTrue(st.is_new("site_reachability", ["x", "y"], self.c))

	def test_cleared_returns_the_failing_set_once_and_then_nothing(self):
		st.is_new("ssh_connectivity", ["s2", "s1"], self.c)
		self.assertEqual(st.cleared("ssh_connectivity", self.c), ["s1", "s2"])
		self.assertEqual(st.cleared("ssh_connectivity", self.c), [])
		self.assertTrue(st.is_new("ssh_connectivity", ["s1"], self.c))

	def test_nothing_failing_before_means_nothing_cleared(self):
		self.assertEqual(st.cleared("site_reachability", self.c), [])

	def test_rules_do_not_share_state_and_the_key_expires(self):
		st.is_new("server_disk", ["a:85"], self.c)
		self.assertTrue(st.is_new("ssh_connectivity", ["a"], self.c))
		self.assertEqual(self.c.ttl["wt:alert_set:server_disk"], st.TTL_SEC)


if __name__ == "__main__":
	unittest.main()
