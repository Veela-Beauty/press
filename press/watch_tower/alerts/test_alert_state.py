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


class BrokenCache:
	def get_value(self, *a, **k):
		raise ConnectionError("redis down")

	set_value = delete_value = get_value


class TestAlertState(unittest.TestCase):
	def setUp(self):
		self.c = FakeCache()

	def test_new_until_remembered_then_the_same_set_is_not(self):
		self.assertTrue(st.is_new("server_disk", ["press-ctrl"], self.c))
		self.assertTrue(
			st.is_new("server_disk", ["press-ctrl"], self.c)
		)  # nothing remembered: a refused send retries
		st.remember("server_disk", ["press-ctrl"], self.c)
		self.assertFalse(st.is_new("server_disk", ["press-ctrl"], self.c))

	def test_a_new_member_is_new_a_shrinking_set_is_not(self):
		st.remember("site_reachability", ["x", "y"], self.c)
		self.assertFalse(st.is_new("site_reachability", ["x"], self.c))
		self.assertTrue(st.is_new("site_reachability", ["x", "z"], self.c))

	def test_failing_and_forget(self):
		st.remember("ssh_connectivity", ["s2", "s1"], self.c)
		self.assertEqual(st.failing("ssh_connectivity", self.c), {"s1", "s2"})
		st.forget("ssh_connectivity", self.c)
		self.assertEqual(st.failing("ssh_connectivity", self.c), set())
		self.assertTrue(st.is_new("ssh_connectivity", ["s1"], self.c))

	def test_rules_do_not_share_state_and_the_key_expires(self):
		st.remember("server_disk", ["a"], self.c)
		self.assertTrue(st.is_new("ssh_connectivity", ["a"], self.c))
		self.assertEqual(self.c.ttl["wt:alert_set:server_disk"], st.TTL_SEC)

	def test_redis_down_means_send_now_and_never_raise(self):
		b = BrokenCache()
		self.assertTrue(st.is_new("server_disk", ["a"], b))
		self.assertEqual(st.failing("server_disk", b), set())
		st.remember("server_disk", ["a"], b)
		st.forget("server_disk", b)


if __name__ == "__main__":
	unittest.main()
