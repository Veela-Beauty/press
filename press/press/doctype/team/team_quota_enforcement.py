"""Quota enforcement for site and bench creation."""
import frappe


def check_site_quota(doc, method=None):
    """Validate site creation against team quotas. Called via doc_events."""
    if frappe.session.user == "Administrator":
        return
    if not doc.team:
        return

    team = doc.team

    # 1. Check max_sites quota (locked to prevent TOCTOU race)
    max_sites = frappe.db.get_value("Team", team, "max_sites") or 0
    if max_sites > 0:
        current = frappe.db.sql(
            "SELECT COUNT(*) FROM tabSite WHERE team=%s AND status NOT IN ('Archived') FOR UPDATE",
            team,
        )[0][0]
        if current >= max_sites:
            frappe.throw(
                f"Site limit reached: {current}/{max_sites} sites. Contact your administrator.",
                frappe.ValidationError,
            )

    # 2. Check allowed site types
    allowed_raw = frappe.db.get_value("Team", team, "allowed_site_types") or ""
    if allowed_raw.strip():
        allowed = [t.strip() for t in allowed_raw.strip().split("\n") if t.strip()]
        site_type = getattr(doc, "site_type", "Production") or "Production"
        if allowed and site_type not in allowed:
            frappe.throw(
                f"Your team is not allowed to create {site_type} sites. "
                f"Allowed types: {', '.join(allowed)}.",
                frappe.ValidationError,
            )


def check_bench_quota(doc, method=None):
    """Validate bench/release group creation against team quota."""
    if frappe.session.user == "Administrator":
        return
    team = doc.team
    if not team:
        return

    max_benches = frappe.db.get_value("Team", team, "max_benches") or 0
    if max_benches > 0:
        current = frappe.db.sql(
            "SELECT COUNT(*) FROM `tabRelease Group` WHERE team=%s AND enabled=1 FOR UPDATE",
            team,
        )[0][0]
        if current >= max_benches:
            frappe.throw(
                f"Bench limit reached: {current}/{max_benches} benches. Contact your administrator.",
                frappe.ValidationError,
            )
