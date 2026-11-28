# Changelog

This file documents changes (current commit level since, no tagged releases yet).

---

## 28-11-2026: MCP tokens: Edit tools, Confirm it's you, the token kept off the screen (0.7.90)

### Added
- **Edit tools** on each active token: the Issue Token picker with this token's tools ticked, each change marked
  Added or Removed. The token stays the same, so there is nothing to copy again. Adding a tool needs Confirm it's
  you; removing only does not. A high-risk tool turns risky tools on for the token (pending approval for a user who
  is not a System User, as at issue).
- **Confirm it's you** with three ways, any one enough: the authenticator app (an app linked during this login does
  not count, as linking needs no password), an email code, or the password. A confirm holds 10 minutes, as the site
  logins' does; issuing a token counts as one. 5 wrong tries lock it for 10 minutes.
- **Token history** under Show details: who issued, reissued, copied or changed the token, when, and how they
  confirmed. Kept in Press MCP Admin Action (new types Issue, Reissue, Edit Tools, Copy Token: needs a migrate).

### Changed
- The token is masked on screen after Issue, Reissue or Copy token (first 8 characters, then dots) in all four tabs
  and the raw row. **Show** and **Copy** ask Confirm it's you; Copy still puts the full token in what is pasted.
- **Copy token** (`recover_token`) and **Reissue** need a recent Confirm it's you. Until now an open dashboard
  session alone handed out a token's plaintext (owner, 28 Nov: "easy copy").
- The Issue Token picker lives in `ToolScopePicker.vue`, shared with Edit tools; its search also matches tool labels.

---

## 28-11-2026: MCP site_archive tool (0.7.89)

### Added
- `site_archive` (high risk): archives a site through Press's own `api.site.archive`, so the team check, the final
  offsite backup and the upstream removal all stay the dashboard's. It refuses any site that is not Inactive, so
  dropping a site always takes two calls (`site_deactivate`, then `site_archive`). It also archives only once a
  healthy offsite backup with files exists from after the switch-off (Success, offsite, all three files in storage,
  database file not empty): when there is none it starts one and answers `backup_started`, so the caller calls
  again until `archive_queued` (owner: a backup before every drop, and make sure it is healthy). Scoped to its site, listed under
  Dangerous in help and in the Issue Token dialog, added to the dev-box proxy catalog. Asked for by the owner on
  28 Nov after two throwaway test sites could only be switched off, not archived.

---

## 27-11-2026: Infrastructure page tabs in one row with the page actions (0.7.88)

### Changed
- The Servers | Inventory tabs sit in the page's header row, with the open tab's actions at the right (List / Cards
  and "updated" on Servers, "Open full screen" on Inventory). The empty band above the tabs and the second row are gone
  (owner 27 Nov: two apps inside each other).
- Inside the Inventory tab NetBox drops its own logo, title, menu and user menu and shows one row of links
  (sanadeoi-infra press-ctrl/netbox brand v=8).

---

## 27-11-2026: Inventory is a tab on the Infrastructure page (0.7.86)

### Changed
- The Infrastructure page has two tabs: Servers (the page as before) and Inventory, which shows our NetBox
  (Accurate Systems Infrastructure) inside the page, signed in through AutoDeploy with no login screen. "Open full
  screen" opens it alone. The Inventory link at the top right is gone (owner: in a bad place).
- The open tab is kept in the address (`?tab=inventory`); NetBox loads on the first open and keeps its place.
- Tabs use the shared tab style (`components/_shared/tabClasses.js`).
- NetBox lets only this page show it in a frame (`frame-ancestors` in its nginx, sanadeoi-infra press-ctrl/netbox).

---

## 27-11-2026: disk, SSH and site-down alerts email when something starts or clears (0.7.85)

### Changed
- A disk, SSH or site-down alert emails when a server or site joins the failing set (disk: also when one reaches 95%).
  While the same set keeps failing, the hourly repeat goes to the 08:00 report instead of an email. When nothing fails
  any more, one "cleared" email goes out (site: to the same people as the site-down email). The set is kept in Redis
  (`press/watch_tower/alerts/alert_state.py`, persistent key `wt:alert_set:*`).
- Before, a new count of servers or a new error text started a new series of three emails: 62 of the 263 alerts Brevo
  held on 27 Nov 2026. The disk fingerprint also never held the server name (it read a field the check does not set).
- A refused first email is tried again at the next check: the set is kept only after the email went out, and the
  "cleared" email forgets it only after it went out. When Redis cannot be read, the alert is sent now.
- Disk: 95% holds until the server is below 85% again (no new email at each crossing of 95%). A server with no
  reading (unreachable, or no `df` line) keeps its place and is never a recovery; nor is an empty server list. The SSH
  and site checks send no "cleared" email when they had nothing to check.

### Tests
- `python3 -m unittest test_alert_state test_alert_on_change_wiring` (from `press/watch_tower/alerts`): 8 offline
  tests; the 3 wiring tests fail on the 0.7.84 code (a repeat emails instead of going to the report).
- Not covered: two overlapping runs of one check can both send (the read and the write are not atomic); the hourly
  job runs the checks one after another.

---

## 27-11-2026: sign in with GitHub and Google; 2FA holds on every sign-in path (0.7.84)

### Added
- The login page's GitHub button works: `press/api/github_login.py` (GitHub OAuth web flow; one-time state in cache that
  must also match an HttpOnly SameSite=Lax cookie; only GitHub's primary verified e-mail; Cancel and GitHub failures go
  back to the login page). `press.api.github.login` (20 starts a minute per address) and `press.api.github.login_callback`
  are the entry points. Keys: site_config `github_login` (from the existing GitHub App mvpstorm-deploy).
- Google sign-in has its key (site_config `google_credentials`); its code was already there.
- 15 offline tests: `python3 press/api/tests/test_github_login_offline.py`.

### Security
- `press/api/oauth_finish.py`: the account step shared by Google and GitHub (moved from `google.py`). 2FA is now checked
  before every path: a Google sign-in through a product sign-up link used to skip it. Accounts are signed in under the
  user name AutoDeploy stores.

---

## 27-11-2026: Inventory link on the Infrastructure page (0.7.83)

### Added
- An "Inventory" link in the Infrastructure header opens Accurate Systems Infrastructure (our NetBox,
  https://netbox.mvpstorm.com) in a new tab. Staff only, like the page.

---

## 27-11-2026: a new site keeps its plan (0.7.82)

### Fixed
- A site made on a public server (press-f1, u4-default) lost the plan chosen for it and showed "No plan set" on its
  Overview: 64 of 98 sites on 27 Nov. `Site.validate_site_plan` swaps a dedicated-server plan for the cheapest
  public-server plan, and our four plans are all dedicated-server plans, so it found none and set the plan to empty.
  It now keeps the chosen plan when there is nothing to swap it for (`site.py`, one line).
- The MCP tool `site_create` refuses an empty or unknown plan with the list of plans to pick from, and its schema
  lists `plan` as required; its help text said an empty plan "lets Press pick", which was never true. Tests
  `test_create_refuses_an_empty_plan`, `test_create_refuses_an_unknown_plan`.

---

## 27-11-2026: Communications, SMS: codes per site, routes per country, log and cost by client (0.7.81)

### Added
- New DocTypes SMS Log (one row per SMS, no number and no text kept), SMS Provider (a local provider account, login encrypted)
  and Messaging Settings (routes per country). Site config keys `basher_sms_token` and `basher_sms_press_url` are internal.
- `press.api.messaging`: owner-only dashboard calls (sites, switch SMS codes on or off, log, cost by client, routes,
  providers, test SMS) and `request_sms`, which a Basher site calls before each SMS: Press checks the site's key, picks
  the route for the number's country, logs the cost and answers "firebase" or sends through the local provider.
- `request_sms` is no relay: a site sends a 6-digit code and a language, Press writes the SMS text itself, and anything else is refused.
- Caps on `request_sms`: 5 SMS per number per hour and a per-site hourly cap (Messaging Settings, default 200, set on the Routes page); over a cap it answers "refused". A provider failure answers "failed" and the log row stays not delivered.
- The smseg sender (`press/messaging/providers/smseg.py`); a new provider type is one more module.
- Menu: Telephony moves under a new Communications group, with an SMS group of five pages (Sites, Log, Cost by client,
  Routes, Providers).

---

## 27-11-2026: site logins and sharing on the site Overview (0.7.80)

### Added
- A "Logins and sharing" card on each site's Overview (prototype PRS-SP-17): the share login (a normal user Press
  creates on the site with a chosen Role Profile) and the Administrator login, each hidden until Show, and "Copy share
  message" (site link, user, password). Team admins see the Administrator login, never on a confidential site; anyone
  whose Press role covers the site sees the share login. Create and reset are for team admins.
- Before every Show, copy, share, create or reset: a 6-digit code from the user's authenticator app, or an emailed
  code; then no code for 10 minutes. A user without an app links one inside the same dialog (QR code, setup key,
  recovery codes). Endpoints in `press/api/site_logins.py`, each checked for the team and the Press role.
- Every action is recorded in Site Activity as "Share Login" (who, what, how verified); the last 5 show in the card.
- Site fields `share_user`, `share_password` and the Site Activity option "Share Login": needs a migrate.
- Wiki: [Site Logins and Sharing](docs/wiki/01-backend-development/site-logins-sharing.md).

## 27-11-2026: An archived bench's Code Server ends Archived, not Broken (0.7.79)

### Fixed
- A Code Server runs inside its bench's container, so once the bench is archived the editor is already gone, but the
  agent's "Archive Code Server" route checks that the bench exists and always failed: the record ended Broken and its
  name was never released. Since 0.7.78 the old bench's Code Server is archived only after that bench is Archived, so
  every deploy hit this. Now archiving skips the agent call when the bench is Archived and counts that part as done:
  the proxy upstream is removed, the record ends Archived and the name is released. The job callback reads the newest
  job of each kind, and stops if the other callback already renamed the record. Code in `code_server_archive.py`.

## 27-11-2026: A deploy keeps the development bench and its Code Server (0.7.78; 0.7.76 and 0.7.77 went to the Watch Tower PRs)

### Fixed
- After a deploy the new bench was a normal bench, so the development flag and Code Server stayed on the old bench
  and the developer lost the editor (SSH certificates fell back to 6 hours). When a new bench becomes Active and the
  bench it replaces (same release group and server) is a development bench, the new bench becomes one too, `bench
  watch` starts, and a Code Server named "code-" plus the bench name is set up if the old bench had one. The old
  bench's Code Server is archived once that bench is confirmed Archived, not before. The decision is made
  before old benches are queued for archive, so the archive job cannot race it. The Code Server is skipped
  when the team's roles have the feature off. Code in `bench_dev_carry_over.py`.

## 26-11-2026: SSH docs for 30-day certificates and their revocation (0.7.74, docs only)

### Changed
- The Team SSH wiki page says certificates last 30 days on a development bench and 6 hours elsewhere, and how the
  revoked-keys job ends access within a minute; lesson `docs/wiki/08-lessons/2026-11-26-a-long-certificate-needs-a-revocation-list.md`.

## 26-11-2026: one morning email instead of an alert flood (0.7.77)

### Changed
- Alerts that need no action within hours (scheduled and background job failures, error spikes, stuck jobs, worker
  queue backup, slow MCP calls, the GitHub token check, stale deploys, exposure without a High finding) are no longer
  emailed one by one: they are kept in Redis (`alerts/digest.py`, at most 2000) and listed once a day in the health
  report under "Alerts since the last report", one row per alert type with how many times, first and last time. The
  owner, 26 Nov: about 60 alert emails a day, all through the Brevo account Press also sends customer emails with.
- Sent at once as before: backup failure, failed deploy build, site down, SSL expiring (`important=True`), and now
  disk above 85% (owner's choice), SSH unreachable, microservice down, MariaDB, Redis and Docker alerts, the email
  queue loop, poll_pending_jobs missing, MCP Agent Watch, the site archive and delete notices, exposure with a High
  finding, and every rule email to its configured recipients (`send_alert_email(immediate=True)`).
- The health report moved from the midnight daily job to 08:00 (`run_morning_report`, cron `0 8 * * *`); the kept
  alerts are cleared only after the report was sent.
- The kept alerts survive `bench clear-cache` and migrate: `wt:digest:*` is a persistent cache key (`hooks.py`).
  Without it a clear-cache between two reports dropped them unseen.

### Fixed
- The GitHub token check ran once per candidate record (203 a night; 5 emails got through the relay on 25 Nov): it now
  runs once an hour at most (`_memoized(..., ttl=3600)`), and counts only enabled App Sources with a failed poll.

## 26-11-2026: Infrastructure page clean-up (0.7.76)

### Changed
- Prototype PRS-SP-12, owner: "much better", and the server rows that open to their containers stay exactly as they
  are (ServerChildRows.vue untouched). The title shows once (the list's own "Infrastructure (N)" heading is gone); the
  four summary tiles are gone from this page (their counts sit on the filter buttons; SummaryCards.vue stays for
  Telephony); the filters are labelled Source, Health, Runtime; the Gate-0 banner is a Setup row inside Needs
  attention; every Needs attention row has the same columns (chip, place, meaning, action) with Down, Load, Offline
  chips; Security shows its worst 3 with "Show N more".

## 26-11-2026: Security risks on the dashboard (0.7.75)

### Added
- The Infrastructure page's Needs attention box opens with a Security group (prototype PRS-SP-11, approved 26 Nov):
  one row per Exposure Watch finding with its severity in words, the place, what it means and a Fix that shows how
  to close it; never cut by the 4-row cap of the other rows. The Watch Tower overview gains a 6th tile, Security
  risks, that opens the Infrastructure page. Data: `press.api.infra_board.get_security_findings` (System Manager;
  anyone else gets None, so a Watch Tower Hub user sees no tile and no error), filled by the hourly check
  (`exposure_alerts.save_findings`, 3-hour cache). 11 tests without a bench.

## 26-11-2026: Watch Tower exposure watch (0.7.74)

### Added
- `check_public_exposure` (`watch_tower/alerts/exposure_alerts.py`), hourly, looked at from outside: service ports
  open to the internet on press-ctrl, sandbox-1 and hetzner-main (press-ctrl is probed from accubuild-stg), a real
  OpenAPI route list on Sanad Brain, the Anwar bridge and every Traefik host on press-ctrl, Sanad Brain admin routes
  that answer without a key, and Sanad Preview pages that answer without its login. One email lists each finding
  with its fix; the usual throttle (3 per 6 hours per finding set). Found on 26 Nov: code-analysis port 8200 open on
  press-ctrl, Brain /admin/audit open. Tests run without a bench (`test_exposure_alerts.py`).

## 25-11-2026: SSH certificates last 30 days on a development bench (0.7.73)

### Changed
- A user SSH certificate for a release group with an active development bench (`is_development_bench`) is now
  signed for 30 days instead of 6 hours (owner, 25 Nov: "make it long access like all our team"). Every other bench
  keeps 6 hours, and a 30-day certificate is refused on a group without a development bench. The SSH, VS Code and
  bench action texts say so. Rule in `ssh_certificate.py` (`has_development_bench`, `user_certificate_validity`).

### Security
- A signed SSH certificate cannot be called back, so a 30-day one would outlive a removed member. Every minute every
  Active bench of a group with a development bench or a live 30-day certificate (the certificate's principal is the
  group, so it opens all of them, including the new bench of a redeploy) gets a revoked-keys file (`revoked_keys.py`,
  hooks `* * * * *`): the keys that still hold a valid certificate for it whose user left the team or was disabled,
  whose key was disabled or removed, whose Press Role no longer covers the group (the dashboard's rule, checked
  against `_role_covers` for all 5 members x 41 release groups of the Quest team: no difference), or whose team's SSH
  access was turned off. A key that also holds a certificate in good standing (re-added) stays off the list. The
  bench's sshd reads the file at every login; the `RevokedKeys` line is added to that bench's sshd_config once,
  checked with `sshd -t`, then sshd reloads, and a failed reload takes the line out again so the next run retries.
  A failing bench writes one Error Log, then waits 5 minutes. Proven twice on Quest Dev with a throwaway key: SSH
  worked, the key was disabled, the next sync refused it. Benches outside those groups are unchanged.
- A saved SSH Certificate is checked for its validity only on insert or when the validity changes, so an old 30-day
  certificate can still be saved after its development bench is archived.

## 25-11-2026: AccuHub tasks as a tree on the tasks page (0.7.72)

### Added
- The AccuHub tasks page of a client shows the stage's tasks as a tree: each task under its group, indented, with
  **Created by**, **Created on** and **Assigned on** columns (owner, 25 Nov; needs accuhub_link 0.6.0 on the client
  site and the hub's 0.2.28). A group that is not in the stage shows as a grey heading and is not counted. A row from
  an older link shows flat as before, with the new columns empty.

## 25-11-2026: A new MCP token opens on the deploy tools (0.7.71)

### Changed
- The Issue Token dialog opens with the **All deploy** preset ticked (14 tools: fetch and approve releases, build,
  deploy, update sites, status) instead of 3 read-only list tools, so a developer no longer has to pick it (owner,
  25 Nov). The member's role still limits what the token reaches (0.7.70), and the high-risk tools still need their
  own tick and approval.

## 25-11-2026: DevOps L1 and L2; MCP tokens follow the member's role (0.7.70)

### Security
- An MCP token reached the whole team whatever its user's role: `issue_token` never read Press Roles, and the call
  guard checked the team only. Proven on 25 Nov: a token a Viewer with 2 Quest benches made for himself listed 83 sites
  and 40 benches. Every Site, Release Group and Server a call names or reaches now passes the dashboard's own
  `role_guard.check`, run as the token's user (`press/mcp_server/scope/roles.py`); `list_sites`,
  `list_release_groups` and `agent_job_list` are filtered; `mint_dashboard_login_url` is refused for a member limited
  to listed benches. Owners, admin roles, System Managers and the Master token are unchanged.
- A disabled user could still make an MCP token. Issuing and using a token now refuse a disabled user.
- The developer helpers behind `ensure_team_access` (console SQL and Python, logs, git, files, SSH, code server)
  checked the team only, so a member limited to some benches could reach every site of the team through their API.
  They now hold him to his role list. `ensure_team_access` moved to `press/utils/team_access.py` (re-exported from
  `press.utils`).

### Changed
- DevOps Admin is renamed **DevOps L2** (same rights). A stored "DevOps Admin" still reads as L2, and a team's Press
  Role titled "DevOps Admin" is renamed in place the first time L2 is needed, so members and resources stay. Patch
  `v0_0_5.rename_devops_admin_to_devops_l2` moves the stored values and the select options.

### Added
- **DevOps L1**: DevOps L2's tools on the benches and sites listed on its role page only (all sites, benches and
  servers off; no server creation). It gets the per-bench and per-site features (Code Server, SSH, logs, site Dev and
  AI tabs, SQL Playground, Database Access, Dev Overview, Code Health, private benches), never the server-level ones
  (Servers, Binlog Browser, DB Analyzer, Daman Backup, Security Portal). Prototype PRS-SP-10, decision PRS-DC-09.

## 24-11-2026: Watch Tower Integrations page (0.7.67 to 0.7.69)

### Fixed (0.7.68, 0.7.69)
- Integrations at 1024 px: the table ran past the card and cut «With Accurate». Under 1280 px «Last run» and «Sync
  notes» hide and a long site name is cut to 140 px (full name on hover; 0.7.69, «Closed» was still cut), so the four
  stages stay in view.

### Added
- Watch Tower › Integrations (prototype ACM-SP-08): per client site and project, the AccuHub link's state and task
  pipeline (Backlog › With OptiFlow › With Accurate › Closed, 30 days). A count opens that stage's tasks
  (`/watch-tower/integrations/<site>?stage=&project=`): the stages as tabs, a Project pick list (ticks, search,
  several), each task linking to the client site. Reads `sanad_ai_control_center.watch_tower_hub.integrations`
  (hub 0.2.27); the task list is read live from the client, nothing is kept. System users only, like Watch Tower.

## 24-11-2026: The MCP dashboard login says why a confidential site blocks it (0.7.65; docs 0.7.66)

### Docs (0.7.66)
- DEVLOG session 26; lessons-learned for the stale `creation_failed` and the 0.7.64 deploy traps; troubleshooting
  entries for the creation-failed banner and the dashboard login refusal; backups notes the hand-finished restore.

### Changed
- `mint_dashboard_login_url` is refused while any confidential site of the team is locked, because a dashboard session
  reaches every site of the team. The refusal named one site only, so asking for a login to another site read like a
  bug. It now says that a dashboard login reaches every site of the team and lists every locked confidential site. The
  rule is unchanged.

## 24-11-2026: A healthy site no longer stays marked "Site creation failed" (0.7.64)

### Fixed
- A failed New Site, New Site from Backup or Restore Site job stamps `Site.creation_failed`, which blocks Login as
  Admin, Update and Backup. Press cleared it only when a Restore Site job succeeded, so a site finished by hand kept the
  banner and the blocked buttons for good (5 Active sites on 24 Nov, the oldest since 2 Jul). A new hourly job
  (`site/stale_creation_failed.py`) clears it on an Active site that has a successful Migrate Site or Update Site
  Migrate job after the flag. Broken sites keep it, so the 14-day auto-drop of a real failure is unchanged.

## 24-11-2026: Error Log noise on press-ctrl (0.7.62; docs 0.7.63)

### Fixed
- The Error Log Spike rule (WT-RULE-1043) counted `[MCP-DESTRUCTIVE]` audit rows, which MCP writes on purpose (up to
  1,346 a day). They are in the rule's noise list now.
- `infra_board._cpu_disk` wrote an Error Log row on every 1-minute warm for a server it cannot reach (about 1,400 a day
  for accurate-portainer). It writes one an hour per server now.

### Changed (data on press-ctrl, by hand)
- 8 fake test VMs (`f5`..`f12-mumbai.fc.dev`, from test runs on 30 May and 8 Sep) no longer snapshot. Each failed
  `snapshot_aws_servers` every 5 minutes with "Server None not found" (2,304 rows a day).
- The 12 Hetzner plans skip the machine availability sync. Hetzner removed `GET /datacenters` on 1 Oct 2026, so the check
  failed for all 3 Hetzner clusters (864 rows a day). Upstream `frappe/press` `16fa391b8` fixes it with hcloud 2.26.0; not
  cherry-picked yet. The error names "Server Plan accurate-portainer-app" only because its `except` reads a loop variable
  left over from the loop before.

### Security
- Each failed availability check stored the Hetzner API token in plain text: the traceback with variables dumped the
  hcloud request headers. 7,209 rows deleted; the token still has to be rotated. 32 other rows hold Bearer tokens
  (Cloudflare DNS 17, MCP audit 12, agent 3).
- 10 test users (`@example.com`, `@example.org`, made by test runs on 19 and 30 May) were enabled System Users. Disabled.

## 23-11-2026: Watch Tower docs cover a client's checks (0.7.61, docs only)

- The Watch Tower section page describes the checks on the Overview and the client page (0.7.53), the prototype
  ACM-SP-07 and the version rows.

## 23-11-2026: deploy notes for 0.7.59 (0.7.60, docs only)

### Changed
- Wiki: the MCP Agent Watch rule's name on press-ctrl (WT-RULE-120625) and its checks; the watch reads 3 hours, not 1.
- Troubleshooting: a new hooks.py override not dispatched after a deploy (clear the cache after the restarts), and an
  alert email the relay accepted but the inbox never showed. Lessons learned: the stale `app_hooks` of 0.7.59.

---

## 23-11-2026: MCP security for team use: agent watch, owner-only call log and token recovery (0.7.59)

### Security
- `recover_token` returned any token's plaintext to any System User (12 on press-ctrl, the whole team), so a member
  could take the owner's token (risky tools enabled) and act as him over MCP. Only the token's owner may recover it now.
- `frappe.client.get_password` gave any System Manager the stored copy of any MCP token (a Password field kept for
  Recover). Press overrides it to refuse `Press MCP Token`; other DocTypes go to Frappe unchanged. System Console and
  bench console can still decrypt, so who holds System Manager is still the real wall.
- Watch Tower Alert Log granted read to role All, so the 8 website users could read every alert through the REST API.
  Read is System Manager only now.
- `Press MCP Call Log` keeps every agent's code, SQL and output on every site; System Manager (11 users) could read it.
  Read is now the new role MCP Auditor only (patch `v0_0_5.add_mcp_auditor_role` creates it; who holds it is set per
  site). Members still see their own calls in the dashboard.

### Added
- Watch Tower rule "MCP Agent Watch" (`check_mcp_agent_watch`, hourly, memoized): six patterns over the last hour of
  the call log (refusal bursts, destructive SQL, secret hunting, a secret or private key in a response, rare dangerous
  tools, runaway volume); one email to the owner and an Alert Log per event that names only the pattern, tool and row.

### Removed
- The `[MCP-DESTRUCTIVE]` Error Log line written for every successful high-risk call (6,878 rows, about 1,000 a day,
  each with the full code or SQL; it buried real errors). The call log keeps the record and the watch reads it.

---

## 23-11-2026: Pending Bench Updates rule works; Issue Token can grant site_create and site_restore (0.7.58)

### Fixed
- Watch Tower rule WT-RULE-1208 "Pending Bench Updates" failed on every one of the 4,501 benches each day: it read
  `status` from `tabDeploy Candidate`, which has none (it lives on Deploy Candidate Build). `check_bench_updates_pending`
  now reads builds that never started (Draft or Pending for over 3 days, created in the last 30 days, so the 13
  never-run builds of May and June 2026 do not alert every day), and is memoized like the other global checks: one
  query per run instead of one per bench. On the live data it matches nothing.
- The dashboard's tool list (`dashboard/src/components/mcp/_tool_catalog.js`) lacked `site_create` and `site_restore`,
  so the Issue Token screen could not grant them. Added with the server's risk: Site Create is medium (site lifecycle),
  Site Restore Backup is high (dangerous: it overwrites the database). `scripts/audit_mcp_catalog_parity.py`: 86 = 86.

---

## 23-11-2026: bench dev tests match today's code (0.7.57, tests only)

### Fixed
- Six bench dev test files failed on the deployed code because they described older code. The permission tests
  expected `frappe.only_for("System Manager")`; the functions call `ensure_team_access` (team members or System
  Manager), so the tests now check that it is called with the bench or site and that nothing runs when it refuses.
  The git status tests expected one batched command; the code runs one `docker_execute` per git command.
- The push tests checked the old one-command push through the `push_app_to_github` shim. The shim test now checks
  only the hand-off; new `test_bench_app_push.py` (10 tests) covers `bench_app_push.py`: team check, upstream apps
  refused, separate add / commit / push, the session user as author, quote escaping, "nothing to commit" still
  pushes, auth hint, feature branch with a PR link, an unsafe branch name refused.
- 114 tests pass on press-ctrl (6 files failed before). Removing one guard makes its test fail. No code changed.

---

## 23-11-2026: bench_dev_overview.py split by concern, behaviour unchanged (0.7.56)

### Changed
- `press/press/doctype/bench/bench_dev_overview.py` (1,326 lines) is a 51-line stub; its 35 definitions live in
  `press/press/doctype/bench/dev_overview/`: `panel` (Dev Overview page, dev panel, git status, restart, push),
  `ssh` (certificates, key registration, instructions, connect), `code_server`, `site_container` (SQL and Python
  console, database process list, bench logs) and `app_files` (read-only app source files). The stub re-exports
  every name, so the dashboard's `frappe.call` paths, the MCP catalog methods and every
  `from press.press.doctype.bench.bench_dev_overview import ...` keep working; all 24 whitelisted functions stay
  whitelisted through the stub path.
- The new modules do not add `from __future__ import annotations` (the original had none): Frappe 15 skips its
  argument type check for string annotations, so adding it would have switched that check off.
- Seven bench dev tests patch `frappe` (and `ensure_team_access`) in the module the code moved to; no assertion
  changed. The 111 tests give the same result, test by test, as before the split.

---

## 23-11-2026: Open in VS Code and push app to GitHub work again (0.7.55)

### Fixed
- `press/press/doctype/bench/bench_app_push.py` and `bench_vscode.py` imported `_ensure_team_access` from
  `bench_dev_overview`, which had become `press.utils.ensure_team_access` (same `bench_name=` argument), so both
  modules failed to import on press-ctrl: the dashboard's Open in VS Code (`get_vscode_remote_url`) and pushing an
  app to GitHub (`push_app_to_github`, the MCP `app_git_push`) raised ImportError. Both import it from `press.utils`.
  The two tests patched the old name; they patch `ensure_team_access` where it is used.

---

## 23-11-2026: deploy_flow.py and tools.py split by concern, behaviour unchanged (0.7.54)

### Changed
- `press/mcp_server/deploy_flow.py` (1,859 lines) is a 60-line stub; its 29 definitions live in
  `press/mcp_server/deploy_ops/` (`candidates`, `waits`, `site_tools`, `agent_tools`, `server_memory`, `app_sources`).
  The stub re-exports every name, so the catalog's `press.mcp_server.deploy_flow.<tool>` paths and every
  `from press.mcp_server.deploy_flow import ...` keep working.
- `press/mcp_server/tools.py` (977 lines) is a ~100-line stub; the catalog lives in `press/mcp_server/tool_catalog/`
  (`_schema`, `core`, `bench_code`, `sites_benches`, `deploy`, `bench_control`), merged into `TOOLS` in the old key
  order. A tool name in two parts now fails at import (a dict merge would keep only one, silently).
- `scripts/audit_mcp_catalog_parity.py` reads the parts (same answer as before: 86 tools, site_create and
  site_restore still missing from the dashboard mirror). `test_deploy_flow.py` patches `_repo_is_public` and
  `_installation_for_owner` in `deploy_ops.app_sources`, where `register_existing_app` looks them up.

### Checked
- Every moved definition and catalog entry is identical to the original (AST compare, press-ops
  `scripts/split-2026-11-23/verify_split_identical.py`); 108% of the original lines (headers, docstrings, re-exports).
- On press-ctrl's bench Python against the new files: test_deploy_flow (31), test_help (18), test_deploy_update (17),
  test_file_ops (20), test_alert_runs (7) give exactly the failures they gave before (2 old ones); new
  `test_tool_paths.py` (3) passes; `audit_mcp_schema_vs_signature` finds 0 drift.

---

## 23-11-2026: Watch Tower shows a client's checks (0.7.53)

### Added
- Overview: «Clients needing action» counts a Production client with a failing check (hub 0.2.24); its chip reads
  «1 check failing» when that is the only reason. The client's row says «AccuHub link failing» (or «2 checks failing»)
  in place of «read just now», the messages on hover.
- Client page: «Checks» on the details line, one badge per check (green working, light red failing), and one line per
  failing check: what the site says and since when. Prototype ACM-SP-07, owner approved 23 Nov. A hub before 0.2.24
  sends no checks: nothing shows, as before.

## 23-11-2026: review follow-ups for the MCP deploy tool and Watch Tower (0.7.52)

### Fixed
- `deploy_update_status` read only the newest bench of a build; a two-server group (bench-0007) has one bench per
  server, so sites waiting for the slower one were marked "Not scheduled". It now waits for every bench (`benches` in
  the answer replaces `bench` / `bench_status`), fails if any is Broken, and counts the grace from the last one ready.
- `bench_deploy_and_update` with `sites` left out took every Active site of the group, so on a shared group the guard
  refused the whole deploy. It now takes the calling team's sites (`scope/sites.py` `chosen_sites`).
  With no team to tell, it refuses ("name the sites") instead of deploying to no site at all.
- `deploy_update_status` for a build that succeeded but got no bench in 10 minutes says done, failed, with a hint
  (it waited for ever).
- `send_alert_email` returns True or False, and a 15 s hard timeout counts as not sent (it was logged and read as
  sent), so a caller that marks records alerted can do it only after a send that worked (the hub digest, 0.2.23).
- `check_failed_deploys` is memoized like the job checks; WT-RULE-1040 targeted every failed build (a text filter),
  so its query ran 255 times an hour. The rule record moves to Server after this deploy.

### Changed
- `bench_deploy_and_wait` and `site_update_and_wait` wait at most 30 s (`deploy_flow.HTTP_WAIT_CAP_SECONDS`, was
  100 s) and say they are the older, blocking path: each holds one of press-ctrl's 9 sync web workers while it waits.
- `chosen_sites` moved to `scope/sites.py`: the scope layer no longer imports the tool it guards.

### Tests
- `press/watch_tower/alerts/test_alert_runs.py` (new, mock-only): no Watch Tower SQL uses the database `NOW()`, the
  MCP-slowness cutoffs come from Frappe's clock, the error-spike and failed-deploy checks run once per evaluation, a
  refused or timed-out alert email returns False with the reason. `test_deploy_update.py` covers the above.

---

## 23-11-2026: a refused alert email says why (0.7.51)

### Fixed
- `press/watch_tower/email_branding.py` `send_alert_email` logged the relay's answer as a warning, and only errors reach
  `watch_tower.log`, so every failure read "Alert email not sent (SMTP unavailable)" (16,665 of them 20-23 Nov, the
  error-spike flood that 0.7.50 ends). The failure line now carries the reason, e.g. `SMTPDataError: (421, ...)`, and
  the two "mail account not readable" notes are errors too.

---

## 23-11-2026: the error-spike check runs once per hour, not once per error (0.7.50)

### Fixed
- `press/watch_tower/alerts/scheduler_alerts.py` `check_error_log_spike` counts errors itself and ignores the document
  it is called for, but it was neither memoized nor throttled, and its rule (WT-RULE-1043) targeted Error Log with a
  filter Frappe read as text, so every Error Log was a candidate (capped at 10,000). It held a long worker 17+ minutes
  every hour, tried one alert email per candidate, and kept a worker restart waiting during the 0.7.49 deploy. It is
  now memoized and throttled like the job checks (at most 3 emails per 6 h for the same top errors); the rule was
  pointed at Server (4 rows) on press-ctrl the same day (press-ops `scripts/mcp-deploy-update-2026-11-23/`).

---

## 23-11-2026: one MCP call deploys and updates the sites (0.7.49)

### Added
- `press/mcp_server/deploy_update.py`: `bench_deploy_and_update` queues what the dashboard's Deploy and update button
  queues (`press.api.bench.deploy_and_update`): build, new bench, then Press updates the chosen sites (default: every
  Active site of the Release Group) when the bench is ready. It returns at once with the build.
  `deploy_update_status(name=<build>)` reports build, bench and each site's Site Update in one call. In 30 days agents
  used about 16 calls a deploy (bench_deploy, wait_for_bench_flip, deploy_candidate_status, site_update), and
  site_update was refused 281 times because the new bench was not ready.
- `scope/call_guard.py` `_rule_site_list`: every site in `sites` must be the team's, allowed by the token and unlocked
  if confidential (the checks a single `site_name` gets). `auth.verify_token` keeps the token's allowed sites on
  `frappe.local.mcp_token_allowed_sites` for it.

### Changed
- `bench_deploy_and_wait` and `site_update_and_wait` wait at most 100 s, then answer `timeout` (call again). They
  promised up to 25 min, but press-ctrl's gunicorn ends a request at 120 s (`-t 120`), so 14 calls in 30 days were cut
  off instead of answered.
- `help.py` deploy recipe leads with the new tool. `devbox_proxy/press_tools_catalog.json` regenerated from `tools.py`
  (86 tools; it lacked `site_create` and `site_restore` too).

---

## 23-11-2026: Watch Tower windows use Frappe's clock (0.7.48)

### Fixed
- `press/watch_tower/` (7 files, 23 queries): windows were written `creation > NOW() - INTERVAL 1 HOUR`. On press-ctrl
  the database's `NOW()` is UTC while Frappe writes `creation`, `modified` and the backup times in Asia/Riyadh, so
  "the last hour" read the last 4 hours and "older than N days" ran 3 hours late. The queries now take Frappe's time
  from `alerts/_helpers.py` `now_sql()`. Measured: Error Log "last hour" 993 rows before, 227 after.
- `health_report.py`: the 24-hour error count compared `creation` with the text "now() - interval 24 hour"; it is a
  real time now.

---

## 23-11-2026: the site-config read takes 0.2 s, and Watch Tower watches MCP speed (0.7.47)

### Changed
- `press/mcp_server/file_ops.py` `site_config_get` ran its code in `bench console`, whose start took about 1.2 s of
  every call. The code needs no Frappe: it now reads `common_site_config.json` and the site's `site_config.json` with
  the bench's plain Python (`_run_on_site`), still hiding every secret inside the container. Measured on a live site:
  0.19 to 0.21 s. The answer is now the parsed config; before, it came back wrapped as `{"raw": ...}`.

### Added
- `press/watch_tower/alerts/mcp_alerts.py` `check_mcp_calls_slow` (rule "MCP Calls Slow", hourly): emails when an MCP
  tool with 5 or more calls in the last hour averaged over 3 times its own 7-day average and over 1 s. Reads Press MCP
  Call Log only. It cannot see a caller's own network.

---

## 23-11-2026: the site-config read works again (0.7.46)

### Fixed
- `press/mcp_server/file_ops.py` `site_config_get` (0.7.45) answered `{}` for every site: Press feeds the code to
  `bench console` (IPython), where a name defined at the top of the code is not seen inside a function or a
  comprehension, so the hiding helpers raised a NameError. The code now runs inside one function with the helpers as
  closures (`_site_code`). The test runs it with globals and locals apart, as the console does.

---

## 23-11-2026: the MCP site-config read hides every secret, on the site itself (0.7.45)

### Security
- `press/mcp_server/file_ops.py` `site_config_get`: only `db_password*` and `encryption_key*` were held back, so app
  secrets in a site's config (a seal key, a converter password) and the passwords inside the redis URLs came back in
  clear, through the tool's answer and in the Agent Job output Press keeps. Now any key whose name holds password,
  secret, token or key reads `(hidden)`, and a URL's password reads `(hidden)`. The hiding runs in the code Press sends
  to the site (`_REDACT_SNIPPET`), so the secret never leaves the site. Found by the Sanad Review security review.
- Setting a key is unchanged (only `db_password*` and `encryption_key*` are refused), so a secret can still be rotated.
- Not a boundary: `site_run_python` still runs any code on a site, so who holds an MCP token with it is what matters.

---

## 22-11-2026: Watch Tower circuit breaker no longer locks itself (0.7.43)

### Fixed
- `press/watch_tower/engine.py`: every check during the 30-minute cooldown restarted it, so rules that run more often
  (the Control Center hub runs its rules after each site read) never ran again. From 14:16 on 22-11 no Watch Tower
  alert email went out. The cooldown is now only reported; it ends 30 minutes after the trip. The trip time is read
  with `expires=True` (a miss otherwise caches None for the rest of the job).
- The breaker counted Watch Tower Alert Log rows (one per document acted on, max 20 an hour), so a busy hour tripped
  it (a phone rollout raised about 30 findings). It now counts alert emails sent (max 30 an hour; a summary email is
  one); the log-row check stays as a runaway guard at 1000 an hour.
- Check: `~/docs/scripts/watch-tower/press_breaker_check.py` (branch module in memory, its own cache keys): 7/7.

## 22-11-2026: Watch Tower users docs (0.7.42)

### Docs
- `docs/wiki/02-frontend-development/watch-tower-section.md`: the Users column and tile, prototype ACM-SP-06, versions 0.7.40 and 0.7.41.

## 22-11-2026: Watch Tower users against the licence cap (0.7.41)

### Added
- Watch Tower Overview, Clients table: a Users column, "322 / 350 Near cap" over "201 active" (Near cap from 90% of the
  User Cap, Over cap from 100%, "no cap set", "-" until the site runs watch_tower 0.7.3; a site that stopped reporting
  shows its last known users, greyed). Prototype ACM-SP-06 approved 22-11-2026. Needs hub 0.2.18.
- Client page: a sixth tile, Users (enabled / cap, active in 30 days, a flag with the level or the % of the cap).

### Changed
- Clients table: Last read moved under the Status badge ("read 3 min ago"), the Open findings bar is 64 px and the
  table's cells 14 px apart, so the six columns (Users in, Last read folded) fit at 1440 as in the prototype.

### Deploy
- Hub 0.2.18 first: before it the page has no users data and would say "needs Watch Tower 0.7.3".

## 22-11-2026: Watch Tower docs (0.7.40)

### Docs
- `docs/wiki/02-frontend-development/watch-tower-section.md`: the Watch Tower section of the dashboard (routes, hub reads, charts, paging, versions 0.7.26 to 0.7.39, deploy, live checks).
- `docs/wiki/08-lessons/2026-11-22-watch-tower-alert-emails-never-sent.md`: why no alert email was sent and how 0.7.39 fixed it.
- `docs/wiki/01-backend-development/team-roles-permissions.md`: developers hold DevOps Admin, never Platform Admin.

## 22-11-2026: Watch Tower alert emails are sent (0.7.39)

### Fixed
- `press/watch_tower/email_branding.py`: no Watch Tower alert email went out ("Alert email not sent (SMTP
  unavailable)" in `logs/watch_tower.log`, every client-site finding since the rules were made). Two causes: the
  direct SMTP login used the account's address, but the Brevo relay account logs in with its own login id (Frappe's
  own queue uses it, which is why other emails worked); and a failed read of the Email Account cached a fallback with
  an empty password for the life of the worker. Now the login id is used when the account has one, nothing empty is
  cached, and a send failure reads the account again next time. Checked on press-ctrl: two test alerts delivered
  to the owner through the fixed code.

## 22-11-2026: search in the top bar, a quiet menu scrollbar, the group menu beside the page (0.7.38)

### Changed
- Owner 22-11-2026 ("the search should open in the top bar, not in the middle of the page"): `AppSearch.vue` is a
  search box in the top bar like the desk's (translucent on the blue, "Search sites, benches, servers"); results drop
  down under it; Escape or a click elsewhere closes them; "/" goes to the box. Same search as 0.7.35.
- "Hide the menu's scrollbar in closed mode, show it on hover": the menu's scrollbar shows only while the pointer is
  on the menu.
- "A group opens over the page and hides its text": a group clicked on the rail opens the full menu beside the page,
  which moves over to make room (no cover, no backdrop); a page chosen, a click outside or Escape closes it.

## 22-11-2026: page buttons in the header show (0.7.37)

### Fixed
- `dashboard/src/components/Header.vue` draws its `#actions` slot at the right end of the page's header row. Seven
  pages put their buttons there (Daman Backup Overview, Job Queue and Alerts; Dev Overview; Infrastructure; Telephony;
  Notifications), but Header never had that slot, so Run Backup, the List / Cards switch and the others never showed.

## 21-11-2026: Room between the bell's count and the avatar (0.7.36)

### Fixed
- The live check after 0.7.35 measured the bell's "99+" count ending 5 px from the avatar: the owner asked for space
  between them. The bell gets 16 px more room on its right while it shows a count.

## 21-11-2026: Search in the top bar (0.7.35)

### Added
- Owner 21-11-2026 ("add a search icon here and space between the bell and the avatar"; chose sites, benches and
  servers): a search icon in the top bar, and "/" anywhere outside a field, open `AppSearch.vue`. Part of a name finds
  the sites, benches and servers this account may see (Press's own list API, so the team rules apply), grouped, 6 a
  group; Enter or a click opens one; arrow keys move between results.

### Changed
- More room between the top bar's icons and the avatar; the unread count sits clear of the bell.

## 21-11-2026: A group opens the full menu, no drop list (0.7.34)

### Changed
- Owner 21-11-2026 ("on click it should open the full drawer, not this drop list, and remove the > arrows when
  collapsed"): on the collapsed rail, a group (Watch Tower, Backups, Daman Backup, Dev Tools, Sanad AI, Admin Panel)
  opens the full 240 px menu as a drawer over the page, that group open with its pages under it; choosing a page, a
  click beside it or Escape closes it (a light backdrop takes that click, so it never lands on the page under the
  drawer). The flyout list is gone. The rail shows no arrows; they show in the full menu only. "..." still keeps the
  menu full (remembered).
- Owner 21-11-2026 ("two colours split here, no gradient"): the top bar, the rail and the drawer are one solid brand
  blue #1a5f7a, so there is no seam where they meet.

## 21-11-2026: Expand the dashboard menu (0.7.33)

### Added
- Owner 21-11-2026 ("where is expand sidebar"; chose the desk-style toggle, remembered): a "..." button at the top of
  the rail, like the desk's. Expanded: 240 px, icon and label side by side, groups open inline with their pages under
  them (open by themselves on one of their pages). Collapsed: the 104 px rail with flyouts. The browser remembers the
  choice (localStorage `as-menu-expanded`); switching closes any open flyout.

## 21-11-2026: The dashboard in the desk look (0.7.32)

### Changed
- Owner 21-11-2026 ("why is the auto deploy dashboard not like this style, like LMS and Projects Hub"; prototype
  ACM-SP-05 approved, the desk look with the icon rail): on a desktop the dashboard takes press-ctrl's desk theme.
  `AppTopbar.vue` (new): 80 px top bar in the Accurate blue gradient, the white logo, the page's breadcrumbs,
  notifications (with the unread count) and the account menu (Change Team, Support & Docs, Share Feedback, Logout,
  moved from the top of the sidebar). `AppSidebar.vue`: the menu as the desk's 104 px icon rail (icon over label, white
  tile for the page you are on), same items and conditions; Notifications is the top bar's bell.
  `AppSidebarItemGroup.vue`: a group opens a flyout of its pages (one at a time; closes on a click outside, Escape or
  a page change), still 2 clicks to a page. Pages sit on a white sheet with the desk's rounded corner (white, not the
  prototype's grey: on grey the Sites list's filter fields disappeared, checked live).
- Breadcrumbs move into the top bar: Press's own `Breadcrumbs` teleports its trail when it sits in a page `Header`
  (its `#actions` stay in the page row); `Header.vue` lifts a frappe-ui `Breadcrumbs` placed directly in it, and hides
  a row left with nothing to show. Four Dev Tools pages with nested breadcrumbs keep them in the page.
- The phone keeps its own menu; sign-up, site login and hidden-sidebar pages are unchanged.
- Review fixes before release: buttons left in a page row stay on its right when the trail moves up; a flyout opened
  from the keyboard takes the focus and Escape returns it to the tile; disabled menu entries leave the Tab order; an
  open flyout resets when the menu unmounts and closes on resize or menu scroll; the top bar loads with the page (no
  trail shown in the page first) and its separator shows only with a trail; the avatar shows the user's initials from
  the session's full name, with names for screen readers on the logo, bell and avatar.

## 21-11-2026: Watch Tower Apps page (0.7.31)

### Added
- Owner 21-11-2026 ("Installed apps make the page too long, better separate; at 100 apps and 100 clients the grid is
  bad"; prototype ACM-SP-04 approved): "Apps" in the Watch Tower sidebar group. `/watch-tower/apps`: one row per app
  (git, clients running it, a bar and counts of major behind / older / current, oldest version installed), the most
  clients behind first, Behind | All, an app search, 20 a page. `/watch-tower/apps/<app>`: the app's git version and
  the clients running it, behind first, then Production, 20 a page; a row opens the client. Job: Watch Tower, Apps, an
  app = 3 clicks.

### Changed
- The Overview loses the apps x clients grid; its "Apps behind git" tile opens the Apps page.
- The client page's Installed apps: behind first, 6 a page, each app opening its Apps page; the health charts are
  taller so both cards end level.

### Needs
- Control Center hub 0.2.15. **Deploy this Press first, then the hub**: hub 0.2.15 stops sending the grid's data,
  which the 0.7.30 Overview still draws.

## 21-11-2026: Watch Tower lists in pages (0.7.30)

### Changed
- Owner 21-11-2026 ("too much empty space, same height", then "pagination"): the Overview's open Critical and High
  findings and a client's open findings show 6 rows with Previous / Page n of N / Next at the card's foot, so the list
  card ends level with the chart beside it instead of running 20 or 50 rows down. Page 1 comes with the page's read;
  the next pages from the hub's `get_findings` / `get_open_findings` (`dashboard/src/pages/watch-tower/paging.js`,
  `WtPager.vue`). Switching client starts again at page 1.

### Needs
- Control Center hub 0.2.14. Deploy the hub first.

## 21-11-2026: Watch Tower tiles draw as tiles (0.7.29)

### Fixed
- `dashboard/src/pages/watch-tower/WtTile.vue`: the clickable Overview tiles drew as small grey buttons with their label
  cut off (found by the live check after the 0.7.28 deploy). `<component is="button">` resolves the string to
  frappe-ui's globally registered Button component, not the HTML element. The tile is now a div with role=button,
  focusable and opened with Enter or Space, its 8 px corners kept against style.css's 6 px rule for [role=button].
- Client page, open findings: the account no longer shows twice when the subject is the account (Token access).

## 21-11-2026: Watch Tower redesign with charts and a page per client (0.7.28)

### Changed
- Watch Tower Overview redrawn to the approved prototype ACM-SP-03 (owner 21-11-2026: "page so ugly", "the client
  workspace is much more beautiful"; charts like Deploy Times): five tiles (clients needing action, open Critical,
  open High, new in 24 h, apps behind git) with the change against 24 h or 7 days ago; new findings per day for 30
  days stacked by client (a segment opens that client); open Critical and High findings; the clients table with a
  mini bar of open findings; installed apps against git. Files in `dashboard/src/pages/watch-tower/`; the v1
  `pages/WatchTower.vue` is removed.
- Charts are drawn in SVG by `WtStackedBars.vue` and `WtHBars.vue` (ported from the prototype, hover tooltip, whole
  number ticks, colours checked with the dataviz validator), not ECharts, so the page looks like the prototype.

### Added
- `/watch-tower/clients/<site>` (route "Watch Tower Client"): one client's page. Header (environment, status, last
  read, Watch Tower and Frappe versions, read problem, open in desk, open the site); tiles (open Critical and High vs
  24 h ago, new in 7 days vs the 7 before, errors 24 h vs yesterday, email failed and stuck); new findings per day by
  severity; open findings by type; open findings (rows open the desk record); top errors in 24 h; errors and failed
  emails per day; installed apps against git. Rows on the Overview open it; the sidebar keeps Overview lit.

### Needs
- Control Center hub 0.2.13 (`get_overview` tiles and days, `client_profile.get_client`, the daily Monitored Site
  Day reading). Deploy the hub first.

## 21-11-2026: Watch Tower page loads its data (0.7.27)

### Fixed
- `dashboard/src/pages/WatchTower.vue` asks the hub with GET. frappe-ui posts by default and the hub's
  `get_overview` answers GET only, so the live page said "Not permitted" to everyone (found by the live check
  right after the 0.7.26 deploy).

## 21-11-2026: Watch Tower page in the dashboard (0.7.26)

### Added
- `dashboard/src/pages/WatchTower.vue`, route `/watch-tower/overview`, sidebar group "Watch Tower" (the module's control
  room; rules and what to watch join it later) with Overview as its first item, for system users (owner
  21-11-2026, prototype ACM-SP-02, "Production first"): status strip; client sites Production first, then the ones
  that need action (environment, status, last read, open Critical and High, errors 24 h, email failed and stuck, read
  problem); open Critical and High findings (newest Critical first, 20 shown with the total); installed app versions
  against git (our apps "older" when behind, framework apps only "major behind"). Rows open the desk records. Data from
  the Control Center hub `sanad_ai_control_center.watch_tower_hub.overview.get_overview` (0.2.12; Watch Tower Hub or
  System Manager).

## 20-11-2026: Watch Tower client sites in the morning health report (0.7.21)

### Added
- `press/watch_tower/health_report.py`: a "Watch Tower client sites" table (status and open findings per client site,
  last read) after the Watch Tower Alerts table, when the Control Center's Watch Tower Hub module (Monitored Site) is on
  the site; otherwise nothing changes. Client names and statuses come from client sites and are escaped. It keeps the
  hub inside the one morning email (Watch Tower plan B, task 6). Live on press-ctrl since 20-11-2026, checked by
  rendering without sending.

## 19-11-2026: A copied Frappe 16 site keeps its own database login (0.7.20)

### Fixed
- `press/fixtures/site_config_key_blacklist.json`: `db_user` is now a blocked config key (upstream Press 00979c2d1, cherry-picked). Frappe 16 writes `db_user` into site_config.json, and Press copied it from the backup into every restored or cloned v16 site, so the copy logged in as the SOURCE's database user and failed at "Uninstall Unavailable Apps" with 1045 Access denied (hub-sanad-v16, job qdn8hse71g). The record was added by hand on press-ctrl on 19-11-2026; this keeps the fixture in line.

## 19-11-2026: Web page previews on the policy form (0.7.19)

### Added
- `AiPolicyForm.vue`: a "Web page previews" select (Full or Sealed) under "How it runs". Sealed hides Open preview in Basher for web pages Claude makes. `policies-derive.js` gains `PREVIEW_MODES`; a new policy starts on Full and `savePayload` sends `preview_mode`. Needs control center 0.1.3 (`save_policy` takes `preview_mode`).

## 17-11-2026: Policies screens fixed after the live UI review (0.7.18)

### Changed
- `AiProviders.vue`: when the pasted key starts with `sk-ant-oat` (a Claude subscription token), the Add account form shows "Only for (person)" (a select of live seats) with the hint "A subscription is for one person only." and sends `only_for_seat`; a token without a person is not sent. Needs control center 0.1.2. Helpers `isSubscriptionToken` and `seatChoices` in `policies-derive.js`, 7 tests in `ai-providers-token.test.js`. The select starts on "Choose a person"; an account locked to a person shows a lock badge "Only for <user> (<site>)" in the gateway pool table (control center `get_accounts_overview` `only_for`).
- `AiPolicyForm.vue`: a saved policy that lists a model locked to one person shows the control center `warnings` as warning toasts (those seats would get a 403).
- `AiPolicyForm.vue`: Models card in two columns with the release select as the 4th cell; inline red message under the name, models and release fields (toast kept); one title row instead of four; note when no skills releases can be read.
- `AiSeats.vue`: default-policy block one line per site with a fixed w-64 select; table scrolls sideways, cells padded, Tier hidden below 1280; Manage seat footer has Revoke (outlined red) left and Save right; long dashes removed.
- `policies-derive.js`: `policyErrors` per field, `validatePolicy` built on it.

## 17-11-2026: client sites can fetch their Claude Code policy (0.7.17)

The control center's new `policy_for_site` and `release_for_site` are authed by the per-site service token, but Press's guest guard would refuse them (401 "Access not allowed for this URL").

### Changed
- `press/auth.py`: `/api/method/sanad_ai_control_center.api.policy_for_site` and `/api/method/sanad_ai_control_center.api.release_for_site` added to the guest allow-list beside `revoke_for_site`, each scoped to that one path.
- `scripts/audit_sanad_ai_guest_paths.py` (new, plus a wrapper test in `press/test_auth.py`): fails when a Sanad AI control center guest path is missing from `ALLOWED_PATHS`.

## 17-11-2026: Policies tab, seat policy and default policy in the Sanad AI admin (0.7.16)

Claude Code policies (permission mode, route, three models, release, allowed and blocked actions) are now created and assigned from the Sanad AI admin. Needs the control center version the phase 2 PR sets (0.1.0 in the phase 2 plan) for the `policies.*` admin API; without it the Policy select is disabled with a short note and the Seats tab works as before.

### Changed
- `dashboard/src/components/admin/AiPolicies.vue` (new) and `AiPolicyForm.vue` (new): Policies tab with a five column table and "New policy", and the policy page ("How it runs", "Models" with the release picker, "What Claude Code may do"). Logic in `policies-derive.js` with 28 unit tests; `policies-sfc.test.js` checks that the touched templates compile.
- `dashboard/src/pages/AdminPanel.vue`: tab `policies` after Providers; `activeGroupLabel` lists it so the page is labelled "Sanad AI".
- `dashboard/src/components/NavigationItems.vue`: "Policies" child in the Sanad AI sidebar group (owner approved). If Task 5b was skipped, delete this bullet.
- `dashboard/src/components/admin/AiSeats.vue`: Policy column, Policy select in Manage seat (sent only when changed), one "Default policy of the site" select per site, skeleton rows while the table loads. Provision seat unchanged.
- No Press allow-list change (staff are System Users); the guest paths for client sites come in a later PR.

## 14-11-2026: restore asks before scanning the backup (0.7.15)

Every database restore from the dashboard ran the backup scan first, even for a 400 KB backup that gains nothing from it, and on a server whose agent cannot scan the user waited for nothing. The scan is now a choice.

### Changed
- `dashboard/src/components/SiteDatabaseRestoreDialog.vue`: new checkbox "Scan backup first" above "Skip failing patches", off by default. Off: the restore starts as soon as the files are uploaded. On: the scan runs and offers log tables to skip, as before. The box locks once the upload starts. Prototype: `docs/prototypes/press-restore-scan-option/` (home repo).

## 14-11-2026: a backup scan the agent cannot take no longer freezes the Restore dialog (0.7.14)

Restoring a site from an uploaded database sat on "Scanning backup... Checking which tables can be safely skipped" for good (engoffice, 13-14 Nov, over 1.5 hours; charity15, 30 Sep). The dialog dispatches an Analyze Backup job and only leaves the spinner on Success or Failure. u5-default runs an older agent with no `analyze_backup` route, so the job stayed Undelivered with the agent error recorded, and the restore never started.

### Changed
- `press/api/site.py` `get_analyze_result`: a job that is Undelivered with a recorded delivery error, or Delivery Failure, reports Failure, so the dialog runs the normal restore it already runs on Failure. A job not yet sent (Undelivered, no error) still reports Undelivered and keeps waiting.

### Added
- `press/api/tests/test_restore_scan_result.py`: 5 cases (agent refused, gave up, not sent yet, finished, failed). Against the old code the first two return Undelivered / Delivery Failure.

## 10-11-2026: deploys read npm version ranges in package.json (0.7.13)

Adding frappe/crm `main` to a release group failed every deploy at "Run Validations / Pre-build" with `Invalid simple block '^20.19.0 || >=22.12.0'`. The pre-build check read each app's `engines.node` with `semantic_version.SimpleSpec`, which does not understand npm range syntax (`||`, `20.x`), so the build stopped on a parse error instead of comparing versions.

### Changed
- `press/press/doctype/deploy_candidate/validations.py`: the Node check parses `engines.node` with `NpmSpec` (falls back to `SimpleSpec` if npm syntax does not parse). The Python check keeps `SimpleSpec`, because `requires-python` uses commas that `NpmSpec` rejects.

### Added
- `test_validations.py`: OR ranges, x-ranges and `>=` for Node; comma ranges for Python. Against the old code the OR-range and `20.x` cases raise the same "Invalid simple block" error.

## 09-11-2026: client sites can turn off a removed AI seat's key (0.7.12)

Sanad AI 0.11.1 asks the control center to turn off a seat's gateway key when an admin removes the seat. The control center's new `revoke_for_site` is authed by the same per-site service token as `provision_for_site`, but Press's guest guard refused it (401 "Access not allowed for this URL").

### Changed
- `press/auth.py`: `/api/method/sanad_ai_control_center.api.revoke_for_site` added to the guest allow-list beside `provision_for_site`, scoped to that one path.

---

## 07-11-2026: MCP token list split into Active / Revoked / Expired (0.7.11)

Every token ever issued showed in one list at the same weight, a revoked token still had **Copy token**, and two tokens could share a name with nothing to tell them apart.

### Changed
- `MCPActiveTokensBody.vue`: a status switch (Active / Revoked / Expired, with counts); the page opens on Active. Revoked and expired rows are grey with no buttons and lead with "Revoked <date>" / "Expired <date>"; active rows lead with "Expires <date>", Revoke is red.
- The first 8 characters of each token show next to its name (searchable); unrestricted tokens show an **all sites** chip; **Purge expired** moved to the Expired tab.
- Prototype: `docs/prototypes/mcp_token_status_tabs_prototype.html` (layout score 97/100).

---

## 07-11-2026: MCP tokens follow the team you switched to (0.7.10)

A user in two teams switched to OptiFlow and opened Dev Tools > MCP: the list showed the main team's tokens, the Allowed Sites picker showed main-team sites, and a new token was bound to the main team. The MCP panel used frappe-ui's `call()`, which sends no `X-Press-Team` header, so `get_current_team()` fell back to the oldest team.

### Fixed
- `dashboard/src/components/mcp/teamCall.js`: wraps frappe-ui `call()` with `X-Press-Team` (same source as `main.js`); the 4 MCP panel files use it.
- `list_my_tokens` lists only the current team's tokens (the token's team through MCP). Test `TestMCPTokenFollowsSwitchedTeam`.

---

## 06-11-2026: Dev tab shows the real Dev Mode and every Code Server state (0.7.9)

The Dev Mode card always said Disabled (it read `developer_mode` / `set_development_mode`, which are not Site fields, and `is_development_site` was not in `dashboard_fields`), so its button could only ever enable. The Code Server card had no state for a Broken or Stopped code server and never refreshed while Starting.

### Fixed
- Dev Mode card reads `is_development_site` (now in `Site.dashboard_fields`); Disable works, and the Options menu item shows the right label.
- Code Server card moved to `SiteDevCodeServerCard.vue`: polls every 10 s while Starting (max 5 min), shows **Code Server failed / stopped** with a **Restart Code Server** button (existing `restart_code_server`, same team and feature check). View logic in `code-server-derive.js` with 11 vitest tests.

---

## 06-11-2026: team owner can switch Dev Mode and a development bench (0.7.8)

The owner of a team (Accurate Systems, u5) clicked **Enable Dev Mode** on engoffice and got "Required role flag: admin_access". The dashboard treats the team owner as admin, but `require_team_role_flag` only let System Managers or a Press Role with the flag through, and the owner's role was Developer.

### Fixed
- `require_team_role_flag(..., owner_passes=True)`: the team owner passes. Only `Site.set_development_mode` and `Bench.set_development_bench` opt in. Confidential, login-as-admin PIN and global PIN gates still need a real `admin_access` role (default `owner_passes=False`). Mock tests in `test_press_role_bridge.py`.

---

## 31-10-2026: Take Backup always offers Database only or Full backup (0.7.6)

The files checkbox in the backup dialog sat inside `v-if="allow_physical_backup_by_user"` (upstream has the same), so on sites without physical backup a manual backup could not be chosen as database-only or full.

### Fixed
- Take Backup shows **Database only** / **Full backup** on every site (Full by default); **Physical Backup** appears only when enabled for the site and forces Database only, since a physical backup cannot include files (PR #20, 0.7.6). Upstream wording: dialog Take Backup / Start Backup, Backups tab button Take Backup. Deployed to press-ctrl 2026-10-31.

Not ported: upstream's separate Backup Schedule dialog (one custom daily backup hour); our fork has none of its backend.

---

## 30-10-2026: confidential sites need the PIN everywhere, benches list with sites, infrastructure tree, log retention (0.7.2 to 0.7.5)

A site marked Confidential could be opened without the Admin PIN from the desk ("Login as Administrator") and through every MCP tool, and `Site.onload` sent the PIN itself to every desk browser that opened any Site. All four releases were deployed to press-ctrl on 2026-10-30 with a snapshot first and `git merge --ff-only` in `apps/press` only.

### Security
- Desk: `Site.login` checks the Admin PIN for confidential sites, so Login as Administrator, `login_as_admin` and the API all pass one gate; `login_as_team` and Show Admin Password refuse them; `Site.onload` no longer copies the PIN (PR #14, 0.7.2). The PIN that leaked should be rotated.
- MCP: a token reaches a confidential site only if the human entered the Admin PIN in the Issue Token dialog for a token that names the site; in-container tools are refused on a bench hosting a locked confidential site, and `mint_dashboard_login_url` while the team has one (PR #14, 0.7.2). New field `Press MCP Token.confidential_sites`.

### Added
- Benches list shows each bench's sites (status, server, region), an Apps column, a row menu and the deploy dialog for Awaiting Deploy benches: a file port of upstream Frappe Cloud (PR #15, 0.7.2).
- Infrastructure servers expand in place as a tree with visible Start / Stop / Restart / Logs instead of the HostDrawer dialog; a server's Benches tab shows the same benches tree (PR #16, 0.7.3).
- Log Settings clears Bench Shell Log after 30 days and Agent Job (with its steps) after 90 days (PR #17, 0.7.4).

### Changed
- Sidebar uses the prototype's solid colors (`#CBD5E1` text, 240px, 6px items) instead of translucent white (PR #15, 0.7.2).
- 10 data pages and tabs are full width; bench names are no longer bold (PR #16, 0.7.3).
- Bench and site names in the benches list are 14px (`text-base`) instead of the browser's 16px (PR #18, 0.7.5).

### Fixed
- `host_unit_action` clears the cached infrastructure tree, so the tree shows a unit's new state after Start / Stop (PR #16, 0.7.3).

Docs: [MCP server: confidential sites](docs/wiki/03-integrations/mcp-server.md), [deploying the press app](docs/wiki/06-deployment-ops/deployment-guide.md), [UI style guide](docs/wiki/02-frontend-development/ui-style-guide.md), [lesson: hooks change not seen](docs/wiki/08-lessons/2026-10-30-hooks-change-not-seen.md).

---

## 24-09-2026: MCP team isolation, Switch Team shows team names, stable default team

A token issued for one team could read and change another team's sites, benches, servers and apps through the MCP server (proven live: a main-team token read an OptiFlow site's status). MCP tools run as the token user and Frappe skips permission checks for System Users. Found by an audit of all 84 MCP tools (59 cross-team paths, each confirmed by two independent verifiers) and closed at the MCP layer. PRs #8 to #12, all deployed to press-ctrl (now `c7f3fa122`).

### Security
- MCP calls stay inside their token's team (PR #11): the Site/Release Group target must be in the token team, and so must every other resource an argument names (benches, servers, deploy candidates and builds, agent jobs, app sources and releases, backup Remote Files, `team`). Missing and other-team objects get the same message, so a token cannot enumerate another team. Code in the new `press/mcp_server/scope/` package; `server.py` split first (1001 to 677 lines, pure move).
- Decoy arguments refused (PR #11): the scope check used to read `site` / `target_name` / `release_group` while the tool ran on `name` / `site_name` / `dn`. Undeclared resource arguments, and non-string values for them, are now refused before the check.
- Host command injection closed in `app_create_locally`, `app_init_github`, `bench_read_app_file` and `bench_list_app_files` (PR #11): character allowlists at the MCP entry point.
- `get_current_team` gives the MCP token team priority over a caller-supplied `X-Press-Team` header (PR #11).
- `mint_dashboard_login_url` logs in the token team's test user (role `Press MCP Test User`, Website User, one team only) instead of the token's System Manager (PR #12).

### Fixed
- MCP tools used "the team this user owns, most recently modified" instead of the team on the token, so creating a second team switched them silently (PR #9).
- Dashboard default team: the owner lookups order by `creation asc`, so a user who owns two teams keeps the first as default (PR #10).
- Switch Team dialog labelled every team by its owner email, so two teams of one user looked identical; it now shows the team name with the email underneath, for System Users (PR #8).

### Changed
- `agent_job_list`, `list_pending_releases`, `list_my_tokens`, `revoke_my_token` and `audit_verify_chain` are limited to the token team; tokens without a team fail closed; new tokens take the dashboard's current team (PR #11).

Still open: a re-verification of the fix (90 agents) confirmed 44 of 59 leaks closed and raised further gaps; the follow-up is on branch `fix/mcp-isolation-hardening` (not merged). Details: `docs/wiki/08-lessons/2026-09-24-mcp-cross-team-leak.md`.

---

## 19-06-2026: MCP bench-control tools + arg-alias normalization + dev-box stdio proxy

Ten Release-Group (bench) tools so an agent can compose a bench without the Desk, a server-side fix that stops agents stalling on wrong arg names, and a stdio proxy that lets a standard MCP client (Claude Code) connect to the Frappe-RPC MCP.

### Added
- 10 bench-control MCP tools (press/mcp_server/bench_ops.py): release_group_add_app, remove_app, list_branches, versions, installable_apps, rename, redeploy, archive; bench_rebuild_assets; release_group_create. Catalog 72 to 82. Registered in the dashboard _tool_catalog.js scope picker + an "All bench control" preset.
- Dev-box stdio MCP proxy (press/mcp_server/devbox_proxy/): bridges a standard MCP stdio client to the single-call handle() RPC: tools/list from a catalog snapshot (82 tools with inputSchema), tools/call forwards to handle().
- 6 tests for the new tools resource-scope wiring + the arg-alias normalizer (module: 45 green).

### Fixed
- Agents stalling on "missing required args": server.py _normalize_arg_aliases() rewrites common arg-name guesses (site to site_name, bench to bench_name, name to dn) before validation, guarded so clone_site(site) and bench_deploy(name) stay untouched.

### Changed
- /clean-code + /code-review (PASS) on all new code.

---

## 07-06-2026 - Infrastructure Control Panel: dashboard live, 3 bug fixes, two code-reviews, Gate-0 self-diagnosis

The Press Infrastructure dashboard (Plan 2b) went live at /dashboard/infrastructure: one view over Press servers (server to bench to service, read-only) and managed Docker/plain hosts (drill to units to start/stop/restart to logs), System-Manager-gated, served from a scheduler-pre-warmed get_infra_tree cache.

### Added
- Infrastructure dashboard: Servers/Infrastructure toggle, summary cards, filters/search/sort, NeedsAttention, 3-step Add-host wizard, unit control + logs drawer, 15s poll.
- Server CPU + Disk metrics: a host_probes cpu/disk SSH probe (1-min load over cores, root df) shown alongside Mem for Press servers.
- Bespoke Notifications page replacing the bare ObjectList: derived severity, Today/Yesterday/Earlier grouping, summary chips, tab/type/severity filters, mark read / mark all.
- gate0_status() preflight + a dashboard banner that names exactly what is missing (control-plane key, CA secret) with the fix commands, so an unprovisioned control plane no longer fails silently.

### Fixed
- Servers/Infrastructure toggle moved inline into the page body (it was hidden in the Header actions slot).
- get_infra_tree pre-warmed by a scheduler cron (TTL 15 to 90s); the dashboard no longer waits ~12s on first load.
- Notifications relative-time clamps future timestamps to "just now" (server/browser clock skew).
- Managed-host failures captured + surfaced: classify_conn_error maps raw ssh/docker errors to actionable reasons, persisted on Managed Host.last_error and shown on the card.

### Changed
- Two BIG /code-review passes: DRY (dayjs.fromNow, centralized severity map), robustness (defensive _parse_cpu_disk, list reload over optimistic mutation, dropped a redundant SSH round-trip), i18n + actionable adapter throws, plus vitest + python tests (python 13 to 20).

---

## 22-05-2026 — MCP deploy-chain hardening: 4 new tools + 2 fixes + scope expansion

Six commits closing the gap that bit us during the `fingerprint_external` /
`selfstorage-stg` deploys earlier today. Agents were stuck telling the human
"go click Fetch Latest in the dashboard", polling empty filesystems, and
choking on a misleading "Could not find suitable Destination Bench" error.

### New tools (commits `7d0e16dbc8` + `8125233489`)

| Tool | Purpose | Risk |
|---|---|---|
| `app_source_fetch_latest(app+release_group OR app_source)` | Replaces the dashboard's **Fetch Latest** button — polls upstream Git and creates a Draft App Release row. | low |
| `list_pending_releases(app?, release_group?, limit?)` | Audits Draft App Releases waiting for approval. Filter by any combination. | low |
| `register_existing_app(repository_url, branch, app_name)` | Onboards an existing GitHub repo as a new App Source (different from `app_create_locally` which scaffolds a NEW empty app). | medium |
| `bench_provision_progress(bench_name)` | Single-call stage rollup: `build → new_bench → setup_bench → site_migrate → ready`. **Replaces the broken pattern of polling the filesystem** — directories are empty for 5-10 min during setup_bench by design. | low |

### Fixes shipped today

- **`a561b0be91`** — `site_update` rewrap. Press's underlying error
  "Could not find suitable Destination Bench" actually means "no newer
  candidate to migrate to" — confusing because the message suggests the
  bench is missing. Wrapper now pre-checks for a Deploy Candidate
  Difference and an Active destination bench, returning structured
  `{ok:false, reason:'no_destination_candidate', hint:...}` instead of
  throwing.

- **`cd4a874fa8`** — `app_source_fetch_latest` + `list_pending_releases`
  threw `(1054, "Unknown column 'tag' in 'SELECT'")` on every call.
  I assumed App Release had a `tag` field; it doesn't. Mock-based unit
  tests passed because they mocked `frappe.db.sql` and never hit the
  real schema. **Lesson recorded in `press/docs/wiki/lessons-learned.md`.**

### Discovery (commit `ccca9f2070`)

The MCP help endpoint now returns three discovery surfaces so new agents
find new tools on first contact:
- `recipes` array → canonical_deploy now has Step 0
  (`app_source_fetch_latest`) + new `app_lifecycle` recipe +
  `watch_bench_provision` recipe with the "don't restart the agent
  because the filesystem looks empty" caveat.
- `whats_new` array → last ~3 batches of shipped tools with date +
  summary.
- `recently_shipped_tools` + `recently_shipped_hint` on every
  single-tool detail response.

### Out-of-band: token scope expansion (DB-side)

MCP tokens carry a frozen scope (allowlist of tool names) set at issue
time. When new tools shipped, **existing tokens didn't auto-pick them
up**. Ran a one-shot script on press-ctrl that found every Active
deploy-flow token (3 total — eng.elgogary, markomaher333, ahmedmowafy74)
and appended the 4 new tool names to each token's `scope` JSON list.
Idempotent — re-running is a no-op.

**Follow-up worth doing**: the token-issuance UI should dynamically read
`PRESETS['All deploy']` from the dashboard catalog so the scope auto-
includes new tools without a DB migration. Not built yet.

### UI + wiki (commits `9cc2c4b91a` + `50c943587a`)

- Dashboard MCP Guide tab catalog (`_tool_catalog.js`) now lists all 4
  new tools with correct risk badges + copy-curl buttons.
- `PRESETS['All deploy']` extended to include `app_source_fetch_latest`
  + `list_pending_releases` so newly issued tokens auto-scope them.
- `press/docs/wiki/02-operations/mcp-server.md` updated:
  category counts (Read-only 19 → 21, Bench/RG 11 → 12), new "App
  lifecycle tools" section, return-shape documented (`list_pending_releases`
  returns `{name, app, source, hash, status, creation}` — no `tag`),
  `site_update` documented as the pre-flight rewrap.

### Deploy

```bash
# press-ctrl, in order:
git pull origin cloudflare-dns
cd dashboard && yarn build       # only needed for 9cc2c4b91a + 8125233489 (JS catalog)
bench --site demo.mvpstorm.com clear-cache
supervisorctl restart frappe-bench-web:
```

No `bench migrate` needed for any commit in this batch.

---

## 21-05-2026 — Schema fix: is_decommissioned on Database Server + Proxy Server (commit `82abdb535c`)

Closes the gap behind Sessions 1+2. Before this commit, only `tabServer` had the flag — DB/Proxy crons had to walk the link to know decom state. Now both lower doctypes have their own flag, plus an `on_update` sync hook on `tabServer` to keep them in lockstep.

### Schema (Custom Fields via `*_admin_setup.py`)
- `tabDatabase Server.is_decommissioned` (Check, default 0, after `is_self_hosted`)
- `tabProxy Server.is_decommissioned` (Check, default 0, after `is_self_hosted`)

### Sync (one-way, app Server is authoritative)
- `Server.on_update` → `sync_decommissioned_to_cluster()` runs when `has_value_changed('is_decommissioned')`.
- DB Server (1:1): mirror directly.
- Proxy Server (N:1): set 1 **only when ALL linked app Servers** are decom; clear if ANY sibling is still active. Prevents accidental decom of a shared proxy.
- Skips writes when target already matches (no event spam).

### Backfill (`patches.v0_0_5.add_is_decommissioned_to_db_and_proxy_servers`)
- Installs Custom Fields (idempotent).
- Backfills DB Server flag from linked decommissioned app Servers.
- Backfills Proxy Server flag using the same ALL-decom rule.

### Why
- Sessions 1+2 patched 15 crons with **indirect** helpers (walk-the-link). That works but is a workaround. With direct flags on DB+Proxy, future crons filter naturally: `frappe.get_all('Database Server', {'is_decommissioned': 0}, ...)`.
- Closes the architectural gap that caused the 2026-05-21 incident (1798 wasted snapshot jobs against decommissioned test servers).

### Risk profile (deploy = low)
- Custom Field install: ALTER TABLE on 2 tiny tables (~15 rows each). Instant.
- Backfill UPDATE: ≤8 rows total.
- on_update hook: 1-2 extra `set_value` calls per Server save. Servers aren't hot-saved.
- Idempotent throughout (re-running migrate is safe).

### Deploy (deferred — not urgent)

```bash
sudo -u frappe bash -lc 'cd /home/frappe/frappe-bench/apps/press && git pull origin cloudflare-dns'
sudo -u frappe bash -lc 'cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com migrate 2>&1 | tail -30'
sudo supervisorctl restart frappe-bench-web:
```

### Rollback (if needed)
```bash
sudo -u frappe bash -lc 'cd /home/frappe/frappe-bench/apps/press && git reset --hard dea8ec3dfc'
bench --site demo.mvpstorm.com execute frappe.client.delete_doc --args '["Custom Field","Database Server-is_decommissioned"]'
bench --site demo.mvpstorm.com execute frappe.client.delete_doc --args '["Custom Field","Proxy Server-is_decommissioned"]'
bench --site demo.mvpstorm.com mariadb -e "DELETE FROM \`tabPatch Log\` WHERE patch LIKE '%add_is_decommissioned_to_db_and_proxy%';"
sudo supervisorctl restart frappe-bench-web:
```

### Follow-ups (next session)
- UI: add Decommission button to DB Server + Proxy Server admin pages.
- Cron cleanup: replace indirect helpers with direct `is_decommissioned: 0` filters once schema is live.
- Tests: extend `test_decom.py` with cases for the on_update sync hook.

---

## 21-05-2026 — Decom sweep Session 2: 7 more crons + intentional skips

Continuation of Session 1 (`3b7d613651`). Audit identified **17 unpatched crons** total. Session 1 fixed the top 3; Session 2 finishes the sweep with 7 more, leaving 2 intentionally unpatched (with documented reasoning).

### Patched (all use existing helpers from `press/utils/decom.py`)

| Cron | File | Pattern |
|---|---|---|
| `sync_binlogs_info` | database_server.py:2428 | `is_database_server_in_decommissioned_cluster()` |
| `remove_uploaded_binlogs_from_disk` | database_server.py:2454 | same |
| `remove_uploaded_binlogs_from_s3` | database_server.py:2474 | same |
| `schedule_updates` | site_update.py:855 | `is_decommissioned: 0` in filter |
| `scale_workers` | server.py:3560 | `is_decommissioned: 0` in filter |
| `update_cpu_usages` | site/site_usages.py:35 | `is_decommissioned: 0` in filter |
| `sync_benches` | bench.py:1635 | `is_bench_on_decommissioned_server()` |
| `fetch_stalks` | mariadb_stalk.py:67 | `is_database_server_in_decommissioned_cluster()` |
| `add_public_servers_to_public_groups` | release_group.py:1930 | `is_decommissioned: 0` in filter |

### Two patterns used
- **Direct tabServer fetches** → add `"is_decommissioned": 0` to the existing filter dict. Cheapest fix, no helper call.
- **Indirect (Database Server / Bench) fetches** → import helper, skip in Python loop. Database Server doctype has no flag of its own; the helper walks the link.

### NOT patched (intentional)
- **`fail_old_jobs`** (agent_job.py:649) — marks 2+-day-old jobs as Failure. This is CLEANUP of existing stuck jobs. Skipping decom-server jobs here would leave them stuck in Pending forever — worse than the status quo.
- **`archive_broken_benches`** (bench.py:1533) — same logic. Even on dead servers, marking the bench as Archived prevents pile-up. The archive job timeout is the right failure mode.

Both decisions documented in `feedback_dead-server-cleanup-audit-first.md` so a future engineer doesn't "fix" them and accidentally break the cleanup path.

### Coverage after Sessions 1+2
- 5 snapshot crons (`f6087e11e0`)
- 8 schedule/sync crons (`3b7d613651` + `2ff6fd2a99`)
- 2 cleanup crons left running on decom servers (intentional)

**= 15 of 17 audited crons protected; 2 intentionally not.**

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `2ff6fd2a99` — feat(decom): Session 2 sweep — 7 more crons


## 21-05-2026 — Decom sweep Session 1: shared helpers + 3 highest-waste crons patched

Cron audit (after the snapshot fix) identified **17 unpatched crons** with the same class of bug — picking targets from lower-level doctypes (VM, Site, Bench, Agent Job) without checking the linked `tabServer.is_decommissioned`. This commit ships Session 1: the shared helpers + the top 3 by waste rate.

### Added — shared helper module
**`press/utils/decom.py`** with 4 helpers + fail-open contract:
- `is_server_decommissioned(name)` — direct tabServer check
- `is_database_server_in_decommissioned_cluster(name)` — walks Database Server → linked app Server (no flag on DB doctype)
- `is_site_on_decommissioned_server(name)` — walks Site.server + Site.bench → cluster
- `is_bench_on_decommissioned_server(name)` — walks Bench.{server,database_server} → cluster

All helpers fail OPEN: missing input → False, lookup error → False. False-negative = one wasted job; false-positive = silently broken scheduling.

### Patched — 3 highest-waste crons

**1. `poll_pending_jobs`** (`agent_job.py:filter_active_servers`)
- Runs every 5 seconds. THE worst offender (was generating Undelivered Backup Site jobs on dmg-erp that triggered yesterday's "agent stuck" misdiagnosis).
- Fix: `filter_active_servers()` now skips servers whose decom flag is set OR whose Database Server cluster is decommissioned.

**2. `Site.get_sites_for_backup`** (`site.py:3362`)
- Powers BOTH `schedule_logical_backups` AND `schedule_physical_backups` — **single fix, two crons.**
- Fix: added `is_decommissioned: 0` to the existing Server filter.

**3. `archive_obsolete_benches`** (`bench.py:1556`)
- Hourly + per-bench archive jobs to dead servers.
- Fix: `LEFT JOIN tabServer + WHERE is_decommissioned IS NULL OR = 0` (NULL handles benches without a Server link).

### Tests
`press/utils/test_decom.py` — 9 unit tests covering happy paths, fail-open contract (None / DB error → False), indirect links (Site → Bench → DB Server), bench traversal.

### Live verified
```
is_server_decommissioned('f-0001.fc.dev')                          → True   (decom)
is_server_decommissioned('press-f1.sandbox.mvpstorm.com')          → False  (real)
is_database_server_in_decommissioned_cluster('m2927.fc.dev')       → True   (DB of decom)
is_site_on_decommissioned_server('test-site-00001.fc.dev')         → True   (on decom)
is_bench_on_decommissioned_server('bench-0024-000001-f-0001')      → True   (on decom)
is_server_decommissioned(None) / ''                                → False  (fail-open)
```

### Bug caught in live verification
First deploy returned `False` for `is_site_on_decommissioned_server('test-site-00001')` because the helper queried `tabSite.database_server` — a column that doesn't exist on tabSite (only on tabBench). Fixed by walking `Site → Bench → cluster` instead of `Site → DB Server` directly. Reminder: **always live-verify schema assumptions, don't trust column-name patterns.**

### Not in this commit (Session 2)
8 more HIGH-risk + 4 MEDIUM-risk crons identified by the audit. All follow the same pattern; can be batched in a follow-up using the same helpers. Remaining list documented in `feedback_dead-server-cleanup-audit-first.md`.

### Risk note
`poll_pending_jobs` is Press's heartbeat (every 5s, drives all agent communication). The fix is purely subtractive (skip-if-decom) with a fail-open helper. Worst case: helper errors → no skips happen, behaviour identical to today. Belt-and-suspenders SQL flags on 8 dead VMs remain set so the snapshot path is doubly guarded.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `3b7d613651` — feat(decom): shared helpers + 3 cron patches + tests
  - `8b8a7f7e90` — fix(decom): tabSite has no database_server column — walk via Bench


## 21-05-2026 — Snapshot guard: shared helper applied to ALL 5 snapshot crons + 4 unit tests

Follow-up to 6414bd9ad9. The one-line fix only covered `snapshot_aws_servers`. There are **4 other snapshot crons** in `virtual_machine.py` (oci, hetzner, aws_internal, rolling_db) that had the SAME bug — they pick targets by `tabVirtualMachine` without checking the linked `tabServer.is_decommissioned`. If anyone decommissioned a Hetzner or OCI test server tomorrow, the same wasted-jobs pattern would repeat there.

### Added — shared helper
**`press/press/doctype/virtual_machine/virtual_machine.py:is_vm_for_decommissioned_server(vm_name)`**

Single source of truth for "should snapshot crons skip this VM?". Handles 3 paths to the decommission flag because the flag lives ONLY on `tabServer` (Database Server and Proxy Server doctypes don't have their own):

1. **Direct**: VM is an app Server's VM → check `Server.is_decommissioned`
2. **Indirect (DB half)**: VM is a Database Server's VM → walk to linked app Server → check its flag
3. **Indirect (Proxy half)**: VM is a Proxy Server's VM → walk to ALL linked app Servers → True if ALL are decommissioned (a proxy may serve multiple clusters)

The app Server's flag is **authoritative for the whole cluster**.

### Applied to all 5 snapshot crons
Each cron now has the same one-line guard at the top of its loop:
```python
if is_vm_for_decommissioned_server(vm_name):
    continue
```
Covered: `snapshot_oci_virtual_machines`, `snapshot_hetzner_virtual_machines`, `snapshot_aws_internal_virtual_machines`, `snapshot_aws_servers` (replaces 6414bd9ad9's inline fix — converges on one approach), `rolling_snapshot_database_server_virtual_machines`.

### Tests
`TestIsVmForDecommissionedServer` with 4 unit tests:
- `test_direct_decom_app_server_returns_true` — VM backs a decommissioned app server
- `test_direct_active_app_server_returns_false` — VM backs an active server (don't skip)
- `test_indirect_via_db_server_returns_true` — VM is DB server's VM, linked app is decommissioned
- `test_orphan_vm_returns_false` — VM doesn't back anything (no decom signal, let normal logic run)

If anyone reverts the guards in 6 months, these tests fail in CI.

### Live verified
```
> is_vm_for_decommissioned_server('f1-mumbai.fc.dev')  → True   (decom app server)
> is_vm_for_decommissioned_server('m2-mumbai.fc.dev')  → True   (DB server of decom cluster)
> is_vm_for_decommissioned_server(<production VM>)     → False  (real server, snapshot normally)
```

### Belt-and-suspenders
The earlier SQL quick-fix (`skip_automated_snapshot=1` + `disable_server_snapshot=1` on 8 VMs) is intentionally kept ON. The helper is new code; if it has an edge-case bug, those VM-level flags catch it. No cost to leaving both layers in place.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `f6087e11e0` — refactor(snapshots): shared helper + apply to all 5 crons + 4 tests


## 21-05-2026 — Snapshot cron now respects is_decommissioned

Follow-up to the dead-server cleanup. The `snapshot_aws_servers` scheduled job in `press/press/doctype/virtual_machine/virtual_machine.py` was creating ~37 Snapshot Disk Press Jobs per hour against 4 decommissioned test servers (`f-000*`). Over 2 days that's **1798 wasted jobs**.

### Root cause
`snapshot_aws_servers` selects targets via:
```python
frappe.get_all("Virtual Machine", {
    "status": "Running", "series": "f",
    "skip_automated_snapshot": 0, "disable_server_snapshot": 0,
})
```
That filter operates on the **Virtual Machine** doctype. It does NOT check the linked **Server** doctype's `is_decommissioned` flag. So decommissioning a Server via the admin panel had **no effect on the snapshot cron** — the VM stayed `Running` and the cron kept picking it.

### Fixed
- Added a `server.is_decommissioned` check at the loop body, right next to the existing "skip if Press Job in flight" guard. One-line surgical fix.
- Note: Database Server doctype doesn't have its own `is_decommissioned` field. The app Server's flag is treated as authoritative for the whole cluster.

### Quick-fix applied to stop the bleeding immediately
Before the code patch landed, set `skip_automated_snapshot=1` AND `disable_server_snapshot=1` on the 8 affected VMs (4 f-mumbai + 4 m-mumbai) via SQL. The flags are belt+suspenders for the different snapshot crons.

### Live verification
Worker scheduler restarted at 11:25Z so the patched code is loaded. Next 5 min of `tabPress Job WHERE server LIKE 'f-000%' AND status IN ('Pending','Running')` should stay at zero.

### Memory rule
`feedback_dead-server-cleanup-audit-first.md` updated to document this exact failure mode.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `6414bd9ad9` — fix(snapshots): skip decommissioned servers in snapshot_aws_servers


## 21-05-2026 — Admin: hide decommissioned / IP-less servers + decommission 4 dead test servers

User asked "why all these servers appear — only 3 are working?" After full dependency audit:
- 4 `f-000*` (app), 4 `m29*` (DB), 4 `n00000*` (proxy) = 12 dead test rows from 2026-05-19
- All 4 clusters were **coupled** (app → DB + proxy via FK link columns). NOT orphans.
- 1798 `tabPress Job` rows (Snapshot Disk) + 30 Site Backups + 44 Agent Jobs reference them as history.

### Done — safe cleanup only
- **Decommissioned 4 f-000\* app servers** via UI Decommission button (Playwright). `is_decommissioned=1`. Reversible. Zero data loss.
- **NO row deletion.** All 12 dead rows + their history stay in the DB.

### Added — UI filter (5a2cd96b00)
`ServerAdmin.vue` `displayServers` computed now:
- Hides decommissioned by default (`!s.is_decommissioned`)
- Hides IP-less servers by default (`s.ip`) — catches the m29*/n00000* that don't have an `is_decommissioned` field on their parent doctype
- Toggle: `Show decommissioned (N)` checkbox in the header reveals all 15

### Result on /dashboard/admin → Servers tab
- **Default**: 3 rows visible (u4, u5, press-f1 — the 3 real production servers)
- **Toggle ticked**: 15 rows (3 real + 12 dead test rows)
- Summary cards: Total 15 / Active 11 / Decommissioned 4 / Effective Cost €36

### Near-miss + the lesson
My initial audit said "m29* and n00000* have zero deps — safe to DELETE." A paranoid re-check before the DELETE caught that they were FK-linked to the f-000* app servers via `tabBench.database_server` and `tabServer.proxy_server` columns. **Press has 3 server doctypes that cross-link; the obvious `WHERE server = X` audit misses these joins.** Memory rule `feedback_dead-server-cleanup-audit-first.md` documents the right audit template + the "decommission first, UI filter second, delete never inline" rule.

### Out of scope (deferred)
- **`server_snapshot.move_pending_snapshots_to_processing` cron** is still firing Snapshot Disk jobs against the decommissioned f-000* servers (1798 jobs in 2 days). The cron may not respect `is_decommissioned`. Separate followup: read `press/press/doctype/server_snapshot/server_snapshot.py` and confirm/patch the scheduler skips decommissioned servers.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `7ff53d9c9c` — feat(admin): hide decommissioned servers by default (with toggle)
  - `5a2cd96b00` — fix(admin): also hide IP-less servers (test/incomplete provision rows)


## 21-05-2026 — StatCard + statCardClasses.js + dashboard design-system wiki

Sibling to the tabs unification earlier today. Audit found **31 stat cards across 7 files** with drifting font-weight (bold vs semibold), label transform (UPPERCASE vs none), label size (text-xs vs text-sm vs text-[10px]). User feedback: "too many number cards have same icon in left padding/border — audit them and unify."

### Added — shared primitives
- **`dashboard/src/components/_shared/statCardClasses.js`** — `STAT_CARD_BASE`, `STAT_LABEL`, `STAT_NUMBER`, `STAT_SUBLINE`, `STAT_NUMBER_COLORS` (intent tokens: `default` / `good` / `warn` / `bad` / `info` / `muted`), `statNumberClass()` helper.
- **`dashboard/src/components/_shared/StatCard.vue`** — props `{label, number, subline, color}` with slots for `#number` (custom formatting) and `#sub` (custom subline rendering).

### Retrofitted — 5 files, 21 cards
- `AdminPanel.vue` (5 cards: Teams / Sites / Benches / Monthly Cost / Servers)
- `ServerBackups.vue` (4 cards: Total / Enabled / Scheduled / Last Failed)
- `BackupServers.vue` (4 cards: Total / Enabled / Connected / Disconnected)
- `BackupClients.vue` (4 cards: Total / Healthy / Warning / Critical)
- `BackupRunLog.vue` (4 cards: Total Runs / Success Rate / Avg Duration / Total Data) — `successRateColor` refactored to `successRateColorToken` returning intent tokens (`good`/`warn`/`bad`) instead of raw CSS classes.

All 21 cards now share **identical** styling. New stat cards on the dashboard MUST use `<StatCard>` or import from `statCardClasses.js`.

### Anti-patterns explicitly forbidden (per user feedback + audit)
- **Left-padding icon** inside a stat card (preventive — audit found NONE currently exist, user wants to keep it that way).
- **Left-border-color accent** (preventive — same reason).
- Custom font-weight, padding, label size, raw color classes — use the tokens.

### Added — developer-facing wiki page
`press/docs/wiki/02-operations/dashboard-design-system.md` documents both tabs + cards with copy-pasteable examples + the anti-patterns audit found. New design primitives (chips, badges, button groups) should follow the same pattern: extract to `_shared/`, add a memory rule, document on this wiki page.

### Memory rule
`feedback_dashboard-card-style-shared-source.md` added + indexed in MEMORY.md Critical Rules. Next agent (and me next session) will see it before adding a new stat card.

### Deferred (auditor flagged for Phase 2)
- `CodeHealth.vue` — health-score cards with color-coded ranges + sub-stats. Needs a multi-line variant before retrofit.
- `BackupClientDetail.vue` — has a storage-with-progress-bar card. Use inline `STAT_CARD_BASE` + classes; full component refactor not worth the slot complexity.

### Live verified (Playwright on /dashboard/admin)
- 5 stat cards rendered via `<StatCard>`
- "Monthly Cost" number color = `rgb(0, 123, 224)` (blue, confirms `color="info"` → `text-blue-600` token mapping works)
- 16px padding (`p-4`) consistent across all cards
- Screenshot: `.playwright-mcp/admin_stat_cards_unified.png`

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `740cb95119` — feat(dashboard): StatCard + statCardClasses.js + design-system wiki


## 21-05-2026 — tabClasses.js: single source of truth for dashboard tab styling

User feedback: "tabs style and size and height aren't same across all tabs across pages." Audit confirmed: **4 conflicting active-tab patterns** (bold-only, blue underline, gray background, pill+ring), **3 font sizes** (xs / sm / base), **3 paddings** (py-1.5 / py-2 / py-2.5).

### Added
- **`dashboard/src/components/_shared/tabClasses.js`** — exports `TAB_BUTTON_BASE`, `TAB_BUTTON_ACTIVE`, `TAB_BUTTON_INACTIVE`, `TAB_STRIP_BASE`, `TAB_STRIP_PANEL_TOP`, `TAB_STRIP_DIVIDER`, plus a `tabClass(isActive)` helper. Single source of truth.

### Retrofitted to use shared constants
- `dashboard/src/pages/AdminPanel.vue` (was: same look as MCP, but inline classes — now: imports)
- `dashboard/src/pages/backups/BackupRunLog.vue` (was: `border-b-2 border-blue-500` underline — now: bold-only)
- `dashboard/src/components/BenchCodeHealth.vue` (was: same blue-underline — now: bold-only)
- `dashboard/src/components/_shared/UnifiedTabs.vue` (was: hardcoded same classes — now: imports)
- `dashboard/src/components/mcp/MCPTopTabs.vue` (was: hardcoded — now: imports)

5 implementations, **one source of truth**. Add a new tabbed page → import `tabClasses.js`. Refuse to fork the style.

### Icon-size follow-up
First deploy showed admin tabs at 34.94px height vs MCP at 49.875px — same button styling but admin icons were `text-xs` (~12px) FontAwesome vs MCP icons at `h-4 w-4` (16px) FeatherIcon. Normalized admin icons to 1rem.

Post-fix: admin tabs render at **36px**, MCP at **49.875px**. Remaining 14px is the card chrome wrapping MCP tabs (intentional — MCP page wraps its 4 tabs in a card; admin sits on the page directly). The BUTTONS themselves are pixel-identical: 10px 16px padding, 700/500 font weight, 13px font, same colors.

### Out of scope (deferred — auditor flagged for Phase 2/3)
- Sidebar tabs (`AutoScaleTabs`, `SiteInsights`) — router-driven left-column pattern, different beast
- `TabsWithRouter` consumers (Settings, Billing, Partners) — wrap frappe-ui `FTabs`, can't easily restyle without losing router integration
- `DevFlowsGuide` pill+ring pattern — intentionally different aesthetic
- Dialog-internal tabs (`RoleConfigureDialog`, `NewAppDialog`)

### Memory rule
`feedback_dashboard-tab-style-shared-source.md` added + indexed in MEMORY.md Critical Rules. Next agent (and me next session) will see it before adding a new tab.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `b00f0c3381` — feat(dashboard): tabClasses.js + retrofit 5 files
  - `f703b926c4` — fix(admin): tab icon size to match other pages


## 21-05-2026 — Revert: remove user-facing AI banner

User correction on the AI-built banner shipped earlier today (`be325789e4`): customers / dashboard users must **not** know which pages are AI-built. The amber "Built by Claude — pending UI/UX team review" banner I added was inappropriate for an end-user surface.

### Removed
- `<AISlopBanner />` usage from `/dashboard/admin` and `/dashboard/dev-tools/mcp`.
- `AISlopBanner.vue` component file deleted from the repo.
- Imports + Vue component registrations cleaned up in both pages.

### Kept (still good — separate concern from AI marker)
- The bold-only active-tab style change in both pages (no underline, no pill).
- `UnifiedTabs.vue` shared component — has nothing to do with AI marker, useful for future tabbed pages.

### New rule (documented in memory)
`feedback_no-user-facing-ai-marker.md` added to `~/.claude/projects/-home-eslam/memory/` and indexed in MEMORY.md Critical Rules. Future agents (and me next session) will see it and avoid this pattern.

**Internal team awareness of AI involvement** should happen via:
- `CHANGELOG.md` entries (already standard)
- This repo's commit `Co-Authored-By: Claude Opus 4.7` trailers (already auto)
- Per-feature memory entries

NOT via rendered UI text.

### Live verified (Playwright)
- `/dashboard/admin`: no "Built by Claude" / "AI-generated" / "pending UI/UX" text in body. Tab style preserved (Teams tab `font-weight: 700`, `border-bottom: 0px`, color `rgb(23,23,23)`).

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `ea02556248` — revert: remove user-facing AI banner from dashboard pages


## 21-05-2026 — Unify tab style + AI-built warning banner across AI pages

User feedback drove two changes:
1. The blue underline on active tabs in `/dashboard/admin` and our new MCP tabs doesn't match a single house style — unify.
2. Pages built by Claude should LOUDLY signal they're pending UI/UX team review, so reviewers know what hasn't been signed off yet.

### Added — shared components
- **`dashboard/src/components/_shared/UnifiedTabs.vue`** — slot-based reusable tab component. Active tab = `font-bold text-gray-900`, inactive = `font-medium text-gray-500`. No underline, no pill, no shape change — just bold + darker text. Optional collapsible mode (clicking active tab again hides body). Future pages adding tabs should use this so the design doesn't drift again.
- **`dashboard/src/components/_shared/AISlopBanner.vue`** — prominent amber-bordered banner with text "Built by Claude (AI) — pending UI/UX team review & approval. Audit the diff before relying on this in production." Per-session dismissible (banner returns on next page load).

### Retrofitted — /dashboard/admin (AdminPanel.vue)
- Tab strip: dropped `border-b-2 border-blue-500` underline pattern. Active tab = `font-bold text-gray-900`, inactive = `font-medium text-gray-500 hover:text-gray-900`. Inactive icons get `opacity: 0.6`.
- Tabs now sit inside a rounded gray strip (matches the MCP page's visual rhythm).
- AISlopBanner added at top.
- Tab implementation stays inline (Font Awesome icons) — UnifiedTabs is FeatherIcon-only. Same VISUAL outcome without forcing a component swap on a page with 7 tabs.

### Retrofitted — /dashboard/dev-tools/mcp (MCPPanel.vue)
- AISlopBanner added at top.

### Live verified (Playwright)
- `/dashboard/admin`: banner present + "pending UI/UX team review" copy + active Teams tab `font-weight: 700`, color `rgb(23,23,23)`, `border-bottom: 0px`. Inactive Servers tab `font-weight: 500`, color `rgb(153,153,153)`. No `.border-blue-500` in tab strip.
- `/dashboard/dev-tools/mcp`: banner present.

### Why this isn't "swap every tab to UnifiedTabs"
Existing pages keep their tab implementation; only the VISUAL style applies inline (6 lines of classes). Replacing every tab implementation across the dashboard is a bigger refactor (~20 pages, regression risk). UnifiedTabs is the canonical component for NEW pages.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `be325789e4` — feat(dashboard): unify tab style + AI-built banner


## 21-05-2026 — MCP page restructure: 4 tabs (Active Tokens default) + style polish

Long-stacked layout replaced with tabs at the top of `/dashboard/dev-tools/mcp`. Less scroll, clearer mental model. Multiple user-feedback iterations consolidated here.

### Final layout
```
[ Active Tokens (default) | MCP Guide | Quickstart | Recent Calls ]
   ↑ bold-only active style, no underline / pill / shape change
[ active tab body ]
[ Test Tool Call section ]
```

### Tab contents
- **Active Tokens** (default) — token cards + Copy/Reissue/Revoke + summary chips + Issue + Purge expired + scope-details expand. Extracted to `MCPActiveTokensBody.vue` (~250 lines). Search by label or tool. Auto-refreshes after Issue Token dialog completes.
- **MCP Guide** — catalog of all 66 tools. Search + risk filter. Per-tool: args table, Copy curl button, expandable example call. Catalog-driven (`tools.py` + `args_schema`) — never drifts.
- **Quickstart** (renamed from "How to use MCP") — token-issuance walkthrough + canonical recipes (Playwright passwordless login, deploy chain, agent diagnostics).
- **Recent Calls** — paginated audit log with 10s background poll, page size selector, status pills.

### MCPPanel.vue cleanup
Removed ~200 lines of token-card template + scopeBuckets, toolsInCategory, toggleScopeDetail, filteredTokens, summary, onPurgeExpired, performRevoke, onShowHandover, onReissue, onRevoke, tokenRiskCount, statusClass, formatDate (all moved into MCPActiveTokensBody.vue). Kept `loadTokens` because the Test Tool Call dropdown still needs the list.

### Wire mechanism (Issue → tab refresh)
- MCPPanel: `ref="topTabs"` on MCPTopTabs + `@issue="showIssueDialog=true"`
- MCPTopTabs: `defineExpose({ refreshTokens })` — switches to Active Tokens tab + reloads body
- IssueTokenDialog `@issued` → `onTokenIssued()` refreshes BOTH the local list (Test Tool Call) AND the body (cards)

### Style fixes from user feedback
- **Tool name pill invisible** (text-emerald-300 on bg-gray-900 rendered as black-on-black in production CSS): switched to inline `style="background-color: #1f2937; color: #6ee7b7"` — survives any Tailwind purge.
- **Active-tab underline removed**: original `border-b-2 border-blue-600` matched Frappe Press patterns (e.g. HandoverPanel) but didn't match user's preferred design language. Replaced with bold-only: active = `font-bold text-gray-900`, inactive = `font-medium text-gray-500`.

### Live verified (Playwright)
- All 4 tab buttons render with correct labels
- Active Tokens default-open with summary chips + Master token row + Issue + Purge expired
- MCP Guide tool name pill computed colors: `rgb(31,41,55)` bg + `rgb(110,231,183)` text (visible contrast)

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `6d8c9537b1` — feat(mcp): top tabs — How to use | MCP Guide | Recent Calls
  - `571b418c5c` — feat(mcp): 4-tab layout + Active Tokens default + invisible-pill fix
  - `f9b43c4863` — fix(mcp): drop active-tab underline (bold-only)


## 21-05-2026 — MCP Guide: dashboard tool catalog (catalog-driven, never drifts)

Closes the "humans can't browse what MCP tools exist and what they do" gap. New collapsible **MCP Guide** box on `/dashboard/dev-tools/mcp` renders every tool from `tools.py` as a card with: name, risk badge, 1-line description, args table (name | type | required | description), and a copy-pasteable curl example. Search box + risk filter at the top.

### Added
- **`press/mcp_server/help.py:get_tool_catalog_for_guide()`** — whitelisted method returning `{categories: [...], total, recipes}`. Categories grouped + tools sorted alpha within each category. Returns FULL catalog (not scope-filtered) because humans want to see everything.
- **`dashboard/src/components/mcp/MCPGuideBox.vue`** — collapsible box pattern (mirrors MCPHowToBox). Lazy-loads catalog on first expand. Live search filters by name + description. Risk filter (`all` / `low` / `medium` / `high`). Per-tool Copy curl button.
- Wired into MCPPanel.vue as a sibling of MCPHowToBox (2 lines: import + render).

### Source of truth
`tools.py` + `args_schema`. Add a new tool → its card appears in the Guide on next deploy. Zero hand-written prose to maintain.

### Live verified (Playwright)
- Page rendered at `/dashboard/dev-tools/mcp` with the MCP Guide button visible
- Expanded → 66 tools across 5 categories (27 Read-only, 11 Bench/RG, 13 Site lifecycle, 5 File/Config, 10 Dangerous)
- Sample tools `agent_health`, `mint_dashboard_login_url`, `site_run_python` all rendered with full args tables
- Search filter working: typing "agent" → 7/66 shown
- 66 "Show example call" expandables + 66 "Copy curl" buttons

### Pivot note
Original plan was full tabs refactor of MCPPanel.vue (~700 lines). Pivoted to sibling collapsible box (~3 lines change in MCPPanel.vue) — smaller blast radius, ships the value today. True tabs refactor can land later if needed.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `87a4c29815` — feat(mcp): MCP Guide box on dashboard


## 21-05-2026 — Canonical Recipes: twin-surface (MCP help + dashboard UI)

Both AI agents (via `mcp 'help'`) and humans (via `/dashboard/dev-tools/mcp`) now see the same 3 canonical recipes today's incidents revealed:

1. **`playwright_admin_login`** — passwordless Playwright auth via `mint_dashboard_login_url`
2. **`canonical_deploy`** — 8-step build → flip → verify chain that avoids "agent polls forever" traps
3. **`agent_diagnostics`** — don't restart busy agents; check `agent_health` first

### Added
- **`SERVER_RECIPES`** list in `help.py`. Each recipe is `{id, title, purpose, steps[], caveats}`.
- **`help` index response** now includes `.recipes` array. `DISCOVERABILITY_HINT` updated to point at it.
- **`get_server_recipes()`** whitelisted method so the Vue UI can fetch the same list without going through MCP token dispatch (auth allowlist already covers `press.mcp_server.*`).
- **`MCPHowToBox.vue` Recipes panel** under the "How to use MCP" expandable. Each recipe has a Copy button that formats it as markdown + code block. Loads via `createResource` on mount; graceful loading/error states.

### Single source of truth
Add a new recipe by appending to `SERVER_RECIPES` in `help.py`. Both the MCP `help` command and the dashboard UI pick it up on next deploy — no drift possible.

### Live verification (just shipped + Playwright-verified)
- `mcp("help")` returned all 3 recipes.
- Browser at `/dashboard/dev-tools/mcp` rendered "Canonical Recipes" header, all 3 recipe titles, Copy buttons, and code blocks containing `mint_dashboard_login_url`, `agent_health`, `bench_deploy_and_wait`.
- Initial recipe had wrong URL path (`/devtools/mcp` instead of `/dev-tools/mcp`); fixed in follow-up commit `a5e4ef183f`.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `2711c0a9ed` — feat(mcp): canonical recipes in help command + UI panel
  - `a5e4ef183f` — fix(mcp): correct recipe URL path /devtools → /dev-tools


## 21-05-2026 — mint_dashboard_login_url: passwordless admin login for Playwright/E2E

Closes the "change password every Playwright test" anti-pattern. The MCP token IS the auth; this new tool bridges it into a real Press dashboard session cookie via Frappe's LoginManager + Frappe's `?sid=` query handler.

### Added
- **`press/mcp_server/deploy_flow.py:mint_dashboard_login_url(redirect_to='/dashboard')`** — mints a real Frappe Session for the MCP token's user (Administrator for the Master token, or any team user). Returns `{url, sid, user, expires_in_seconds}`. The `url` embeds `?sid=<sid>` which Frappe's CookieManager picks up on first request — Playwright just calls `browser_navigate(url)` and lands authenticated. No password ever transmitted.
- Tool registered in `tools.py` (`risk='medium'`) + mirrored in `_tool_catalog.js`. Catalog parity: **66/66**.

### Flow
```python
# 1. Mint a URL via MCP
mcp("mint_dashboard_login_url", {"redirect_to": "/dashboard/devtools/mcp"})
# → { "url": "https://autodeploypanel.mvpstorm.com/dashboard/devtools/mcp?sid=<60-char-sid>",
#     "user": "eng.elgogary@gmail.com", "expires_in_seconds": 21600 }

# 2. Playwright opens it
mcp__playwright__browser_navigate(url=<the url above>)
# → authenticated, on /dashboard/devtools/mcp, no login form
```

### Live verification (just shipped)
- Master token (`MCPT-2465`) added scope; mint call returned `?sid=da66686033...785c467a2df02bce` for `eng.elgogary@gmail.com`.
- Playwright navigated → page title "Accurate Systems Cloud", `has_login_form: false`, user text "elgogary" rendered in dashboard chrome.
- `sid` cookie is HttpOnly (not visible to JS — correct security); auth confirmed by Vue API calls succeeding + user name rendering.

### Notes
- TTL: inherits from `System Settings.session_expiry` (Frappe default 6h; deploy showed 612000s = 170h on this Press because session_expiry is overridden).
- User: bound to the MCP token's owner. No `mint_as` override yet — add when multi-user impersonation is needed.
- Audit: login is recorded in Frappe's Activity Log + the MCP Call Log via the dispatcher's `_log_call`.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `db892d8ce6` — feat(mcp): mint_dashboard_login_url


## 20-05-2026 — Gate A: dispatcher-level busy-worker restart guard

Closes the "restart a busy migrate worker → corrupt the live DB" failure mode that nearly hit selfstorage-stg on 2026-05-20 (the agent recommended `supervisorctl restart agent:` while the worker was 8min into a migrate).

### Added
- **`press/mcp_server/server.py:_check_busy_worker_guard`** — server-side refusal of `bench_restart` and `bench_update` when the target bench's agent verdict (via `agent_health(server, lookback_minutes=5)`) is `'slow'`. Error message names the running jobs + their ages so the caller knows what they were about to kill.
- **`_GATE_A_GUARDED_TOOLS`** registry — explicit list of tools the guard fires on. Today: `{bench_restart, bench_update}`. Add tools here as the catalog grows.
- **`args.force=true` bypass** — for genuine emergencies the agent can override the guard. The bypass is audit-logged via the existing `_track_rejection` path (`rejection_kind='busy_worker_guard'`).
- **Fail-open**: any exception in the guard itself (bench not found, agent_health import broken, db down) logs to `frappe.log_error` and **allows the call through**. Guards must never block legitimate ops because of their own bugs.

### Tests (4)
- `test_refuses_bench_restart_when_agent_is_slow` — happy refusal path
- `test_allows_bench_restart_when_agent_is_healthy` — pass-through
- `test_allows_when_bench_not_found` — fail-open for unknown bench
- `test_allows_when_agent_health_raises` — fail-open + log_error verified

### Notes
- Verified live on autodeploypanel: with `press-f1` verdict='healthy' (last Success 46s ago), a real `bench_restart` call passed the guard and created agent job `f2lgpjcume`.
- Independent of `wait_for_bench_flip` gates B/C/D/E (those are read-side; Gate A is write-side).
- Repair: discovered `agent_health` had not landed cleanly on press-ctrl from the earlier `f9d4efd0b` patch (the function was missing from the live file even though it was on origin). Re-synced `deploy_flow.py` directly via scp; all 4 functions (`agent_health`, `agent_job_traceback`, `agent_job_progress`, `site_update_and_wait`) now confirmed live at lines 525/751/843/787.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `8a65106003` — feat(mcp): Gate A busy-worker guard


## 20-05-2026 — Platform fix: refresh destination bench nginx after site_update flip

Closes the "stale CSS 404 after site_update" trap that bit the gulf-corner-precast demo (2026-05-13) and again the wazin-mx-demo (2026-05-20, 75 minutes burned before a memory check found the workaround).

### Root cause

The proxy server does NOT serve `/assets/` from disk — it does `proxy_pass` to the app server with a 2-min cache (`proxy_cache_valid 200 302 2m`). The actual stale state lives on the **app-server bench nginx**, whose config contains a hardcoded `alias /home/frappe/benches/<bench-name>/sites/assets/` for `/assets/<app>/*`. After `site_update` flips a site to a new bench, this alias is NOT auto-refreshed — it keeps pointing at the OLD bench's filesystem path until the next full Release Group rebuild rebakes it.

My initial diagnosis assumed a proxy-side per-RG mount. **That was wrong** (the public Frappe agent source has zero proxy-side bench paths). A research-agent grep through `frappe/agent` corrected the diagnosis before any code shipped.

### Fixed
- **`press/press/doctype/site_update/site_update.py:handle_success`** now calls `Bench(destination_bench).generate_nginx_config()` after `reset_previous_status`. This fires the existing `Update Bench Configuration` agent job which regenerates the bench-side nginx config with the correct `/assets/<app>/` alias pointing at the new bench.
- Best-effort: wrapped in try/except + `frappe.log_error` so a transient agent failure does NOT mark the site_update as Failed. Site IS on the new bench; assets self-heal within the proxy's 2-min cache TTL in the worst case.

### Tests
- `test_handle_success_refreshes_destination_bench_nginx` — confirms `Bench.generate_nginx_config()` is called with the destination bench name.
- `test_handle_success_swallows_nginx_refresh_failure` — confirms agent-down errors are logged and swallowed; site_update completion is not gated on nginx refresh succeeding.

### Notes
- **No new Agent Job type.** Reuses the existing `Update Bench Configuration` job that `bench.generate_nginx_config()` already fires.
- **No proxy-server-side code change.** The proxy was misdiagnosed; nothing on it needed to change.
- Fix is **idempotent** at the bench level — regenerating nginx config on a bench whose alias is already correct is a no-op write + nginx -s reload.
- The 2-min proxy cache TTL is the self-healing safety net if this fix ever fails silently.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `d326445bdf` — fix(site_update): refresh destination bench nginx on flip success


## 20-05-2026 — MCP: 4 new agent tools + 4 safety gates on wait_for_bench_flip

A live agent driving the dmg-erp deploy got stuck polling `wait_for_bench_flip` indefinitely because the call returned `pending` even though the most recent Update Site Migrate had FAILED and been rolled back at 06:55 → 07:06. Same agent had no way to see in-flight job output the way the dashboard's job page does. This session ships the four MCP enhancements that fix BOTH gaps + the four server-side safety gates that prevent the misdiagnosis from happening at the source.

### Added — new tools
- **`agent_health(server, lookback_minutes=10)`** — verdict `healthy | slow | stuck | no_activity` from Press-side Agent Job rows. Stops the "every job Pending so the agent is dead → restart it" misdiagnosis that almost killed a busy migrate worker this morning. Verdict `slow` explicitly says DO NOT restart.
- **`agent_job_traceback(job_name, output_chars=4000)`** — one-shot post-mortem returning `{status, job_type, site, output_tail, traceback_tail, age_seconds}`. Replaces the 4-roundtrip "ssh press-ctrl + bench console + get_doc + print" dance.
- **`agent_job_progress(job_name, step_output_chars=1500, job_output_chars=4000)`** — **Cursor-style live in-flight stream**. Returns `{status, current_step, steps[], steps_summary, output_tail, dashboard_url}`. Each step has its own status + output_tail + duration. Mirrors the dashboard's `/dashboard/sites/<site>/jobs/<job>` page so the agent can poll every few seconds and SEE the live step pointer move. Verified live against `pll399vmj4` — full per-step output + traceback returned as structured JSON.
- **`site_update_and_wait(site_name, target_candidate, ...)`** — blocking companion to `bench_deploy_and_wait`. On standalone Press, a successful Deploy Candidate Build does NOT auto-flip sites onto the new bench; each site needs an explicit site_update. This wraps `schedule_update` + poll into one blocking call so the agent doesn't have to manage the two-step dance.

### Added — 4 safety gates inside `wait_for_bench_flip`
All server-enforced, no agent opt-out, all verified live on dmg-erp:
- **Gate B (`no_build`)** — target_candidate has no Deploy Candidate Build → return early with hint pointing at `deploy_candidate_schedule_build` or `bench_deploy_and_wait`. Hint distinguishes "candidate missing" from "candidate exists but build never scheduled".
- **Gate C (`flip_not_triggered`)** — Build is Success but no Update Site Migrate job exists in the last 60 min → return status with hint to call `site_update_and_wait`. Without this gate, agents poll indefinitely for an auto-flip standalone Press never performs.
- **Gate D (auto-poll-pending-jobs)** — stale Undelivered jobs >2min old for this site → fire ONE `poll_pending_jobs` call before returning. Idempotent — Press's own scheduler does this every 60s, we just help it catch up. Recovers from scheduler hiccups (the 2026-05-20 selfstorage-stg incident) automatically.
- **Gate E (`flip_failed`)** — the most recent Update Site Migrate FAILED and (optionally) was rolled back by Recover Failed Site Migrate → return early with `failed_migrate_job` + `recover_job` + hint to call `agent_job_traceback`. Catches dmg-erp's exact symptom.

The `flipped` fast path short-circuits BEFORE the gate checks so a healthy poll stays cheap (one Site read, one Bench read).

### Tests
- `test_gate_b_no_build_for_target_candidate`
- `test_gate_b_no_candidate_at_all`
- `test_gate_c_flip_not_triggered_when_build_success_but_no_migrate`
- `test_gate_d_kicks_poll_pending_jobs_when_stale_undelivered`
- `test_gate_e_flip_failed_with_recover`
- Existing `test_wait_for_bench_flip_*` updated to mock the new exists/count/get_all paths.

### Notes
- Catalog parity verified: 65/65 tools in `tools.py` and `_tool_catalog.js`.
- Token-side: Master tokens (`MCPT-2465`, `MCPT-3028`) now carry 62 scopes including the 4 new tools.
- Live evidence the design works: same `wait_for_bench_flip(dmg-erp, deploy-0017-000014)` call that returned `pending` for ~9 minutes this morning now returns `flip_failed` with both job names + an actionable next-step hint.
- Live evidence Cursor-style streaming works: calling `agent_job_progress("pll399vmj4")` returns 13 steps including the failed `Migrate Site` (duration `0:03:48`) with its output tail + traceback tail — same data the dashboard page renders, as structured JSON.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `f9d4efd0b` — feat(mcp): agent_health + agent_job_traceback + site_update_and_wait
  - `6586cd43b3` — feat(mcp): safety gates B/C/D inside wait_for_bench_flip
  - `b8727ea098` — feat(mcp): Gate E — detect failed migrate + rollback in wait_for_bench_flip
  - `664828efda` — fix(mcp): extend migrate-job lookback to 60min + document Gate E
  - `2651672025` — fix(mcp): include 'Recover Failed Site Migrate' in Gate E job filter
  - `e8b92d3488` — feat(mcp): agent_job_progress — Cursor-style live in-flight job stream


## 20-05-2026 — MCP dispatcher: drop unknown args + fail-fast burst guard

### Fixed
- **Repeated `wait_for_bench_flip() got an unexpected keyword argument 'timeout'`.** A live agent ran a 30-iteration polling loop sending `{timeout: 25}` (which `wait_for_bench_flip` doesn't accept). Each call rejected in <1ms → no server-side delay → bursted the rate limit in seconds. Same failure mode would fire for any kwarg-typo'd loop. Two server-side guardrails now stop this at the source.

### Added
- **Dispatcher: schema-based arg filtering.** `press/mcp_server/server.py` now filters incoming `args` to ONLY the names declared in the tool's `args_schema.properties` (plus the meta-args `dry_run` + `suppress_hints`). Unknown args are dropped, logged via `frappe.log_error`, and never reach the Python method. A `wait_for_bench_flip(site_name=..., target_candidate=..., timeout=25, bogus="x")` call now succeeds — the unknown `timeout` and `bogus` are silently ignored. The classic "agent guessed an arg from the description" failure mode can no longer 500 the method.
- **Fail-fast burst guard.** Same `(token, tool, rejection_kind, signature)` rejection 3x in <10s → guard fires with `BURST-GUARD: same X rejection on Y fired 3x in <10s. Fix the call before retrying.` Counter resets on guard-fire so the agent can retry once it fixes the call. Stored in-process per gunicorn worker; rate limiter (Redis-backed) is the cross-worker enforcement, this is the local "stop hammering" gate. Tracks two kinds today: `missing_required_args` and `unknown_args`.

### Notes
- 6/6 `press.test_auth` audit tests still pass.
- Verified live: (1) `wait_for_bench_flip` with `{timeout, bogus}` extras returns `status: pending` cleanly. (2) Three identical missing-args rejections triggers `BURST-GUARD` on the 3rd; 4th call goes back to the normal error path (counter auto-reset).
- The unknown-args drop is at the **MCP layer**, not the Python method. Methods don't change. This lets all 60+ tools benefit without per-method `**kwargs` plumbing.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — feat(mcp): drop unknown args + burst guard


## 20-05-2026 — MCP: 3 more methods + 1 SQL fix surfaced by a live agent run

A real agent driving the erp_selfstorage Phase-0+1 deploy to `bench-0006` hit three workflow gaps. Each is now a tool:

### Fixed
- **`deploy_candidate_status(name=<DC>)` → `Unknown column 'status' in 'SELECT'`.** The Deploy Candidate doctype has no `status` column (only Deploy Candidate Build does). Our SELECT included `status` for both branches. Fix: drop `status` from the Deploy Candidate SELECT and derive it from the **most recent Deploy Candidate Build** for that candidate (falls back to `'Draft'` if no build has been scheduled). Response also gains `latest_build`, `build_start`, `build_end` for the Deploy Candidate kind so the agent can poll progress without a second call.

### Added
- **`list_sites_on_release_group(release_group, status?)`** — `press.api.site.all()` only accepts status/tag/team filters, so an agent asking "which sites would be touched by a bench rebuild of RG X" had to fall back to client-side filtering of ALL sites. New tool does the join server-side: `frappe.get_all("Site", filters={"group": rg, ...})` with team-scoping. Returns `[{name, status, bench, team, host_name, group}, ...]`. Risk: low.
- **`bench_set_app_branch(release_group, app, branch)`** — flips the App Source's git branch so the next Deploy Candidate Build pulls from a different branch. Use BEFORE `release_group_create_deploy_candidate` when you want to deploy a feature branch instead of whatever Press is currently pointed at. Without this, an agent has to either (a) merge the feature branch into Press's configured branch (lossy — destroys audit trail of the feature branch), or (b) ask a human to change the branch in the Desk UI. Risk: medium. The branch must exist on the configured repository — no pre-validation against GitHub (no token plumbing in MCP context).

### Notes
- 6/6 `press.test_auth` audits pass. Catalog parity audit shows 61 tools each side (was 59). Schema-vs-signature audit validates the 3 new tools.
- The agent's deploy is in flight as of this commit: `bench-0006` Deploy Candidate Build for the Phase-0+1 erp_selfstorage release (`hc56udu00t`) is `Running`. Only `selfstorage-stg.sandbox.mvpstorm.com` has erp_selfstorage installed of the 13 sites on bench-0006; the other 12 won't run the migration patches.
- `bench_set_app_branch` affects every Release Group that shares the same App Source. For per-RG branch isolation, the agent should create a new App Source in the Desk first. Documented in the tool's description.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — feat(mcp): deploy_candidate_status SQL fix + list_sites_on_release_group + bench_set_app_branch


## 19-05-2026 — MCP: `bench_deploy_and_wait` blocking tool + fix `suppress_hints` arg leak

### Fixed
- **`wait_for_bench_flip() got an unexpected keyword argument 'suppress_hints'`.** Hit by a live agent at 17:44 sending `{site_name, target_candidate, suppress_hints: true}`. `suppress_hints` is a META-arg documented in the `_hint` block of every successful response ("Pass args.suppress_hints=true to silence this") — meant for the MCP layer to filter, not the underlying tool method. But the dispatcher only stripped `dry_run`, not `suppress_hints`. Method got the extra kwarg, blew up with `TypeError`. Fix: dispatcher now strips both as `_META_ARGS`.

### Added
- **`bench_deploy_and_wait` MCP tool.** Single-shot deploy + block until the site's bench flips to the new Deploy Candidate (or `max_wait_seconds` expires, default 25 min). Use INSTEAD of the previous `bench_deploy + manual loop on wait_for_bench_flip` two-step. The agent doesn't need its own timer / re-poll. Long-running HTTP request stays safely under Press's 1800s gunicorn timeout (we cap at 1500s default, 1700s max).
  - Args: `name` (RG docname), `apps` (list of `{app, release, hash}` dicts), `site_name` (one site on the RG to watch — multiple sites can be on the same RG, but this only waits for the named one).
  - Returns: `{candidate, status: 'flipped'|'timeout', elapsed_seconds, current_bench, current_candidate, target_candidate, site}`.
  - Accepts `apps` as either list-of-dicts OR JSON-string (MCP HTTP layers sometimes stringify lists).
  - Polls every 30s by default (`poll_interval_seconds` 5-300).
  - Commits between polls so reads pick up the agent's writes when the bench flips.

### Notes
- 6/6 `press.test_auth` tests pass. Catalog-parity audit confirms the JS mirror has the new tool. Schema-vs-signature audit confirms args_schema matches `inspect.signature(bench_deploy_and_wait)`.
- The `wait_for_bench_flip` description was updated to point at `bench_deploy_and_wait` for the blocking variant — guides LLM clients away from the 3-step trap.
- This is the **second meta-arg** we've shipped (`dry_run`, `suppress_hints`). If we add a third, refactor to a single `_META_ARGS` constant at module top instead of two stripping passes.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — feat(mcp): bench_deploy_and_wait + suppress_hints meta-arg fix


## 19-05-2026 — MCP audit 6: args_schema must match the Python method's actual signature

### Fixed
A real-world MCP agent (running `bench_deploy` against the `wazin-build` flow) hit a 3-error chain in a row:

1. `bench_deploy(name="bench-0005", apps=["accubuild_core", "wazin_re"])` → `'str' object has no attribute 'get'`. **Schema said `apps: array of string`, method iterates expecting dicts** with `{app, release, hash}`.
2. `wait_for_bench_flip(candidate="2m82cdqceb", timeout=1800)` → `missing required args: ['site_name', 'target_candidate']`. Caller guessed names from the description.
3. `wait_for_bench_flip(site_name=..., target_candidate=..., timeout=1800)` → `unexpected keyword argument 'timeout'`. There IS no timeout — the method is single-shot poll, caller decides cadence.

The bare schema audit (`audit_mcp_catalog_parity.py`) didn't catch the drift because it only checks tool-name parity between Python and JS. The new audit catches each tool's `args_schema` vs the actual Python `inspect.signature()`.

### Added
- **`scripts/audit_mcp_schema_vs_signature.py`** — new audit that iterates every tool in `tools.py`, imports the underlying Python method, and flags drift between the published `args_schema` and the real signature. Two failure modes caught:
  - Schema documents an arg the method doesn't accept (caller sends it, dispatcher 500s)
  - Schema marks an arg optional that the method requires (caller omits it, dispatcher 500s)
- **`press/test_auth.py:test_audit_mcp_schema_vs_signature`** — wraps the audit in a bench test. Runs in-process (not via subprocess) because the audit needs Frappe context to import Press modules. CI fails if drift recurs.

### Fixed schemas
The audit found **4 additional schema drifts** (beyond the 2 the live error chain exposed):

| Tool | Schema said | Method actually takes |
|---|---|---|
| `bench_deploy` | `apps: array<string>` | `apps: array<{app, release, hash}>` ← caused the live failure |
| `agent_job_list` | `hours`, `site_name` | `site`, `since_minutes`, `status`, `limit` |
| `bench_list_app_files` | `glob` | `pattern` |
| `bench_recent_logs` | `lines`, `log` | `limit`, `log_type` |
| `site_backup` | `offsite`, `with_files` | `with_files` only (no `offsite`) |

### Description enrichments
Tightened two descriptions where LLM clients had been guessing arg names from natural-language ("candidate", "timeout"):

- `bench_deploy.description` now says "apps (list of DICTS, NOT strings — each item {app, release, hash})" with the exact source pointer for hash+release.
- `wait_for_bench_flip.description` now says "Single-shot poll (NOT a blocking wait)... NO timeout arg — caller decides cadence" with the exact arg names spelled out.

### Notes
- 6/6 `press.test_auth.TestDashboardContracts` tests pass after the fixes (5 → 6).
- The wider lesson: when an LLM client builds calls from `description` + `args_schema`, BOTH must be precise. A correct schema with a vague description still produces wrong calls. The schema-vs-signature audit catches the "schema lies" half; the next audit candidate is "description matches the schema's required args" — defer until we hit it.
- `audit_mcp_schema_vs_signature.py` can't run standalone like the other 5 (needs Frappe context to import modules). Run via `bench --site demo.mvpstorm.com run-tests --module press.test_auth` instead.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — feat(audit): args_schema vs Python signature; fixes for 5 drift cases


## 19-05-2026 — Day index (6 commits, see entries below)

A long day. Listed top-to-bottom in commit order so each entry is followed
by its successor:

1. `962d1e4acb` — `fix(clone-site)`: commit fresh-backup row before throw
2. `89943bedc6` — `fix(press-settings)`: preserve Password fields on save
3. `154b30d537` — `feat(mcp)`: publish JSON Schema per tool + Test Tool Call form
4. `755f9c8111` — `fix(auth+bench)`: 4-bug perm fix for new team members + first audit script
5. `621aad98e4` — `feat(audit)`: 4 more audits + agent fork rolled to u4 + u5
6. `47d27d3095` — `fix(api)`: 5 missing Vue→Python methods the audits surfaced

Net effect: Ahmed (new on Marko's team) went from "every button I click logs
me out" to a working dashboard. The trap that caused him pain (and the
3 incidents in 8 days before him) is now CI-enforced via 5 audit scripts.
All 5 audits exit 0 with zero exclusions; combined runtime <2s.

New wiki page: `press/docs/wiki/02-operations/contract-audit-suite.md`.


## 19-05-2026 — Fix the 5 broken Vue→Python links the audit just surfaced

### Fixed
The `audit_dashboard_method_exists.py` script (shipped earlier today) flagged 5 Vue→Python links pointing at methods that don't exist. Each would 500 with "has no attribute" when a user clicked the corresponding feature. All 5 are now fixed and the audit's `KNOWN_DYNAMIC` set is empty:

- **`press.api.product_trial.signup`** (Signup.vue) — added a shim in `press/api/product_trial.py` that delegates to `press.api.account.signup` for canonical Account Request creation, then patches `first_name`/`last_name`/`country` onto the row so `setup_account()` has them later. Vue's existing param shape preserved.
- **`press.api.regional_payments.mpesa.utils.create_payment_partner_payout`** (PartnerPaymentPayout.vue) — added a shim in `mpesa/utils.py` that translates Vue's param names (`payment_partner` → `partner`, `payments` → `transactions`), looks up `partner_commission` from the Team doctype, then delegates to `submit_payment_payout`. Vue stays unchanged.
- **`press.api.saas.subscription`** (Subscription.vue) — added real method: validates team access, returns `{current_plan: <Site Plan name>, plans: [<enabled site plans>]}` matching the shape Vue expects.
- **`press.api.saas.set_subscription_plan`** (Subscription.vue) — added real method: validates team access + plan existence, delegates to `Site.change_plan(plan, ignore_card_setup=True)`.
- **`press.press.ai.api.update_team_ai_rules`** (AiTeamRules.vue) — added real method in `press/press/ai/api.py`: validates that caller is System User OR on the target team, accepts settings as either dict or JSON string (Vue stringifies before send), persists via `frappe.defaults.set_user_default("ai_team_rules", json.dumps(settings), user=team)` so no schema change is needed.

### Audit suite now fully green with no exclusions
- `audit_dashboard_allowlist.py`: 311 callers → all covered
- `audit_dashboard_method_exists.py`: 290 callers → **all resolve to real methods** (was 5 in KNOWN_DYNAMIC)
- `audit_dashboard_whitelisted.py`: 290 callers → all whitelisted
- `audit_audit_log_inserts.py`: Bench Shell Log uses ignore_permissions=True
- `audit_mcp_catalog_parity.py`: 58 tools each side, in sync

`KNOWN_DYNAMIC` in `audit_dashboard_method_exists.py` is now `set()` — empty. Any future entry needs a comment justifying why the path can't be statically resolved (e.g. dotted path built from a runtime variable).

### Notes
- 5/5 `press.test_auth` bench tests pass after the fixes. All audits pass with zero exclusions.
- These are SHIMS where the real path was wrong (#1, #2) or stubs scaffolded against existing infra (#3, #4, #5). None of them touch billing flows that move money on production systems — `set_subscription_plan` delegates to the existing `Site.change_plan` which already handles billing math.
- The AI team rules storage (`frappe.defaults` keyed by team name) is intentionally simple — when AI governance graduates to per-team Frappe DocTypes, swap the storage; the API contract stays.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — fix(api): the 5 missing methods + empty KNOWN_DYNAMIC


## 19-05-2026 — Long-term forcing-function suite: 4 more audits + agent fork rolled to all 3 servers

### Added — audit suite that fails CI on regressions

`scripts/audit_dashboard_*` and `scripts/audit_mcp_*` — 5 scripts that catch
the recurring contract-drift bugs we've hit since 2026-05-10. Each is
runnable standalone and wrapped by `press/test_auth.py:TestDashboardContracts`
so `bench run-tests --module press.test_auth` fails CI on any regression:

| # | Script | Catches |
|---|---|---|
| 1 | `audit_dashboard_allowlist.py` | (already shipped earlier today) Vue caller missing from `ALLOWED_WILDCARD_PATHS` in `press/auth.py` |
| 2 | `audit_dashboard_method_exists.py` | Vue caller points at a Python module/symbol that doesn't exist (Ahmed's VSCode bug) |
| 3 | `audit_dashboard_whitelisted.py` | Vue caller points at a method missing `@frappe.whitelist()` |
| 4 | `audit_audit_log_inserts.py` | Regression-locked: `Bench Shell Log` insert must keep `ignore_permissions=True` |
| 5 | `audit_mcp_catalog_parity.py` | `press/mcp_server/tools.py` ↔ `dashboard/src/components/mcp/_tool_catalog.js` drift |

Audit 2 found **5 pre-existing bugs** during its first run — methods that
Vue calls but don't exist on the backend. They'd 500 with `has no attribute`
when someone clicked the corresponding feature:

- `press.api.product_trial.signup` (Signup.vue)
- `press.api.regional_payments.mpesa.utils.create_payment_partner_payout` (PartnerPaymentPayout.vue)
- `press.api.saas.set_subscription_plan` (Subscription.vue)
- `press.api.saas.subscription` (Subscription.vue)
- `press.press.ai.api.update_team_ai_rules` (AiTeamRules.vue)

These are added to `KNOWN_DYNAMIC` in the audit script with a clear "fix me"
comment so the audit doesn't fail CI for them. They are separate follow-up
tickets — not in scope for this audit-tooling PR (Gate 1c, surgical
changes). The audit catches everything NEW, which is the point.

### Applied — agent fork rolled to all 3 servers (was: press-f1 only)

- **u4 (157.90.244.216)** — cherry-picked `809e9c2` (consume `auth.ENDPOINT_URL`)
  onto upstream `master`, restarted `agent:web` + `agent:worker-0` +
  `agent:worker-1`. Local server.py docker_login null-check patch preserved.
- **u5 (46.224.170.58)** — same: cherry-picked `809e9c2`, restarted workers.

Both servers were tracking upstream `frappe/agent`, not our fork.
Cherry-pick was needed (NOT a re-point of the remote) because both were on
NEWER upstream commits than our fork's base. Going forward, when our fork
falls behind upstream and needs a rebase, the cherry-pick approach keeps
u4/u5 in sync independently.

### Notes
- Pre-existing 4 `test_server.py` SSH-cert failures (flagged in earlier
  changelog entries) remain unrelated to this PR. Tracked separately.
- The 5 audit scripts run in <2s combined; they're safe to wire into
  `scripts/pre_push_check.py` (deferred to a follow-up so this PR stays
  focused on the contract-audit + multi-server rollout).
- All 5 `test_auth` tests pass. 5 audit scripts all exit 0 on the current
  tree. The 5 KNOWN_DYNAMIC entries are 5 separate "method missing" bugs
  for future tickets.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — long-term: 4 more audits + agent fork rolled to all 3 servers
- Agent (running locally on app servers; no fork-side commit since the
  cherry-pick happens on each server's local clone):
  - u4: `2cc5f06` (= our fork's `809e9c2` re-applied)
  - u5: `3b39a41` (= our fork's `809e9c2` re-applied)


## 19-05-2026 — New-team-member permissions: 4-way fix + auto-audit to stop the recurrence

### Fixed
- **`Access not allowed for this URL` on Clone Bench / Release Group.** Clicking *Clone + Deploy* or *Clone RG only* from `CloneBenchPrompt.vue` 401'd for non-System team users because `release_group_clone.*` was never added to `ALLOWED_WILDCARD_PATHS` in `press/auth.py`. The dialog was wired up in commit `63c5a0d5fc` as the "Create a new bench" pivot inside the Clone Site flow; Marko's teammate `ahmedmowafy74@gmail.com` was the first non-System user to exercise the path.
- **`No permission for Bench Shell Log` flooding every bench Actions page.** `Bench.docker_execute()` (called by bench dev watch, bench dev overview, app management, etc.) writes an audit log via `create_bench_shell_log()` on every call. The doctype grants `create` only to System Manager; non-System team users threw `PermissionError` on each `.insert()`. The Bench Watch panel polls every 10s → users saw the error every 10s. Fix: insert with `ignore_permissions=True` — the `owner` field still captures the real session user so the audit trail stays intact, and the user can no longer be blocked from triggering a shell that they're already authorised to trigger via `_check_team_access`.
- **`Failed to get method for command ... has no attribute 'get_vscode_remote_url'`.** `VSCodeLaunchDialog.vue:311` called `press.press.doctype.bench.bench_dev_overview.get_vscode_remote_url` — but the method actually lives at `press.press.doctype.bench.bench_vscode.get_vscode_remote_url` (sibling file). Stale path from a refactor. Two-line fix: corrected the dotted path AND added `bench_vscode.*` to the auth allowlist (without both, fixing the path alone would still 401 for team users).

### Audit follow-ups (caught BY the new audit script in the same PR)
- **`press.press.ai.api.*` was missing from the allowlist** — `AiPolicyGate.vue:acknowledge_policy` and `AiTeamRules.vue:update_team_ai_rules` would have force-logged-out any non-System user who acknowledged the AI policy or edited per-team AI rules. Added preemptively before anyone hit it.

### Added
- **`scripts/audit_dashboard_allowlist.py`** — runnable audit that diffs every dotted-path caller in `dashboard/src/**/*.{vue,js,ts}` against `ALLOWED_WILDCARD_PATHS` in `press/auth.py`. Exit code 0 = all covered; 1 = missing entries listed with the files that reference them. 311 callers audited; all now covered after this PR.
- **`press/test_auth.py:TestAuthAllowlistCoverage`** — wraps the audit script in `bench run-tests` so any future PR that adds a whitelisted method without the allowlist entry fails CI. Stops the recurring trap (this is the third time we've hit it in 2 weeks: 2026-05-10 deploy_candidate_build, 2026-05-18 bench_dev_watch + bench_code_health, today's quadruple).
- **`press/press/doctype/bench_shell_log/test_bench_shell_log.py`** — regression test that calls `create_bench_shell_log` as a non-System Website User and asserts the row inserts with `owner` set to the real user. Would fail on pre-fix code (PermissionError) and passes on the new code.

### Notes
- All four fixes deployed in one commit because they affect the same user (Ahmed) trying to do his first day of work. The audit script + test are the long-term forcing function — without them we will keep hitting this trap.
- The `bench_dev_overview.*` and `bench_code_health.*` allowlist entries already existed (added in earlier sessions). Today's gaps were `release_group_clone.*`, `bench_vscode.*`, and `press.ai.api.*`.
- `Bench Shell Log` is now writeable via `ignore_permissions=True` from `create_bench_shell_log`. This is the ONLY code path that creates these rows — all callers funnel through `Bench.docker_execute(create_log=True)`. The team-access check on the parent bench remains the real authorisation gate; the audit log is now audit-complete instead of audit-blocked.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — fix(auth+bench): 4-bug perm fix for new team members + dashboard allowlist audit script


## 19-05-2026 — MCP: publish JSON Schema per tool + in-dashboard Test Tool Call form

### Fixed
- **`missing required args: ['query']` / `['site_name']` from `site_run_sql` and `site_status`.** Real call-log evidence: callers sent `{"site": "..."}` and `{"sql": "..."}` instead of the canonical `site_name` / `query`. Root cause: the MCP catalog only published `required_args` as a flat list of names — clients (Claude Code, Cursor, etc.) inferring args from the natural-language `description` field guessed the shorter natural names. No JSON Schema = no contract. Multiple users hit this (call log shows `eng.elgogary@gmail.com`, `markomaher333@gmail.com`).

### Added
- **`args_schema` (JSON Schema fragment) per tool in `press/mcp_server/tools.py`.** All 58 tools now declare `{type: "object", properties: {...}, required: [...]}` with per-arg type + description. Authored via a `_schema()` helper + shared `_ARG_FRAGMENTS` dict so common args (`site_name`, `bench_name`, etc.) have one canonical declaration reused everywhere.
- **Import-time consistency check** (`_assert_schema_covers_required_args`) fires at module load if any `required_args` entry is missing from its `args_schema.properties`. Prevents drift — every future tool added to TOOLS must keep the two in lockstep.
- **`get_tool_help()` now returns `args_schema` in the single-tool response.** MCP-compliant clients can now read the exact param names + types + descriptions without guessing.
- **Enriched dispatcher error message.** When required args are missing, the error now includes `Got: [keys you sent]. Expected: [canonical names]. For the full args_schema, call {tool: 'help', args: {tool: '<name>'}}.` so a misnamed-arg failure is self-explaining instead of "you got it wrong, figure it out".
- **In-dashboard "Test Tool Call" form** on `/dashboard/dev-tools/mcp`. Pick a token, pick a tool from a dropdown of every tool in the catalog, the form reads `args_schema` from the help endpoint and renders one input per arg (text/select for `enum`, checkbox for booleans, textarea for code/sql/objects). Required args are marked with `*`. Submit calls `press.mcp_server.server.handle` directly — same path as external clients — and shows the JSON response inline. Refreshes the Recent Calls table on completion so the user sees their test land.
- **2 new unit tests** in `test_help.py`:
  - `test_every_tool_has_args_schema_covering_required_args` — locks in the registration contract for every tool
  - `test_single_tool_detail_includes_args_schema` — locks in the `site_status` + `site_run_sql` regression specifically

### Notes
- 15/15 `test_help.py` tests pass (was 13/13; +2 new).
- Pre-existing `test_server.py` 4-test failure (SSH cert tests) is unrelated — verified by running on pre-patch tree. Tracked separately.
- The catalog mirror at `dashboard/src/components/mcp/_tool_catalog.js` still only lists tool metadata (category, risk, label, description) — it does NOT carry the schema. That's intentional: the schema source of truth is the backend; the frontend asks `help` at runtime. Avoids duplication and drift.
- `args_schema` is purely additive. External clients that only read `required_args` keep working. No breaking changes.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — feat(mcp): publish JSON Schema per tool + in-dashboard Test Tool Call form


## 19-05-2026 — Press Settings: preserve Password fields on save (stop wiping `__Auth`)

### Fixed
- **Saving Press Settings was wiping every Password field that came in falsy.** Frappe's `Document._save_passwords()` calls `remove_encrypted_password()` on any Password field whose in-memory value is falsy at save time. The desk UI shows `••••` placeholders but doesn't always re-send them — and `frappe.get_single("Press Settings").save()` from console doesn't auto-load passwords into the doc, so the in-memory value is `None` even when `__Auth` has a real encrypted value. Result: any unrelated save (via desk OR console) wiped `offsite_backups_secret_access_key`, `aws_secret_access_key`, and every other Password field on Press Settings. We hit this twice in 48h on `offsite_backups_secret_access_key` — both times the symptom was the same: Clone Site `latest_backup` mode → `Password not found for Press Settings Press Settings offsite_backups_secret_access_key`.
- **Fix: `before_save()` override on `PressSettings`.** Walks every Password field on the doctype, collects fieldnames whose in-memory value is falsy, and adds them to `self.flags.ignore_save_passwords`. Frappe's `_save_passwords()` honours that flag and skips both `remove_encrypted_password()` and `set_encrypted_password()` for those fields, leaving the existing `__Auth` rows untouched. Applies to ALL 15 Password fields on Press Settings (`offsite_backups_secret_access_key`, `aws_secret_access_key`, `twilio_api_key_secret`, `stripe_secret_key`, `razorpay_key_secret`, `remote_secret_access_key`, etc.) so the trap never bites again.

### Added
- **`test_password_preservation_on_save_without_password_resubmit`** in `test_press_settings.py`. Seeds a known secret, re-fetches the Single, changes a non-Password field, calls `.save()`, then asserts the secret is STILL decryptable. Would fail on the pre-fix code (secret wiped) and passes on the new code (secret preserved). 1/1 new test green.

### Notes
- Caveat: if a sysadmin genuinely wants to CLEAR a Press Settings password, they must now do it via `frappe.utils.password.remove_encrypted_password("Press Settings", "Press Settings", fieldname)` directly — saving Press Settings with an empty Password field will no longer wipe the row. For a system-config singleton the tradeoff is correct: cost of accidental wipe (broken offsite backups, restore by hand) >>> cost of needing a console one-liner to clear a credential.
- This is a Frappe-wide UX trap, not just Press Settings. The same risk exists on any DocType with Password fields (User, Email Account, anything with API keys). Fix is generic — copy the `before_save()` pattern to any other Single / singleton-ish doctype where field preservation matters.
- Live incident this morning: `accubuild-stg-qimma.sandbox.mvpstorm.com` clone blocked because the offsite secret got wiped between yesterday's fix and today. Restored via console (copied from `remote_secret_access_key`) — same MinIO user `pressadmin` is shared between the uploads and offsite codepaths so they share the secret.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — fix(press-settings): preserve Password fields on save so __Auth rows don't get wiped


## 19-05-2026 — Clone Site `fresh_backup` mode now actually persists

### Fixed
- **`fresh_backup` mode created the Site Backup row, then `frappe.throw()` rolled it back.** The dialog showed "Fresh backup queued for source site. Wait for it to complete, then retry…" but no Site Backup row appeared, no Agent Job ran, and the user waited forever. Symptom: clone in `fresh_backup` mode → red toast looks right → re-open in `latest_backup` mode after 10 minutes → "No usable offsite backup found". Root cause: `clone_site()` in `site_clone.py` does `source.backup(...)` (which inserts a Site Backup doc) immediately followed by `frappe.throw(...)`. Both run inside the same HTTP request's DB transaction, and `frappe.throw` rolls the whole transaction back — the insert vanishes. Fix is one line: explicit `frappe.db.commit()` between the insert and the throw. Matches the canonical pattern in `press/press/doctype/site/backups.py:357` (`schedule_logical_backups_for_sites_with_backup_time` commits between each per-site backup call).

### Added
- **Regression test `test_clone_fresh_backup_persists_site_backup_row`** in `test_site_clone.py`. Calls `clone_site(mode='fresh_backup')` against a real source (no Site.backup mock — the original test mocked it and so wouldn't catch the rollback), asserts the throw fires, then counts `Site Backup` rows with `offsite=1` for the source site to confirm exactly one new row landed. Fails on the pre-fix code path; passes after the commit is added. Locks the behaviour in.

### Notes
- 11/11 unit tests pass in `test_site_clone.py` (was 10/10 yesterday; +1 for the persistence regression).
- Live impact: `accubuild-stg-qimma.sandbox.mvpstorm.com` had this issue today. Manually triggered an offsite backup via `bench --site demo.mvpstorm.com execute press._clone_trigger.run` (one-off wrapper at `/home/frappe/frappe-bench/apps/press/press/_clone_trigger.py`) to unblock the user; backup `9547t8b5vk` is in flight against MinIO at the time of this commit.
- The original mock-based test (`test_clone_fresh_backup_triggers_backup_then_raises`) kept its place — it documents the INTENT (backup called with the right args, throw fires with right message) but doesn't exercise the transaction. The new test exercises the transaction. Both stay.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `<this-commit>` — fix(clone-site): commit fresh-backup row before throw so it actually persists


## 18-05-2026 — Dashboard pull/push UX gaps + auth allowlist audit (2 logout fixes)

### Fixed
- **Non-System users force-logged-out after clicking Launch Code Server.** Symptom: `markomaher333@gmail.com` opens `/dashboard/groups/<bench>/actions`, clicks Launch Code Server, gets bounced to `/dashboard/login` within ~10 s. Logs showed the user transitioning logged-in → Guest on `press.press.doctype.bench.bench_dev_watch.get_watch_status` (221 Guest hits in 2k log lines). Root cause: `BenchWatchStatus` Vue panel polls `bench_dev_watch.get_watch_status` every 10 s on the bench Actions page and Site Dev tab. `bench_dev_watch` was added in `2719f44c5c` but never added to `ALLOWED_WILDCARD_PATHS` in `press/auth.py`. The Press auth hook rejected every poll with HTTP 401, the Vue dashboard mapped 401 → "session expired" → force-logout. The click itself was incidental — the next poll tick is what killed the session, but users associated the logout with the click.
- **`/dashboard/code-health` would have logged out non-admin users.** Audit follow-up after fixing `bench_dev_watch`: grep'd every `@frappe.whitelist` under `press/press/doctype/bench/` and cross-referenced against Vue dashboard call sites. Found `bench_code_health.*` (10+ whitelisted methods called from `BenchCodeHealth.vue`, `CodeHealth.vue`, `HealthAdvanced.vue`) also missing from the allowlist. Same 401 → logout pattern would have fired on first visit to the Code Health page or expanding the Site Dev Health panel.
- **Dashboard "How to pull and push code" panel had 3 blocking gaps.** Real-world session (Mahmoud on `bench-0022-000015-press-f1` for `eltarek_dist_app`) showed the panel was wrong on:
  1. **Token lifetime: panel said `~60 min`, actual is `~8 hours`** (`bench-git-setup` issues 480-min tokens — Mahmoud's session showed "token valid ~479 min")
  2. **No `origin` remote check.** Fresh bench containers ship apps with only an `upstream` remote pointing at `file:///home/frappe/context/apps/<app>` — not GitHub. Panel jumped straight to `git pull` which fails with `fatal: 'origin' does not appear to be a git repository`.
  3. **No detached-HEAD check.** Fresh containers come in detached HEAD. Panel said `git pull` would just work — actually fails with `You are not currently on a branch`.
- **Misleading line in SSH tab removed.** Old copy: *"Don't run `git remote add origin` manually — the existing remote is set up by Press"*. In fresh containers there literally is no `origin` to begin with, so the advice was actively wrong.

### Added
- **`DevFlowsGuide.vue`** — Dashboard tab now has a blue Prerequisite callout up front + "If Push fails — common fixes" section covering the 3 real errors users hit (`'origin' does not appear`, detached HEAD, 403). Code Server + SSH tabs got two new steps: **3.5 Make sure `origin` points to GitHub** (with `git remote -v` + `git remote add origin`) and **3.6 Get on a real branch** (with `git status` + `git checkout`/`git switch -c`). Migrate-after-pull reminder. Shared yellow callout now differentiates `bench restart` (recycles processes — files survive) from container *rebuild* (wipes uncommitted work).
- **`ReleaseGroupActions.vue`** — Dev Bench panel ("How to use a Dev Bench") got a blue "Before you push" callout pointing devs at steps 3.5 + 3.6 in the tabs below, so they don't hit the gap blind.
- **Wiki**: `docs/wiki/06-deployment-ops/known-issues-and-fixes.md` got a new "Non-System users force-logged-out when Vue dashboard hits a 401" section — diagnostic playbook (auth.json.log tail + audit script), curl verify procedure, prevention rule, and incident history (3 incidents in 8 days).
- **Audit script** in the wiki — one-shot check that finds every dashboard-called whitelisted method NOT in the allowlist. Run before any PR that adds `@frappe.whitelist()` at a `press.press.doctype.*` path.

### Notes
- **Rule for future PRs:** every PR that adds `@frappe.whitelist()` at a `press.press.doctype.<x>.<y>.<method>` path MUST add `/api/method/press.press.doctype.<x>.<y>.` to `ALLOWED_WILDCARD_PATHS` in `press/auth.py` in the SAME commit. The audit script in the wiki enforces this — zero output = safe.
- **3 incidents in 8 days of the identical 401-allowlist bug pattern**: `cb55aebf6e` (deploy_candidate_build / site_clone / partner_payment_payout, 2026-05-10), `4b775755d0` (press.mcp_server., 2026-05-10), `cb22ec0d53` (bench_dev_watch., today), `6e18abbbfb` (bench_code_health., today audit follow-up). Adding the rule to the runbook + memory file makes this the last one.
- **Audited and confirmed safe** (no allowlist entry needed): `bench.py` controller (Vue uses `press.api.*` wrappers — already covered by `press.api.` wildcard), `bench_vscode.py` (Vue calls via `bench_dev_overview.get_vscode_remote_url` wrapper — already covered), `health_inventory.py` (the `@frappe.whitelist` text is inside a string literal, not a decorator).
- **press-ctrl `.git/objects/` permission gotcha**: during deploy, `sudo -u frappe git fetch` failed with `insufficient permission for adding an object to repository database .git/objects` because 43 object files were owned by `root:root` (someone ran git as root earlier). Fixed with `chown -R frappe:frappe .git`. Rule: ALWAYS use `sudo -u frappe git` on press-ctrl, never bare `git` as root.

### Commits
- `95827c5f48` — `docs(dashboard): close gaps in DevFlowsGuide + Dev Bench panel`
- `cb22ec0d53` — `fix(auth-hook): allowlist bench_dev_watch.* to stop force-logout on Dev pages`
- `6e18abbbfb` — `fix(auth-hook): allowlist bench_code_health.* (audit follow-up to bench_dev_watch)`



## 17-05-2026 — Clone Site dialog rewrite + offsite backups to MinIO end-to-end

### Fixed
- **`Password not found for Press Settings offsite_backups_secret_access_key`.** Offsite-backup credentials were never set on this deployment — Press's MinIO wiring existed only for the `remote_uploads` codepath (frontend file uploads). Backup uploads needed their own credentials. Fix is configuration (copy uploads creds across to the `offsite_backups_*` slots, create a `Backup Bucket` row for `press-uploads`), but the underlying code path requires `462ef02133` + agent fork `809e9c2` (next entry).
- **Agent uploaded to real AWS S3, not MinIO.** `press/agent.py:_get_offsite_backup_config()` was sending the agent only `ACCESS_KEY` / `SECRET_KEY` / `REGION` + `bucket` + `path`. Without `endpoint_url`, the agent's boto3 client defaulted to `s3.amazonaws.com` and rejected the upload with `InvalidAccessKeyId: The AWS Access Key Id you provided does not exist in our records.` Now `_get_offsite_backup_config()` passes `ENDPOINT_URL` (from `Backup Bucket.endpoint_url`) and the agent fork at `Veela-Beauty/press-agent` consumes it in `agent/site.py:upload_offsite_backup`. Same pattern `remote_file.py` already uses for downloads. Backwards compatible: empty `ENDPOINT_URL` → boto3 defaults to AWS S3, AWS users unaffected.
- **`get_backup_bucket()` didn't fetch `endpoint_url`.** Sibling fix in `press/press/doctype/site_backup/site_backup.py` — the helper was selecting only `name` and `region` so even with the agent.py fix, no endpoint would propagate. Now selects `endpoint_url` too.
- **Clone Site dialog rendered Target Bench + Data mode as plain text inputs.** The old `confirmDialog` invocation used `fieldtype: 'Select'` (Frappe casing) on the mode field — frappe-ui's FormControl expects `type: 'select'` (lowercase), so the field silently degraded to text. Target Bench had no type at all. Replaced the inline `confirmDialog` with a proper SFC `dashboard/src/components/site/CloneSiteDialog.vue`. Now: combobox bench picker (filtered to app-superset matches), proper select for mode, live subdomain availability check on blur via `press.api.site.exists`.
- **Clone Site redirect produced `/sites/[object Object]`.** `clone_site` returns `{site, job}` (it proxies through `press.api.site._new`) but the dialog templated the whole object into the URL → 404 from `press.api.client.get`. Now reads `response.site` for the route and `response.job` for the Site Job progress page, matching `NewSite.vue`'s `onSuccess` exactly. Python type hint also corrected from `-> str` to `-> dict`.

### Added
- **Clone Site dialog (`dashboard/src/components/site/CloneSiteDialog.vue`).** Replaces the old plain-text prompt. Five fields:
  - **Target Bench** — combobox of compatible benches (`source.apps ⊆ bench.apps`), team-scoped, plus `➕ Create a new bench` sentinel that pivots to `CloneBenchPrompt` against the source site's release group.
  - **New subdomain** — live availability check on blur with red/green inline feedback, regex pre-check before any network call.
  - **Site Plan** — preselected to source's plan, dropdown of enabled `Site Plan` rows. Without this, Press's `_new` silently dropped unknown plan values and left `Site.plan = None`.
  - **Disk-space banner** — when a real bench is picked, calls `check_bench_space(target_bench, required_bytes = source.current_disk_usage * 1.2)`. Public servers auto-extend so the banner short-circuits to OK. Submit is blocked on insufficient space.
  - **Data mode** — `latest_backup` (default), `fresh_backup`, `empty`, with dynamic hint paragraph.
- **`list_compatible_benches(site)`** in `site_clone.py` — returns benches whose app set ⊇ source apps. Team-scoped: team users see only their team's benches, System Users see all.
- **`get_clone_options(site)`** — single-shot fetch for the dialog. Returns `{compatible_benches, plans, source_plan, source_disk_usage}` so the frontend doesn't make three round trips.
- **`check_bench_space(target_bench, required_bytes)`** — mirrors `press.api.site.validate_restoration_space_requirements` but keyed by bench instead of pre-existing site. Returns `{server, free_bytes, required_bytes, sufficient, is_public_server}`.
- **Optional `plan` parameter** on `clone_site()` so the dashboard can pass an explicit plan (defaults to source's plan, falls back to `"Free"`).
- **Wiki**: `press/docs/wiki/02-operations/backups.md` now has full "Offsite backups to MinIO" section + Clone Site dialog reference (credentials checklist, Backup Bucket row schema, agent fork version requirement, symptom→cause table, file map).

### Notes
- 10/10 unit tests pass in `test_site_clone.py` (8 original + 2 new for `get_clone_options` and `check_bench_space`).
- Agent fork commit `809e9c2` was deployed to **press-f1 only** this round. Roll to u4 and u5 separately when ready — without it, offsite backups on those clusters will silently fail the same way ours did. Tracked as a follow-up.
- The `Backup Bucket.bucket_name` field uses `autoname: field:bucket_name` — when creating new rows programmatically, pass `bucket_name=` (NOT `name=`), otherwise Frappe throws `Bucket Name is required`. Documented in the wiki.
- Pre-existing `Site.plan = None` on `roseline-erpsys` (the test clone) was backfilled via `Site.change_plan('USD 25', ignore_card_setup=True)`. New clones via the patched dialog supply `plan` to `_new` directly so this should not recur — confirm on next clone.

### Commits
- Press (`Veela-Beauty/press` `cloudflare-dns`):
  - `63c5a0d5fc` — Clone Site dialog with proper dropdowns + bench-clone pivot + `list_compatible_benches`
  - `462ef02133` — Send `ENDPOINT_URL` to agent so MinIO/custom-S3 offsite backups work
  - `5eb0a94f4a` — Redirect uses `response.site` not the whole dict (fixes `[object Object]` 404)
  - `cc417f2cc7` — Plan picker + disk-space pre-check + `get_clone_options` + `check_bench_space`
- Agent fork (`Veela-Beauty/press-agent` `master`):
  - `809e9c2` — Consume `auth.ENDPOINT_URL` in `upload_offsite_backup` so boto3 routes to MinIO



## 12-05-2026 — MCP token issuance: 1–90 day TTL + email-OTP password alternative

### Changed
- **MCP token TTL field switched from minutes (max 1440) to days (1–90), default 7.** Backend `TTL_MAX` in `press/mcp_server/auth.py` bumped from 1440 minutes to `60 * 24 * 90`. UI converts days → minutes before sending. Long-lived agent tokens were the stated need — minute granularity is meaningless past a few hours. The Reissue dialog in `MCPPanel.vue` was switched to days for consistency. Existing tokens are unaffected (their `expires_at` was already set at issue time).

### Added
- **Email-OTP alternative to password re-auth at token issuance.** Users on SSO / forgot-password flows could not issue MCP tokens because the dialog required typing a password. New flow: click *"Forgot password? Use email OTP instead"* → click **Send code** → a 6-digit code is mailed to `User.email`, valid 10 min, one-shot consume, hashed at rest via `passlibctx.hash`. Server-side throttle: max one OTP per username per 30s. IP brute-force gate (5 fails / 5 min → 60 min block) applies to OTP failures the same way it does to password failures. `issue_token` now accepts either `password` OR `otp` — at least one required.
- **New doctype: Press MCP Email OTP** (`press/press/doctype/press_mcp_email_otp/`). Hash-named, transient, System Manager read-only. Fields: `username`, `code_hash`, `expires_at`, `consumed`. No web/dashboard exposure.
- **New whitelisted endpoint: `press.mcp_server.auth.request_email_otp`** — guest-allowed (matches `issue_token`), uses Frappe's `sendmail` (now=True). Silently does nothing if the user doesn't exist or is disabled — never leaks user existence.
- **Wiki page**: `docs/wiki/03-integrations/mcp-server.md` — full token issuance guide (TTL range, both re-auth paths, API contract, doctype shape, operational notes, file map).

### Notes
- Email delivery depends on Press's outgoing Email Account. If `disable_mail_notifications=1` is set in `site_config.json`, turn it off before relying on OTP — the OTP path will silently degrade to "code never arrives".
- No scheduler hook ships for cleaning up consumed/expired OTP rows. They're tiny but a daily prune by `expires_at < now() - 1 day` is reasonable hygiene if rows pile up.
- Deployed to press-ctrl 2026-05-12: patch applied via `git am`, `bench migrate` installed the new doctype, `yarn build` rebuilt the dashboard, web restarted. Live at `https://autodeploypanel.mvpstorm.com/dashboard/dev-tools/mcp`.



## 06-05-2026 — Deploy logout fix + press-f1 MariaDB firewall

### Fixed
- **System Users blocked from deploying cross-team benches.** `get_bench_update()` in `bench_update.py:175` had a second team check after `@protected("Release Group")` that rejected ALL users including System Users. The decorator exempts System Users but the inner function did not — inconsistent. Added `and not is_system_user` to the check so System Users can deploy any bench (matching `@protected` behavior). 1-line fix.
- **Vue dashboard `logoutWithTeamError()` destroyed session on team PermissionError.** `waitUntilTeamLoaded()` in `router.js:712` treated all PermissionError/ValidationError from `getTeam()` as session-invalid — called `session.logout.submit()` which destroyed the Frappe session. Team error != session invalid. Replaced with `localStorage.removeItem("current_team")` + `window.location.href="/app"` — clears stale team, redirects to Desk, no session destruction. 5-second timeout fallback unchanged as safety net.
- **press-f1 MariaDB port 3306 exposed to internet.** Hetzner abuse report (CB-Report#...). MariaDB bound to `0.0.0.0:3306` with no firewall (UFW inactive, iptables empty). Could not change bind-address because Docker bench containers connect via public IP `89.167.57.21:3306`. Applied iptables rules: ACCEPT from press-ctrl, Docker bridge (172.17.0.0/16), localhost; DROP everything else. Installed `iptables-persistent`, rules saved to `/etc/iptables/rules.v4`, `netfilter-persistent.service` enabled.

### Added
- **Wiki: press-ctrl push workaround** in `docs/wiki/06-deployment-ops/press-ctrl-stability-runbook.md`. Press-ctrl deploy keys are read-only — document the bundle-to-Hetzner-dev-box push method.
- **Wiki: press-f1 MariaDB firewall recovery** in same runbook. iptables rule table, verification commands, recovery steps.



## 05-05-2026 — Team permissions: session caps, sane Press Role defaults, actionable 403 hints

### Fixed
- **`User.simultaneous_sessions = 2` evicting active dashboard tabs.** Frappe's `is_whitelisted()` raises identical wording — *"Function X is not whitelisted"* — for both the missing-decorator case AND the guest-not-allow_guest case. With a low session cap, opening a 3rd tab kicked the cookie of an older one; the next click from that tab arrived as Guest and surfaced the misleading whitelist error. New `MIN_SIMULTANEOUS_SESSIONS = 10` in `press/press/doctype/team/team_roles.py`. Patch `v0_0_5/bump_team_member_session_cap.py` backfills every existing Team Member's user.
- **Press Role with all 18 flags = 0 silently locked out members.** A freshly created Press Role started with every boolean flag at 0 — total dashboard lockout for any member assigned. `before_insert` on the Press Role doctype now pre-ticks a 7-flag Developer baseline (`allow_dashboard`, `all_release_groups`, `all_sites`, `all_servers`, `allow_apps`, `allow_bench_creation`, `allow_site_creation`); sensitive flags (`admin_access`, `allow_billing`, `allow_server_creation`, team-management, webhook) stay 0 by default.
- **`raise_not_permitted()` returned generic "Not permitted".** The dashboard 403 toast now names the missing flag — *"Ask your team admin to enable 'all_release_groups' on your Press Role (or grant access to this specific Bench via Manage Team -> Roles -> Resources)."* Driven by a new `_DOCTYPE_TO_FLAG` map (31 doctypes) in `press/api/client.py`. 6 of 7 call sites updated to pass doctype context; the 7th (unwhitelisted-method case in `check_dashboard_actions`) keeps the bare call because that's a developer config error, not a user-actionable role gap.

### Added
- **`Team Member.after_insert` → `ensure_session_cap`** — every newly invited team member gets `simultaneous_sessions = 10` automatically. Hook only raises the cap, never lowers an admin-set higher value. Idempotent.
- **`Press Role.validate` → `warn_if_zero_flag_lockout`** — orange `msgprint` warning *"Empty role — members will be locked out"* fires when a role has users assigned but every flag at 0. Not a hard block — placeholder roles still allowed.
- **Admin guide** at `docs/wiki/01-backend-development/team-roles-permissions.md` (279 lines) — explains the two parallel permission systems (`Team Member.press_role` string vs `Press Role` doctype's 18 booleans), categorizes all 18 flags, ships 5 copy-paste preset recipes (Developer / Site Admin / Ops Admin / Read-only Viewer / Full Admin), and includes a SQL recovery playbook for locked-out members.

### Notes
- Hint-aware errors land in `press.api.client` only — the highest-traffic 403 source (Vue dashboard data loads). `team_guard` decorators + per-method action throws (e.g. `Bench.deploy()`, billing methods) keep their existing wording for now. Same `_DOCTYPE_TO_FLAG` pattern is reusable when extending.
- `accurate-systems/press` is now a GitHub redirect to `Veela-Beauty/press`. press-ctrl's `upstream` remote can return stale fetch content — always use `veela` remote for canonical state.

---

## 22-04-2026 — Admin Panel: Servers tab, live stats, unified rows

### Added
- **Admin Panel sidebar entry** wired in `dashboard/src/components/NavigationItems.vue`. Was previously reachable only via direct `/dashboard/admin` URL.
- **Real Servers tab** in Admin Panel (replaces placeholder). Component at `dashboard/src/components/admin/ServerAdmin.vue`. Shows summary cards (Total / Active / Decommissioned / Effective Cost), table with edit + decommission actions per server.
- **3 Custom Fields** on `Server` DocType via `press/press/doctype/server/server_admin_setup.py`: `monthly_cost_override` (Currency), `is_decommissioned` (Check), `admin_notes` (Small Text). Idempotent setup mirrors `team_admin_setup.py` pattern.
- **3 admin APIs** in `press/api/admin_panel.py`:
  - `get_servers_admin()` — returns one row per physical machine (grouped by IP), with `roles` array
  - `update_server_admin(server, monthly_cost_override, admin_notes)` — edit cost + notes
  - `set_server_decommissioned(server, decommissioned)` — toggle the soft-archive flag
- **Live RAM/CPU/Disk stats** via SSH probe from press-ctrl (new `press/api/admin_panel_stats.py`). Single SSH call per server, cached 60s in `frappe.cache`. Returns total/used/avail RAM, CPU cores + load avg, disk size + used + percentage. Lazy-loaded per row in the UI with color thresholds (green <70%, orange 70-85%, red ≥85%).

### Changed
- **Server rows unified by physical machine.** In standalone-mode deployments where one machine runs Server + Database Server + Proxy Server records on the same IP, the table now shows **one row per machine** with multiple role badges (was: 3 separate rows = 7 total → now 3 rows). Cost / sites / benches / admin overrides are still owned by the `app` role only — no double counting.
- **`_get_server_costs()` and `_calc_team_cost()`** now skip decommissioned servers and prefer `monthly_cost_override` over the hardcoded `SERVER_COSTS` baseline. Teams tab `total_cost` updates accordingly when an admin decommissions a server or sets an override.

### Notes
- Stats collection uses the frappe user's default SSH key (`~/.ssh/id_ed25519`) which Press provisioning already deploys. No new secrets required.
- Decommission is a soft flag — no infrastructure changes are made (agent stays running, sites keep serving). Only excluded from cost rollups + UI signal.

---

## 03-02-2026

### Changed
- Introduced stricter app versioning requirements for all Frappe apps.
- All apps (Marketplace and private) must now:
  - Include a `pyproject.toml` file
  - Declare a bounded Frappe dependency under `[tool.bench.frappe-dependencies]`.
  - Support is only added for NPM based versioning, 

### Breaking Changes
- Apps without a `pyproject.toml` file will fail validation.
- Apps using unbounded Frappe version ranges (e.g. `^`, `~`, or single-sided constraints) are rejected.

### Note on version syntax

Frappe app version constraints are validated using **NPM-style semantic versioning** (`NpmSpec`), in favour of internal frappe applications such as CRM and helpdesk.

As a result:
- Version ranges must follow **NPM semver syntax**
- Python-style version specifiers (PEP 440), such as `~=`, are **not supported**

### Relevant links
https://github.com/frappe/press/issues/4809

### Example
```toml
[tool.bench.frappe-dependencies]
frappe = ">=16.0.0-dev,<17.0.0-dev"
