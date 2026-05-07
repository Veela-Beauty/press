# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import frappe
from frappe.utils import now_datetime

VALID_TARGETS = ("Site", "Release Group")


@frappe.whitelist()
def acquire(
	target_doctype: str,
	target_name: str,
	reason: str,
	ttl_minutes: int = 30,
	override: bool = False,
) -> dict[str, Any]:
	"""Acquire (or refresh) an advisory lock on the target.

	Returns:
		{status: "active"|"blocked", holder, reason, expires_at, override_history?}
	"""
	_validate_target(target_doctype, target_name)
	if not reason or not str(reason).strip():
		frappe.throw("Lock reason is required", frappe.ValidationError)
	ttl_minutes = max(1, int(ttl_minutes))

	user = frappe.session.user
	existing = _get_active_lock(target_doctype, target_name)

	if existing and existing.holder != user and not override:
		return {
			"status": "blocked",
			"holder": existing.holder,
			"reason": existing.reason,
			"expires_at": existing.expires_at.isoformat() if existing.expires_at else None,
		}

	if existing and existing.holder == user:
		# Same user — refresh TTL and reason
		existing.reason = reason
		existing.ttl_minutes = ttl_minutes
		existing.expires_at = now_datetime() + timedelta(minutes=ttl_minutes)
		existing.save(ignore_permissions=True)
		return _serialize(existing, lock_status="active")

	if existing and existing.holder != user and override:
		# Override: revoke existing, create new, append to history
		hist = _parse_history(existing.override_history)
		hist.append({
			"at": now_datetime().isoformat(),
			"by": user,
			"prev_holder": existing.holder,
			"prev_reason": existing.reason,
			"override_reason": reason,
		})
		existing.revoked = 1
		existing.revoked_by = user
		existing.revoked_at = now_datetime()
		existing.save(ignore_permissions=True)
		new_lock = _create_lock(target_doctype, target_name, user, reason, ttl_minutes)
		new_lock.override_history = json.dumps(hist)
		new_lock.save(ignore_permissions=True)
		return _serialize(new_lock, lock_status="active")

	# No existing lock — create
	new_lock = _create_lock(target_doctype, target_name, user, reason, ttl_minutes)
	return _serialize(new_lock, lock_status="active")


@frappe.whitelist()
def release(target_doctype: str, target_name: str) -> dict[str, str]:
	"""Release the lock if held by the current user (or if System User)."""
	_validate_target(target_doctype, target_name)
	existing = _get_active_lock(target_doctype, target_name)
	if not existing:
		return {"status": "free"}
	is_system_user = frappe.session.data.user_type == "System User"
	if existing.holder != frappe.session.user and not is_system_user:
		frappe.throw(
			f"You don't hold this lock. Current holder: {existing.holder}",
			frappe.PermissionError,
		)
	existing.revoked = 1
	existing.revoked_by = frappe.session.user
	existing.revoked_at = now_datetime()
	existing.save(ignore_permissions=True)
	return {"status": "released"}


@frappe.whitelist()
def status(target_doctype: str, target_name: str) -> dict[str, Any]:
	"""Return current lock state. If a Site's parent RG is locked, return
	{status: 'blocked_by_parent', parent_lock: {...}}."""
	_validate_target(target_doctype, target_name)

	# Parent (Release Group) lock supersedes site lock
	if target_doctype == "Site":
		parent_rg = frappe.db.get_value("Site", target_name, "group")
		if parent_rg:
			parent_lock = _get_active_lock("Release Group", parent_rg)
			if parent_lock:
				return {
					"status": "blocked_by_parent",
					"parent_lock": _serialize(parent_lock, lock_status="active"),
				}

	existing = _get_active_lock(target_doctype, target_name)
	if not existing:
		return {"status": "free"}
	return _serialize(existing, lock_status="active")


def _get_active_lock(target_doctype: str, target_name: str):
	rows = frappe.get_all(
		"Press Lock",
		filters={
			"target_doctype": target_doctype,
			"target_name": target_name,
			"revoked": 0,
			"expires_at": (">", now_datetime()),
		},
		order_by="creation desc",
		limit=1,
		pluck="name",
	)
	if not rows:
		return None
	return frappe.get_doc("Press Lock", rows[0])


def _create_lock(target_doctype, target_name, holder, reason, ttl_minutes):
	doc = frappe.get_doc({
		"doctype": "Press Lock",
		"target_doctype": target_doctype,
		"target_name": target_name,
		"holder": holder,
		"reason": reason,
		"ttl_minutes": ttl_minutes,
		"expires_at": now_datetime() + timedelta(minutes=ttl_minutes),
	}).insert(ignore_permissions=True)
	return doc


def _validate_target(target_doctype: str, target_name: str) -> None:
	if target_doctype not in VALID_TARGETS:
		frappe.throw(
			f"target_doctype must be one of {VALID_TARGETS}",
			frappe.ValidationError,
		)
	if not target_name:
		frappe.throw("target_name is required", frappe.ValidationError)


def _parse_history(raw):
	if not raw:
		return []
	if isinstance(raw, list):
		return raw
	try:
		return json.loads(raw)
	except (ValueError, TypeError):
		return []


def _serialize(lock_doc, lock_status: str) -> dict[str, Any]:
	return {
		"status": lock_status,
		"name": lock_doc.name,
		"holder": lock_doc.holder,
		"reason": lock_doc.reason,
		"target_doctype": lock_doc.target_doctype,
		"target_name": lock_doc.target_name,
		"expires_at": lock_doc.expires_at.isoformat() if lock_doc.expires_at else None,
		"override_history": _parse_history(lock_doc.override_history),
	}
