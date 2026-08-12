# MCP tools: create a site and restore a backup — design

**Date:** 2026-08-12
**Branch:** `feat/mcp-site-create-restore`
**Status:** design, awaiting implementation

## Problem

The Press MCP server exposes 82 tools. A caller can migrate, update, clone, back up,
install apps on and SSH into a site — but **cannot create a site, and cannot restore a
backup into one**. Verified against the live catalog on `autodeploypanel.mvpstorm.com`:
the `site_*` family is activate / add_domain / backup / config_get / config_set /
db_processlist / deactivate / domains_list / file_read / file_write / install_app /
migrate / remove_domain / run_python / run_sql / schedule_update / set_host_name /
status / uninstall_app / update / update_and_wait / update_config_bulk. No create, no
restore.

Consequence: any workflow that needs a fresh site seeded from an existing database has
to leave the API and go through the dashboard by hand. That blocks automation of the
single most common support/QA task — "give me a copy of this data on a throwaway site".

**Triggering case.** A 440 MB (3.63 GB uncompressed) production backup of
`erpsys.liptoneg.com`, recovered from the Daman borg archive, needs to land on
`bench-0020` as an isolated test site. Every step except site-create and restore is
already automatable.

## Goals

1. Create a site through MCP.
2. Restore a database backup into a site through MCP.
3. Get a **local file** into a restorable state without a browser.
4. Keep the audit trail and token resource-scoping that every other tool has.

## Non-goals

- Restoring public/private file archives. The nightly Lipton backup contains database +
  site_config only; file archives need `bench backup --with-files` upstream. The tools
  will accept those keys because `api.site.restore` does, but they are not exercised.
- Physical/snapshot restores (`restore_site_from_physical_backup`).
- Replacing the dashboard's restore dialog. This is an API surface, not a UI rewrite.

## Why three tools, not two

`api.site.restore(name, files, ...)` does not take file paths. It takes **Remote File**
docnames:

```python
def restore_site_from_files(self, files, skip_failing_patches=False):
    self.remote_database_file = files["database"]   # Remote File docname
    self.remote_public_file   = files["public"]
    self.remote_private_file  = files["private"]
```

So `site_restore` alone is only usable against a backup that is *already* in Press's S3.
A local file has no route in. The dashboard solves this with two calls that are already
whitelisted:

| API | Role |
|---|---|
| `api.site.get_upload_link(file, parts=1)` | presigned S3 PUT URL |
| `api.site.uploaded_backup_info(file, path, type, size, url)` | creates the Remote File record |

Exposing those as one staging tool is what makes the pair usable end to end.

## Design

### 1. `site_create` — risk `medium`

```
method: press.api.site.new
args:   { name, group, apps?, plan?, cluster?, server?, domain? }
```

`api.site.new` takes a single `site` payload dict; the tool assembles it from flat args so
callers don't hand-build nested JSON. `group` (Release Group) is required here even though
the API can infer it — inference picks a shared bench, which is the wrong default for a
tool whose main use is "put a site on *this* bench".

### 2. `site_backup_stage` — risk `medium`

```
method: (new thin wrapper) press.mcp_server.site_ops.stage_backup_upload
args:   { file, size, type = database|public|private|config, parts? }
returns { upload_url, remote_file_hint, path }
```

Two-step by design: the tool returns a presigned URL, the **caller** uploads the bytes,
then calls again with `confirm: true` to run `uploaded_backup_info` and get the Remote
File docname. Press never fetches a URL supplied by the caller.

**Security decision — presigned client upload, not server-side fetch.** A
`source_url` parameter that made Press download the file would be an SSRF primitive on the
control plane: the caller chooses a URL and the control plane fetches it, with its own
network position and credentials. Rejected for v1. If server-side fetch is ever added it
needs an explicit domain allowlist, and it should be a separate tool so the risk tier is
visible in the catalog rather than hidden behind an optional argument.

### 3. `site_restore` — risk `high`

```
method: press.api.site.restore
args:   { site, database, public?, private?, config?, skip_failing_patches?, skip_tables? }
```

`high`, not `medium`: this **overwrites the target site's database**. It belongs in the
same tier as `site_run_sql` and `site_uninstall_app`, which means it needs explicit
per-token approval rather than riding along with medium-risk site management.

## Touch points

| File | Change |
|---|---|
| `press/mcp_server/tools.py` | 3 `TOOLS` entries (`method`, `description`, `required_args`, `args_schema`, `risk`) |
| `press/mcp_server/help.py` | 3 entries in the category map → `site_lifecycle` |
| `press/mcp_server/server.py` | add the 3 names to the site-targeted set in `_extract_target()` |
| `press/mcp_server/site_ops.py` | **new** — the `stage_backup_upload` wrapper |
| `press/mcp_server/test_server.py` | scoping + schema tests |
| `press/mcp_server/test_site_ops.py` | **new** — staging wrapper tests |

`_extract_target` is not optional. A tool that carries a resource argument but is missing
from that function is refused at call time — the server returns a `PermissionError`
telling you it "refuses to bypass token resource scope". Skipping it ships a dead tool.

### Bundled fix (same function, already broken)

`app_git_status` and `bench_provision_progress` are both in the catalog and both
uncallable today, with exactly that error. They carry `release_group` but were never
added to `_extract_target`. Two lines in the set we are already editing. `site_create`
takes `group` rather than `site`, so it needs the release-group branch anyway — the fix
and the feature touch the same code.

## Vue surface

The MCP catalog UI (`dashboard/src/pages/devtools/mcp/`, `components/mcp/`) renders from
`TOOLS`, so the three tools appear in the Issue Token dialog and the guide with their risk
badges once registered — no per-tool UI work. What needs checking is that `site_restore`
renders as a **high**-risk chip so nobody grants it by accident while clicking through a
token.

`components/SiteDatabaseRestoreDialog.vue` already covers human restore. It is untouched.

## Testing

1. `args_schema` for all three validates against `_ARG_FRAGMENTS` (a missing fragment
   raises `KeyError` at import — a broken schema fails the test suite, not production).
2. `_extract_target` returns the right `(doctype, name)` for each tool, including the two
   repaired tools.
3. Scoping: a token scoped to site A is refused when it calls `site_restore` on site B.
4. `site_restore` is rejected unless the token carries explicit high-risk approval.
5. Staging wrapper: `confirm: false` returns a URL and creates nothing; `confirm: true`
   creates exactly one Remote File.

## Deploy

Press runs on **press-ctrl**. Per the standing lesson, Press work is edited and tested on
the server — you cannot push from press-ctrl. So: land the branch on GitHub from the dev
box, pull it on the server, run the MCP tests there, `bench build` the dashboard for the
Vue catalog change, restart, then verify with a live `list_tools` that all three appear
with the right risk tiers.

## Success criteria

- `list_tools` shows `site_create`, `site_backup_stage`, `site_restore` with risk
  `medium/medium/high`.
- `app_git_status` and `bench_provision_progress` answer instead of erroring.
- The Lipton backup reaches a new site on `bench-0020` with no browser involved.
- Every call appears in the MCP Call Log with args and duration.

## Risks

| Risk | Mitigation |
|---|---|
| Restore overwrites the wrong site | `high` tier + resource scoping + the site name is a required arg with no default |
| A 3.63 GB restore exhausts disk on the target server | Check `df -h` before restore; not enforced by the tool in v1 — documented, not automated |
| The staged Remote File is left orphaned if the caller never confirms | Press's existing Remote File cleanup applies; no new lifecycle |
| Restored copy runs production side effects (emails, external syncs) | Out of scope for the tool. Caller's responsibility — pause the scheduler before the first migrate |
