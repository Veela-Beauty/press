"""Validate site_type against bench type — Dev/Demo only on development benches."""

import frappe


def validate_site_type(doc, method=None):
    """Called via doc_events hook on Site.validate."""
    site_type = getattr(doc, "site_type", None)
    if site_type not in ("Dev", "Demo"):
        return

    bench_name = doc.bench
    if not bench_name and doc.group:
        bench_name = frappe.get_value(
            "Bench", {"group": doc.group, "status": "Active"},
            "name", order_by="creation desc",
        )

    if not bench_name:
        return

    is_dev = frappe.get_value("Bench", bench_name, "is_development_bench")
    if not is_dev:
        frappe.throw(
            f"{site_type} sites can only be created on development benches. "
            f"Mark the bench as development first from the bench Actions tab.",
            frappe.ValidationError,
        )
