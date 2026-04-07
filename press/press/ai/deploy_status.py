"""Deploy build status API — simple endpoint for deploy progress viewing."""

import frappe


@frappe.whitelist()
def get_deploy_build(name):
    """Get deploy build data with steps."""
    frappe.only_for(["System Manager", "Press Admin"])
    
    build = frappe.get_doc("Deploy Candidate Build", name)
    steps = []
    for s in build.build_steps:
        steps.append({
            "step": s.step,
            "status": s.status,
            "stage": s.stage,
            "duration": s.duration,
            "output": s.output,
        })
    
    return {
        "name": build.name,
        "deploy_candidate": build.deploy_candidate,
        "status": build.status,
        "build_start": str(build.build_start) if build.build_start else None,
        "build_end": str(build.build_end) if build.build_end else None,
        "build_duration": str(build.build_duration) if build.build_duration else None,
        "build_error": build.build_error,
        "group": build.group,
        "steps": steps,
    }


@frappe.whitelist()
def get_deploy_history(group, limit=20):
    """Get deploy history for a release group."""
    frappe.only_for(["System Manager", "Press Admin"])
    
    builds = frappe.get_all(
        "Deploy Candidate Build",
        filters={"group": group},
        fields=["name", "deploy_candidate", "status", "build_start", "build_end", "build_duration", "creation"],
        order_by="creation desc",
        limit=limit,
    )
    return builds
