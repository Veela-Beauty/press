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
import secrets
import string

import frappe
from frappe.utils import getdate, nowdate


# Configuration
DEMO_RELEASE_GROUP = "bench-0005"
DEMO_PLAN = "Free"
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

    # 4. One active demo site per email
    existing = frappe.db.sql("""
        SELECT dsr.site FROM `tabDemo Site Request` dsr
        JOIN `tabSite` s ON s.name = dsr.site
        WHERE dsr.email = %s AND s.status IN ('Active', 'Installing', 'Pending')
        LIMIT 1
    """, email, as_dict=True)
    if existing:
        ex_site = existing[0].site
        ex_status = frappe.db.get_value("Site", ex_site, "status")
        return {
            "site": ex_site,
            "url": f"https://{ex_site}",
            "status": ex_status.lower(),
            "ready": ex_status == "Active",
            "message": "You already have an active demo site.",
        }

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

    # 8. Generate unique password and create site
    admin_password = _generate_password()

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
        "admin_password": admin_password,
        "apps": apps,
    })
    site.insert(ignore_permissions=True)
    frappe.set_user(original_user)

    # 9. Log the request and increment invite code usage
    _log_demo_request(company, email, phone, site.name, invite_code, admin_password)
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
    """Check if a demo site is ready. Sends welcome email on first Active check."""
    if not site or not frappe.db.exists("Site", site):
        return {"status": "not_found"}

    status = frappe.db.get_value("Site", site, "status")
    ready = status == "Active"

    # Send welcome email once when site becomes active
    if ready:
        _send_welcome_email_once(site)

    return {
        "site": site,
        "status": status.lower(),
        "ready": ready,
        "url": f"https://{site}",
    }


MAX_RESEND_PER_DAY = 3


@frappe.whitelist(allow_guest=True)
def resend_credentials(email: str):
    """Resend login credentials to the user's email (max 3/day)."""
    email = (email or "").strip().lower()
    if not email:
        frappe.throw("Email is required")

    # Rate limit: 3 resend attempts per email per day
    cache_key = f"demo_resend:{email}"
    attempts = frappe.cache.get_value(cache_key) or 0
    if attempts >= MAX_RESEND_PER_DAY:
        frappe.throw("Maximum credential recovery attempts reached for today. Try again tomorrow.")

    req = frappe.db.sql("""
        SELECT dsr.name, dsr.email, dsr.company, dsr.site, dsr.admin_password
        FROM `tabDemo Site Request` dsr
        JOIN `tabSite` s ON s.name = dsr.site
        WHERE dsr.email = %s AND s.status = 'Active'
        ORDER BY dsr.creation DESC LIMIT 1
    """, email, as_dict=True)

    if not req:
        frappe.throw("No active demo site found for this email")

    req = req[0]
    try:
        frappe.sendmail(
            recipients=[req.email],
            subject=f"Your Demo Credentials — {req.company}",
            message=f"""<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
<h2 style="color: #171717;">Your Demo Credentials</h2>
<p>Here are your login details for <strong>{req.company}</strong>:</p>

<table style="border-collapse: collapse; margin: 20px 0; width: 100%;">
<tr>
    <td style="padding: 10px; border: 1px solid #e5e5e5; background: #f9f9f9; font-weight: bold; width: 140px;">Site URL</td>
    <td style="padding: 10px; border: 1px solid #e5e5e5;"><a href="https://{req.site}">{req.site}</a></td>
</tr>
<tr>
    <td style="padding: 10px; border: 1px solid #e5e5e5; background: #f9f9f9; font-weight: bold;">Login URL</td>
    <td style="padding: 10px; border: 1px solid #e5e5e5;"><a href="https://{req.site}/app">https://{req.site}/app</a></td>
</tr>
<tr>
    <td style="padding: 10px; border: 1px solid #e5e5e5; background: #f9f9f9; font-weight: bold;">Username</td>
    <td style="padding: 10px; border: 1px solid #e5e5e5;"><code>{req.email}</code></td>
</tr>
<tr>
    <td style="padding: 10px; border: 1px solid #e5e5e5; background: #f9f9f9; font-weight: bold;">Password</td>
    <td style="padding: 10px; border: 1px solid #e5e5e5;"><code>{req.admin_password}</code></td>
</tr>
</table>
</div>""",
            now=True,
        )
        frappe.cache.set_value(cache_key, attempts + 1, expires_in_sec=86400)
        return {"message": "Credentials sent to your email"}
    except Exception:
        frappe.log_error("Demo resend credentials failed")
        frappe.throw("Failed to send email. Please try again later.")


@frappe.whitelist(allow_guest=True)
def request_demo(company: str, email: str, phone: str = "", industry: str = "", message: str = ""):
    """Submit a demo request (no invite code). Admin reviews and approves later."""
    email = (email or "").strip().lower()
    company = (company or "").strip()

    if not company or len(company) < 2:
        frappe.throw("Company name is required (min 2 characters)")

    if not email or not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        frappe.throw("Valid email address is required")

    # Check if already has a pending request
    existing = frappe.db.get_value(
        "Demo Site Request",
        {"email": email, "request_status": ["in", ["Pending", "Approved"]]},
        "name",
    )
    if existing:
        return {"message": "You already have a pending request. Check your email for an invite code."}

    # Check if already has an active site
    active = frappe.db.sql("""
        SELECT dsr.site FROM `tabDemo Site Request` dsr
        JOIN `tabSite` s ON s.name = dsr.site
        WHERE dsr.email = %s AND s.status IN ('Active', 'Installing', 'Pending')
        LIMIT 1
    """, email, as_dict=True)
    if active:
        return {"message": "You already have an active demo site. Check your email for credentials."}

    frappe.get_doc({
        "doctype": "Demo Site Request",
        "company": company,
        "email": email,
        "phone": (phone or "").strip(),
        "industry": (industry or "").strip(),
        "request_message": (message or "").strip()[:2000],
        "request_status": "Pending",
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    return {"message": "Request submitted successfully"}


@frappe.whitelist()
def approve_request(request_name: str):
    """Admin approves a demo request: generates invite code and emails it to the user."""
    req = frappe.get_doc("Demo Site Request", request_name)

    if req.request_status == "Approved":
        frappe.throw("This request has already been approved")

    if req.invite_code:
        frappe.throw("An invite code has already been assigned to this request")

    # Generate a unique invite code
    code = f"DEMO-{secrets.token_hex(4).upper()}"
    while frappe.db.exists("Demo Invite Code", code):
        code = f"DEMO-{secrets.token_hex(4).upper()}"

    # Create the invite code record (single use, locked to this email, 30 day expiry)
    from frappe.utils import add_days
    frappe.get_doc({
        "doctype": "Demo Invite Code",
        "code": code,
        "enabled": 1,
        "max_uses": 1,
        "used_count": 0,
        "email": req.email,
        "expires_on": add_days(nowdate(), 30),
    }).insert(ignore_permissions=True)

    # Update request
    req.invite_code = code
    req.request_status = "Approved"
    req.save(ignore_permissions=True)

    # Email the invite code
    demo_url = "https://demo.sandbox.mvpstorm.com"
    frappe.sendmail(
        recipients=[req.email],
        subject=f"Your Demo Invite Code — {req.company}",
        message=f"""<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
<h2 style="color: #171717;">Your Demo Request is Approved!</h2>
<p>Hi,</p>
<p>Your demo request for <strong>{req.company}</strong> has been approved.</p>

<p>Use the invite code below to create your demo site:</p>

<div style="text-align: center; margin: 24px 0;">
    <div style="display: inline-block; padding: 16px 32px; background: #f0f9ff; border: 2px solid #2563eb; border-radius: 8px;">
        <span style="font-size: 24px; font-weight: 700; letter-spacing: 2px; color: #2563eb;">{code}</span>
    </div>
</div>

<p style="text-align: center;">
    <a href="{demo_url}" style="display: inline-block; padding: 12px 24px; background: #2563eb; color: white; text-decoration: none; border-radius: 8px; font-weight: 600;">Create My Demo Site</a>
</p>

<p style="color: #6b7280; font-size: 13px; margin-top: 20px;">This code is valid for 30 days and can be used once.</p>
</div>""",
        now=True,
    )

    frappe.db.commit()
    return {"message": f"Approved! Invite code {code} sent to {req.email}"}


@frappe.whitelist(allow_guest=True)
def submit_requirements(site: str, answers: list | str):
    """Save requirements form answers as child table rows on Demo Site Request.

    Input: {"site": "acme.demo.mvpstorm.com", "answers": [{"section": "...", "question": "...", "answer": "..."}]}
    """
    site = (site or "").strip()
    if not site:
        frappe.throw("Site is required")

    if isinstance(answers, str):
        import json
        answers = json.loads(answers)

    if not answers or not isinstance(answers, list):
        frappe.throw("Answers list is required")

    req_name = frappe.db.get_value("Demo Site Request", {"site": site}, "name")
    if not req_name:
        frappe.throw("No demo site request found for this site")

    req = frappe.get_doc("Demo Site Request", req_name)

    # Clear existing answers (allows re-submission)
    req.requirements = []

    for item in answers:
        section = (item.get("section") or "").strip()
        question = (item.get("question") or "").strip()
        answer = (item.get("answer") or "").strip()
        if not section or not question or not answer:
            continue
        req.append("requirements", {
            "section": section[:140],
            "question": question[:140],
            "answer": answer[:2000],
        })

    req.requirements_submitted = 1
    req.save(ignore_permissions=True)
    frappe.db.commit()

    return {"message": "Requirements saved successfully", "count": len(req.requirements)}


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


def _generate_password(length=12):
    """Generate a random alphanumeric password."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _log_demo_request(company: str, email: str, phone: str, site: str, invite_code: str = "", admin_password: str = ""):
    """Log the demo request with credentials."""
    try:
        frappe.get_doc({
            "doctype": "Demo Site Request",
            "company": company,
            "email": email,
            "phone": phone,
            "site": site,
            "invite_code": invite_code,
            "admin_password": admin_password,
        }).insert(ignore_permissions=True)
    except Exception:
        pass


def _send_welcome_email_once(site: str):
    """Create user on demo site and send welcome email when site first becomes active."""
    req = frappe.db.get_value(
        "Demo Site Request", {"site": site}, ["email", "company", "name", "email_sent", "admin_password"], as_dict=True
    )
    if not req or req.email_sent:
        return

    # Create a normal user on the demo site via Press agent
    try:
        site_doc = frappe.get_doc("Site", site)
        site_doc.create_user(req.email, req.company, "", req.admin_password)
    except Exception:
        frappe.log_error("Demo user creation failed")

    try:
        frappe.sendmail(
            recipients=[req.email],
            subject=f"Your Demo Site is Ready — {req.company}",
            message=f"""<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
<h2 style="color: #171717;">Your Demo Site is Ready!</h2>
<p>Hi,</p>
<p>Your demo site for <strong>{req.company}</strong> has been created and is now live.</p>

<table style="border-collapse: collapse; margin: 20px 0; width: 100%;">
<tr>
    <td style="padding: 10px; border: 1px solid #e5e5e5; background: #f9f9f9; font-weight: bold; width: 140px;">Site URL</td>
    <td style="padding: 10px; border: 1px solid #e5e5e5;"><a href="https://{site}">{site}</a></td>
</tr>
<tr>
    <td style="padding: 10px; border: 1px solid #e5e5e5; background: #f9f9f9; font-weight: bold;">Login URL</td>
    <td style="padding: 10px; border: 1px solid #e5e5e5;"><a href="https://{site}/app">https://{site}/app</a></td>
</tr>
<tr>
    <td style="padding: 10px; border: 1px solid #e5e5e5; background: #f9f9f9; font-weight: bold;">Username</td>
    <td style="padding: 10px; border: 1px solid #e5e5e5;"><code>{req.email}</code></td>
</tr>
<tr>
    <td style="padding: 10px; border: 1px solid #e5e5e5; background: #f9f9f9; font-weight: bold;">Password</td>
    <td style="padding: 10px; border: 1px solid #e5e5e5;"><code>{req.admin_password}</code></td>
</tr>
</table>

<p>This is a demo environment — data may be reset periodically.</p>
<p style="color: #737373; font-size: 13px;">If you didn't request this demo, please ignore this email.</p>
</div>""",
            now=True,
        )
        frappe.db.set_value("Demo Site Request", req.name, "email_sent", 1)
        frappe.db.commit()
    except Exception:
        frappe.log_error("Demo welcome email failed")
