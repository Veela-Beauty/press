# Watch Tower Section of the Dashboard

> The Watch Tower pages show every connected client site: its findings, errors, health and installed apps.
> Built in Press 0.7.26 to 0.7.31. All data comes from the Control Center hub app, not from Press itself.

## Who sees it

System users only. The sidebar group condition in `dashboard/src/components/NavigationItems.vue` is
`onboardingComplete && !isSaasUser && this.$session.isSystemUser`. The group has two entries:

| Entry | Route | Lit on |
|---|---|---|
| Overview | `/watch-tower/overview` | Overview and client pages |
| Apps | `/watch-tower/apps` | Apps and app pages |

`/watch-tower` redirects to `/watch-tower/overview`.

## Routes and pages

Routes are in `dashboard/src/router.js`. Pages are in `dashboard/src/pages/watch-tower/`.

| Path | Route name | File |
|---|---|---|
| `/watch-tower/overview` | Watch Tower Overview | `Overview.vue` |
| `/watch-tower/clients/:site` | Watch Tower Client | `Client.vue` |
| `/watch-tower/apps` | Watch Tower Apps | `Apps.vue` |
| `/watch-tower/apps/:app` | Watch Tower App | `AppDetail.vue` |

## Where the data comes from

Every read is a hub method in the app `sanad_ai_control_center`, module `watch_tower_hub`.

| Page | Method | Arguments |
|---|---|---|
| Overview | `overview.get_overview` | none |
| Overview, later pages of findings | `overview.get_findings` | `start` |
| Client | `client_profile.get_client` | `site` |
| Client, later pages of findings | `client_profile.get_open_findings` | `site`, `start` |
| Apps | `apps.get_apps` | `search`, `behind_only`, `start` |
| App | `apps.get_app` | `app`, `start` |

The caller needs the role Watch Tower Hub or System Manager.

All six methods answer GET only. frappe-ui posts by default, and Frappe refuses a POST to a GET-only method as
"Not permitted". So every `createResource` in these pages sets `method: 'GET'`. A page that forgets it shows an
error, not data. This was the 0.7.27 hotfix.

## What each page shows

**Overview**
- Five tiles at the top.
- Chart: new findings per day, one colour per client.
- List: Open Critical and High findings, 6 to a page.
- Table: Clients, one row per connected site. Since 0.7.41 "Last read" sits under the Status badge and a Users column
  shows "N / cap" with "Near cap" (90%) or "Over cap" (100%) and "N active" under it; "no cap set" when no User Cap is
  typed on the hub; "-" until the site runs watch_tower 0.7.3; greyed "last known" for a site that stopped reporting.
- Checks (0.7.53, hub 0.2.24, client watch_tower 0.7.6): "Clients needing action" also counts a Production client with
  a failing check, and its chip reads "1 check failing" when that is the only reason. The client's row shows
  "AccuHub link failing" (or "2 checks failing") in place of "read just now", the sites' messages on hover. A test
  copy shows the line in its row but is not counted: copies run with the scheduler paused on purpose.

**Client page**
- Header: client name, status and environment badges, last error if any. Since 0.7.53 the details line ends with
  "Checks" and one badge per check (green working, light red failing), and each failing check adds a line: what the
  site says and since when.
- Six tiles (Users added in 0.7.41: enabled / cap, active in 30 days, a flag with the level or the % of the cap) and
  the charts: new findings per day, open findings by type.
- Open findings, 6 to a page.
- Top errors.
- Site health per day, last 30 days (one reading per client per day).
- Installed apps, apps that are behind first, 6 to a page.

**Apps**
- One row per app, with a bar showing how its clients stand (current or behind).
- Toggle Behind or All, a search box, 20 rows to a page.

**App page**
- The clients running that app: behind first, then Production. 20 to a page.
- Used to plan an update of one app across clients.

## Components and why they look like this

| File | What it is |
|---|---|
| `WtTile.vue` | One number tile: label, value, comparison, optional flag |
| `WtStackedBars.vue` | SVG stacked bar chart per day |
| `WtHBars.vue` | SVG horizontal bars |
| `WtPager.vue` | Previous and next, hidden when one page holds everything |
| `paging.js` | `usePages`, the paging helper |
| `shared.js` | Colours, badge classes, time helpers |
| `watch-tower.css` | Styles shared by the pages |

**Charts are SVG components, not ECharts.** They were ported from the approved HTML prototype so the pages
match it. There is no chart library in the bundle for these pages.

**Colours** are in `shared.js` and were checked with the dataviz palette validator (light mode, both sets pass):

- Clients: `#2a78d6`, `#eb6834`, `#1baf7a`. Any further client is grouped as Other: `#4a3aa7`.
- Severity: Critical `#d03b3b`, High `#eda100`, Medium `#4a3aa7`, Low `#2a78d6`. Order is red, amber, violet, blue.
- `#c2c6cb` is the remainder part of a mini bar. It is not a series.

**`WtTile` is a `div` with `role="button"`.** Never write `<component :is="'button'">`. Vue resolves the string
`'button'` to frappe-ui's globally registered Button component, which drew the tiles as small grey buttons
(fixed in 0.7.29). The same `style.css` forces a 6px radius on every `[role='button']`, so the tile sets its own
radius with `!important`.

**`watch-tower.css` loads with `<style scoped src="./watch-tower.css">`** so nothing leaks to other dashboard pages.

## Paging

`dashboard/src/pages/watch-tower/paging.js` exports `usePages(url, first, params)`.

- Page 1 arrives with the page's own read. No extra request.
- Later pages come from the paged read (`get_findings`, `get_open_findings`), GET only, with `start`.
- `PAGE_ROWS` is 6 and must match `PAGE_ROWS` in the hub's `page_data`. Change one, change both.
- The Apps pages use 20 (`PAGE` in `Apps.vue` and `AppDetail.vue`, matching the hub's `apps.PAGE`).
- `WtPager` hides itself when one page holds everything.
- On the Client page the installed apps list is paged in the browser from the data already loaded.

## Prototypes

The pages follow these approved prototypes, kept on the owner's machine under
`~/docs/prototypes/watch-tower-press/`:

- ACM-SP-03 (v2): Overview and Client pages.
- ACM-SP-04: Apps page.
- ACM-SP-05: the desk look of the dashboard.
- ACM-SP-06 (v4): users against the licence cap (`watch_tower_press_v4_users_prototype.html`).
- ACM-SP-07: a client's checks, an overlay on the live pages (`checks/index.html`).

## Version history

| Press | What changed |
|---|---|
| 0.7.26 | Watch Tower page, first version |
| 0.7.27 | GET fix: every read sets `method: 'GET'` |
| 0.7.28 | v2 redesign: charts and the client page |
| 0.7.29 | Tiles draw as tiles (the `role="button"` fix) |
| 0.7.30 | Lists in pages of 6 |
| 0.7.31 | Apps page and app page; the apps grid left the Overview |
| 0.7.32 to 0.7.36 | The desk look, built in another session |
| 0.7.37 | `Header` draws its `#actions` slot. Seven pages never showed their buttons: Daman Overview, Job Queue, Alerts, Dev Overview, Infrastructure, Telephony, Notifications |
| 0.7.38 | Search box in the top bar; menu scrollbar only on hover; a group opens the menu beside the page, not over it |
| 0.7.39 | Watch Tower alert emails are actually sent, see [the lesson](../08-lessons/2026-11-22-watch-tower-alert-emails-never-sent.md) |
| 0.7.40 | Watch Tower docs |
| 0.7.41 | Users against the licence cap: Users column on the Overview, Users tile on the client page. Needs hub 0.2.18 first |
| 0.7.53 | A client's checks: the needing-action tile, the row line, the client header badges and messages. Needs hub 0.2.24 first |
| 0.7.61 | Docs: this page covers the checks |

## Deploy

Order matters when a Press page needs a new hub read: deploy the hub first, then Press. One exception: hub 0.2.15
went with Press 0.7.31 Press first, because the hub stopped sending data that the old Overview still drew.

Press deploy on press-ctrl, in this order:

1. Bundle `origin/cloudflare-dns`.
2. `press_ff_preview.sh`
3. `press_ff_deploy.sh`
4. `press_dashboard_build.sh`
5. Restart the web program only. Never restart the workers.

The scripts live in the owner's `~/docs/scripts/watch-tower/`.

## Live checks

These scripts live in the owner's `~/docs/tests/`:

- `watch-tower/press-page-v2-2026-11-21/live_check.py`: the 3-click job, tiles, charts, pages and a human-read probe.
- `press-dashboard-desk-look-2026-11-21/header_actions_check.py` and `fixes_0738_check.py`: the 0.7.37 and 0.7.38 fixes.

They sign in with a one-time login key. Press allows 5 keys an hour per address. Past that it answers 500, not 429.
`press_login.py` stops a check before that limit.
