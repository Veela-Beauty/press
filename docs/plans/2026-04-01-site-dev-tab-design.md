# Site Dev Tab Design

**Goal:** A "Dev" tab on every Frappe Press site detail page that gives developers all dev-relevant status and actions in one place.

**Approved approach:** Approach A — 4 status-action cards in a grid row, recent errors table below, plus a "Push to GitHub" button.

---

## Layout

```
┌─────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌───────────────────┐
│ Developer Mode  │ │ Scheduler        │ │ Migration        │ │ Cache             │
│ ● Enabled       │ │ ● Running        │ │ Last: 2h ago     │ │                   │
│ [Disable Dev]   │ │ (read-only)      │ │ [Migrate Now]    │ │ [Clear Cache]     │
└─────────────────┘ └──────────────────┘ └──────────────────┘ └───────────────────┘

[Push to GitHub]

┌─ Recent Errors ────────────────────────────────────────────────────────────────────┐
│ 2m ago  | Install App Failure        | [View Job]                                 │
│ 1h ago  | Update Site Failure        | [View Job]                                 │
└────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Cards

| Card | Status source | Status display | Action |
|------|--------------|---------------|--------|
| Developer Mode | `site.doc.is_development_site` | `● Enabled` / `● Disabled` | Enable / Disable Dev Mode |
| Scheduler | `press.api.site.get_scheduler_status(name)` | `● Running` / `● Paused` | None (read-only) |
| Migration | `press.api.site.get_migration_status(name)` | `Last: X ago` / `Never` | Migrate Now |
| Cache | — | — | Clear Cache |

---

## Push to GitHub

- Button above the errors table: **"Push to GitHub"**
- Opens a dialog:
  - App dropdown (apps in site's bench, from `frappe.get_all("Bench App", {"parent": bench_name})`)
  - Commit message input (default: `"WIP"`)
- Calls: `press.press.doctype.bench.bench_dev_overview.push_app_to_github(bench_name, app, message)`
- Backend: uses `bench.docker_execute(cmd, subdir=f"apps/{app}")` to run:
  ```
  git add -A && git commit -m "<message>" && git push
  ```
- Returns `ExecuteResult` dict: `{status, output, returncode}`
- UI shows: success toast with output snippet, or error toast with stderr

---

## Recent Errors

- Source: `press.api.site.get_recent_errors(name)` — last 10 failed Agent Jobs for this site
- Columns: Time (relative) | Job Type | [View Job] link
- Shows "No recent errors" when empty
- Auto-reloads after any action

---

## Data Loading

```
mount() → load scheduler status + migration status + recent errors in parallel
site doc → from getCachedDocumentResource (already loaded by parent page)
```

All three status calls use `createResource({ url, params: { name }, auto: true })`.

---

## Component

Single file: `dashboard/src/components/SiteDevTab.vue`
Replaces current minimal version (currently only has dev mode toggle).

Props: `{ site: String }` (site name)

---

## Files Changed

| File | Change |
|------|--------|
| `press/press/doctype/bench/bench_dev_overview.py` | Add `push_app_to_github(bench_name, app, message)` |
| `press/press/doctype/bench/test_bench_dev_overview.py` | Add tests for `push_app_to_github` |
| `dashboard/src/components/SiteDevTab.vue` | Full rewrite |

`dashboard/src/objects/site.js` already has the Dev tab wired — no changes needed there.
