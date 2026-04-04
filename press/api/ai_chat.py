"""AI Chat API — thin wrapper at press.api.ai_chat for Frappe URL routing.

Frappe blocks deep module paths (press.press.ai.api) for web requests.
This wrapper at press.api.ai_chat makes endpoints accessible via:
  POST /api/method/press.api.ai_chat.chat

Uses allow_guest=True with internal auth (same pattern as Press dashboard APIs).
"""

import frappe
from press.press.ai.api import chat as _chat, get_ai_config as _get_ai_config
from press.utils import get_current_team


@frappe.whitelist(allow_guest=True)
def chat(prompt, site_name="", bench_name="", site_type="Dev",
         branch="", session_id=None):
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to use the AI Assistant")
    return _chat(prompt, site_name, bench_name, site_type, branch, session_id)


@frappe.whitelist(allow_guest=True)
def get_ai_config():
    if frappe.session.user == "Guest":
        frappe.throw("Please log in")
    return _get_ai_config()
