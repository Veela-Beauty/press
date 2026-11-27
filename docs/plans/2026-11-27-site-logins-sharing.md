# Site logins and sharing (PRS-SP-17)

Prototype (approved by the owner 27 Nov 2026): `~/docs/prototypes/press-site-logins/index.html`,
https://sanad-preview.sanadeoi.mvpstorm.com/sanad-protos/press-site-logins/index.html

## Objective
On a site's Overview, a "Logins and sharing" card: the share login (anyone whose Press role gives them the site) and
the Administrator login (team admins only, never on a confidential site), each hidden until Show; "Copy share message"
(site link, user, password). Every Show, copy, share, reset and create asks for a 6-digit code first (authenticator
app, or an emailed code), then no code for 10 minutes. Every action is recorded (who, what, when, how verified) in
Site Activity ("Share Login") and the last 5 show in the card.

## Decisions
- No new DocType. Site gets `share_user` (Data, read only) and `share_password` (Password); Site Activity's action
  gets the option "Share Login". One migrate at deploy.
- Backend in `press/api/site_logins.py` (site.py is 3466 lines). Each endpoint: `@protected("Site")` (team) and
  `@role_guard.document("Site")` (the role's sites). Administrator half: `account.user_permissions()["admin"]`.
- Unlock is per user and site in Redis for 10 minutes (`site_logins:unlock:<user>:<site>`), value = how verified.
- App code: `account.verify_2fa`. A user who links the app inside the dialog types one code: the dialog sends it to
  `enable_2fa`, then to `verify_code` (still valid in the same 30-second step). Supersedes the first idea (unlock when
  User 2FA changed in the last 2 minutes): a recent change is not proof of a code. If the second check misses, the
  recovery codes stay on screen and Done asks for the next code.
- Email code: 6 digits, sha256 in Redis for 10 minutes, `frappe.sendmail`. Brevo delays our mail by about 1.5 days
  (27 Nov), so the app code is the working path until that is fixed.
- Share user: created over the site's REST as Administrator (`Site.get_connection_as_admin`), `role_profile_name` from
  the site's Role Profiles, a random 18-character password, no welcome email.

## Tasks
- [x] Site fields + Site Activity option (9e38cd50c)
- [x] `press/api/site_logins.py` + 11 offline tests (c7f839b40)
- [x] `SiteLogins.vue` card + `SiteLoginsCodeDialog.vue`, placed after SiteDailyUsage in SiteOverview.vue; vite build passes (07cbdd10e)
- [ ] Audits: layout re-score on the built card, the role jobs measured, code review, security review
- [ ] Version 0.7.78, CHANGELOG, PR stacked on feat/watch-tower-digest
- [ ] Deploy only when the owner says "deploy" (needs migrate on press-ctrl)

## Resume here (2026-11-27)
- Done: fields (9e38cd50c), backend + 11 tests (c7f839b40), card + dialog (07cbdd10e), version 0.7.78.
- In progress: independent code and security review. Next: fixes, PR stacked on feat/watch-tower-digest.
- Measured on the real screen after deploy (no Press dev site): layout score and the role jobs.
