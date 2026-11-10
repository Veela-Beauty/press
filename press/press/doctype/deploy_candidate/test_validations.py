from unittest import TestCase

from press.press.doctype.deploy_candidate.validations import check_version


class TestCheckVersion(TestCase):
	def test_node_engines_with_or_range(self):
		# frappe/crm frontend/package.json, 2026-11: failed with "Invalid simple block".
		spec = "^20.19.0 || >=22.12.0"
		self.assertTrue(check_version("20.19.0", spec, npm=True))
		self.assertTrue(check_version("22.12.0", spec, npm=True))
		self.assertFalse(check_version("18.16.0", spec, npm=True))
		self.assertFalse(check_version("21.0.0", spec, npm=True))

	def test_node_engines_simple_forms(self):
		self.assertTrue(check_version("18.16.0", ">=16.0.0", npm=True))
		self.assertTrue(check_version("20.19.0", "20.x", npm=True))
		self.assertFalse(check_version("18.16.0", ">=20", npm=True))

	def test_python_requires_with_comma(self):
		self.assertTrue(check_version("3.11", ">=3.10,<3.13"))
		self.assertFalse(check_version("3.13", ">=3.10,<3.13"))
