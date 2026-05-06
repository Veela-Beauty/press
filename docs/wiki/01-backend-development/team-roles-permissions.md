# Team Roles & Permissions Guide

How to give a team member the right access to the dashboard, deploys, sites,
servers, and billing — and how to debug "Not permitted" errors.

> **TL;DR** — Press has **two** permission systems that often get confused.
> If a member gets "Not permitted" or "is not whitelisted" *after* you set
> their role, you almost certainly need to tick flags on the **Press Role**
> doctype, not just the `Team Member.press_role` field. Skip to
> [Recovery: member is locked out](#recovery-member-is-locked-out) for the fix.

---

## The two permission systems

| System | Set via | What it gates |
|---|---|---|
| **`Team Member.press_role`** (string field: Owner / Platform Admin / DevOps Admin / DevOps User / Developer / Implementor / Viewer) | Team page → member row → role dropdown | Feature visibility from `DEFAULT_FEATURES` (Code Server, Dev Tools, SSH Access, etc.) — see `press/api/admin_panel.py` |
| **`Press Role` doctype** (18 boolean flags + per-resource grants) | Manage Team → Roles → create/edit role | Per-doctype access (Bench, Site, Server, Deploy, Billing, Webhook config, etc.) — enforced by `team_guard` and `role_guard` |

Granting "everything" on the **first** doesn't grant access on the **second**.
A new Press Role starts with **every flag = 0** (total lockout), so any
member assigned to it can't see or do anything in the dashboard until you
tick at least one flag.

---

## Press Role flag reference

Each row of `tabPress Role` has 18 boolean flags. Tick each one based on what
the member needs to do.

### Resource visibility (the "what they can SEE" flags)

| Flag | What it controls |
|---|---|
| `all_release_groups` | See **all benches / release groups** in the team. Without this, member only sees release groups explicitly granted via `Press Role Resource`. |
| `all_sites` | See **all sites** in the team. Without this, only sites explicitly granted. |
| `all_servers` | See **all servers** in the team. Without this, only servers explicitly granted. |
| `allow_dashboard` | **Required to log into the dashboard at all.** Without this, member is bounced back to login. |

### Action flags (the "what they can DO" flags)

| Flag | What it unlocks |
|---|---|
| `allow_bench_creation` | Create new release groups, **deploy** new builds, push apps to Github via Dev tab. |
| `allow_site_creation` | Create new sites on existing benches. |
| `allow_server_creation` | **Provision new servers** (App Server, Database Server, Proxy). Sensitive — incurs cost. |
| `allow_apps` | Manage App Sources, install/update apps on benches, view App Releases. |
| `allow_billing` | View invoices, payment methods, change plan, top up balance, view usage costs. Sensitive — adds member to `Press Admin` Frappe role. |
| `allow_webhook_configuration` | Create / edit Press Webhooks (event-driven integrations). |

### Admin / management flags

| Flag | What it unlocks |
|---|---|
| `admin_access` | **Full bypass** — equivalent to ticking everything else. Adds member to `Press Admin` Frappe role. Use sparingly. |
| `allow_invite_team_members` | Send team invitations. |
| `allow_manage_team_members` | Change other members' roles, remove members. |
| `allow_manage_team_roles` | Create / edit / delete Press Role rows themselves. **Be careful** — a member with this can grant themselves `admin_access`. |

### Niche / partner-side flags

These are mostly relevant on the saas/partner side of Press; on a self-hosted
control instance you can leave them off unless you actively use the feature.

| Flag | What it unlocks |
|---|---|
| `allow_partner` | Partner dashboard, partner-only routes. |
| `allow_customer` | Customer-facing CRM features. |
| `allow_leads` | Sales lead management. |
| `allow_contribution` | App contribution / marketplace flow. |

---

## Preset recipes — copy-paste a role

When creating a Press Role, tick the flags that match the role's intent.
Below are battle-tested presets. As of cloudflare-dns commit
`6bc...session-cap-followup`, **new Press Roles default to the Developer
preset** so a half-configured role isn't a brick.

### Developer (default for new roles)

For a teammate who builds, deploys, and tests apps but shouldn't touch
billing or provision servers.

```
✅ allow_dashboard
✅ all_release_groups
✅ all_sites
✅ all_servers
✅ allow_apps
✅ allow_bench_creation
✅ allow_site_creation
❌ allow_server_creation        (ops-team only — costs money)
❌ allow_billing                 (ops-team only)
❌ admin_access                  (ops-team only)
❌ allow_invite_team_members     (admin-only)
❌ allow_manage_team_members     (admin-only)
❌ allow_manage_team_roles       (admin-only)
❌ allow_webhook_configuration   (security)
```

### Site Admin (no deploy)

For a teammate who manages sites — installs apps, restores backups, scales
plans — but doesn't deploy code.

```
✅ allow_dashboard
✅ all_sites
✅ all_release_groups   (read-only access — needed to view bench details)
✅ allow_apps
✅ allow_site_creation
❌ allow_bench_creation
❌ allow_server_creation
❌ allow_billing
```

### Ops Admin

For a teammate who provisions infra and manages the bill.

```
✅ allow_dashboard
✅ all_release_groups, all_sites, all_servers
✅ allow_bench_creation, allow_site_creation, allow_server_creation
✅ allow_apps
✅ allow_billing
✅ allow_webhook_configuration
✅ allow_invite_team_members
✅ allow_manage_team_members
❌ allow_manage_team_roles   (only the team owner manages roles)
```

### Read-only Viewer

For an auditor or stakeholder who needs to see status but never change
anything.

```
✅ allow_dashboard
✅ all_release_groups, all_sites, all_servers
❌ everything else
```

### Full Admin

The team owner equivalent — only for a co-founder.

```
✅ admin_access   (single tick = full bypass; no need to tick others)
```

---

## Recovery: member is locked out

If a member reports any of these — they're hitting a Press Role denial:

- "Not permitted" / "is not whitelisted" toast on a deploy/site/server page
- Dashboard shows empty bench / site / server lists when there should be data
- Bounced to `/dashboard/login?reason=INVALID_TEAM` after login
- Browser auto-logs them out repeatedly

### 1. Find their Press Role

```sql
SELECT pr.name, pr.title, pr.team
FROM `tabPress Role` pr
JOIN `tabPress Role User` pru ON pru.parent = pr.name
WHERE pru.user = 'member@example.com';
```

If the query returns nothing, the member has no Press Role assigned. Either
they're the team **owner** (gets full access by default) or they need a role
created and assigned.

### 2. Check what flags are set

```sql
SELECT * FROM `tabPress Role` WHERE name = '<role-id-from-step-1>'\G
```

Look at the 18 flag columns (`admin_access`, `allow_*`, `all_*`). Anything at
0 that should be 1 explains the denial.

### 3. Fix the flags

Either edit the role from the dashboard (Manage Team → Roles → click the
role), or run a targeted SQL update:

```sql
UPDATE `tabPress Role`
SET allow_dashboard = 1,
    all_release_groups = 1,
    all_sites = 1,
    allow_bench_creation = 1,
    modified = NOW()
WHERE name = '<role-id>';
```

Then `bench --site <site> clear-cache` and tell the member to refresh their
browser tab — **no re-login required**.

### 4. If the error said "is not whitelisted" — also check session cap

That specific wording can also mean the member's `simultaneous_sessions` cap
is too low and Frappe is evicting their session when they open new tabs.
See `frappe-press-lessons.md` lesson #127 — fix is to bump
`User.simultaneous_sessions` (default cap is 10 since cloudflare-dns commit
`ce99c03c2d`, but pre-existing users invited before that may still be at 2).

---

## Defaults applied automatically (going forward)

Two safety nets ship with cloudflare-dns to prevent future lockouts:

1. **`before_insert` on Press Role** — every newly created Press Role
   pre-ticks the Developer preset flags above, so a forgetful admin doesn't
   accidentally save a 0-flag role and lock its members out. Admins can still
   untick anything before saving.

2. **`validate` zero-flag warning** — if a Press Role is saved with users
   assigned **and** every flag at 0, an orange warning appears: *"Empty
   role — members will be locked out."* Not a hard block (placeholder roles
   are still allowed), just an audible signal.

Both live in `press/press/doctype/press_role/press_role.py`. To change the
default preset, edit `DEVELOPER_PRESET_FLAGS` — single source of truth.

---

## Cheat sheet — common asks

| Member needs to… | Tick these flags |
|---|---|
| Just view the dashboard | `allow_dashboard` + `all_release_groups` + `all_sites` |
| **Deploy** a new build | + `allow_bench_creation` |
| Push code via Dev tab / Code Server | + `allow_apps` + `allow_bench_creation` |
| Create a new site | + `allow_site_creation` |
| Manage billing | + `allow_billing` |
| Provision a new server | + `allow_server_creation` |
| Invite teammates | + `allow_invite_team_members` |
| Have full access | tick `admin_access` alone — covers everything |

---

## Related

- `press/press/doctype/press_role/press_role.py` — the controller + flag definitions
- `press/api/admin_panel.py` `DEFAULT_FEATURES` — the *other* role system (`Team Member.press_role` → feature gates)
- `press/guards/role_guard/` — request-time enforcement of Press Role flags
- `press/utils/__init__.py` `ensure_team_access` — base team-membership check fired before any role flag
- `frappe-press-lessons.md` lesson #127 — `simultaneous_sessions` cap that masquerades as a permission error

---

## Self-service error messages (new in cloudflare-dns)

When a member hits a permission denial, the dashboard now shows the **specific
flag** they are missing instead of generic "Not permitted." The toast looks
like:

> **Permission denied** — You don't have access to this resource. Ask your
> team admin to enable `all_release_groups` on your Press Role (or grant access
> to this specific Bench via Manage Team -> Roles -> Resources).

That gives the member exactly the words to send to their admin: *"please tick
`all_release_groups` on my role."* No code-spelunking, no Slack guessing.

The mapping lives in `press/api/client.py` `_DOCTYPE_TO_FLAG` — to add a new
doctype, drop a row in that dict and the hint comes through automatically.
The 6 `raise_not_permitted()` call sites in client.py already pass `doctype`
context. Internal-only failures (e.g. an unwhitelisted method on
`run_doc_method`) intentionally still raise the generic message — those are
developer config errors, not user-actionable role gaps.

---

## Gotcha: `get_bench_update()` double team-check (fixed 2026-05-06)

The `@protected("Release Group")` decorator on `deploy_and_update()` correctly exempts System Users from team checks. However, `get_bench_update()` (called internally by `deploy_and_update`) had a **second** team check at `bench_update.py:175` that rejected ALL users including System Users:

```python
# OLD — blocked everyone
if rg_team != current_team:
    frappe.throw("Bench can only be deployed by the bench owner", exc=frappe.PermissionError)

# NEW — System Users exempt (matches @protected)
if rg_team != current_team and not is_system_user:
    frappe.throw("Bench can only be deployed by the bench owner", exc=frappe.PermissionError)
```

**Root cause pattern**: When an API method decorated with `@protected` calls a second function that does its own team check, that second function MUST mirror the same exemptions as `@protected`. Otherwise the outer decorators System User bypass is silently defeated.

## Gotcha: `get_bench_update()` double team-check (fixed 2026-05-06)

The `@protected("Release Group")` decorator on `deploy_and_update()` correctly exempts System Users from team checks. However, `get_bench_update()` (called internally by `deploy_and_update`) had a **second** team check at `bench_update.py:175` that rejected ALL users including System Users:

```python
# OLD - blocked everyone
if rg_team != current_team:
    frappe.throw("Bench can only be deployed by the bench owner", exc=frappe.PermissionError)

# NEW - System Users exempt (matches @protected)
if rg_team != current_team and not is_system_user:
    frappe.throw("Bench can only be deployed by the bench owner", exc=frappe.PermissionError)
```

**Root cause pattern**: When an API method decorated with `@protected` calls a second function that does its own team check, that second function MUST mirror the same exemptions as `@protected`. Otherwise the outer decorator's System User bypass is silently defeated.

**Audit checklist** for any future Press API changes:
1. Does the API have `@protected("Doctype")`?
2. Does it call any internal function that does its own team/ownership check?
3. If yes - does that internal check exempt System Users?
