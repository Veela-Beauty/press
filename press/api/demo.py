"""
Demo Site Provisioning API
============================
Public API for creating demo sites from a landing page.

Endpoint: POST /api/method/press.api.demo.create
Input: {"company": "Acme Corp", "email": "user@example.com", "invite_code": "ACCU-DEMO-2026"}
Output: {"site": "acme-corp.sandbox.mvpstorm.com", "status": "creating"}

Invite codes are managed via the Demo Invite Code DocType in Press.
"""

import re

import frappe
from frappe.utils import getdate, now_datetime, nowdate


# Configuration
DEMO_RELEASE_GROUP = "bench-0005"
DEMO_PLAN = "Free"
DEMO_ADMIN_PASSWORD = "demo1234"
MAX_DEMOS_PER_EMAIL_PER_DAY = 2
MAX_TOTAL_DEMO_SITES = 50


@frappe.whitelist(allow_guest=True)
def create(company: str, email: str, phone: str = "", invite_code: str = ""):
    """Create a demo site for a potential customer."""

    invite_code = (invite_code or "").strip()
    email = (email or "").strip().lower()
    company = (company or "").strip()

    # 0. Validate invite code
    _validate_invite_code(invite_code, email)

    # 1. Validate input
    if not company or len(company) < 2:
        frappe.throw("Company name is required (min 2 characters)")

    if not email or not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        frappe.throw("Valid email address is required")

    # 2. Generate subdomain from company name
    subdomain = _slugify(company)
    if len(subdomain) < 2:
        frappe.throw("Company name must contain at least 2 alphanumeric characters")

    domain = frappe.db.get_single_value("Press Settings", "domain")
    site_name = f"{subdomain}.{domain}"

    # 3. Check if site already exists
    if frappe.db.exists("Site", site_name):
        return {
            "site": site_name,
            "url": f"https://{site_name}",
            "status": "exists",
            "message": "A demo site with this name already exists. Try a different company name.",
        }

    # 4. Rate limiting
    today = now_datetime().date()
    demo_count = frappe.db.count("Demo Site Request", filters={
        "email": email,
        "creation": [">=", str(today)],
    })
    if demo_count >= MAX_DEMOS_PER_EMAIL_PER_DAY:
        frappe.throw(f"Maximum {MAX_DEMOS_PER_EMAIL_PER_DAY} demo sites per email per day")

    # Check total demo sites
    total = frappe.db.count("Site", filters={
        "group": DEMO_RELEASE_GROUP,
        "status": ["not in", ["Archived"]],
    })
    if total >= MAX_TOTAL_DEMO_SITES:
        frappe.throw("Demo capacity reached. Please try again later or contact sales.")

    # 5. Find active bench
    bench = frappe.get_all(
        "Bench",
        filters={"group": DEMO_RELEASE_GROUP, "status": "Active"},
        fields=["name", "server"],
        order_by="creation desc",
        limit=1,
    )
    if not bench:
        frappe.throw("Demo environment is being prepared. Please try again in a few minutes.")

    bench = bench[0]

    # 6. Get team (use first non-admin team)
    teams = frappe.get_all("Team", filters={"user": ["!=", "Administrator"]}, pluck="name")
    team = teams[0] if teams else frappe.get_all("Team", pluck="name")[0]

    # 7. Get apps from release group
    rg = frappe.get_doc("Release Group", DEMO_RELEASE_GROUP)
    apps = [{"app": a.app} for a in rg.apps]

    # 8. Create site (run as Administrator to bypass role guards)
    original_user = frappe.session.user
    frappe.set_user("Administrator")
    site = frappe.get_doc({
        "doctype": "Site",
        "subdomain": subdomain,
        "domain": domain,
        "group": DEMO_RELEASE_GROUP,
        "server": bench.server,
        "bench": bench.name,
        "team": team,
        "free": 1,
        "subscription_plan": DEMO_PLAN,
        "apps": apps,
    })
    site.insert(ignore_permissions=True)
    frappe.set_user(original_user)

    # 9. Log the request and increment invite code usage
    _log_demo_request(company, email, phone, site.name, invite_code)
    _increment_invite_usage(invite_code)

    frappe.db.commit()

    return {
        "site": site.name,
        "url": f"https://{site.name}",
        "status": "creating",
        "message": "Your demo site is being created. It will be ready in about 2 minutes.",
        "admin_url": f"https://{site.name}/app",
    }


@frappe.whitelist(allow_guest=True)
def check_status(site: str):
    """Check if a demo site is ready."""
    if not site or not frappe.db.exists("Site", site):
        return {"status": "not_found"}

    status = frappe.db.get_value("Site", site, "status")
    return {
        "site": site,
        "status": status.lower(),
        "ready": status == "Active",
        "url": f"https://{site}",
    }


def _validate_invite_code(code: str, email: str):
    """Validate invite code against Demo Invite Code DocType."""
    if not code:
        frappe.throw("Invite code is required")

    if not frappe.db.exists("Demo Invite Code", code):
        frappe.throw("Invalid invite code")

    doc = frappe.get_doc("Demo Invite Code", code)

    if not doc.enabled:
        frappe.throw("This invite code has been disabled")

    if doc.expires_on and getdate(doc.expires_on) < getdate(nowdate()):
        frappe.throw("This invite code has expired")

    if doc.max_uses and doc.used_count >= doc.max_uses:
        frappe.throw("This invite code has reached its usage limit")

    if doc.email and doc.email.lower() != email:
        frappe.throw("This invite code is not valid for your email address")


def _increment_invite_usage(code: str):
    """Increment the used_count on the invite code."""
    if code and frappe.db.exists("Demo Invite Code", code):
        frappe.db.set_value("Demo Invite Code", code, "used_count",
            frappe.db.get_value("Demo Invite Code", code, "used_count") + 1)


def _slugify(text: str) -> str:
    """Convert company name to valid subdomain."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug[:30]


def _log_demo_request(company: str, email: str, phone: str, site: str, invite_code: str = ""):
    """Log the demo request."""
    try:
        frappe.get_doc({
            "doctype": "Demo Site Request",
            "company": company,
            "email": email,
            "phone": phone,
            "site": site,
            "invite_code": invite_code,
        }).insert(ignore_permissions=True)
    except Exception:
        pass
