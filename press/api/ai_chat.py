"""AI Chat API — thin wrapper at press.api.ai_chat for Frappe URL routing.

Frappe blocks deep module paths (press.press.ai.api) for web requests.
This wrapper at press.api.ai_chat makes endpoints accessible via:
  POST /api/method/press.api.ai_chat.chat
"""

import frappe
from press.press.ai.api import chat as _chat, get_ai_config as _get_ai_config


@frappe.whitelist()
def chat(prompt, site_name="", bench_name="", site_type="Dev",
         branch="", session_id=None):
    return _chat(prompt, site_name, bench_name, site_type, branch, session_id)


@frappe.whitelist()
def get_ai_config():
    return _get_ai_config()
