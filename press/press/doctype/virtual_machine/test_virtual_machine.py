# Copyright (c) 2021, Frappe and Contributors
# See license.txt

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.press.doctype.cluster.test_cluster import create_test_cluster
from press.press.doctype.root_domain.test_root_domain import create_test_root_domain
from press.press.doctype.virtual_machine.virtual_machine import VirtualMachine

if TYPE_CHECKING:
	from press.press.doctype.cluster.cluster import Cluster


@patch.object(VirtualMachine, "client", new=MagicMock())
def create_test_virtual_machine(
	ip: str | None = None,
	cluster: Cluster | None = None,
	series: str = "m",
	platform: str = "x86_64",
	cloud_provider: str = "AWS EC2",
	disk_size: int = 100,
	has_data_volume: bool = False,
) -> VirtualMachine:
	"""Create test Virtual Machine doc"""
	if not ip:
		ip = frappe.mock("ipv4")
	if not cluster:
		cluster = create_test_cluster()
	vm = frappe.get_doc(
		{
			"doctype": "Virtual Machine",
			"domain": create_test_root_domain("fc.dev", cluster.name).name,
			"series": series,
			"status": "Running",
			"machine_type": "r5.xlarge",
			"disk_size": disk_size,
			"cluster": cluster.name,
			"instance_id": "i-1234567890",
			"vcpu": 4,
			"platform": platform,
			"cloud_provider": cloud_provider,
		}
	).insert(ignore_if_duplicate=True)

	volumes = []
	# Root volume
	volumes.append(
		frappe.get_doc(
			{
				"doctype": "Virtual Machine Volume",
				"parenttype": "Virtual Machine",
				"parent": vm.name,
				"parentfield": "volumes",
				"volume_type": "gp3",
				"throughput": 125,
				"device": "/dev/sdf",
				"size": disk_size if not has_data_volume else 8,
				"volume_id": f"vol-{frappe.generate_hash(11)}",
			}
		)
	)
	if has_data_volume:
		volumes.append(
			frappe.get_doc(
				{
					"doctype": "Virtual Machine Volume",
					"parenttype": "Virtual Machine",
					"parent": vm.name,
					"parentfield": "volumes",
					"volume_type": "gp3",
					"throughput": 125,
					"device": "/dev/sdg",
					"size": disk_size,
					"volume_id": f"vol-{frappe.generate_hash(11)}",
				}
			)
		)

	for volume in volumes:
		volume.insert()

	return vm


@patch.object(VirtualMachine, "client", new=MagicMock())
class TestVirtualMachine(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_database_server_creation_works(self):
		"""Test if database server creation works"""
		vm = create_test_virtual_machine()
		try:
			vm.create_database_server()
		except Exception as e:
			self.fail(e)


class TestIsVmForDecommissionedServer(FrappeTestCase):
	"""Guard against the 2026-05-21 incident: snapshot crons created 1798
	wasted Snapshot Disk jobs in 2 days because they picked targets by VM
	flags without checking the linked Server's is_decommissioned flag.

	The helper is_vm_for_decommissioned_server() is the single source of
	truth for 'should snapshot crons skip this VM?'. Every snapshot cron
	in virtual_machine.py calls it. If you add a new snapshot cron, call
	this helper before triggering a snapshot."""

	def test_direct_decom_app_server_returns_true(self):
		"""VM is the backing for a decommissioned app Server → True."""
		from press.press.doctype.virtual_machine.virtual_machine import (
			is_vm_for_decommissioned_server,
		)

		def fake_get_value(doctype, filters, fieldname=None, as_dict=False):
			if doctype == "Server" and filters == {"virtual_machine": "f1-mumbai.fc.dev"} and as_dict:
				return frappe._dict({"name": "f-0001.fc.dev", "is_decommissioned": 1})
			return None

		with patch("press.press.doctype.virtual_machine.virtual_machine.frappe.db.get_value", side_effect=fake_get_value):
			self.assertTrue(is_vm_for_decommissioned_server("f1-mumbai.fc.dev"))

	def test_direct_active_app_server_returns_false(self):
		"""VM backs an active app Server → False (don't skip)."""
		from press.press.doctype.virtual_machine.virtual_machine import (
			is_vm_for_decommissioned_server,
		)

		def fake_get_value(doctype, filters, fieldname=None, as_dict=False):
			if doctype == "Server" and as_dict:
				return frappe._dict({"name": "press-f1.example.com", "is_decommissioned": 0})
			return None

		with patch("press.press.doctype.virtual_machine.virtual_machine.frappe.db.get_value", side_effect=fake_get_value):
			self.assertFalse(is_vm_for_decommissioned_server("press-f1-vm.example.com"))

	def test_indirect_via_db_server_returns_true(self):
		"""VM is a Database Server's VM whose linked app Server is decommissioned → True."""
		from press.press.doctype.virtual_machine.virtual_machine import (
			is_vm_for_decommissioned_server,
		)

		def fake_get_value(doctype, filters, fieldname=None, as_dict=False):
			# No direct Server match
			if doctype == "Server" and "virtual_machine" in filters and as_dict:
				return None
			# Database Server matches this VM
			if doctype == "Database Server" and filters == {"virtual_machine": "m2-mumbai.fc.dev"} and fieldname == "name":
				return "m2927.fc.dev"
			# Linked app Server IS decommissioned
			if doctype == "Server" and filters == {"database_server": "m2927.fc.dev", "is_decommissioned": 1} and fieldname == "name":
				return "f-0001.fc.dev"
			return None

		with patch("press.press.doctype.virtual_machine.virtual_machine.frappe.db.get_value", side_effect=fake_get_value):
			self.assertTrue(is_vm_for_decommissioned_server("m2-mumbai.fc.dev"))

	def test_orphan_vm_returns_false(self):
		"""VM that doesn't back any Server/Database/Proxy at all → False (let normal snapshot logic run)."""
		from press.press.doctype.virtual_machine.virtual_machine import (
			is_vm_for_decommissioned_server,
		)

		with patch(
			"press.press.doctype.virtual_machine.virtual_machine.frappe.db.get_value",
			return_value=None,
		), patch(
			"press.press.doctype.virtual_machine.virtual_machine.frappe.get_all",
			return_value=[],
		):
			self.assertFalse(is_vm_for_decommissioned_server("orphan-vm.example.com"))
