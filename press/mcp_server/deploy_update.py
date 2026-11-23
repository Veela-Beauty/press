# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""One-call deploy for MCP agents (0.7.49): build, new bench and site updates, queued the way the dashboard's
Deploy and update button queues them (press.api.bench.deploy_and_update), and one status call that covers all three.

Agents chained bench_deploy, wait_for_bench_flip, deploy_candidate_status and site_update: about 16 calls a deploy.
site_update was refused 281 times in 30 days because the new bench was not ready yet, and the *_and_wait tools were
cut off by gunicorn at 120 s. Here Press updates the sites itself once the bench is ready
(BenchUpdate.update_sites_on_server), and the agent only reads deploy_update_status.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe.utils import now_datetime, time_diff_in_seconds

from press.mcp_server.scope.sites import chosen_sites

_BUILD_FAILED = ("Failure",)
_BENCH_READY = ("Active", "Archived")  # Archived: a later deploy replaced the bench after this one ran
_NOT_SCHEDULED = "Not scheduled"
_SITE_DONE = ("Success", "Failure", "Recovered", "Fatal", _NOT_SCHEDULED)
# Press schedules the site updates when the bench turns Active; a row still unscheduled after this never will be
_SCHEDULE_GRACE_SECONDS = 120
# Press makes the new benches right after a build succeeds; none after this long means it never will
_NO_BENCH_GRACE_SECONDS = 600


@frappe.whitelist()
def bench_deploy_and_update(
	name: str, apps: list[dict] | str, sites: list[str] | str | None = None
) -> dict[str, Any]:
	"""Deploy `apps` to Release Group `name` and update its sites once the new bench is ready. Returns at once.

	sites: names of Active sites on this Release Group to update; leave out for all of them. Then call
	deploy_update_status(name=<build>) about every 30 s until done is true.
	"""
	from press.api.bench import deploy_and_update

	if isinstance(apps, str):
		try:
			apps = json.loads(apps)
		except ValueError:
			apps = None
	if not apps or not isinstance(apps, list) or not all(isinstance(a, dict) for a in apps):
		frappe.throw(
			"apps must be a list of {app, release, hash} from bench_deploy_information",
			frappe.ValidationError,
		)
	chosen = chosen_sites(name, sites)
	payload = [
		{
			"name": s.name,
			"server": s.server,
			"bench": s.bench,
			"skip_failing_patches": False,
			"skip_backups": False,
		}
		for s in chosen
	]
	build = deploy_and_update(name=name, apps=apps, sites=payload)
	return {
		"build": build,
		"candidate": frappe.db.get_value("Deploy Candidate Build", build, "deploy_candidate"),
		"sites": [s.name for s in chosen],
		"next": f"deploy_update_status(name={build!r}) about every 30 s until done is true",
	}


@frappe.whitelist()
def deploy_update_status(name: str) -> dict[str, Any]:
	"""Where a bench_deploy_and_update is: the build, its new benches (one per server of the group), then each site's
	update. name = the build. 0.7.52: every bench is read, not only the newest (a two-server group has two)."""
	build = frappe.db.get_value(
		"Deploy Candidate Build", name, ["name", "status", "deploy_candidate", "build_end"], as_dict=True
	)
	if not build:
		frappe.throw(f"Deploy Candidate Build {name!r} not found", frappe.DoesNotExistError)
	benches = frappe.get_all(
		"Bench",
		filters={"candidate": build.deploy_candidate},
		fields=["name", "status", "modified"],
		order_by="creation",
	)
	ready = bool(benches) and all(b.status in _BENCH_READY for b in benches)
	bench_update = frappe.db.get_value(
		"Bench Update", {"candidate": build.deploy_candidate}, "name", order_by="creation desc"
	)
	ready_since = max(b.modified for b in benches) if ready else None
	sites = _visible(_site_rows(bench_update, ready_since)) if bench_update else []
	result = {
		"build": build.name,
		"build_status": build.status,
		"benches": [{"bench": b.name, "status": b.status} for b in benches],
		"sites": sites,
	}
	if not bench_update:
		result["note"] = (
			"this build was not started by bench_deploy_and_update, so it updates no sites; "
			"update each with site_update_and_wait"
		)
	return {**result, **_stage(build, benches, ready, sites)}


def _stage(build, benches, ready: bool, sites: list[dict]) -> dict[str, Any]:
	"""stage, done, ok and a hint: build first, then every bench, then every site."""
	if build.status in _BUILD_FAILED:
		return {"stage": "build", "done": True, "ok": False, "hint": f"deploy_failure_details(name={build.name!r})"}
	if build.status != "Success":
		return {"stage": "build", "done": False, "ok": False}
	if any(b.status == "Broken" for b in benches):
		return {"stage": "bench", "done": True, "ok": False, "hint": "agent_job_list for the broken bench's New Bench job"}
	if not benches and build.build_end and time_diff_in_seconds(now_datetime(), build.build_end) > _NO_BENCH_GRACE_SECONDS:
		return {
			"stage": "bench",
			"done": True,
			"ok": False,
			"hint": "no bench was made for this build in 10 minutes: agent_job_list, then deploy_candidate_status",
		}
	if not ready:
		return {"stage": "bench", "done": False, "ok": False}
	if any(s["status"] not in _SITE_DONE for s in sites):
		return {"stage": "sites", "done": False, "ok": False}
	if all(s["status"] == "Success" for s in sites):
		return {"stage": "done", "done": True, "ok": True}
	return {
		"stage": "done",
		"done": True,
		"ok": False,
		"hint": "agent_job_traceback(job_name=<update_job>) for a failed site; a site that is Not scheduled had another "
		"update pending or running: site_status, then site_update_and_wait",
	}


def _site_rows(bench_update: str, ready_since) -> list[dict]:
	"""Each site of the Bench Update and its Site Update status. The Bench Site Update row keeps "Pending" after its
	Site Update is created, so the Site Update's own status is read. Press skips a site that already has an update
	pending or running, and its row then stays Pending with no Site Update: Not scheduled, once every bench is ready."""
	rows = frappe.get_all(
		"Bench Site Update", filters={"parent": bench_update}, fields=["site", "site_update", "status"]
	)
	updates = {
		u.name: u
		for u in frappe.get_all(
			"Site Update",
			filters={"name": ["in", [r.site_update for r in rows if r.site_update] or ["-"]]},
			fields=["name", "status", "update_job"],
		)
	}
	late = bool(ready_since and time_diff_in_seconds(now_datetime(), ready_since) > _SCHEDULE_GRACE_SECONDS)
	out = []
	for r in rows:
		update = updates.get(r.site_update)
		if update:
			out.append(
				{
					"site": r.site,
					"status": update.status,
					"site_update": update.name,
					"update_job": update.update_job,
				}
			)
		elif r.status == "Pending":
			out.append({"site": r.site, "status": _NOT_SCHEDULED if late else "Waiting for the bench"})
		else:  # Success: already on the newest bench; Failure: the update could not be scheduled
			out.append({"site": r.site, "status": r.status})
	return out


def _visible(sites: list[dict]) -> list[dict]:
	"""Only the sites the calling token may see: its allowed sites when it names any, and no confidential site it
	has not unlocked."""
	from press.mcp_server.scope.confidential import confidential_sites

	allowed = set(getattr(frappe.local, "mcp_token_allowed_sites", None) or ())
	unlocked = set(getattr(frappe.local, "mcp_token_confidential_sites", None) or ())
	hidden = set(confidential_sites([s["site"] for s in sites])) - unlocked
	return [s for s in sites if s["site"] not in hidden and (not allowed or s["site"] in allowed)]
