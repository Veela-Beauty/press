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
- App code: `account.verify_2fa`. A user who links the app inside the dialog is unlocked by the link itself (enable_2fa
  already verified a code) when User 2FA changed in the last 2 minutes.
- Email code: 6 digits, sha256 in Redis for 10 minutes, `frappe.sendmail`. Brevo delays our mail by about 1.5 days
  (27 Nov), so the app code is the working path until that is fixed.
- Share user: created over the site's REST as Administrator (`Site.get_connection_as_admin`), `role_profile_name` from
  the site's Role Profiles, a random 18-character password, no welcome email.

## Tasks
- [ ] Site fields + Site Activity option
- [ ] `press/api/site_logins.py` + tests on fakes
- [ ] `SiteLogins.vue` card + `SiteLoginsCodeDialog.vue`, placed after SiteDailyUsage in SiteOverview.vue
- [ ] Audits: layout re-score on the built card, the role jobs measured, code review, security review
- [ ] Version 0.7.78, CHANGELOG, PR stacked on feat/watch-tower-digest
- [ ] Deploy only when the owner says "deploy" (needs migrate on press-ctrl)

## Resume here (2026-11-27)
- Branch `feat/site-logins` from `feat/watch-tower-digest` (live 0.7.77). Next: the Site fields.
