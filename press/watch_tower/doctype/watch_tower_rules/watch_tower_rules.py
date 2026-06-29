# Copyright (c) 2026, Accurate Systems and contributors
# For license information, please see license.txt

import inspect

import frappe
from press.watch_tower import _nolicense as licensing
from frappe.model.document import Document
from frappe.utils import now_datetime


class WatchTowerRules(Document):
	"""
	Watch Tower Rules -  general-purpose rule engine.

	Monitors any DocType, evaluates configurable conditions,
	and takes actions (set field values, send emails).
	Uses doc.save() for matched docs so Frappe's native
	Notification system fires automatically.
	"""

	def validate(self):
		self._validate_target_doctype()
		self._validate_condition()
		self._validate_actions()
		self._validate_email()

	def _validate_target_doctype(self):
		"""Ensure target DocType exists."""
		if not frappe.db.exists("DocType", self.target_doctype):
			frappe.throw(f"DocType '{self.target_doctype}' does not exist.")

	def _validate_condition(self):
		"""Mode-specific condition validation."""
		if self.evaluation_mode == "Field Comparison":
			if not self.condition_field:
				frappe.throw("Field Name is required for Field Comparison mode.")
			if not self.condition_operator:
				frappe.throw("Operator is required for Field Comparison mode.")
			# Validate field exists on target DocType
			meta = frappe.get_meta(self.target_doctype)
			if not meta.has_field(self.condition_field):
				frappe.throw(
					f"Field '{self.condition_field}' does not exist on {self.target_doctype}."
				)

		elif self.evaluation_mode == "Python Expression":
			if not self.condition_expression:
				frappe.throw("Condition expression is required for Python Expression mode.")
			try:
				compile(self.condition_expression, "<watch_tower_rule>", "eval")
			except SyntaxError as e:
				frappe.throw(f"Invalid Python expression: {e}")

		elif self.evaluation_mode == "Python Script":
			if not self.condition_script:
				frappe.throw("Condition script is required for Python Script mode.")
			try:
				compile(self.condition_script, "<watch_tower_rule>", "exec")
			except SyntaxError as e:
				frappe.throw(f"Invalid Python script: {e}")

		elif self.evaluation_mode == "Python Method":
			if not self.condition_method:
				frappe.throw("Python method path is required for Python Method mode.")
			# Validate the dotted path resolves to a callable
			try:
				module_path, func_name = self.condition_method.rsplit(".", 1)
				module = frappe.get_module(module_path)
				if not hasattr(module, func_name):
					frappe.throw(
						f"Method '{func_name}' not found in module '{module_path}'."
					)
				func = getattr(module, func_name)
				if not callable(func):
					frappe.throw(
						f"'{self.condition_method}' is not callable."
					)
			except (ValueError, ImportError) as e:
				frappe.throw(f"Invalid method path '{self.condition_method}': {e}")

	def _validate_actions(self):
		"""Validate each action row."""
		if not self.actions and self.evaluation_mode == "Field Comparison" and not self.send_email:
			frappe.throw("At least one action or Send Email is required.")

		meta = frappe.get_meta(self.target_doctype)
		for action in self.actions:
			if action.action_type == "Set Field Value":
				if not meta.has_field(action.target_field):
					frappe.throw(
						f"Target field '{action.target_field}' does not exist "
						f"on {self.target_doctype}."
					)

	def _validate_email(self):
		"""Validate email configuration if enabled."""
		if self.send_email:
			if not self.email_subject:
				frappe.throw("Email Subject is required when Send Email is enabled.")
			if not self.email_template:
				frappe.throw("Email Template is required when Send Email is enabled.")
			if not self.email_recipients:
				frappe.throw("At least one Email Recipient is required when Send Email is enabled.")

	@frappe.whitelist()
	@licensing.gated("watch_tower")
	def evaluate_now(self):
		"""
		Manually trigger rule evaluation via background job.
		Called from the form's "Evaluate Now" button.
		"""
		frappe.enqueue(
			"press.watch_tower.engine.evaluate_rule",
			queue="long",
			rule_name=self.name,
			triggered_by=frappe.session.user,
		)

		# Set status to Running immediately
		self.db_set("last_run_status", "Running", update_modified=False)

		frappe.msgprint(
			f"Rule '{self.rule_name}' evaluation has been queued. "
			"Check the Watch Tower Alert Log for results.",
			alert=True,
			indicator="blue",
		)


@frappe.whitelist()
@licensing.gated("watch_tower")
def get_available_methods():
	"""Auto-discover rule functions from installed apps.

	Scans for public functions with signature (doc, rule) -> bool
	in any app's watch_tower.rules package.
	Returns newline-separated dotted paths for use in a Select field.
	"""
	import importlib

	methods = []
	for app in frappe.get_installed_apps():
		rules_module_path = f"{app}.watch_tower.rules"
		try:
			module = importlib.import_module(rules_module_path)
		except (ImportError, ModuleNotFoundError):
			continue

		for attr_name in sorted(dir(module)):
			if attr_name.startswith("_"):
				continue
			attr = getattr(module, attr_name)
			if not callable(attr) or not inspect.isfunction(attr):
				continue
			if not getattr(attr, "__module__", "").startswith(rules_module_path):
				continue
			sig = inspect.signature(attr)
			params = list(sig.parameters.keys())
			if params == ["doc", "rule"]:
				methods.append(f"{rules_module_path}.{attr_name}")

	return "\n".join(methods)


@frappe.whitelist()
@licensing.gated("watch_tower")
def get_method_defaults(method_path):
	"""Return the _RULE_DEFAULTS for a given method, if defined."""
	if not method_path:
		return {}
	try:
		module_path, func_name = method_path.rsplit(".", 1)
		module = frappe.get_module(module_path)
		defaults = getattr(module, "_RULE_DEFAULTS", {})
		return defaults.get(func_name, {})
	except Exception:
		return {}


@frappe.whitelist()
@licensing.gated("watch_tower")
def get_method_description(method_path):
	"""Return the docstring of a rule function given its dotted path."""
	if not method_path:
		return ""
	try:
		module_path, func_name = method_path.rsplit(".", 1)
		module = frappe.get_module(module_path)
		func = getattr(module, func_name, None)
		if func and callable(func):
			return inspect.getdoc(func) or ""
	except Exception:
		pass
	return ""
