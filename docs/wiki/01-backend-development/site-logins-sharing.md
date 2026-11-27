# Site Logins and Sharing

A "Logins and sharing" card on each site's Overview in the dashboard: the site's share login (a normal user Press
creates on the site, for people outside the team) and its Administrator login, each hidden until Show, and "Copy share
message" (site link, user, password) ready for WhatsApp or email. Every Show, copy, share, create and reset asks for a
6-digit code first, then no code for 10 minutes, and every action is recorded.

Shipped in Press 0.7.80 (PR #94, merge `5f818671f`), live on press-ctrl since 27 Nov 2026 09:38 Riyadh.
Prototype PRS-SP-17: `~/docs/prototypes/press-site-logins/index.html`. Plan and decisions:
[docs/plans/2026-11-27-site-logins-sharing.md](../../plans/2026-11-27-site-logins-sharing.md).

---

## Feature Overview

| Who | Share login | Administrator login | Create / reset share user |
|---|---|---|---|
| Team admin (owner, Platform Admin, or a team with no roles set up) | Show, copy, Copy share message | Show, copy | Yes |
| Member whose Press role covers the site | Show, copy, Copy share message | Not shown | No ("Ask a team admin to create one") |
| Anyone else, another team, a guest | 403 | 403 | 403 |
| Any user, confidential site | As above | Never shown: "use Login as Administrator with your PIN" | No share user on a confidential site |

"Team admin" is `press.api.account.user_permissions()["admin"]`, the same flag the dashboard already uses.

---

## Architecture

### Data model

| Where | Field | Type | Notes |
|---|---|---|---|
| Site | `share_user` | Data, read only | Set by Press when the share user is created |
| Site | `share_password` | Password, read only | Encrypted with the site's encryption key; replaced on reset |
| Site Activity | `action` option `Share Login` | Select option | One row per action, `reason` says what and how verified |

No new DocType. The role profile of the share user is read back from the newest "created the share user" activity.

### Access checks (every endpoint)

All endpoints live in [press/api/site_logins.py](../../../press/api/site_logins.py) and pass, in order:

1. `frappe.whitelist(methods=["POST"])`: POST only. A GET request is rolled back at the end, which would drop the
   activity row while still returning the password.
2. `protected("Site")`: the team owns the site.
3. `role_guard.document("Site", name)`: the user's Press role covers this site.
4. `_same_team`: the site's team is the user's current team. This also binds System Users, which `protected` lets
   through; only a System Manager passes for any site.

On top of that, the Administrator login, `role_profiles`, `create_share_user` and `reset_share_password` require a team
admin.

### The code step

| Rule | Value |
|---|---|
| App code | Checked directly against User 2FA (`totp_secret`, `pyotp`). Not through `account.verify_2fa`: its rate limit keys on the outer endpoint and would stack with ours. |
| App code reuse | The same code is refused within 90 seconds |
| Email code | 6 digits, HMAC-SHA256 with the site encryption key, kept 10 minutes, works once |
| Email sends | 5 per user per 10 minutes |
| Unlock | 10 minutes per user and site, in Redis (`site_logins:unlock:<user>:<site>`) |
| Wrong codes | 5 in a row lock the user out of codes for 10 minutes, recorded as an activity row |
| Redis down | Fails closed: "The service is busy. Try again in a minute." |

A user without an authenticator app links one inside the dialog: the dialog calls `press.api.account.get_2fa_qr_code_url`
and `enable_2fa`, shows the recovery codes once (the dialog cannot be closed until Done), then sends the same code to
`verify_code` with `linked=1`.

### What is recorded

Each action adds a Site Activity row, action `Share Login`, owner = the user, for example:

- `showed the share password (app code)`
- `copied the Administrator password (email code)`
- `copied the share message (app code)`
- `created the share user, role profile Basher Trainee (app code)`
- `reset the share password (app code)`
- `linked an authenticator app in the code dialog (app code)`
- `locked out of codes for 10 minutes after 5 wrong codes`

No row contains a password or a code. The card shows the last 5; the site's Activity tab has all of them.

### The share user

- Created over the site's REST API as Administrator, with a 30-second timeout on every request (a `FrappeClient`
  subclass sets it before the login).
- Email `share-<6 hex>@<site name>`, first name Share, last name Login, System User, no welcome email, an 18-character
  random password.
- Role profile: only one the site already has, and never one that holds System Manager or Administrator. The server
  re-reads the list before creating. Both `role_profile_name` and `role_profiles` are sent, so v14 and newer v15 sites
  work.
- A confidential site gets no share user.
- After the remote change, Press commits its own copy at once, so a later error cannot lose the password.

### Backend API

All `POST /api/method/press.api.site_logins.<name>`, all with `name` = the site name.

| Endpoint | Extra arguments | Needs a code | Team admin | Returns |
|---|---|---|---|---|
| `get_logins` | | No | No | `share_user`, `role_profile`, `admin_visible`, `confidential`, `has_app`, `unlocked_seconds`, `history` (5 rows). Never a password. |
| `send_email_code` | | No | No | `sent_to` (masked email) |
| `verify_code` | `code`, `method` (`app` or `email`), `linked` | No | No | `unlocked_seconds` |
| `get_secret` | `which` (`share` or `admin`), `purpose` (`show`, `copy`, `message`) | Yes | Only for `admin` | `user`, `password` |
| `role_profiles` | | Yes | Yes | Safe role profile names on the site |
| `create_share_user` | `role_profile` | Yes | Yes | `share_user` |
| `reset_share_password` | | Yes | Yes | `ok` |

Example, from the dashboard's resource layer:

```js
await createResource({ url: 'press.api.site_logins.get_secret' })
	.submit({ name: 'basher-training.sandbox.mvpstorm.com', which: 'share', purpose: 'message' });
```

Without a valid code in the last 10 minutes the call fails with `PermissionError: Enter your 6-digit code first`, and
the card reopens the code dialog and repeats the action.

---

## Frontend

- [SiteLogins.vue](../../../dashboard/src/components/site/SiteLogins.vue): the card, placed in
  [SiteOverview.vue](../../../dashboard/src/components/SiteOverview.vue) after Daily usage, across both columns. Two
  halves (share login, Administrator), Access history, "Verified for 10 min" after a code. Passwords live only in the
  component and leave the screen when the 10 minutes end.
- [SiteLoginsCodeDialog.vue](../../../dashboard/src/components/site/SiteLoginsCodeDialog.vue): "Confirm it's you",
  the in-dialog app link (QR code, setup key, recovery codes) and "Email me a code instead".

---

## Deploy and rollback

Deployed by file copy, not a full migrate (press-ops `scripts/site-logins-2026-11-27/`):

1. `01_drift.sh <release>`: compare the live files with the release; copy only what differs.
2. `02_deploy_0780.sh` (root, under nohup): back up, copy the code files and the dashboard build
   (`press/public/dashboard`, `press/www/dashboard.html`), run `03_reload.py`, restart web, then the scheduler and the
   short, long and sync workers one at a time.
3. `03_reload.py`: `frappe.reload_doc` for Site and Site Activity, then checks the column and the option.
4. `04_smoke.py`: `get_logins` in real Frappe returns no secret; `get_secret` without a code is refused.

Rollback: `02_deploy_0780.sh rollback` restores the code and the dashboard. The new fields and option can stay.

---

## Testing

- `python3 press/api/tests/test_site_logins_offline.py`: 20 tests on a stand-in for Frappe (no bench). They skip
  themselves where the real Frappe is importable.
- Covered: POST only, other team refused even for a System User, code first, app code once, 5 wrong codes lock,
  email code once and sends limited, admin-only parts, confidential site, safe role profiles, a down site, reset on
  both sides, no secret in `get_logins`.
- Live, 27 Nov 2026, as the team's dashboard test user (`dashboard-test@optiflowsys.com`, Press role Viewer, which
  names basher-training): the member view on basher-training shows the share login only, "No share user yet. Ask a
  team admin to create one.", no Administrator half, no console error. Pictures: `~/docs/prototypes/press-site-logins/live/`.
- Not yet measured: each role's clicks (prototype: share 3 steps, first share 5). The share jobs need a share user,
  and creating one needs a team admin's 6-digit code, so the owner's first use comes first.

---

## Known limits

- Emailed codes depend on Brevo, which on 27 Nov 2026 held our mail and delivered it about 1.5 days late. Use the
  authenticator app until that is fixed.
- Linking an app inside the dialog proves no more than the session. A session can already use Login as Administrator
  on a non-confidential site, so this opens nothing new; the link is recorded.
- A revoked login keeps its unlock until the 10 minutes end.

---

## Related Files

| File | Role |
|---|---|
| [press/api/site_logins.py](../../../press/api/site_logins.py) | Endpoints, access checks, codes, share user |
| [press/api/tests/test_site_logins_offline.py](../../../press/api/tests/test_site_logins_offline.py) | Offline tests |
| [dashboard/src/components/site/SiteLogins.vue](../../../dashboard/src/components/site/SiteLogins.vue) | The card |
| [dashboard/src/components/site/SiteLoginsCodeDialog.vue](../../../dashboard/src/components/site/SiteLoginsCodeDialog.vue) | The code dialog |
| [press/press/doctype/site/site.json](../../../press/press/doctype/site/site.json) | `share_user`, `share_password` |
| [press/press/doctype/site_activity/site_activity.json](../../../press/press/doctype/site_activity/site_activity.json) | Option `Share Login` |
