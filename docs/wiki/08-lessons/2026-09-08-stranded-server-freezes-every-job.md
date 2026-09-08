# Lessons Learned — 2026-09-08: a Server stuck at "Pending" froze every job on it

> Client report: *"pending for ever ... and it keep in old bench"* (release group
> `bench-0014`, server `u5-default`). Four benches sat at `Pending` for 8 days and
> four sites could not leave a 24-day-old bench.
>
> The agent was healthy the whole time. Press had simply stopped listening.

## Lesson 1 — `Server.status != "Active"` silently deletes a whole box from Press

### What it is
Two schedulers gate on the Server's status, and neither logs when it skips:

```python
# agent_job.py
def poll_pending_jobs_server(server):
	if frappe.db.get_value(server.server_type, server.server, "status") != "Active":
		return                      # no job on this box is ever polled again

# site_update.py
def schedule_updates():
	servers = frappe.get_all("Server", {"status": "Active", "is_decommissioned": 0}, pluck="name")
	                                    # no site on this box is ever auto-updated
```

One field, two whole subsystems. There is no alert, no log line, and nothing in the
dashboard says the server was dropped.

### How it bit us
`u5-default` was set to `Pending` at 2026-08-31 09:45 (a bare `db.set_value`, so not
even a Version row to find it by). After that:

- every agent job on the box stayed `Pending` forever, however healthy the agent was;
- every site on the box was pinned to its current bench, because the auto-update
  scheduler never considered the server.

The dashboard rendered the benches as "Pending" and the sites as normal, so the box
read as *busy* rather than *abandoned*. That is why it went unnoticed for 8 days.

### How to spot it
**Ask the agent what it thinks, and compare with Press.** This is the single most
useful probe in this whole class of bug:

```python
job = frappe.db.get_value("Agent Job", "<name>", ["job_id", "status"], as_dict=True)
res = Agent("<server>").request("GET", f"jobs/{job.job_id}")
print("press:", job.status, "| agent:", res["status"])
```

If the agent says `Success` and Press says `Pending`, the agent is fine — Press is not
collecting. Check `Server.status` before you touch anything on the box:

```python
frappe.db.get_value("Server", "<server>", ["status", "halt_agent_jobs", "is_decommissioned"])
```

`detect_stranded_servers()` (hourly, `press/press/doctype/server/stranded_server_detection.py`)
now reports any server that is not Active while it still owns Active benches or live
sites. It deliberately does not auto-correct the status — a server can legitimately be
`Installing` or `Broken`, and guessing `Active` for a genuinely broken box is worse
than the silence.

## Lesson 2 — writing `Agent Job.status` without the callback orphans the record

`stuck_job_recovery._mark_failure()` used a bare `frappe.db.set_value`, which skips
`process_job_updates`. The job went `Failure`, but the **Bench it was created for never
left `Pending`** — and a bench at `Pending` is invisible to `archive_broken_benches` and
to every retry path, so it stays there forever.

The proof was a contrast on the same server on the same day:

| Bench | How its New Bench job failed | Where it ended up |
|---|---|---|
| 000039–000042 | normal agent failure → callback ran | `Broken` → auto-archived |
| 000037/38/43/44 | marked Failure by the cron | **`Pending`, 8 days later** |

Any code that sets a terminal `Agent Job.status` by hand must run
`process_job_updates(job_name)` afterwards, or it strands whatever the job was for.

## Lesson 3 — `"Undelivered"` is a real `Agent Job.status`

`process_new_bench_job_update()` mapped `Pending / Running / Success / Failure /
Delivery Failure` and indexed the dict directly, so an `Undelivered` job raised
`KeyError` and left the bench at `Pending`. The status literal has six values; a
`[job.status]` lookup over five of them is a latent crash.

## Lesson 4 — the site list painted over the real status

`Site.get_list_query` overrode the status of **every** non-Archived site whose bench had
an update available:

```python
for site in sites:
	if site.bench in benches_with_available_update:
		site.status = "Update Available"     # even if the site is Broken
```

`charity.sandbox.mvpstorm.com` had never been provisioned — no directory on the bench at
all — and showed as "Update Available" in the dashboard for 8 days. A status column that
can hide `Broken` is worse than no status column.

## Lesson 5 — `bench clear-cache` does not clear `app_hooks`

After adding an entry to `scheduler_events["hourly"]`, `frappe.get_hooks` kept returning
the old list through a full `supervisorctl restart` **and** a `bench --site X clear-cache`.
The hooks live under their own cache key:

```python
frappe.cache.delete_value("app_hooks")     # this is the one that matters
```

Verify a new scheduler entry is actually registered — never assume the restart did it:

```python
[h for h in frappe.get_hooks("scheduler_events")["hourly"] if "your_module" in h]
```

## Lesson 6 — the registry purge makes a stuck bench unfixable, so don't plan to retry it

`delete_old_images_from_registry` keeps only the live tag. When we went to re-provision
the four stuck benches, the registry held exactly one tag for the whole release group:

```
GET /v2/sandbox.mvpstorm.com/bench-0014/tags/list
{"name":"sandbox.mvpstorm.com/bench-0014","tags":["rhihll7e17"]}
```

Every stuck bench's image was gone. A bench whose image has been purged can never be
retried — the only path forward is a fresh deploy candidate and build. Check the registry
tag list before promising anyone a retry.

## Recovery recipe used

1. `df -h /` on the app server — the box was at 99%, which is what broke the agent originally.
2. Reclaim disk (remove containers/images for benches Press already lists as `Archived`).
3. `Server.status` back to `Active`, then `poll_pending_jobs_server(frappe._dict({"server": ..., "server_type": "Server"}))`
   — note it takes the **dict**, not a string; passing a string raises `AttributeError: 'str' object has no attribute 'server_type'`.
4. Everything else healed itself: the poller collected the finished job, the bench went
   `Active`, and the auto-update scheduler moved the sites on its own.
