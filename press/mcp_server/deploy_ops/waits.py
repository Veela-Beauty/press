# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Waiting for a bench or a site to move to a new deploy candidate: the single-shot poll and the older,
blocking wait tools (moved from deploy_flow.py in 0.7.54)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import add_to_date


@frappe.whitelist()
def wait_for_bench_flip(
	site_name: str,
	target_candidate: str,
) -> dict[str, Any]:
	"""Async-style poll: check whether the site's current bench was built from
	the target Deploy Candidate. Returns immediately. Caller re-polls.

	Status values:
		flipped              site is now on a bench produced by target_candidate
		pending              site is on older bench AND Update Site Migrate
		                     job is in-flight — keep polling
		no_build             target_candidate has no Deploy Candidate Build —
		                     the build was never triggered. STOP polling.
		flip_not_triggered   build succeeded but no Update Site Migrate job
		                     exists in the last 60 min — site_update was
		                     never called. STOP polling, call
		                     site_update_and_wait instead.
		flip_failed          most recent Update Site Migrate FAILED (and was
		                     rolled back by Recover Failed Site Migrate, if
		                     that ran). STOP polling, call agent_job_traceback
		                     on the failed_migrate_job to see the error.

	Safety gates (server-enforced, can't be bypassed by agent):
		Gate B (no_build)            return early with hint instead of looping
		Gate C (flip_not_triggered)  detect missing site_update trigger
		Gate D (scheduler auto-kick) if Undelivered jobs >2min old exist for
		                             this site, run poll_pending_jobs ONCE
		                             before returning. Idempotent.
	"""
	current_bench = frappe.db.get_value("Site", site_name, "bench")
	if not current_bench:
		frappe.throw(
			f"Site {site_name!r} does not exist or has no bench",
			frappe.DoesNotExistError,
		)
	bench_candidate = frappe.db.get_value("Bench", current_bench, "candidate")
	flipped = bench_candidate == target_candidate

	# Already flipped — short-circuit. No gate checks needed.
	if flipped:
		return {
			"status": "flipped",
			"site": site_name,
			"current_bench": current_bench,
			"current_candidate": bench_candidate,
			"target_candidate": target_candidate,
		}

	# Gate B: does the target candidate even have a Build?
	# If no Deploy Candidate Build row exists, the agent is waiting on a
	# phantom — the build was never triggered. Return early with the fix.
	build_exists = frappe.db.exists("Deploy Candidate Build", {"deploy_candidate": target_candidate})
	if not build_exists:
		# Could be: candidate doesn't exist OR exists but no build scheduled
		cand_exists = frappe.db.exists("Deploy Candidate", target_candidate)
		return {
			"status": "no_build",
			"site": site_name,
			"current_bench": current_bench,
			"current_candidate": bench_candidate,
			"target_candidate": target_candidate,
			"hint": (
				f"No Deploy Candidate Build exists for {target_candidate!r}. "
				+ (
					"The candidate exists but no build was scheduled — call "
					"deploy_candidate_schedule_build(candidate_name=...) or "
					"bench_deploy_and_wait(...)."
					if cand_exists
					else "The Deploy Candidate itself does not exist — check "
					"the target_candidate name."
				)
			),
		}

	# Gate D (auto-kick): if Undelivered jobs older than 2min exist for this
	# site, the poll_pending_jobs scheduler likely stalled. Fire ONE manual
	# poll to sync the backlog. Idempotent — Press's own scheduler does this
	# every 60s, so we're just helping it catch up.
	stale_undelivered = frappe.db.count(
		"Agent Job",
		filters={
			"site": site_name,
			"status": "Undelivered",
			"creation": ("<", add_to_date(None, minutes=-2)),
		},
	)
	if stale_undelivered > 0:
		try:
			from press.press.doctype.agent_job.agent_job import poll_pending_jobs as _ppj
			_ppj()
			frappe.db.commit()
		except Exception as e:  # noqa: BLE001 — best-effort, never fail the poll
			frappe.log_error(
				title="wait_for_bench_flip: Gate D poll_pending_jobs kick failed",
				message=str(e),
			)
		# Re-read in case the kick already flipped the site
		current_bench = frappe.db.get_value("Site", site_name, "bench")
		bench_candidate = frappe.db.get_value("Bench", current_bench, "candidate")
		if bench_candidate == target_candidate:
			return {
				"status": "flipped",
				"site": site_name,
				"current_bench": current_bench,
				"current_candidate": bench_candidate,
				"target_candidate": target_candidate,
				"gate_d_triggered": True,
				"hint": "Gate D auto-kicked poll_pending_jobs and the flip resolved.",
			}

	# Gate C/E: inspect site_update history for this site
	# C: build Success but no migrate job → flip_not_triggered
	# E: migrate FAILED and Recover rolled back → flip_failed (don't poll)
	build_row = frappe.db.get_value(
		"Deploy Candidate Build",
		{"deploy_candidate": target_candidate},
		["name", "status"],
		order_by="creation desc",
		as_dict=True,
	)
	if build_row and build_row.status == "Success":
		recent_migrate_jobs = frappe.get_all(
			"Agent Job",
			filters={
				"site": site_name,
				"job_type": (
					"in",
					[
						"Update Site Migrate",
						"Update Site Migrate Steps",
						"Recover Failed Site Migrate",
					],
				),
				"creation": (">", add_to_date(None, minutes=-60)),
			},
			fields=["name", "job_type", "status", "creation"],
			order_by="creation desc",
			limit=20,
		)
		# Gate C: no migrate job exists for this site
		if not recent_migrate_jobs:
			return {
				"status": "flip_not_triggered",
				"site": site_name,
				"current_bench": current_bench,
				"current_candidate": bench_candidate,
				"target_candidate": target_candidate,
				"build_status": build_row.status,
				"hint": (
					f"Build {build_row.name} for {target_candidate} is Success but "
					f"no Update Site Migrate job exists for {site_name} in the "
					f"last 60 min. On standalone Press, sites don't auto-flip — "
					f"call site_update_and_wait(site_name={site_name!r}, "
					f"target_candidate={target_candidate!r}) to trigger the flip."
				),
			}
		# Gate E: most recent migrate run finished (Failure or Recover Success)
		# and site is STILL on old bench → flip failed and rolled back.
		# Look for the most recent Update Site Migrate result.
		migrate_results = [j for j in recent_migrate_jobs if j.job_type == "Update Site Migrate"]
		if migrate_results:
			last_migrate = migrate_results[0]
			recover_after = [
				j for j in recent_migrate_jobs
				if j.job_type == "Recover Failed Site Migrate" and j.creation > last_migrate.creation
			]
			if last_migrate.status == "Failure" and recover_after:
				return {
					"status": "flip_failed",
					"site": site_name,
					"current_bench": current_bench,
					"current_candidate": bench_candidate,
					"target_candidate": target_candidate,
					"build_status": build_row.status,
					"failed_migrate_job": last_migrate.name,
					"recover_job": recover_after[0].name,
					"hint": (
						f"Most recent Update Site Migrate for {site_name} "
						f"({last_migrate.name}) FAILED at "
						f"{last_migrate.creation.isoformat()}. Site was rolled "
						f"back to old bench by Recover job {recover_after[0].name}. "
						f"Call agent_job_traceback(job_name={last_migrate.name!r}) "
						f"to see the migrate error before retrying."
					),
				}
			if last_migrate.status == "Failure" and not recover_after:
				return {
					"status": "flip_failed",
					"site": site_name,
					"current_bench": current_bench,
					"current_candidate": bench_candidate,
					"target_candidate": target_candidate,
					"build_status": build_row.status,
					"failed_migrate_job": last_migrate.name,
					"hint": (
						f"Update Site Migrate {last_migrate.name} for {site_name} "
						f"FAILED. No Recover job has run yet — site may be in a "
						f"half-migrated state. Call agent_job_traceback("
						f"job_name={last_migrate.name!r}) to see the error."
					),
				}

	# Normal pending — flip is in-flight or scheduled
	return {
		"status": "pending",
		"site": site_name,
		"current_bench": current_bench,
		"current_candidate": bench_candidate,
		"target_candidate": target_candidate,
	}


# The two blocking *_and_wait tools hold one of press-ctrl's 9 sync gunicorn workers while they wait, and gunicorn ends
# a request at 120 s (-t 120): 0.7.49 capped the wait at 100 s, 0.7.52 at 30 s so parallel agents cannot fill the web
# workers. Past the cap they answer status='timeout': call again, or use bench_deploy_and_update, which returns at once.
HTTP_WAIT_CAP_SECONDS = 30


@frappe.whitelist()
def bench_deploy_and_wait(
	name: str,
	apps: list[dict] | str,
	site_name: str,
	max_wait_seconds: int = 1500,
	poll_interval_seconds: int = 5,
) -> dict[str, Any]:
	"""Trigger a deploy + block until the site's bench flips to the new
	Deploy Candidate, or timeout. Single MCP call covers the entire wait.

	Args:
		name: Release Group docname, e.g. 'bench-0005'
		apps: list of {app, release, hash} dicts (same shape as bench_deploy).
			Get from bench_deploy_information(name).apps[*].releases[0].
			Accepts a JSON string too — MCP HTTP layer sometimes stringifies lists.
		site_name: Site FQDN to watch. The deploy may affect multiple sites
			on the same RG; this method only waits for the named one to flip.
		max_wait_seconds: hard cap (default 1500 = 25 min; leaves 5 min headroom
			capped at HTTP_WAIT_CAP_SECONDS). Returns status='timeout'
			beyond this — agent can re-call to keep waiting.
		poll_interval_seconds: how often to re-check (default 5s, the minimum: a bench or site that
			finishes just after a check no longer waits up to 30s to be seen).

	Returns:
		{
			"candidate": <Deploy Candidate docname>,   # always set
			"status": "flipped" | "timeout",
			"elapsed_seconds": <int>,
			"site": <site_name>,
			"current_bench": <bench docname after flip / when polled last>,
			"current_candidate": <its candidate>,
			"target_candidate": <the new candidate we waited for>,
		}

	Use this INSTEAD of bench_deploy + a manual loop on wait_for_bench_flip.
	The single-call shape means the agent doesn't have to manage its own
	timer + re-poll. Long-running HTTP request (up to max_wait_seconds) — safe
	within HTTP_WAIT_CAP_SECONDS.
	"""
	import json
	import time

	from press.api.bench import deploy as _bench_deploy

	# Accept apps as JSON string (some MCP HTTP layers stringify lists)
	if isinstance(apps, str):
		apps = json.loads(apps)
	if not isinstance(apps, list) or not all(isinstance(a, dict) for a in apps):
		frappe.throw(
			"apps must be a list of dicts with {app, release, hash} keys; "
			f"got {type(apps).__name__}",
			frappe.ValidationError,
		)

	poll_interval = max(5, int(poll_interval_seconds))
	max_wait = min(HTTP_WAIT_CAP_SECONDS, max(poll_interval, int(max_wait_seconds)))

	# Step 1 — trigger the deploy. Returns the Deploy Candidate docname.
	candidate = _bench_deploy(name=name, apps=apps)
	if isinstance(candidate, dict):
		# defensive — _bench_deploy normally returns a string but in case
		candidate = candidate.get("name") or candidate.get("candidate") or str(candidate)

	# On standalone Press, press.api.bench.deploy returns a Deploy Candidate BUILD name,
	# not a Deploy Candidate. wait_for_bench_flip below compares against Deploy Candidate
	# names, so without this translation the poll can never match and the tool always
	# reports 'timeout' with the misleading hint "the Deploy Candidate itself does not
	# exist" — while the build is in fact running fine.
	build = None
	if frappe.db.exists("Deploy Candidate Build", candidate):
		build = candidate
		candidate = (
			frappe.db.get_value("Deploy Candidate Build", build, "deploy_candidate")
			or candidate
		)

	# Step 2 — poll until flip or timeout. Frappe HTTP requests are blocked
	# from sleeping inside a transaction; commit each iteration so reads
	# pick up the agent's writes when the bench flips.
	start = time.monotonic()
	deadline = start + max_wait
	last_poll: dict[str, Any] = {}
	while time.monotonic() < deadline:
		frappe.db.commit()
		last_poll = wait_for_bench_flip(site_name=site_name, target_candidate=candidate)
		if last_poll["status"] == "flipped":
			elapsed = int(time.monotonic() - start)
			return {
				"candidate": candidate,
				"build": build,
				"status": "flipped",
				"elapsed_seconds": elapsed,
				**{k: v for k, v in last_poll.items() if k != "status"},
			}
		time.sleep(max(0, min(poll_interval, deadline - time.monotonic())))

	elapsed = int(time.monotonic() - start)
	return {
		"candidate": candidate,
		"status": "timeout",
		"elapsed_seconds": elapsed,
		**{k: v for k, v in last_poll.items() if k != "status"},
	}


@frappe.whitelist()
def site_update_and_wait(
	site_name: str,
	target_candidate: str,
	skip_failing_patches: bool = False,
	skip_backups: bool = False,
	max_wait_seconds: int = 1500,
	poll_interval_seconds: int = 5,
) -> dict[str, Any]:
	"""Trigger a Site Update (migrate to latest bench) + block until flipped.

	On standalone Press setups, a successful Deploy Candidate Build does NOT
	auto-flip sites onto the new bench — each site needs an explicit
	site_update call. This wraps schedule_update + poll into one blocking
	call so an agent doesn't have to manage the two-step dance manually.
	Companion to bench_deploy_and_wait: build → then call this per site.
	"""
	import time

	poll_interval = max(5, int(poll_interval_seconds))
	max_wait = min(HTTP_WAIT_CAP_SECONDS, max(poll_interval, int(max_wait_seconds)))

	site = frappe.get_doc("Site", site_name)

	# The Deploy Candidate Difference that SiteUpdate needs is written a moment AFTER the
	# build reports Success, so a call issued straight after bench_deploy_and_wait races it
	# and dies with "Could not find suitable Destination Bench". That is a timing artefact,
	# not a real missing bench, so retry briefly instead of making the caller re-issue the
	# whole tool call and re-guess the cadence.
	# one deadline for the whole call, retries included: gunicorn ends the request at 120 s (0.7.49)
	start = time.monotonic()
	deadline = start + max_wait
	job_name = None
	last_error = None
	for _attempt in range(6):
		try:
			job_name = site.schedule_update(
				skip_failing_patches=skip_failing_patches,
				skip_backups=skip_backups,
			)
			break
		except frappe.ValidationError as exc:
			if "Destination Bench" not in str(exc):
				raise
			last_error = str(exc)
			frappe.db.rollback()
			site.reload()
			if time.monotonic() + 10 > deadline:
				break
			time.sleep(10)
	if job_name is None:
		frappe.throw(
			f"site_update could not be scheduled for {site_name!r} within {max_wait}s "
			f"(retried every 10s): {last_error}. If this persists the Deploy Candidate Difference for "
			f"{target_candidate!r} is genuinely missing — confirm the build succeeded with "
			"deploy_candidate_status.",
			frappe.ValidationError,
		)
	frappe.db.commit()

	last_poll: dict[str, Any] = {}
	while time.monotonic() < deadline:
		frappe.db.commit()
		last_poll = wait_for_bench_flip(site_name=site_name, target_candidate=target_candidate)
		if last_poll["status"] == "flipped":
			elapsed = int(time.monotonic() - start)
			return {
				"site": site_name,
				"status": "flipped",
				"site_update_job": job_name,
				"elapsed_seconds": elapsed,
				**{k: v for k, v in last_poll.items() if k not in ("status", "site")},
			}
		time.sleep(max(0, min(poll_interval, deadline - time.monotonic())))

	elapsed = int(time.monotonic() - start)
	return {
		"site": site_name,
		"status": "timeout",
		"site_update_job": job_name,
		"elapsed_seconds": elapsed,
		**{k: v for k, v in last_poll.items() if k not in ("status", "site")},
	}


@frappe.whitelist()
def site_update_with_hint(name: str, skip_failing_patches: int | bool = False) -> dict[str, Any]:
	"""Friendlier wrapper around press.api.site.update.

	Press's underlying site_update throws 'Could not find suitable Destination
	Bench' for TWO different conditions — confusing because the message
	suggests the destination bench is missing when usually it's that no NEWER
	candidate has been built yet. This wrapper pre-checks and returns a
	structured hint so the calling agent knows exactly what to do next.
	"""
	if not frappe.db.exists("Site", name):
		frappe.throw(f"Site {name!r} not found", frappe.DoesNotExistError)

	site = frappe.db.get_value(
		"Site", name, ["name", "bench", "group", "server", "status"], as_dict=True
	)

	# Pre-flight #1: any Deploy Candidate Difference from source candidate?
	source_candidate = frappe.db.get_value("Bench", site.bench, "candidate")
	diff_count = frappe.db.count(
		"Deploy Candidate Difference",
		{"group": site.group, "source": source_candidate},
	)
	if not diff_count:
		# No newer candidate has been built. Suggest the next step.
		newer_bench = frappe.db.get_value(
			"Bench",
			{"group": site.group, "server": site.server, "status": "Active",
			 "candidate": ["!=", source_candidate]},
			"name",
		)
		hint = (
			"No newer Deploy Candidate exists for this site's Release Group. "
			"Build one first: call release_group_create_deploy_candidate("
			f"name={site.group!r}) then deploy_candidate_schedule_build(...)."
		)
		if newer_bench:
			hint = (
				f"A newer Active bench {newer_bench!r} exists on this server, "
				"but no Deploy Candidate Difference has been computed yet. "
				"This usually self-resolves within ~60s; retry after a brief wait."
			)
		return {
			"ok": False,
			"site": name,
			"source_bench": site.bench,
			"source_candidate": source_candidate,
			"reason": "no_destination_candidate",
			"hint": hint,
		}

	# Pre-flight #2: any Active bench with a different candidate on same server?
	dest = frappe.db.get_value(
		"Bench",
		{"group": site.group, "server": site.server, "status": "Active",
		 "candidate": ["!=", source_candidate]},
		"name",
	)
	if not dest:
		return {
			"ok": False,
			"site": name,
			"source_bench": site.bench,
			"reason": "no_active_destination_bench",
			"hint": (
				"Deploy Candidate Differences exist but no Active bench on the "
				"same server has a different candidate. Either the build is "
				"still running (poll bench_provision_progress) or the build "
				"failed (check deploy_candidate_status)."
			),
		}

	# Pre-flight passed — call Press's real site_update.
	from press.api.site import update as _press_site_update

	job_name = _press_site_update(name=name, skip_failing_patches=bool(skip_failing_patches))
	return {
		"ok": True,
		"site": name,
		"site_update": job_name,
		"destination_bench": dest,
	}
