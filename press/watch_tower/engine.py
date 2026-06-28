"""
Watch Tower Execution Engine.

Core function: evaluate_rule(rule_name, triggered_by)
- Loads the rule, fetches candidate documents, evaluates conditions,
  executes actions via doc.save(), creates alert logs, sends emails.
"""
import json
from typing import Dict, List, Optional, Any

import frappe
from press.watch_tower import _nolicense as licensing
from frappe.utils import now_datetime, flt, cint, cstr


# Circuit Breaker
# Prevents feedback loops: if Watch Tower itself is generating too many
# alerts or errors, stop evaluating rules until the storm passes.
CIRCUIT_BREAKER_MAX_ALERTS_PER_HOUR = 20   # Max alert logs per hour
CIRCUIT_BREAKER_MAX_QUEUE_SIZE = 500       # Max unsent emails in queue
CIRCUIT_BREAKER_COOLDOWN_MINUTES = 30      # Pause rules for this long

# Upper bound on candidate documents fetched per rule evaluation. Without this,
# a rule targeting a high-volume DocType (e.g. Sales Invoice with no filters)
# would load every row into worker memory and OOM the process. Tune via the
# `watch_tower_max_candidates` site_config value if a legitimate rule needs more.
MAX_CANDIDATES = 10_000


def _circuit_breaker_tripped() -> str:
    """
    Check if Watch Tower should pause itself.
    Returns empty string if OK, or reason string if tripped.
    """
    from frappe.utils import add_to_date

    # Check 1: Too many Watch Tower alerts in the last hour
    one_hour_ago = add_to_date(now_datetime(), hours=-1)
    recent_alerts = frappe.db.count(
        "Watch Tower Alert Log",
        {"alert_datetime": [">", one_hour_ago]},
    )
    if recent_alerts > CIRCUIT_BREAKER_MAX_ALERTS_PER_HOUR:
        return f"Circuit breaker: {recent_alerts} alerts in last hour (max {CIRCUIT_BREAKER_MAX_ALERTS_PER_HOUR})"

    # Check 2: Email queue is backing up (sign of SMTP failure loop)
    unsent = frappe.db.count("Email Queue", {"status": "Not Sent"})
    if unsent > CIRCUIT_BREAKER_MAX_QUEUE_SIZE:
        return f"Circuit breaker: {unsent} unsent emails in queue (max {CIRCUIT_BREAKER_MAX_QUEUE_SIZE})"

    # Check 3: Cooldown -  if we tripped recently, stay paused
    last_trip = frappe.cache.get_value("watch_tower_circuit_breaker_tripped_at")
    if last_trip:
        from frappe.utils import time_diff_in_seconds
        elapsed = time_diff_in_seconds(now_datetime(), last_trip)
        if elapsed < CIRCUIT_BREAKER_COOLDOWN_MINUTES * 60:
            remaining = int((CIRCUIT_BREAKER_COOLDOWN_MINUTES * 60 - elapsed) / 60)
            return f"Circuit breaker: cooling down ({remaining} min remaining)"

    return ""


def _trip_circuit_breaker(reason: str):
    """Record that the circuit breaker was tripped."""
    frappe.cache.set_value(
        "watch_tower_circuit_breaker_tripped_at",
        now_datetime(),
        expires_in_sec=CIRCUIT_BREAKER_COOLDOWN_MINUTES * 60,
    )
    frappe.logger("watch_tower").warning(f"CIRCUIT BREAKER TRIPPED: {reason}")


class RuleResult:
    """Container for rule evaluation statistics."""

    def __init__(self):
        self.evaluated = 0
        self.matched = 0
        self.actions_taken = 0
        self.skipped = 0
        self.failed = 0
        self.errors: List[str] = []
        self.matched_docs: List[Dict] = []  # For email context

    @property
    def status(self) -> str:
        if self.failed > 0 and self.actions_taken > 0:
            return "Partial Success"
        elif self.failed > 0:
            return "Failed"
        elif self.matched == 0:
            return "No Matches"
        return "Success"

    @property
    def summary(self) -> str:
        return (
            f"Evaluated {self.evaluated}, "
            f"{self.matched} matched, "
            f"{self.actions_taken} actions, "
            f"{self.skipped} skipped, "
            f"{self.failed} failed"
        )

    def to_dict(self) -> Dict:
        return {
            "status": self.status,
            "summary": self.summary,
            "evaluated": self.evaluated,
            "matched": self.matched,
            "actions_taken": self.actions_taken,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors[:50],
        }


def _prepare_candidates(rule):
    """Parse filters, determine fields, and fetch candidate documents."""
    filters = {}
    if rule.target_filters_json:
        filters = json.loads(rule.target_filters_json)

    if rule.evaluation_mode in ("Python Expression", "Python Script", "Python Method"):
        fields = ["*"]
    else:
        fields = ["name"]
        if rule.condition_field:
            fields.append(rule.condition_field)
        for action in rule.actions:
            if action.target_field and action.target_field not in fields:
                fields.append(action.target_field)

    # Site-config override for legitimate high-volume rules; otherwise the cap.
    cap = cint(frappe.conf.get("watch_tower_max_candidates") or MAX_CANDIDATES)
    documents = frappe.get_all(
        rule.target_doctype,
        filters=filters,
        fields=fields,
        limit_page_length=cap,
    )
    if len(documents) >= cap:
        frappe.logger().warning(
            "[watch_tower] %s: candidate fetch hit cap=%s on %s -  extra rows skipped",
            rule.name, cap, rule.target_doctype,
        )
    return filters, fields, documents


def _get_display_name(doc_dict):
    """Try to get a human-readable name from a document dict."""
    for name_field in ("customer_name", "employee_name", "title", "subject", "lead_name"):
        if doc_dict.get(name_field):
            return doc_dict[name_field]
    return doc_dict.get("name", "")


def evaluate_rule(rule_name: str, triggered_by: str = "Scheduler") -> Dict:
    """
    Evaluate a single Watch Tower Rule against all matching documents.

    Internal-only -  called by scheduler and post-sync, not by web requests.

    Args:
        rule_name: Name of the Watch Tower Rules document
        triggered_by: User who triggered, or "Scheduler" / "Post-Sync"

    Returns:
        Dict with status, summary, and statistics
    """
    # Block direct web calls -  this function writes with ignore_permissions
    if frappe.request and frappe.session.user != "Administrator":
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

    # Circuit breaker -  stop if Watch Tower itself is causing a storm
    trip_reason = _circuit_breaker_tripped()
    if trip_reason:
        _trip_circuit_breaker(trip_reason)
        return {"status": "Circuit Breaker", "summary": trip_reason}

    from .evaluator import evaluate as eval_condition

    rule = frappe.get_doc("Watch Tower Rules", rule_name)

    if not rule.enabled:
        return {"status": "Skipped", "summary": "Rule is disabled"}

    result = RuleResult()

    # Mark rule as Running (no commit -  flushed by the batch commit below)
    frappe.db.set_value(
        "Watch Tower Rules", rule_name,
        {"last_run_status": "Running"},
        update_modified=False,
    )

    try:
        try:
            filters, fields, documents = _prepare_candidates(rule)
        except json.JSONDecodeError:
            result.errors.append("Invalid JSON in target_filters_json")
            _update_rule_status(rule_name, result)
            frappe.db.commit()
            return result.to_dict()

        result.evaluated = len(documents)

        # Step 4: Evaluate and act in batches
        batch_size = 50
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            for doc_dict in batch:
                try:
                    matches = eval_condition(rule, doc_dict)

                    if matches:
                        result.matched += 1
                        action_result = _execute_actions(
                            rule, doc_dict, triggered_by
                        )
                        result.actions_taken += action_result["actions_applied"]
                        result.skipped += action_result["actions_skipped"]
                        if len(result.matched_docs) < 50:
                            result.matched_docs.append(action_result["doc_result"])

                        if action_result.get("error"):
                            result.failed += 1
                            result.errors.append(action_result["error"])
                except Exception as e:
                    result.failed += 1
                    result.errors.append(
                        f"Doc {doc_dict.get('name')}: {str(e)}"
                    )

            frappe.db.commit()

            # Publish progress for realtime updates
            frappe.publish_realtime(
                "watch_tower_progress",
                {
                    "rule": rule_name,
                    "evaluated": min(i + batch_size, result.evaluated),
                    "total": result.evaluated,
                    "matched": result.matched,
                },
                doctype="Watch Tower Rules",
                docname=rule_name,
            )

        # Step 5: Send email if configured
        if rule.send_email and result.matched > 0:
            try:
                from .email import send_rule_email
                send_rule_email(rule, result.to_dict(), result.matched_docs)
            except Exception as e:
                result.errors.append(f"Email send failed: {str(e)}")
                frappe.log_error(
                    title=f"Watch Tower Email Failed: {rule_name}",
                    message=frappe.get_traceback(),
                )

    except Exception as e:
        result.failed += 1
        result.errors.append(f"Rule execution error: {str(e)}")
        frappe.log_error(
            title=f"Watch Tower Rule Failed: {rule_name}",
            message=frappe.get_traceback(),
        )

    # Step 6: Update rule status
    _update_rule_status(rule_name, result)
    frappe.db.commit()

    return result.to_dict()


def _execute_actions(rule, doc_dict: Dict, triggered_by: str) -> Dict:
    """
    Execute all actions for a matched document.
    Uses doc.save() to trigger Frappe Notifications.
    """
    actions_applied = 0
    actions_skipped = 0
    before_values = {}
    after_values = {}
    action_descriptions = []

    try:
        # Load full document for save
        doc = frappe.get_doc(rule.target_doctype, doc_dict["name"])
        meta = frappe.get_meta(rule.target_doctype)

        for action in rule.actions:
            if action.action_type == "Set Field Value":
                current_value = doc.get(action.target_field)

                # Check overwrite policy
                if not action.overwrite_existing:
                    if current_value is not None and current_value != "" and current_value != 0:
                        actions_skipped += 1
                        continue

                new_value = action.field_value

                # Type coercion based on field type
                field_meta = meta.get_field(action.target_field)
                if field_meta and field_meta.fieldtype in ("Currency", "Float", "Percent"):
                    new_value = flt(new_value)
                elif field_meta and field_meta.fieldtype == "Int":
                    new_value = cint(new_value)

                before_values[action.target_field] = current_value
                after_values[action.target_field] = new_value
                action_descriptions.append(
                    f"{action.target_field}: '{current_value}' -> '{new_value}'"
                )

                doc.set(action.target_field, new_value)
                actions_applied += 1

        # Save with ignore_permissions to trigger Frappe Notifications
        if actions_applied > 0:
            doc.flags.ignore_validate = True
            doc.flags.ignore_mandatory = True
            doc.save(ignore_permissions=True)

        # Create alert log only when actions were actually applied
        if actions_applied > 0:
            _create_alert_log(
                rule=rule,
                doc_dict=doc_dict,
                status="Success",
                triggered_by=triggered_by,
                action_summary="; ".join(action_descriptions),
                before_values=before_values,
                after_values=after_values,
            )

        # Build doc result for email context
        doc_result = {
            "doc": doc_dict,
            "before": before_values,
            "after": after_values,
            "actions": action_descriptions,
        }

        return {
            "actions_applied": actions_applied,
            "actions_skipped": actions_skipped,
            "error": None,
            "doc_result": doc_result,
        }

    except Exception as e:
        _create_alert_log(
            rule=rule,
            doc_dict=doc_dict,
            status="Failed",
            triggered_by=triggered_by,
            action_summary="; ".join(action_descriptions),
            before_values=before_values,
            after_values=after_values,
            error_message=str(e),
        )
        return {
            "actions_applied": actions_applied,
            "actions_skipped": actions_skipped,
            "error": f"Doc {doc_dict.get('name')}: {str(e)}",
            "doc_result": {"doc": doc_dict, "before": before_values, "after": after_values, "actions": action_descriptions},
        }


def _create_alert_log(
    rule, doc_dict, status, triggered_by, action_summary,
    before_values, after_values, error_message="",
):
    """Create a Watch Tower Alert Log entry."""
    doc_name_display = _get_display_name(doc_dict)

    try:
        log = frappe.get_doc({
            "doctype": "Watch Tower Alert Log",
            "rule": rule.name,
            "rule_name": rule.rule_name,
            "status": status,
            "alert_datetime": now_datetime(),
            "triggered_by": triggered_by,
            "target_doctype": rule.target_doctype,
            "target_document": doc_dict["name"],
            "target_document_name": cstr(doc_name_display)[:140],
            "action_summary": action_summary,
            "before_values_json": json.dumps(before_values, default=str),
            "after_values_json": json.dumps(after_values, default=str),
            "error_message": error_message,
        })
        log.insert(ignore_permissions=True)
    except Exception:
        # Don't let log creation failure break the rule evaluation
        frappe.log_error(
            title="Watch Tower Alert Log Creation Failed",
            message=frappe.get_traceback(),
        )


def _update_rule_status(rule_name: str, result: RuleResult):
    """Update the rule doc with last run results."""
    frappe.db.set_value(
        "Watch Tower Rules",
        rule_name,
        {
            "last_evaluated_at": now_datetime(),
            "last_run_status": result.status,
            "last_result_summary": result.summary,
        },
        update_modified=False,
    )


def _build_match_details(rule, doc_dict: Dict) -> str:
    """Build a human-readable summary of WHY a document matched.

    For Field Comparison: shows the field value vs threshold.
    For Python Method/Expression/Script: shows key financial fields
    from the document so the user can understand the match reason.
    """
    parts = []

    if rule.evaluation_mode == "Field Comparison":
        val = doc_dict.get(rule.condition_field)
        parts.append(f"{rule.condition_field} = {val} ({rule.condition_operator} {rule.condition_value})")
    else:
        # Show key non-standard fields from the document for context
        skip_keys = {"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx"}
        for key, val in doc_dict.items():
            if key in skip_keys:
                continue
            if val not in (None, "", 0, "0", 0.0):
                if isinstance(val, float):
                    parts.append(f"{key}: {val:,.0f}")
                else:
                    parts.append(f"{key}: {val}")
            if len(parts) >= 5:
                break

    return " | ".join(parts) if parts else ""


@frappe.whitelist()
@licensing.gated("watch_tower")
def dry_run_rule(rule_name: str, limit: int = 100) -> Dict:
    """Evaluate a rule without executing actions or creating logs.

    Returns matched documents with what actions WOULD be taken.
    Runs synchronously (not enqueued) since it's read-only.
    """
    frappe.only_for("System Manager")
    from .evaluator import evaluate as eval_condition

    limit = min(cint(limit) or 100, 500)
    rule = frappe.get_doc("Watch Tower Rules", rule_name)
    filters, fields, documents = _prepare_candidates(rule)

    matched = []
    evaluated = 0
    for doc_dict in documents:
        evaluated += 1
        try:
            if eval_condition(rule, doc_dict):
                # Build what-would-happen summary
                would_do = []
                for action in rule.actions:
                    if action.action_type == "Set Field Value":
                        current = doc_dict.get(action.target_field, "")
                        if not action.overwrite_existing and current not in (None, "", 0):
                            would_do.append(f"{action.target_field}: SKIP (already set)")
                        else:
                            would_do.append(f"{action.target_field}: '{current}' -> '{action.field_value}'")

                matched.append({
                    "name": doc_dict.get("name"),
                    "display_name": cstr(_get_display_name(doc_dict)),
                    "actions": "; ".join(would_do),
                    "details": _build_match_details(rule, doc_dict),
                })
                if len(matched) >= limit:
                    break
        except Exception as e:
            matched.append({
                "name": doc_dict.get("name"),
                "display_name": doc_dict.get("name"),
                "actions": f"ERROR: {str(e)}",
            })

    return {
        "evaluated": evaluated,
        "total_candidates": len(documents),
        "matched": len(matched),
        "truncated": len(matched) >= limit,
        "results": matched,
    }


def run_scheduled_rules(frequency: str):
    """
    Run all enabled rules matching the given frequency.
    Called by scheduler jobs. Each rule is enqueued separately.
    """
    rules = frappe.get_all(
        "Watch Tower Rules",
        filters={"enabled": 1, "frequency": frequency},
        fields=["name"],
        order_by="priority asc",
    )

    for rule_row in rules:
        frappe.enqueue(
            "press.watch_tower.engine.evaluate_rule",
            queue="long",
            rule_name=rule_row.name,
            triggered_by="Scheduler",
        )


def run_post_sync_rules():
    """
    Run all Post-Sync frequency rules synchronously.
    Called from customer_daily_delta_sync.py Step 5.
    Returns summary dict for the orchestrator.
    """
    rules = frappe.get_all(
        "Watch Tower Rules",
        filters={"enabled": 1, "frequency": "Post-Sync"},
        fields=["name"],
        order_by="priority asc",
    )

    total_matched = 0
    total_failed = 0
    rule_summaries = []

    for rule_row in rules:
        try:
            result = evaluate_rule(rule_row.name, triggered_by="Post-Sync")
            total_matched += result.get("matched", 0)
            total_failed += result.get("failed", 0)
            rule_summaries.append(f"{rule_row.name}: {result.get('summary', '')}")
        except Exception as e:
            total_failed += 1
            rule_summaries.append(f"{rule_row.name}: ERROR - {str(e)}")
            frappe.log_error(
                title=f"Watch Tower Post-Sync Failed: {rule_row.name}",
                message=frappe.get_traceback(),
            )

    return {
        "rules_evaluated": len(rules),
        "total_matched": total_matched,
        "total_failed": total_failed,
        "summaries": rule_summaries,
    }
