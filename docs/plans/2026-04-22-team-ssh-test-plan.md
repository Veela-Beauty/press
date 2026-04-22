# Test Plan — Team SSH Access Management

**Build:** commits `6f8b039edf`, `9e45fdce22`, `97fd1b5c6c`, `b80e223fb6`, `afe3171e04` on `autodeploypanel.mvpstorm.com`
**Test date:** _______ **Tester:** _______

## Roles needed
- **Owner** (team owner email) — can see Team SSH tab, controls all keys
- **Member A** — a team member, has 1–2 SSH keys
- **Member B** — another team member, no SSH keys yet

---

## Part 1 — Member self-service (Developer tab)

### T1. Member adds SSH key
**As:** Member A
**Steps:**
1. Login → Settings → **Developer**
2. Click **+ Add SSH Key** → paste `ssh-ed25519 AAAA... laptop`
3. Save

- [ ] Key appears in list with fingerprint and "Default" pill (if first)
- [ ] No errors in console

### T2. Member adds a second key
**As:** Member A
**Steps:** Add another key (e.g., home desktop)

- [ ] Second key appears. Only the first is "Default"

---

## Part 2 — Owner admin view (Team SSH tab)

### T3. Owner sees Team SSH tab
**As:** Owner
**Steps:** Settings

- [ ] Sees 5 tabs: Profile, Team, Roles, Developer, **Team SSH**
- [ ] Click Team SSH → table lists every member's keys

### T4. Owner labels a key
**Steps:**
1. Team SSH tab → find Member A's second key
2. Click label input → type "Home Desktop" → press Enter or blur

- [ ] Toast "Label updated"
- [ ] Refresh page → label persists

### T5. Owner disables Member A's key
**Steps:** Next to "Home Desktop" → click **Disable**

- [ ] Status pill flips from green "Active" → red "Disabled"
- [ ] Button changes to **Enable**
- [ ] Toast confirms
- [ ] DB check (optional): `disabled_by` = owner email, `disabled_on` = now

### T6. Owner re-enables
**Steps:** Click **Enable** on the same row

- [ ] Status → "Active", audit fields cleared

### T7. Owner removes a key
**Steps:** Click **Remove** → confirm dialog

- [ ] Row disappears from list
- [ ] Member A in Developer tab also no longer sees it

### T8. Non-owner (Member A) cannot see Team SSH tab
**As:** Member A
**Steps:** Settings

- [ ] Team SSH tab is **hidden**
- [ ] Direct URL `/dashboard/settings/team-ssh` → shows no data / forbidden (API returns PermissionError)

---

## Part 3 — Certificate generation (bench SSH)

### T9. Single-key member generates cert
**As:** Member B (add 1 key first)
**Steps:**
1. Benches → open a bench → Options → **SSH Access**
2. Dialog shows "Using your only registered key: `<label>`"
3. Click **Generate SSH Certificate**

- [ ] 2-step Cert + SSH commands appear
- [ ] Step 2 command format: `ssh -A bench-name@press-f1.sandbox.mvpstorm.com -p 2222`

### T10. Multi-key member picks key
**As:** Member A (2 keys)
**Steps:**
1. Bench → SSH Access
2. Dialog shows "Certificate issued for key: **Default**" if cert exists
3. Click **Reissue for a different key**
4. See radio list with both keys (labels shown, Default pill, Disabled pill if any)
5. Select second key → **Generate SSH Certificate**

- [ ] Cert dialog reappears with Step 1/2 and "Certificate issued for key: Home Desktop"
- [ ] No "A valid certificate already exists" error

### T11. Disabled key is blocked from cert dialog
**Setup:** Owner disables Member A's "Home Desktop" key
**As:** Member A
**Steps:**
1. Bench → SSH Access → Reissue for a different key
2. Inspect "Home Desktop" row

- [ ] Row has red background + **Disabled** pill
- [ ] Radio is `disabled` (cannot be clicked)
- [ ] If selected (e.g., via keyboard), Generate button reads "Selected key is disabled by admin" and is greyed out

### T12. Backend also blocks disabled key
**Setup:** Member A's "Home Desktop" is disabled
**Test via browser console:**
```js
await fetch('/api/method/press.api.client.run_doc_method', {
  method: 'POST',
  headers: {'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': window.csrf_token},
  body: JSON.stringify({dt: 'Release Group', dn: 'bench-0011', method: 'generate_certificate', args: {ssh_key_name: '<disabled_key_name>'}})
}).then(r => r.json())
```

- [ ] Response contains: `"This SSH key has been disabled by your team admin..."`

---

## Part 4 — Dev tab integration

### T13. Dev tab shows Setup SSH Key when no key
**As:** a member with no SSH keys
**Steps:** Site → Dev tab

- [ ] **Setup SSH Key** yellow button visible
- [ ] Click → navigates to `/dashboard/settings/developer`

### T14. Dev tab shows Local VS Code when key exists
**As:** member with ≥1 SSH key
**Steps:** Site → Dev tab

- [ ] **Local VS Code** button with `SSH Remote → <ip>:<port>`
- [ ] Click → triggers `vscode://vscode-remote/ssh-remote+...` (VS Code opens locally if installed)

### T15. Launch Code Server (Web VS Code)
**Steps:** Site → Dev tab → **Launch Code Server**

- [ ] Toast "Code Server setup started"
- [ ] Status changes to "Pending" then "Running" within ~1–2 min
- [ ] Button becomes green "Open Code Server" linking to the running instance

---

## Part 5 — Real SSH + git (verifies end-to-end)

### T16. SSH into a bench with valid cert + git pull via agent forwarding
**As:** Member A with active key + cert, laptop has GitHub SSH key in agent
**Steps (local machine):**
1. `ssh-add ~/.ssh/id_ed25519` (load GitHub key)
2. `ssh-add -L` — verify key is listed
3. Copy Step 1 command from SSH Access dialog → run in terminal
4. Copy Step 2 command (includes `-A`) → run

- [ ] Lands in `frappe@<bench-container>` shell
- [ ] `ssh -T git@github.com` → `Hi <github-handle>! You've successfully authenticated, but GitHub does not provide shell access.`
- [ ] `cd ~/frappe-bench/apps/<app> && git remote set-url origin git@github.com:<org>/<repo>.git`
- [ ] `git fetch origin` → succeeds, no "Permission denied"
- [ ] `git pull` → succeeds

### T17. Disabled key + 6h cert expiry
**Setup:** Member A has cert, then owner disables the key
**Steps:** Try to SSH again (use the still-valid cert file)

- [ ] Either: SSH works for the remainder of the 6h cert (existing cert is valid — acceptable behavior), OR admin force-expires via desk
- [ ] Next Generate Cert attempt is blocked at cert creation with admin-contact message

---

## Sign-off
- [ ] All tests pass
- [ ] Owner signs: _______
- [ ] Team lead signs: _______

**Report bugs as:** `#paperclip-bugs` or open issue with test ID (e.g., "T10 fails — cert issued for wrong key") + console error if any.
