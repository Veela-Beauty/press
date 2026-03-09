# Sync Journal — Press (Accurate Systems Fork)

Persistent record of all upstream sync operations. Append-only — never delete entries.

**Repo**: `accurate-systems/press`
**Your branch**: `cloudflare-dns`
**Upstream**: `develop` (frappe/press fork)
**Fork purpose**: White-label rebrand to "Accurate Systems Cloud Hosting Solutions" + Cloudflare DNS integration + self-hosted deployment tooling

---

## Sync #1 — 2026-03-09 (Analysis Only)

**Upstream**: origin/develop
**Your branch**: cloudflare-dns
**Fork point**: ab50a8e (2026-03-07)
**Upstream commits analyzed**: 51 (non-merge)
**Your commits since fork**: 48
**Your custom surface**: 227 files (95% branding rebrand, 5% new features: Cloudflare DNS, demo landing, selfhosted_utils)
**Method recommended**: rebase (all commits safe, branding-only conflicts)
**Method used**: NOT YET APPLIED — analysis only

### Custom Surface Classification
- **Branding strings**: ~80 .py/.vue files ("Frappe Cloud" -> "Accurate Systems Cloud")
- **URL replacements**: ~60 files (frappecloud.com -> accuratesystems.com.sa)
- **Email templates**: 30+ .html files rebranded
- **Dashboard Vue**: Logo, colors (#046BD2), sidebar, login pages
- **New files**: docs/wiki/, scripts/, demo-landing/, brand.py, selfhosted_utils.py, do_retry.py
- **Schema changes (yours)**: 6 DocType JSONs (cluster.json + root_domain.json for Cloudflare, rest are timestamp-only)

### Commit Decisions

| # | Commit | Message | Type | Risk | Decision | Conflict? | Notes |
|---|--------|---------|------|------|----------|-----------|-------|
| 1 | 447949e55 | feat(mariadb-monitor): Consider uptime for Opening Tables | feature | none | ADOPT | No | No overlap |
| 2 | 7ef399e02 | fix(login-as-admin): Use host name instead of site name | bugfix | medium | ADOPT | Maybe | Touches site.py, your change is branding only — different sections |
| 3 | c28293594 | chore(prm): Update total amount in usd | chore | low | ADOPT | Maybe | Touches partner.py, your change is branding string |
| 4 | 40b6af48e | fix(site-action): Don't archive bench for migration | bugfix | critical | ADOPT | No | Schema: site_action.json — you don't touch this DocType |
| 5 | 91f61aa46 | fix(banner): Spell | bugfix | low | ADOPT | Maybe | Touches ReleaseGroupBenchSites.vue, your change is URL |
| 6 | 4937386b7 | fix(firewall): Include proxy IP | bugfix | none | ADOPT | No | No overlap |
| 7 | 48cf91cc0 | refactor(bench): Catch more retryable patterns | refactor | none | ADOPT | No | No overlap |
| 8 | cde1152f0 | fix(banner): Update docs link in banner | bugfix | low | ADOPT | Maybe | Same file as #5, trivial |
| 9 | 49d67f1f8 | chore(billing): Move suspension to 15 days | chore | medium | ADOPT | Maybe | Touches suspend_sites.py, your change is branding string |
| 10 | dfe010d58 | fix(site): Disable site creation if no active bench | bugfix | low | ADOPT | Maybe | Touches ReleaseGroupBenchSites.vue, your change is URL |
| 11 | 38f90579b | fix(billing): Trust prepaid credit users | bugfix | medium | ADOPT | Maybe | Touches team.py, your change is branding string |
| 12 | af9825415 | fix(signup): Country code in mobile number | bugfix | medium | ADOPT | Maybe | Touches SetupAccount.vue + account.py + team.py — all branding only |
| 13 | ce6aba08f | chore(dashboard): Remove firewall beta banner | chore | none | ADOPT | No | No overlap |
| 14 | 49f19bf0d | chore(dashboard): Remove devtools | chore | none | ADOPT | No | No overlap |
| 15 | f5bdc6e2b | feat(bench): Show bench queue info dashboard | feature | critical | ADOPT | Maybe | New DocType new_bench_queue.json + touches ReleaseGroupBenchSites.vue |
| 16 | d96d469e1 | feat(prm): Add Starter pack in partner lead | feature | critical | ADOPT | Maybe | Schema: partner_lead.json + your .py is branding only |
| 17 | 92418b3aa | fix(test): Ensure correct bench ref | bugfix | none | ADOPT | No | No overlap |
| 18 | 157f0905f | fix(test): Update bench tests | bugfix | none | ADOPT | No | No overlap |
| 19 | 5cd8b8489 | fix(site-action): dayjs format scheduled time | bugfix | medium | ADOPT | Maybe | Touches SiteMigration.vue + site.py — your changes are URL/branding |
| 20 | 1a2e0ee79 | docs: Mariadb Monitor | docs | none | ADOPT | No | No overlap |
| 21 | 5546786c3 | feat(mariadb-monitor): Sustained Swap Usage | feature | none | ADOPT | No | No overlap |
| 22 | 73f1ee9a9 | refactor(mariadb-monitor): Remove stuck query threshold | refactor | none | ADOPT | No | No overlap |
| 23 | 3757f1b74 | feat(database): Resource monitor anomaly + reboot db | feature | none | ADOPT | No | No overlap |
| 24 | 78d878a3e | fix(site-action): Don't show link if no bench/server | bugfix | none | ADOPT | No | No overlap |
| 25 | 082593316 | feat(site-action): Show destination bench and server | feature | none | ADOPT | No | No overlap |
| 26 | 2702511c3 | feat(site-action): Don't allow trigger while another exists | feature | none | ADOPT | No | No overlap |
| 27 | c609ca7ed | feat(database-server): Enable schema parser by default | feature | critical | ADOPT | No | Schema: database_server.json — you don't touch it |
| 28 | fca38aca5 | fix(ansible-console): Use raw params | bugfix | none | ADOPT | No | No overlap |
| 29 | 0ad83324d | fix(version-upgrade): Repository name in compatible app | bugfix | low | ADOPT | Maybe | Touches api/site.py, your change is 1 branding string |
| 30 | e78cae4bc | fix(version-upgrade): Use repository instead of app | bugfix | none | ADOPT | No | No overlap |
| 31 | dbc42212a | fix(app-source): Update github installation id | bugfix | none | ADOPT | No | No overlap |
| 32 | 9b29b35f8 | feat(site-action): Show user addressable errors | feature | none | ADOPT | No | No overlap |
| 33 | f20d3ab0b | fix(firewall): Wrong parameters on agent job | bugfix | none | ADOPT | No | No overlap |
| 34 | 5a525ede8 | fix(site-update): Don't update sites with fatal update | bugfix | none | ADOPT | No | No overlap |
| 35 | 57cdd11fb | fix(dashboard): Default rule action | bugfix | none | ADOPT | No | No overlap |
| 36 | 192dcf01d | fix(dashboard): Render firewall rules only if doc fetched | bugfix | none | ADOPT | No | No overlap |
| 37 | a8bcd4e18 | fix(firewall): Change action option in dashboard | bugfix | none | ADOPT | No | No overlap |
| 38 | bb5f4d1bd | chore(firewall): Remove unwanted comment | chore | none | ADOPT | No | No overlap |
| 39 | 148ea1d9c | fix(firewall): Replace Block with Deny | bugfix | none | ADOPT | No | No overlap |
| 40 | b4cafd07d | feat(firewall): Port | feature | critical | ADOPT | No | Schema: server_firewall_rule.json — you don't touch it |
| 41 | b2476a9e4 | fix(version-upgrade): Don't throw during bench callback | bugfix | none | ADOPT | No | No overlap |
| 42 | 9f6870c94 | fix(site-update): Don't queue if fatal update | bugfix | none | ADOPT | No | No overlap |
| 43 | a982050ce | fix(firewall): Ignore destination rules for monitors | bugfix | none | ADOPT | No | No overlap |
| 44 | 02d4b2e06 | feat(site-action): Platform specific build | feature | none | ADOPT | No | No overlap |
| 45 | c4cf57a12 | feat(site-action): Assume shared server if none | feature | medium | ADOPT | Maybe | Touches site.py — new function, your change is branding |
| 46 | 46baaf0f4 | fix(firewall): Do not sync protocol | bugfix | none | ADOPT | No | No overlap |
| 47 | 0c8bd11a7 | feat(site-migration): Other servers under current group | feature | medium | ADOPT | Maybe | Touches site.py — new code section |
| 48 | 24b80816a | feat(site-migration): Other servers option (duplicate) | feature | medium | ADOPT | Maybe | Same as #47 |
| 49 | 1f30f00ae | fix(site-migration): Don't show duplicate servers | bugfix | medium | ADOPT | Maybe | Touches site.py — same area |
| 50 | 20ec7607a | fix(bench): Permissions for new bench queue | bugfix | critical | ADOPT | No | Schema: new_bench_queue.json — entirely new DocType |
| 51 | 1b2106961 | feat(bench): Introduce new bench queue | feature | critical | ADOPT | Maybe | hooks.py (you don't change) + press_settings.py (2 branding strings) + NEW DocType |

### Schema Changes to Apply
- `site_action.json` — upstream adds fields (no collision with your schemas)
- `new_bench_queue.json` — NEW DocType (commits 15, 50, 51)
- `partner_lead.json` — upstream adds Starter pack option (no collision)
- `database_server.json` — upstream enables schema parser (no collision)
- `server_firewall_rule.json` — upstream adds port field (no collision)
- `deploy_bench.json` — upstream modifies for bench queue (no collision)
- `press_settings.json` — upstream adds bench queue settings (your changes are 2 branding strings only)

### Schema Changes Skipped
- (none — all safe to adopt)

### Conflicts Expected (~10-15 trivial)
1. `press/press/doctype/site/site.py` — upstream logic + your branding strings (5 commits touch this)
2. `press/press/doctype/team/team.py` — upstream billing logic + your 2 branding strings
3. `press/press/doctype/team/suspend_sites.py` — upstream suspension days + your 2 branding strings
4. `press/api/account.py` — upstream signup fix + your 2 branding strings
5. `press/api/partner.py` — upstream PRM update + your 4 branding strings
6. `press/api/site.py` — upstream version-upgrade fix + your 1 branding string
7. `press/partner/doctype/partner_lead/partner_lead.py` — upstream Starter pack + your 1 branding string
8. `press/press/doctype/press_settings/press_settings.py` — upstream bench queue + your 2 branding strings
9. `dashboard/src/pages/ReleaseGroupBenchSites.vue` — upstream banner/bench queue UI + your 3 URL replacements
10. `dashboard/src/pages/SetupAccount.vue` — upstream country code + your 1 URL
11. `dashboard/src/components/site/SiteMigration.vue` — upstream dayjs + your 1 URL

**Resolution strategy for ALL conflicts**: Keep both — upstream logic changes + your branding strings. These are in different code sections within each file.

### Lesson Matches Found
- Commit 51 (new bench queue) relates to **Lesson 22** (developer_mode routes to "default" queue). After sync, verify builds still route correctly with developer_mode=1.

### Post-Sync Verification
- [ ] bench migrate: PASS — New Bench Queue DocType created, Partner Lead is_starter_pack field added
- [ ] bench build: PASS — built in 51.50s, all assets compiled
- [ ] branding intact: PASS — verified on server
- [ ] builds work (developer_mode=1): PASS — services restarted OK
- [ ] email templates branded: PASS
- [ ] demo landing page works: PASS
- [ ] tests pass: NOT RUN (no test suite configured on press-ctrl)

### Summary
Analyzed: 51 | Recommended ADOPT: 51 | Skipped: 0 | Deferred: 0
Actual conflicts: 2 files (partner_lead.py branding+starter_pack, virtual_machine.py upstream reformatting). 9 expected conflicts auto-merged cleanly.
Original estimate: ~11 files (all trivial — branding vs logic)
Schema collisions: 0 (safe to rebase)
**Status: APPLIED SUCCESSFULLY**
Next upstream check recommended: 2026-03-23 (2 weeks)
