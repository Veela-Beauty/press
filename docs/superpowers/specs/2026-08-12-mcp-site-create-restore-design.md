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

## Why two tools, not three

An earlier draft of this spec called for a third tool, `site_backup_stage`, on the
reasoning that `api.site.restore` takes **Remote File** docnames rather than file paths:

```python
def restore_site_from_files(self, files, skip_failing_patches=False):
    self.remote_database_file = files["database"]   # Remote File docname
```

That constraint is real, but the conclusion was wrong. **The staging endpoint already
exists**: `press.api.site.upload_backup_file()` is whitelisted, takes a multipart upload,
streams to disk in 8 MB chunks, enforces a 5 GiB cap, checks `Site` write permission, and
creates the Remote File record itself (pushing to MinIO when a bucket is configured). A
third tool would have reimplemented it.

It also cannot be an MCP tool. MCP dispatch passes JSON `args`; a multipart binary body has
no representation there. So the upload stays a plain Frappe API call.

Full path, with no browser and only the MCP token as the starting credential:

| Step | Call | Credential |
|---|---|---|
| 1 | `mint_dashboard_login_url` → `sid` | MCP token |
| 2 | POST `press.api.site.upload_backup_file` (multipart) → Remote File docname | `sid` cookie |
| 3 | `site_restore(site, database=<remote_file>)` | MCP token |

Verified on `autodeploypanel.mvpstorm.com`: a minted `sid` authenticates
`frappe.auth.get_logged_user` (returns the token owner), `upload_backup_file` answers `417`
to a GET (present, POST-only), and `is_s3_configured` returns `true`.

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

**Security decision — no `source_url` argument.** A parameter that made Press download the
backup itself would be an SSRF primitive on the control plane: the caller picks a URL and
the control plane fetches it, with its own network position and credentials. The upload
therefore stays a push from the caller to `upload_backup_file`. If server-side fetch is ever
wanted it needs an explicit domain allowlist and its own tool, so the risk tier shows in the
catalog instead of hiding behind an optional argument.

### 2. `site_restore` — risk `high`

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
| `press/mcp_server/site_ops.py` | **new** — both implementations (matches the existing `bench_ops.py` / `file_ops.py` pattern) |
| `press/mcp_server/tools.py` | 2 `TOOLS` entries (`method`, `description`, `required_args`, `args_schema`, `risk`) |
| `press/mcp_server/help.py` | 2 entries in the category map → `site_lifecycle` |
| `press/mcp_server/server.py` | register both in `_extract_target()` + repair the two broken tools |
| `press/mcp_server/test_site_ops.py` | **new** — implementation tests |
| `press/mcp_server/test_server.py` | scoping test + the registry guard test |

**File-size note.** `tools.py` (925 lines) and `server.py` (973) are both over the 700-line
gate. The implementation therefore goes in a new `site_ops.py`; what lands in `tools.py` is
registry data only (~30 lines of `description` and `args_schema`). Splitting the registry
itself is a real refactor — `_ARG_FRAGMENTS` and `_schema()` live in `tools.py`, so a second
registry module would import from it circularly — and it belongs in its own commit rather
than tangled with a feature, where it would make both harder to review.

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
`TOOLS`, so both tools appear in the Issue Token dialog and the guide with their risk
badges once registered — no per-tool UI work. What needs checking is that `site_restore`
renders as a **high**-risk chip so nobody grants it by accident while clicking through a
token.

`components/SiteDatabaseRestoreDialog.vue` already covers human restore. It is untouched.

## Testing

1. `args_schema` for both tools validates against `_ARG_FRAGMENTS` (a missing fragment
   raises `KeyError` at import — a broken schema fails the test suite, not production).
2. `_extract_target` returns the right `(doctype, name)` for each tool, including the two
   repaired tools.
3. Scoping: a token scoped to site A is refused when it calls `site_restore` on site B.
4. `site_restore` is rejected unless the token carries explicit high-risk approval.
5. `site_create` refuses a name that already exists, and refuses a missing release group,
   before it reaches `api.site.new`.

### The guard test (the point of this section)

`252991d2a` was titled *"register six tools missing from `_extract_target`"* — the same class
of bug this spec repairs two more instances of. Fixing the third and fourth by hand invites
a fifth. So the suite gets a test that walks `TOOLS` and fails if **any** tool declaring a
`site` / `site_name` / `release_group` / `name` argument is absent from `_extract_target`
and not in `RESOURCELESS_TOOLS`. That converts a recurring silent gap into a red test at
the moment the tool is added.

## Deploy

Press runs on **press-ctrl**. Per the standing lesson, Press work is edited and tested on
the server — you cannot push from press-ctrl. So: land the branch on GitHub from the dev
box, pull it on the server, run the MCP tests there, `bench build` the dashboard for the
Vue catalog change, restart, then verify with a live `list_tools` that all three appear
with the right risk tiers.

## Success criteria

- `list_tools` shows `site_create` (`medium`) and `site_restore` (`high`).
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
