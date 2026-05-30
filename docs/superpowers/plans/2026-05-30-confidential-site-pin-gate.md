# Confidential-Site PIN Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Require a global PIN (backend-verified) before "Login As Administrator" on sites flagged confidential; log + rate-limit + email-alert wrong attempts; make "Visit Site" load fresh. Non-confidential sites unchanged.

**Architecture:** `is_confidential` Check on Site + `admin_login_pin` (Password) and `confidential_alert_email` (Data) on Press Settings. The PIN check is enforced in the backend `Site.login_as_admin`; the Vue dialog only collects the PIN. Rate-limit via Redis `frappe.cache()`. Visit Site appends a cache-buster.

**Tech Stack:** Frappe v15 (Python), Vue 3 dashboard, site `autodeploypanel.mvpstorm.com`, Press fork `accurate-systems/press` branch `cloudflare-dns`. Work on `feat/confidential-pin-gate`.

**Conventions:**
- Repo on dev box: `/data/eslam-data/erpnext-app-repos/press_local/`
- Tests run on press-ctrl. Sync first: `scp -q <localfile> press-ctrl:/home/frappe/frappe-bench/apps/press/<relpath>`
- Backend tests: `ssh press-ctrl "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com run-tests --module press.press.doctype.site.test_site"` (NOTE: confirm the Press site name on press-ctrl; demo.mvpstorm.com is the daman site. Press dashboard runs on the SAME bench — verify with `bench --site demo.mvpstorm.com list-apps | grep press`).
- `login_as_admin` is already `@dashboard_whitelist()` -> NO new auth_hook allowlist entry needed (same method, new optional param).

---

## File Structure

- Modify: `press/press/doctype/site/site.json` (+1 field `is_confidential`)
- Modify: `press/press/doctype/press_settings/press_settings.json` (+2 fields under security_tab)
- Modify: `press/press/doctype/site/site.py` (`login_as_admin` PIN guard + `_send_wrong_pin_alert` helper + `validate` gate on is_confidential)
- Modify: `dashboard/src/objects/site.js` (dialog PIN field + Visit Site cache-buster + confidential toggle)
- Test: `press/press/doctype/site/test_site.py` (append a TestConfidentialPinGate class)
- Prototype: `docs/prototypes/confidential-pin-dialog.html` (dialog states, for approval before Vue port)

---

## Task 1: Schema — is_confidential on Site

**Files:** Modify `press/press/doctype/site/site.json`

- [ ] **Step 1: Add the field**

Add to the `fields` array (near `is_development_site`) and to `field_order` in the same position:

```json
{
 "fieldname": "is_confidential",
 "fieldtype": "Check",
 "label": "Confidential Site",
 "default": "0",
 "description": "When set, Login As Administrator requires the global admin PIN (Press Settings). Desk/System Manager only can change this."
}
```

- [ ] **Step 2: Sync + migrate**

```bash
scp -q press/press/doctype/site/site.json press-ctrl:/home/frappe/frappe-bench/apps/press/press/press/doctype/site/site.json
ssh press-ctrl "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com migrate"
```
Expected: migrate completes; `is_confidential` column exists.

- [ ] **Step 3: Verify column**

```bash
ssh press-ctrl "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com execute frappe.db.get_table_columns --kwargs \"{'doctype':'Site'}\"" 2>&1 | grep -o is_confidential
```
Expected: `is_confidential` printed.

- [ ] **Step 4: Commit**

```bash
git add press/press/doctype/site/site.json
git commit -m "feat(site): add is_confidential flag"
```

---

## Task 2: Schema — Press Settings PIN + alert email

**Files:** Modify `press/press/doctype/press_settings/press_settings.json`

- [ ] **Step 1: Add two fields**

Add to `fields` + `field_order` (under the existing `security_tab` section, after `wazuh_server`):

```json
{
 "fieldname": "admin_login_pin",
 "fieldtype": "Password",
 "label": "Confidential Site Admin PIN",
 "description": "Global PIN required to Login As Administrator on sites flagged Confidential."
},
{
 "fieldname": "confidential_alert_email",
 "fieldtype": "Data",
 "options": "Email",
 "label": "Confidential Wrong-PIN Alert Email",
 "default": "eng.elgogary@gmail.com",
 "description": "Recipient for wrong-PIN attempt alerts on confidential sites."
}
```

- [ ] **Step 2: Sync + migrate**

```bash
scp -q press/press/doctype/press_settings/press_settings.json press-ctrl:/home/frappe/frappe-bench/apps/press/press/press/doctype/press_settings/press_settings.json
ssh press-ctrl "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com migrate"
```
Expected: migrate completes.

- [ ] **Step 3: Verify**

```bash
ssh press-ctrl "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com execute frappe.db.get_single_value --kwargs \"{'doctype':'Press Settings','field':'confidential_alert_email'}\""
```
Expected: prints `eng.elgogary@gmail.com` (the default).

- [ ] **Step 4: Commit**

```bash
git add press/press/doctype/press_settings/press_settings.json
git commit -m "feat(press-settings): admin_login_pin + confidential_alert_email"
```

---

## Task 3: Backend PIN guard (TDD) — the security core

**Files:** Modify `press/press/doctype/site/site.py`; Test `press/press/doctype/site/test_site.py`

- [ ] **Step 1: Write failing tests**

Append to `test_site.py` (adapt the site-creation helper to match the file's existing `create_test_site` / fixture pattern — read the top of the file first):

```python
class TestConfidentialPinGate(FrappeTestCase):
    def setUp(self):
        frappe.db.set_single_value("Press Settings", "admin_login_pin", "1234")
        frappe.db.set_single_value("Press Settings", "confidential_alert_email", "eng.elgogary@gmail.com")
        self.site = create_test_site()  # use the module's existing helper
        frappe.cache().delete_value(f"confidential_pin_fail:{frappe.session.user}:{self.site.name}")

    def test_non_confidential_ignores_pin(self):
        self.site.is_confidential = 0
        # should not raise on missing pin
        with patch.object(self.site, "login", return_value="SID"):
            url = self.site.login_as_admin(reason="t")
        self.assertIn("sid=SID", url)

    def test_confidential_correct_pin_passes(self):
        self.site.is_confidential = 1
        with patch.object(self.site, "login", return_value="SID"):
            url = self.site.login_as_admin(reason="t", pin="1234")
        self.assertIn("sid=SID", url)

    def test_confidential_wrong_pin_throws_and_alerts(self):
        self.site.is_confidential = 1
        with patch("press.press.doctype.site.site.frappe.sendmail") as mail, \
             patch.object(self.site, "login", return_value="SID"):
            with self.assertRaises(frappe.ValidationError):
                self.site.login_as_admin(reason="t", pin="0000")
        mail.assert_called_once()  # first wrong attempt alerts

    def test_no_pin_configured_blocks(self):
        frappe.db.set_single_value("Press Settings", "admin_login_pin", "")
        self.site.is_confidential = 1
        with self.assertRaises(frappe.ValidationError):
            self.site.login_as_admin(reason="t", pin="anything")

    def test_lockout_after_three(self):
        self.site.is_confidential = 1
        with patch("press.press.doctype.site.site.frappe.sendmail"), \
             patch.object(self.site, "login", return_value="SID"):
            for _ in range(3):
                with self.assertRaises(frappe.ValidationError):
                    self.site.login_as_admin(reason="t", pin="0000")
            # 4th is the lockout message
            with self.assertRaises(frappe.ValidationError) as ctx:
                self.site.login_as_admin(reason="t", pin="1234")  # even correct pin blocked
            self.assertIn("Too many", str(ctx.exception))
```

- [ ] **Step 2: Run to confirm failure**

```bash
scp -q press/press/doctype/site/test_site.py press-ctrl:/home/frappe/frappe-bench/apps/press/press/press/doctype/site/test_site.py
ssh press-ctrl "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com run-tests --module press.press.doctype.site.test_site --test TestConfidentialPinGate"
```
Expected: FAIL (pin param not handled / no guard).

- [ ] **Step 3: Implement the guard + alert helper**

In `site.py`, replace `login_as_admin` (line ~1821) with:

```python
	def login_as_admin(self, reason=None, pin=None):
		if self.is_confidential:
			self._check_confidential_pin(pin, reason)
		sid = self.login(reason=reason)
		return f"https://{self.host_name or self.name}/app?sid={sid}"

	def _check_confidential_pin(self, pin, reason):
		configured = frappe.get_doc("Press Settings").get_password(
			"admin_login_pin", raise_exception=False
		)
		if not configured:
			frappe.throw(
				"This site is confidential but no admin PIN is configured. "
				"Set it in Press Settings."
			)
		key = f"confidential_pin_fail:{frappe.session.user}:{self.name}"
		fails = int(frappe.cache().get_value(key) or 0)
		if fails >= 3:
			frappe.throw("Too many incorrect PIN attempts. Try again in a few minutes.")
		if (pin or "") != configured:
			fails += 1
			frappe.cache().set_value(key, fails, expires_in_sec=300)
			log_site_activity(self.name, "Login as Administrator - WRONG PIN", reason=reason)
			if fails == 1 or fails >= 3:
				self._send_wrong_pin_alert(reason, fails)
			frappe.throw("Incorrect PIN")
		frappe.cache().delete_value(key)

	def _send_wrong_pin_alert(self, reason, fails):
		try:
			recipient = frappe.db.get_single_value("Press Settings", "confidential_alert_email")
			if not recipient:
				return
			kind = "LOCKOUT" if fails >= 3 else "first wrong attempt"
			frappe.sendmail(
				recipients=[recipient],
				subject=f"[Press] Wrong admin PIN on confidential site {self.name} ({kind})",
				message=(
					f"User: {frappe.session.user}<br>"
					f"Site: {self.name}<br>"
					f"Failed attempts: {fails}<br>"
					f"Reason given: {frappe.utils.escape_html(reason or '(none)')}<br>"
					f"Time: {frappe.utils.now()}"
				),
				now=True,
			)
		except Exception:
			frappe.log_error("Confidential PIN alert email failed", frappe.get_traceback())
```

Confirm `log_site_activity` is imported at the top of site.py (it is used elsewhere; if not, add `from press.press.doctype.site_activity.site_activity import log_site_activity`).

- [ ] **Step 4: Run to confirm pass**

```bash
scp -q press/press/doctype/site/site.py press-ctrl:/home/frappe/frappe-bench/apps/press/press/press/doctype/site/site.py
ssh press-ctrl "cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com run-tests --module press.press.doctype.site.test_site --test TestConfidentialPinGate"
```
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add press/press/doctype/site/site.py press/press/doctype/site/test_site.py
git commit -m "feat(site): backend PIN gate on login_as_admin for confidential sites"
```

---

## Task 4: validate gate — only desk users toggle is_confidential

**Files:** Modify `press/press/doctype/site/site.py`; Test append.

- [ ] **Step 1: Write failing test**

```python
    def test_non_desk_user_cannot_set_confidential(self):
        self.site.is_confidential = 0
        self.site.save()
        self.site.is_confidential = 1
        with patch("press.press.doctype.site.site.frappe.session", frappe._dict(user="team@x.com")), \
             patch("press.press.doctype.site.site.is_desk_user", return_value=False):
            with self.assertRaises(frappe.ValidationError):
                self.site.save()
```

(Adjust the desk-user check name to whatever the codebase uses — search `is_desk_user` / `has_role("System Manager")` in press first.)

- [ ] **Step 2: Confirm fail**, then **Step 3: Implement** in `Site.validate` (or `before_save`): if `self.has_value_changed("is_confidential")` and the current user is not a desk/System Manager user, `frappe.throw("Only platform admins can change the Confidential flag.")`. Use the same desk-user predicate the codebase already uses for dev-mode gating.

- [ ] **Step 4: Run pass. Step 5: Commit** `feat(site): restrict is_confidential toggle to desk users`.

---

## Task 5: Dashboard prototype (prototype-first gate)

**Files:** Create `docs/prototypes/confidential-pin-dialog.html`

- [ ] **Step 1:** Build a standalone HTML mock showing the "Login as Administrator" dialog in two states: (a) normal site — Reason field only; (b) confidential site — Reason + a masked "Admin PIN" field, plus the error state "Incorrect PIN". Use neutral styling (no AI-slop, no emoji). 
- [ ] **Step 2:** Tell the user the file path and ask approval before the Vue port. STOP here for user approval.

---

## Task 6: Vue dialog PIN field + Visit Site cache-buster

**Files:** Modify `dashboard/src/objects/site.js`

- [ ] **Step 1:** In the "Login As Administrator" `confirmDialog` (lines ~1851-1886), build the `fields` array so it includes the existing Reason logic AND, when `site.doc.is_confidential`, a PIN field:

```js
fields: [
  ...(site.doc.is_confidential
    ? [{ label: 'Admin PIN', type: 'password', fieldname: 'pin' }]
    : []),
  ...($team.name !== site.doc.team || $team.doc.is_desk_user
    ? [{ label: 'Reason', type: 'textarea', fieldname: 'reason' }]
    : []),
],
```

- [ ] **Step 2:** In `onSuccess`, pass the pin:

```js
return site.loginAsAdmin
  .submit({ reason: values.reason, pin: values.pin })
  .then((result) => { window.open(result, '_blank'); hide(); });
```

- [ ] **Step 3:** Visit Site cache-buster — find the Visit Site handler (the `external-link` primary button / SiteOverview) and change the opened URL to:

```js
const u = `https://${site.doc.host_name || site.doc.name}/?_nocache=${Date.now()}`;
window.open(u, '_blank');
```

- [ ] **Step 4:** Confidential toggle UI — add a switch in the site settings/overview area, `condition: () => $team.doc?.is_desk_user`, bound to `site.doc.is_confidential`, calling `site.setValue.submit({ is_confidential: ... })` (or the dashboard resource the codebase uses for inline field updates). Reload on success.

- [ ] **Step 5:** Build the dashboard to check for JS errors:

```bash
scp -q dashboard/src/objects/site.js press-ctrl:/home/frappe/frappe-bench/apps/press/dashboard/src/objects/site.js
ssh press-ctrl "cd /home/frappe/frappe-bench/apps/press/dashboard && yarn build 2>&1 | tail -15"
```
Expected: build succeeds, no errors referencing site.js.

- [ ] **Step 6: Commit** `feat(dashboard): PIN field for confidential login + no-cache Visit Site + confidential toggle`.

---

## Task 7: Live smoke + PR

- [ ] **Step 1:** On press-ctrl, mark one test site confidential, set a PIN in Press Settings, and via `bench execute` call `Site.login_as_admin` with wrong then right PIN; confirm throw + email attempt (check Email Queue) + success.
- [ ] **Step 2:** Dual-layer check (per quality-gate Phase 3): also hit the dashboard API path (`/api/method/press.api...` or the dashboard resource) for `login_as_admin` with a wrong pin from a non-desk team user to prove the BACKEND rejects (not just the UI).
- [ ] **Step 3:** Push branch, open PR into `cloudflare-dns`. Do NOT merge/deploy (user merges).

```bash
git push -u origin feat/confidential-pin-gate
gh pr create --base cloudflare-dns --head feat/confidential-pin-gate --title "feat: confidential-site PIN gate on Login As Administrator + no-cache Visit Site" --body "<summary + spec link>"
```

---

## Self-Review

- **Spec coverage:** is_confidential (T1), PIN+email fields (T2), backend guard + rate-limit + alert 1st+lockout (T3), desk-only toggle (T4), prototype (T5), Vue PIN field + cache-buster + toggle (T6), live dual-layer verify + PR (T7). [done]
- **Backend enforcement (the load-bearing risk):** PIN check is in `login_as_admin._check_confidential_pin`, tested by calling the method directly with wrong/empty pin (T3) and via the API path (T7 Step 2). [done]
- **auth_hook:** no new whitelisted method (reused `login_as_admin`), so no allowlist edit. [done]
- **Placeholders:** `demo.mvpstorm.com` is intentionally a lookup the executor must resolve on press-ctrl (Press dashboard site name) — flagged in Conventions, not a content gap. The desk-user predicate name (T4) must be confirmed against the codebase — flagged inline.
- **Branch:** feat/confidential-pin-gate off cloudflare-dns; PR not merged by the agent.
