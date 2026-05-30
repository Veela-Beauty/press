# Confidential-Site PIN Gate + No-Cache Visit Site

Date: 2026-05-30
Status: Design approved, ready for implementation plan
Repo: press_local (accurate-systems/press), branch cloudflare-dns, live at autodeploypanel.mvpstorm.com

## Problem

"Login As Administrator" on the Press dashboard logs an operator straight into any
site's Desk as Administrator after a confirm dialog. For sensitive client sites we
want a second factor: a global PIN that must be entered before admin-login is
allowed, but ONLY for sites explicitly flagged confidential. Normal sites stay
one-click. We also want a wrong-PIN attempt to alert us by email, and we want the
"Visit Site" button to always open a fresh (non-cached) page.

## Goal / Definition of Done

- A site can be flagged `is_confidential` (default OFF; set manually by an admin).
- A single global admin PIN lives in Press Settings (Password field, never sent to
  the browser).
- Clicking "Login As Administrator" on a confidential site requires the correct PIN,
  enforced in the BACKEND (`login_as_admin`), so the API cannot be bypassed.
- Wrong PIN: rejected, logged to Site Activity, rate-limited after 3 tries in 5 min,
  and an alert email is sent (on the 1st wrong attempt and again on lockout).
- Non-confidential sites: behavior unchanged (no PIN prompt).
- "Visit Site" forces a fresh, no-cache load.

## Before / After

Before: any operator with dashboard access clicks "Login As Administrator" ->
confirm dialog (optional reason) -> instant admin session on ANY site.

After: confidential sites additionally require the global PIN (backend-verified);
wrong attempts are logged, rate-limited, and emailed. Visit Site opens fresh.

## Design

### Section 1 : Data model

- **Site doctype** : new field `is_confidential` (Check, default `0`, label
  "Confidential Site"). Toggle restricted to desk / System Manager users
  (controller `validate` rejects a change to this field by non-desk users, since a
  field is sent from the dashboard by team members).
- **Press Settings** (Single) : new fields
  - `admin_login_pin` (Password) : the global PIN. Read server-side via
    `get_password`; never returned to the client.
  - `confidential_alert_email` (Data, default `eng.elgogary@gmail.com`) : recipient
    for wrong-PIN alerts. Configurable, not hardcoded.
  Both editable by System Manager only (Press Settings already is desk-only).
- **Rate-limit counter** : Redis via `frappe.cache()`, key
  `confidential_pin_fail:{user}:{site}`, integer with a 300s TTL. No DocType/schema.

### Section 2 : Backend flow (security-critical)

`login_as_admin(self, reason=None, pin=None)` in
`press/press/doctype/site/site.py` (currently line 1821) gains a guard BEFORE
`self.login()`:

```
if self.is_confidential:
    configured = frappe.get_doc("Press Settings").get_password(
        "admin_login_pin", raise_exception=False)
    if not configured:
        frappe.throw("This site is confidential but no admin PIN is configured. "
                     "Set it in Press Settings.")
    key = f"confidential_pin_fail:{frappe.session.user}:{self.name}"
    fails = int(frappe.cache().get_value(key) or 0)
    if fails >= 3:
        frappe.throw("Too many incorrect PIN attempts. Try again in a few minutes.")
    if (pin or "") != configured:
        fails += 1
        frappe.cache().set_value(key, fails, expires_in_sec=300)
        log_site_activity(self.name, "Login as Administrator - WRONG PIN", reason=reason)
        if fails == 1 or fails >= 3:        # first wrong OR lockout threshold
            _send_wrong_pin_alert(self.name, reason, fails)   # try/except, never blocks
        frappe.throw("Incorrect PIN")
    frappe.cache().delete_value(key)        # correct PIN clears the counter
# ... existing self.login() continues
```

- The PIN check is BACKEND only. The Vue dialog collects the PIN but does not decide.
- `get_password` decrypts server-side; the PIN never reaches the browser.
- Non-confidential sites skip the entire block (unchanged).
- `_send_wrong_pin_alert` builds a `frappe.sendmail` to `confidential_alert_email`
  with: `frappe.session.user`, site name, timestamp, reason text. Wrapped in
  try/except + `frappe.log_error` so a mail failure never blocks the rejection.
- `login_as_admin` stays `@dashboard_whitelist()` : same method, new optional param,
  so NO new `auth_hook` allowlist entry is required.

### Section 3 : Frontend (Vue dashboard)

In `dashboard/src/objects/site.js`, the "Login As Administrator" `confirmDialog`
(lines ~1851-1886):

- `fields` array conditionally includes a PIN field when `site.doc.is_confidential`:
  `{ label: 'Admin PIN', type: 'password', fieldname: 'pin' }`. Non-confidential
  sites get the existing dialog (optional Reason only).
- `onSuccess` passes `pin: values.pin` into
  `site.loginAsAdmin.submit({ reason: values.reason, pin: values.pin })`. On a
  backend throw, the error shows and the dialog stays open for retry.
- **Confidential toggle UI** : a switch in the site settings area (SiteOverview or a
  settings tab), shown/editable only when `$team.doc?.is_desk_user`, calling a small
  `setConfidential` resource (`site.setValue` on `is_confidential` or a dedicated
  whitelisted method). Reflects `site.doc.is_confidential`.

### Section 4 : Feature 2 : no-cache Visit Site

The "Visit Site" action appends a cache-busting query param at click time:
`https://{host_name||name}/?_nocache={Date.now()}`. One-line change at the Visit
Site handler in `site.js` / `SiteOverview.vue`. Timestamp generated on click, not at
render.

### Section 5 : Testing

Backend (`test_site.py` or a focused test module):
- confidential + correct PIN -> returns login URL, counter cleared.
- confidential + wrong PIN -> throws "Incorrect PIN", logs activity, counter = 1.
- confidential + no PIN configured -> throws the not-configured message.
- 3 wrong tries -> 3rd throws lockout message.
- non-confidential -> no PIN needed (ignores pin arg).
- email: `frappe.sendmail` called on 1st wrong attempt AND on lockout (fails==3),
  NOT on the 2nd. Mock sendmail.

Frontend:
- Prototype the dialog (prototype-first rule) showing the PIN field appearing for a
  confidential site and absent for a normal site. Get approval before porting.

## Out of scope

- Per-site PINs (one global PIN only).
- Auto-opening a real incognito window (browser-impossible; rejected in feasibility).
- Any change to `login_as_team` / `login_as_user`.
- 2FA / TOTP (a static PIN is the agreed mechanism).

## Risks

- Backend-only enforcement is the load-bearing requirement : if the check were
  frontend-only, the dashboard API call could be replayed without a PIN. The plan
  must put the throw in `login_as_admin`, with a test that calls the method directly
  with a wrong/empty pin.
- `is_confidential` editable by non-desk users would let a team member unprotect
  their own site : the controller `validate` gate is required, not just a UI
  `condition`.
