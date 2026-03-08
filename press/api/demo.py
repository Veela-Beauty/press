"""
Demo Site Provisioning API
============================
Public API for creating demo sites from a landing page.

Endpoint: POST /api/method/press.api.demo.create
Input: {"company": "Acme Corp", "email": "user@example.com", "phone": "+1234567890"}
Output: {"site": "acme-corp.demo.mvpstorm.com", "status": "creating"}

The site is created on the AccuBuild Demo bench (bench-0005) with all apps pre-installed.
"""

import re

import frappe
from frappe.utils import now_datetime


# Configuration — change these for your setup
DEMO_RELEASE_GROUP = "bench-0005"
DEMO_PLAN = "Free"
DEMO_ADMIN_PASSWORD = "demo1234"
MAX_DEMOS_PER_EMAIL_PER_DAY = 2
MAX_TOTAL_DEMO_SITES = 50


@frappe.whitelist(allow_guest=True)
def create(company: str, email: str, phone: str = ""):
    """Create a demo site for a potential customer."""

    # 1. Validate input
    company = (company or "").strip()
    email = (email or "").strip().lower()

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

    # 8. Create site
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

    # 9. Log the request
    _log_demo_request(company, email, phone, site.name)

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


def _slugify(text: str) -> str:
    """Convert company name to valid subdomain."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)  # Replace non-alphanumeric with hyphens
    slug = re.sub(r"-+", "-", slug)  # Collapse multiple hyphens
    slug = slug.strip("-")  # Remove leading/trailing hyphens
    return slug[:30]  # Max 30 chars


def _log_demo_request(company: str, email: str, phone: str, site: str):
    """Log the demo request. Creates Demo Site Request doctype if it doesn't exist."""
    try:
        if not frappe.db.table_exists("Demo Site Request"):
            _create_demo_request_doctype()

        frappe.get_doc({
            "doctype": "Demo Site Request",
            "company": company,
            "email": email,
            "phone": phone,
            "site": site,
        }).insert(ignore_permissions=True)
    except Exception:
        pass  # Don't fail site creation if logging fails


def _create_demo_request_doctype():
    """Create the Demo Site Request DocType for logging."""
    if frappe.db.exists("DocType", "Demo Site Request"):
        return

    dt = frappe.get_doc({
        "doctype": "DocType",
        "name": "Demo Site Request",
        "module": "Press",
        "autoname": "autoincrement",
        "fields": [
            {"fieldname": "company", "fieldtype": "Data", "label": "Company", "in_list_view": 1},
            {"fieldname": "email", "fieldtype": "Data", "label": "Email", "options": "Email", "in_list_view": 1},
            {"fieldname": "phone", "fieldtype": "Data", "label": "Phone"},
            {"fieldname": "site", "fieldtype": "Data", "label": "Site", "in_list_view": 1},
        ],
        "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
    })
    dt.insert(ignore_permissions=True)
    frappe.db.commit()
