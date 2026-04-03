"""
Deploy build diagnostics — failure details and build health queries.

Kept separate from deploy_candidate_build.py (1700+ lines, upstream code)
to avoid merge conflicts and respect the 700-line limit.
"""

import frappe


@frappe.whitelist()
def get_failure_details(dn: str) -> dict:
    """Return structured failure info for a deploy build — which step failed, why, and progress."""
    build = frappe.get_doc("Deploy Candidate Build", dn)

    failed_step = None
    total_steps = len(build.build_steps)
    completed_steps = sum(1 for s in build.build_steps if s.status == "Success")

    for step in build.build_steps:
        if step.status == "Failure":
            failed_step = {
                "stage": step.stage,
                "step": step.step,
                "command": step.command or "",
                "output": step.output or "",
                "duration": step.duration,
            }
            break

    return {
        "status": build.status,
        "build_error": build.build_error or "",
        "failed_step": failed_step,
        "total_steps": total_steps,
        "completed_steps": completed_steps,
    }
