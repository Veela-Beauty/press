"""
Watch Tower Email System.

Sends rich, data-driven emails after rule evaluation completes.
Two modes:
- Summary: One email with a table of all matched documents
- Per Document: One email per matched document
"""
import json
from typing import Dict, List

import frappe
from frappe.utils import now_datetime, flt, get_url_to_form


def send_rule_email(rule, evaluation_result: Dict, matched_docs: List[Dict]):
    """
    Send email after rule evaluation completes.

    Args:
        rule: Watch Tower Rules document
        evaluation_result: dict with status, summary, stats
        matched_docs: list of dicts, each with 'doc', 'before', 'after', 'actions'
    """
    if not rule.send_email or not rule.email_subject or not rule.email_template:
        return

    if not matched_docs:
        return

    # Build shared Jinja context
    context = {
        "rule": {
            "name": rule.name,
            "rule_name": rule.rule_name,
            "description": rule.description or "",
            "target_doctype": rule.target_doctype,
            "frequency": rule.frequency,
        },
        "stats": {
            "evaluated": evaluation_result.get("evaluated", 0),
            "matched": evaluation_result.get("matched", 0),
            "actions_taken": evaluation_result.get("actions_taken", 0),
            "skipped": evaluation_result.get("skipped", 0),
            "failed": evaluation_result.get("failed", 0),
            "run_at": now_datetime(),
            "status": evaluation_result.get("status", ""),
        },
        "results": matched_docs,
        # Helpers
        "flt": flt,
        "frappe": frappe,
        "json": json,
        "get_url_to_form": get_url_to_form,
    }

    if rule.email_mode == "Summary":
        _send_summary_email(rule, context)
    elif rule.email_mode == "Per Document":
        _send_per_document_emails(rule, context, matched_docs)


def _send_summary_email(rule, context: Dict):
    """Send ONE email with all matched documents."""
    recipients = _resolve_recipients(rule)

    if not recipients:
        return

    subject = frappe.render_template(rule.email_subject, context)
    message = frappe.render_template(rule.email_template, context)

    from .email_branding import send_alert_email
    send_alert_email(
        recipients=recipients,
        subject=subject,
        message=message,
    )


def _send_per_document_emails(rule, context: Dict, matched_docs: List[Dict]):
    """Send one email PER matched document."""
    from .email_branding import send_alert_email

    for doc_result in matched_docs:
        doc_context = {
            **context,
            "doc": doc_result.get("doc", {}),
            "before": doc_result.get("before", {}),
            "after": doc_result.get("after", {}),
        }

        recipients = _resolve_recipients(rule, doc_result.get("doc"))

        if not recipients:
            continue

        subject = frappe.render_template(rule.email_subject, doc_context)
        message = frappe.render_template(rule.email_template, doc_context)

        send_alert_email(
            recipients=recipients,
            subject=subject,
            message=message,
        )


def _resolve_recipients(rule, doc_dict=None) -> List[str]:
    """
    Build recipient email list from the Watch Tower Email Recipient child table.

    Supports:
   - Role: All users with this role
   - User: Specific user's email
   - Document Field: Email from a field on the matched document
   - Static Email: Hardcoded email address
    """
    emails = set()

    for recipient in rule.email_recipients:
        if recipient.recipient_type == "Role" and recipient.role:
            role_emails = frappe.get_all(
                "Has Role",
                filters={"role": recipient.role, "parenttype": "User"},
                fields=["parent"],
            )
            for re in role_emails:
                user = frappe.get_cached_value("User", re.parent, "email")
                if user and frappe.get_cached_value("User", re.parent, "enabled"):
                    emails.add(user)

        elif recipient.recipient_type == "User" and recipient.user:
            user_email = frappe.get_cached_value("User", recipient.user, "email")
            if user_email:
                emails.add(user_email)

        elif recipient.recipient_type == "Document Field" and recipient.document_field and doc_dict:
            field_value = doc_dict.get(recipient.document_field, "")
            if field_value and "@" in str(field_value):
                emails.add(str(field_value))

        elif recipient.recipient_type == "Static Email" and recipient.email_address:
            emails.add(recipient.email_address)

    return list(emails)
