"""
Watch Tower Rule Evaluator -  4 evaluation modes.

Mode 1: Field Comparison (simple UI, no code)
Mode 2: Python Expression (one-liner via safe_eval)
Mode 3: Python Script (multi-line, reads `result` variable)
Mode 4: Python Method (call a dotted Python path)
"""
import json
from types import SimpleNamespace

import frappe
from frappe.utils import flt, cint, cstr


# Safe builtins for Script mode -  no file/os/system access
SAFE_BUILTINS = {
    "True": True, "False": False, "None": None,
    "abs": abs, "all": all, "any": any, "bool": bool,
    "dict": dict, "enumerate": enumerate, "filter": filter,
    "float": float, "int": int, "isinstance": isinstance,
    "len": len, "list": list, "map": map, "max": max,
    "min": min, "range": range, "round": round, "set": set,
    "sorted": sorted, "str": str, "sum": sum, "tuple": tuple,
    "zip": zip,
}


def evaluate(rule, doc_dict):
    """
    Route to the correct evaluation mode.

    Args:
        rule: Watch Tower Rules document object
        doc_dict: dict of the candidate document's field values

    Returns:
        bool -  True if the document matches the rule condition
    """
    mode = rule.evaluation_mode

    if mode == "Field Comparison":
        return _field_comparison(doc_dict, rule)
    elif mode == "Python Expression":
        return _safe_eval_expression(rule.condition_expression, doc_dict)
    elif mode == "Python Script":
        return _exec_script(rule.condition_script, doc_dict)
    elif mode == "Python Method":
        return _call_method(rule.condition_method, doc_dict, rule)

    return False


def _field_comparison(doc_dict, rule):
    """
    Mode 1: Simple field-operator-value comparison.
    No code execution. Safe for business users.
    """
    field_value = doc_dict.get(rule.condition_field)
    operator = rule.condition_operator
    compare_value = rule.condition_value

    if operator == "is set":
        return field_value is not None and field_value != "" and field_value != 0
    elif operator == "is not set":
        return field_value is None or field_value == "" or field_value == 0

    # Try numeric comparison first
    try:
        field_num = flt(field_value)
        compare_num = flt(compare_value)
        if operator == ">":    return field_num > compare_num
        if operator == ">=":   return field_num >= compare_num
        if operator == "<":    return field_num < compare_num
        if operator == "<=":   return field_num <= compare_num
        if operator == "==":   return field_num == compare_num
        if operator == "!=":   return field_num != compare_num
    except (ValueError, TypeError):
        pass

    # Fall back to string comparison
    field_str = cstr(field_value)
    compare_str = cstr(compare_value)

    if operator == "==":     return field_str == compare_str
    if operator == "!=":     return field_str != compare_str
    if operator == "in":
        values = [v.strip() for v in compare_str.split(",")]
        return field_str in values
    if operator == "not in":
        values = [v.strip() for v in compare_str.split(",")]
        return field_str not in values

    return False


def _safe_eval_expression(expression, doc_dict):
    """
    Mode 2: One-liner Python expression via frappe.safe_eval().
    doc is available as a SimpleNamespace for dot notation.
    """
    if not expression:
        return False

    doc = SimpleNamespace(**doc_dict)

    eval_globals = {"__builtins__": {}}
    eval_locals = {
        "doc": doc,
        "flt": flt,
        "cint": cint,
        "cstr": cstr,
        "json": json,
        "true": True,
        "false": False,
        "null": None,
        "None": None,
    }

    try:
        result = frappe.safe_eval(expression, eval_globals, eval_locals)
        return bool(result)
    except Exception as e:
        raise ValueError(f"Expression evaluation error: {e}")


def _safe_get_value(doctype, name, field):
    """
    Narrow helper exposed to Mode 3 scripts in place of the full `frappe` module.

    Returns a single field value for a single record. No write access, no SQL,
    no document loading. Permissions are NOT bypassed -  the script runs in the
    scheduler context (Administrator), so callers should still consider rule
    authorship as privileged.
    """
    return frappe.db.get_value(doctype, name, field)


def _exec_script(script, doc_dict):
    """
    Mode 3: Multi-line Python script.
    The script sets a `result` variable (True/False).
    doc is available as a SimpleNamespace.

    Sandbox: `frappe` is NOT exposed. Scripts that need DB reads must use the
    narrow `get_value(doctype, name, field)` helper. Exposing the full `frappe`
    module historically let any rule editor call frappe.db.sql, frappe.delete_doc,
    frappe.sendmail, etc. -  undermining the SAFE_BUILTINS restriction entirely.
    """
    if not script:
        return False

    doc = SimpleNamespace(**doc_dict)

    local_vars = {
        "doc": doc,
        "flt": flt,
        "cint": cint,
        "cstr": cstr,
        "json": json,
        "get_value": _safe_get_value,
        "result": False,
    }

    try:
        exec(
            compile(script, "<watch_tower_script>", "exec"),
            {"__builtins__": SAFE_BUILTINS},
            local_vars,
        )
        return bool(local_vars.get("result", False))
    except Exception as e:
        raise ValueError(f"Script execution error: {e}")


def _call_method(method_path, doc_dict, rule):
    """
    Mode 4: Call a Python function by dotted path.
    Function signature: func(doc_dict, rule) -> bool
    """
    if not method_path:
        return False

    try:
        module_path, func_name = method_path.rsplit(".", 1)
        module = frappe.get_module(module_path)
        func = getattr(module, func_name)
        return bool(func(doc_dict, rule))
    except Exception as e:
        raise ValueError(f"Method call error ({method_path}): {e}")
