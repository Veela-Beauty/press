# Admin Panel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. After each task, run superpowers:test-driven-development for TDD and code-review:code-review for deep review. After all tasks, run clean-code for final review.

**Goal:** Build a `/dashboard/admin` page that gives platform administrators full control over teams, quotas, feature access, sites, benches, members, and infrastructure costs — all from a single UI, backed by existing Press APIs + new quota enforcement.

**Architecture:** Custom Fields on Team DocType for quotas/features (avoids modifying upstream). New sibling Python API module `press/api/admin_panel.py` for admin-only endpoints. Single Vue page `AdminPanel.vue` with expandable team rows. Quota enforcement via doc_events hooks on Site and Release Group creation. Feature registry stored as JSON Custom Field on Team — dynamic, no schema changes when adding new features.

**Tech Stack:** Frappe Custom Fields (Python), Vue 3 (Press dashboard SPA), MariaDB, Hetzner API (cost data)

**Prototype:** `docs/prototypes/admin_panel_prototype.html` — approved reference design

**Codegraph reference:** 328 nodes, 1301 links. Team (161 lines, 54 links), Bench (457 lines, 40 links), API (1438 lines, central hub). All work uses sibling files — zero modifications to top-5 modules.

---

## Task 1: Custom Fields — Quotas on Team DocType

**Files:**
- Create: `press/press/doctype/team/team_admin_setup.py`

**Step 1: Write the failing test**

```python
# On press-ctrl bench console:
import frappe
meta = frappe.get_meta('Team')
assert meta.get_field('max_sites') is not None, "FAIL: max_sites missing"
```

**Step 2: Run test to verify it fails**

Run on press-ctrl: `bench --site demo.mvpstorm.com console` → paste test
Expected: AssertionError "FAIL: max_sites missing"

**Step 3: Write minimal implementation**

File: `press/press/doctype/team/team_admin_setup.py`
```python
"""Add admin panel custom fields to Team DocType."""
import frappe

TEAM_QUOTA_FIELDS = [
    {"fieldname": "admin_section", "label": "Admin Controls", "fieldtype": "Section Break",
     "insert_after": "billing_tab", "collapsible": 1},
    {"fieldname": "max_sites", "label": "Max Sites", "fieldtype": "Int",
     "default": "0", "description": "0 = unlimited", "insert_after": "admin_section"},
    {"fieldname": "max_benches", "label": "Max Benches", "fieldtype": "Int",
     "default": "0", "description": "0 = unlimited", "insert_after": "max_sites"},
    {"fieldname": "max_disk_gb", "label": "Max Disk (GB)", "fieldtype": "Float",
     "default": "0", "description": "0 = unlimited", "insert_after": "max_benches"},
    {"fieldname": "column_break_admin", "fieldtype": "Column Break",
     "insert_after": "max_disk_gb"},
    {"fieldname": "allowed_site_types", "label": "Allowed Site Types", "fieldtype": "Small Text",
     "default": "Production\nStaging\nDev\nDemo",
     "description": "One type per line. Leave empty for all types.",
     "insert_after": "column_break_admin"},
    {"fieldname": "enabled_features", "label": "Enabled Features", "fieldtype": "JSON",
     "default": "{}",
     "description": "JSON map of feature_id: true/false",
     "insert_after": "allowed_site_types", "hidden": 1},
]

def setup_admin_fields():
    """Idempotent: add custom fields to Team if missing."""
    for field_def in TEAM_QUOTA_FIELDS:
        cf_name = f"Team-{field_def['fieldname']}"
        if frappe.db.exists("Custom Field", cf_name):
            continue
        doc = {**field_def, "doctype": "Custom Field", "dt": "Team"}
        frappe.get_doc(doc).insert(ignore_permissions=True)
    frappe.db.commit()
```

**Step 4: Run test to verify it passes**

```bash
# On press-ctrl:
bench --site demo.mvpstorm.com console
>>> from press.press.doctype.team.team_admin_setup import setup_admin_fields
>>> setup_admin_fields()
>>> meta = frappe.get_meta('Team')
>>> assert meta.get_field('max_sites') is not None
>>> assert meta.get_field('allowed_site_types') is not None
>>> assert meta.get_field('enabled_features') is not None
>>> print('ALL PASS')
```

**Step 5: Commit**

```bash
git add press/press/doctype/team/team_admin_setup.py
git commit -m "feat(admin): add quota + feature custom fields to Team DocType"
```

**Step 6: Code review** — Run `code-review:code-review` on `team_admin_setup.py`

---

## Task 2: Quota Enforcement — Site Creation

**Files:**
- Create: `press/press/doctype/team/team_quota_enforcement.py`
- Modify: `press/hooks.py:176` (add validate hook)

**Step 1: Write the failing test**

```python
# On press-ctrl console:
import frappe
from press.press.doctype.team.team_quota_enforcement import check_site_quota

# Set quota: max 2 sites
frappe.db.set_value('Team', 'sqkn1globp', 'max_sites', 2)
frappe.db.commit()

# Team has 11 active sites — should fail
mock_site = frappe._dict(team='sqkn1globp', site_type='Production')
try:
    check_site_quota(mock_site)
    print('FAIL — should have thrown')
except frappe.ValidationError as e:
    print('PASS —', str(e)[:80])
```

**Step 2: Run test — expected: ImportError (function doesn't exist yet)**

**Step 3: Write minimal implementation**

File: `press/press/doctype/team/team_quota_enforcement.py`
```python
"""Quota enforcement for site and bench creation."""
import frappe


def check_site_quota(doc, method=None):
    """Validate site creation against team quotas. Called via doc_events."""
    if frappe.session.user == "Administrator":
        return
    if not doc.team:
        return

    team = doc.team

    # 1. Check max_sites quota
    max_sites = frappe.db.get_value("Team", team, "max_sites") or 0
    if max_sites > 0:
        current = frappe.db.count("Site", {"team": team, "status": ("not in", ("Archived",))})
        if current >= max_sites:
            frappe.throw(
                f"Site limit reached: {current}/{max_sites} sites. Contact your administrator.",
                frappe.ValidationError,
            )

    # 2. Check allowed site types
    allowed_raw = frappe.db.get_value("Team", team, "allowed_site_types") or ""
    if allowed_raw.strip():
        allowed = [t.strip() for t in allowed_raw.strip().split("\n") if t.strip()]
        site_type = getattr(doc, "site_type", "Production") or "Production"
        if allowed and site_type not in allowed:
            frappe.throw(
                f"Your team is not allowed to create {site_type} sites. "
                f"Allowed types: {', '.join(allowed)}.",
                frappe.ValidationError,
            )


def check_bench_quota(doc, method=None):
    """Validate bench/release group creation against team quota."""
    if frappe.session.user == "Administrator":
        return
    team = doc.team
    if not team:
        return

    max_benches = frappe.db.get_value("Team", team, "max_benches") or 0
    if max_benches > 0:
        current = frappe.db.count("Release Group", {"team": team, "enabled": 1})
        if current >= max_benches:
            frappe.throw(
                f"Bench limit reached: {current}/{max_benches} benches. Contact your administrator.",
                frappe.ValidationError,
            )
```

**Step 4: Wire into hooks.py**

Add to `doc_events` in `press/hooks.py`:
```python
"Site": {
    "validate": [
        "press.press.doctype.site.site_type_validation.validate_site_type",
        "press.press.doctype.team.team_quota_enforcement.check_site_quota",
    ],
    "before_insert": "press.press.doctype.team.team.validate_site_creation",
    "after_insert": "press.press.doctype.press_role.press_role.create_user_resource",
},
"Release Group": {
    "validate": "press.press.doctype.team.team_quota_enforcement.check_bench_quota",
    "after_insert": "press.press.doctype.press_role.press_role.create_user_resource",
},
```

**Step 5: Run test — expected: PASS**

```python
# Reset quota for real use
frappe.db.set_value('Team', 'sqkn1globp', 'max_sites', 0)
frappe.db.commit()
```

**Step 6: Commit**

```bash
git add press/press/doctype/team/team_quota_enforcement.py press/hooks.py
git commit -m "feat(admin): quota enforcement for sites and benches"
```

**Step 7: Code review** — Run `code-review:code-review` on `team_quota_enforcement.py`

---

## Task 3: Feature Registry — Backend API

**Files:**
- Create: `press/api/admin_panel.py`

**Step 1: Write the failing test**

```python
# Import should fail
from press.api.admin_panel import get_admin_data
```

**Step 2: Run — expected: ImportError**

**Step 3: Write implementation**

File: `press/api/admin_panel.py`
```python
"""Admin Panel API — team management, quotas, features, costs.
All endpoints require System Manager role.
"""
import json
import frappe


DEFAULT_FEATURES = {
    "daman_backup": {"label": "Daman Backup", "icon": "database", "color": "#2490ef"},
    "code_server": {"label": "Code Server", "icon": "code", "color": "#28a745"},
    "dev_tools": {"label": "Dev Tools", "icon": "wrench", "color": "#6f42c1"},
    "database_access": {"label": "Database Access", "icon": "terminal", "color": "#fd7e14"},
    "ssh_access": {"label": "SSH Access", "icon": "key", "color": "#dc3545"},
    "private_benches": {"label": "Private Benches", "icon": "server", "color": "#8d99a6"},
    "servers": {"label": "Servers", "icon": "cloud", "color": "#20c997"},
    "security_portal": {"label": "Security Portal", "icon": "shield", "color": "#6610f2"},
}

# Server costs (Hetzner Cloud pricing, updated manually)
SERVER_COSTS = {
    "press-ctrl.sandbox.mvpstorm.com": {"plan": "CPX51", "cost": 35},
    "press-f1.sandbox.mvpstorm.com": {"plan": "CPX41+disk", "cost": 24},
    "u4-default.sandbox.mvpstorm.com": {"plan": "CX22", "cost": 4},
    "u5-default.sandbox.mvpstorm.com": {"plan": "CX32", "cost": 8},
}


@frappe.whitelist()
def get_feature_registry():
    """Return the list of available features for toggle UI."""
    frappe.only_for("System Manager")
    return DEFAULT_FEATURES


@frappe.whitelist()
def get_admin_data():
    """Return all teams with quotas, usage, members, costs."""
    frappe.only_for("System Manager")

    teams = frappe.get_all("Team", fields=[
        "name", "user", "enabled", "team_title",
        "max_sites", "max_benches", "max_disk_gb",
        "allowed_site_types", "enabled_features",
    ])

    for team in teams:
        t = team.name
        # Usage counts
        team["site_count"] = frappe.db.count("Site", {"team": t, "status": ("not in", ("Archived",))})
        team["bench_count"] = frappe.db.count("Release Group", {"team": t, "enabled": 1})
        team["member_count"] = frappe.db.count("Team Member", {"parent": t})

        # Site counts by type
        type_counts = frappe.db.sql(
            "SELECT IFNULL(site_type, 'Production') as t, COUNT(*) as c "
            "FROM tabSite WHERE team=%s AND status NOT IN ('Archived') GROUP BY site_type",
            t, as_dict=True,
        )
        team["site_type_counts"] = {r.t: r.c for r in type_counts}

        # Parse features JSON
        team["features"] = json.loads(team.get("enabled_features") or "{}")

        # Cost estimate (proportional to sites per server)
        team["cost"] = _calc_team_cost(t)

    # Global stats
    stats = {
        "total_teams": len(teams),
        "total_sites": frappe.db.count("Site", {"status": ("not in", ("Archived",))}),
        "total_benches": frappe.db.count("Release Group", {"enabled": 1}),
        "total_cost": sum(c["cost"] for c in SERVER_COSTS.values()),
    }

    return {"teams": teams, "stats": stats, "server_costs": _get_server_costs()}


@frappe.whitelist()
def update_team_quotas(team, max_sites=None, max_benches=None, max_disk_gb=None,
                       allowed_site_types=None, enabled_features=None):
    """Update quotas and feature flags for a team."""
    frappe.only_for("System Manager")
    updates = {}
    if max_sites is not None:
        updates["max_sites"] = int(max_sites)
    if max_benches is not None:
        updates["max_benches"] = int(max_benches)
    if max_disk_gb is not None:
        updates["max_disk_gb"] = float(max_disk_gb)
    if allowed_site_types is not None:
        updates["allowed_site_types"] = allowed_site_types
    if enabled_features is not None:
        updates["enabled_features"] = (
            enabled_features if isinstance(enabled_features, str)
            else json.dumps(enabled_features)
        )
    for field, value in updates.items():
        frappe.db.set_value("Team", team, field, value)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def toggle_team(team, action):
    """Block or unblock a team."""
    frappe.only_for("System Manager")
    team_doc = frappe.get_doc("Team", team)
    if action == "block":
        team_doc.ban()
    elif action == "unblock":
        team_doc.enabled = 1
        team_doc.save(ignore_permissions=True)
        team_doc.unsuspend_sites()
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def get_team_members(team):
    """Return members of a team with roles."""
    frappe.only_for("System Manager")
    members = frappe.get_all("Team Member", {"parent": team}, ["user"])
    result = []
    for m in members:
        user = frappe.get_value("User", m.user, ["full_name", "last_active", "creation"], as_dict=True)
        result.append({
            "user": m.user,
            "full_name": user.full_name if user else "",
            "joined": user.creation if user else "",
            "last_active": user.last_active if user else "",
        })
    return result


@frappe.whitelist()
def reset_user_password(user, new_password):
    """Reset a user's password."""
    frappe.only_for("System Manager")
    from frappe.utils.password import update_password
    update_password(user, new_password)
    return {"ok": True}


@frappe.whitelist()
def get_team_sites(team):
    """Return all sites for a team."""
    frappe.only_for("System Manager")
    return frappe.get_all("Site", {"team": team, "status": ("not in", ("Archived",))},
                          ["name", "status", "site_type", "group", "bench", "server", "creation"],
                          order_by="creation desc")


@frappe.whitelist()
def get_team_benches(team):
    """Return all benches for a team."""
    frappe.only_for("System Manager")
    benches = frappe.get_all("Release Group", {"team": team, "enabled": 1},
                             ["name", "title", "version", "creation"],
                             order_by="creation desc")
    for b in benches:
        b["site_count"] = frappe.db.count("Site", {"group": b.name, "status": ("not in", ("Archived",))})
        # Find which server(s) this bench deploys to
        servers = frappe.get_all("Bench", {"group": b.name, "status": "Active"},
                                 ["server"], distinct=True, pluck="server")
        b["servers"] = servers
        b["is_dev"] = any(
            frappe.get_value("Bench", {"group": b.name, "server": s, "status": "Active"},
                             "is_development_bench")
            for s in servers
        ) if servers else False
    return benches


@frappe.whitelist()
def create_team_from_admin(email, full_name, max_sites=0, max_benches=0, max_disk_gb=0,
                           allowed_site_types="", enabled_features="{}"):
    """Admin-only: create a new team + user directly."""
    frappe.only_for("System Manager")

    if frappe.db.exists("User", email):
        frappe.throw(f"User {email} already exists.")

    # Create user
    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": full_name.split()[0] if full_name else email.split("@")[0],
        "last_name": " ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else "",
        "user_type": "Website User",
        "send_welcome_email": 0,
    }).insert(ignore_permissions=True)

    # Create team
    team = frappe.get_doc({
        "doctype": "Team",
        "user": email,
        "enabled": 1,
        "max_sites": int(max_sites),
        "max_benches": int(max_benches),
        "max_disk_gb": float(max_disk_gb),
        "allowed_site_types": allowed_site_types,
        "enabled_features": enabled_features,
    })
    team.append("team_members", {"user": email})
    team.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"team": team.name, "user": email}


def _calc_team_cost(team):
    """Calculate proportional infrastructure cost for a team."""
    total = 0
    for server_name, info in SERVER_COSTS.items():
        server_sites = frappe.db.count("Site", {
            "server": server_name, "status": ("not in", ("Archived",)),
        })
        if server_sites == 0:
            continue
        team_sites = frappe.db.count("Site", {
            "team": team, "server": server_name, "status": ("not in", ("Archived",)),
        })
        if team_sites > 0:
            total += round(info["cost"] * team_sites / server_sites, 2)
    return round(total, 2)


def _get_server_costs():
    """Return server cost data with live site counts."""
    result = []
    for server_name, info in SERVER_COSTS.items():
        sites = frappe.db.count("Site", {"server": server_name, "status": ("not in", ("Archived",))})
        teams = len(set(frappe.get_all("Site", {
            "server": server_name, "status": ("not in", ("Archived",)),
        }, pluck="team")))
        server_doc = frappe.db.get_value("Server", server_name,
                                          ["ip", "ram", "vcpus", "disk_size"], as_dict=True) or {}
        result.append({
            "name": server_name,
            "ip": server_doc.get("ip", ""),
            "plan": info["plan"],
            "cost": info["cost"],
            "sites": sites,
            "teams": teams,
            "ram": server_doc.get("ram", 0),
            "vcpus": server_doc.get("vcpus", 0),
            "disk": server_doc.get("disk_size", 0),
        })
    return result
```

**Step 4: Run test — verify import works and get_admin_data returns data**

```python
from press.api.admin_panel import get_admin_data
frappe.set_user('Administrator')
data = get_admin_data()
assert 'teams' in data
assert 'stats' in data
print(f'PASS — {len(data["teams"])} teams, {data["stats"]["total_sites"]} sites')
```

**Step 5: Commit**

```bash
git add press/api/admin_panel.py
git commit -m "feat(admin): admin panel API — teams, quotas, features, costs, members"
```

**Step 6: Code review** — Run `code-review:code-review` on `admin_panel.py`

---

## Task 4: Dashboard — AdminPanel.vue Page

**Files:**
- Create: `dashboard/src/pages/AdminPanel.vue`
- Modify: `dashboard/src/router.js` (add route)

**Step 1: Create AdminPanel.vue**

Build from the approved prototype (`docs/prototypes/admin_panel_prototype.html`). Convert to Vue 3 with:
- `$resources` for API calls (get_admin_data, update_team_quotas, etc.)
- Reactive expandable team rows
- Tab switching per team (Quotas & Features, Members, Sites, Benches)
- Dialogs for Create Team, Reset Password, Transfer Bench
- Server costs table

Key sections:
1. Stats bar (teams, sites, benches, disk, cost)
2. Search + status filter
3. Teams table with expandable rows
4. Per-team tabs: Quotas, Features, Members, Sites, Benches
5. Dialogs: Create Team, Reset Password

**Step 2: Add route in router.js**

```javascript
{
    name: 'Admin Panel',
    path: '/admin',
    component: () => import('./pages/AdminPanel.vue'),
}
```

**Step 3: Add sidebar link** — in the navigation items config, add "Admin" link visible only for `is_desk_user`.

**Step 4: Build and verify**

```bash
bench build --app press
# Navigate to /dashboard/admin — should show the admin panel
```

**Step 5: Commit**

```bash
git add dashboard/src/pages/AdminPanel.vue dashboard/src/router.js
git commit -m "feat(ui): Admin Panel page with teams, quotas, features, costs"
```

**Step 6: Code review** — Run `code-review:code-review` on `AdminPanel.vue`

---

## Task 5: Feature Access Check — Sidebar Integration

**Files:**
- Create: `press/api/feature_access.py`

**Step 1: Write the test**

```python
from press.api.feature_access import has_feature
# Team with daman_backup enabled
frappe.db.set_value('Team', 'sqkn1globp', 'enabled_features', '{"daman_backup": true}')
assert has_feature('sqkn1globp', 'daman_backup') == True
assert has_feature('sqkn1globp', 'ssh_access') == False
print('PASS')
```

**Step 2: Implement**

File: `press/api/feature_access.py`
```python
"""Check if a team has access to a specific feature."""
import json
import frappe


@frappe.whitelist()
def has_feature(team=None, feature_id=""):
    """Check if the current team has a feature enabled."""
    if not team:
        from press.utils import get_current_team
        team = get_current_team()
    features_json = frappe.db.get_value("Team", team, "enabled_features") or "{}"
    features = json.loads(features_json)
    return bool(features.get(feature_id))


@frappe.whitelist()
def get_team_features(team=None):
    """Return all enabled features for a team."""
    if not team:
        from press.utils import get_current_team
        team = get_current_team()
    features_json = frappe.db.get_value("Team", team, "enabled_features") or "{}"
    return json.loads(features_json)
```

**Step 3: Dashboard integration** — The sidebar and feature pages check `has_feature` before rendering. For example, Daman Backup sidebar link:

```javascript
// In navigation config:
{
    label: 'Daman Backup',
    icon: 'database',
    route: '/daman-backup',
    condition: () => this.$team?.doc?.enabled_features?.daman_backup,
}
```

**Step 4: Commit**

```bash
git add press/api/feature_access.py
git commit -m "feat(admin): feature access check API for sidebar/page gating"
```

**Step 5: Code review**

---

## Task 6: Deploy + E2E Verification

**Step 1: Run setup on press-ctrl**

```bash
# SCP all new files to press-ctrl
# Run field setup:
bench --site demo.mvpstorm.com console
>>> from press.press.doctype.team.team_admin_setup import setup_admin_fields
>>> setup_admin_fields()
```

**Step 2: Build dashboard**

```bash
bench build --app press
bench --site demo.mvpstorm.com clear-cache
supervisorctl restart frappe-bench-web:* frappe-bench-workers:*
```

**Step 3: E2E test checklist**

- [ ] `/dashboard/admin` loads with stats bar
- [ ] Teams list shows all 3 teams with usage bars
- [ ] Click team row → expands with 4 tabs
- [ ] Quotas tab: edit max_sites → Save → verify enforced on site creation
- [ ] Features tab: toggle Daman Backup → sidebar link appears/disappears
- [ ] Members tab: shows members, Reset Password works
- [ ] Sites tab: shows sites with type badges, Suspend/Transfer/Archive buttons work
- [ ] Benches tab: shows benches, Transfer button works
- [ ] Create Team dialog: creates team + user with initial quotas
- [ ] Block/Unblock toggle: blocks team, suspends all sites
- [ ] Server costs table: shows correct costs
- [ ] Cost/mo per team shows in table

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(admin): complete admin panel — quotas, features, costs, team management"
git push
```

---

## Task 7: Final Clean Code Review

**Step 1: Run `clean-code` on all new files**

```
press/press/doctype/team/team_admin_setup.py
press/press/doctype/team/team_quota_enforcement.py
press/api/admin_panel.py
press/api/feature_access.py
dashboard/src/pages/AdminPanel.vue
```

Check: file sizes <700 lines, no anti-patterns, consistent naming.

**Step 2: Run `code-review:code-review` — deep final review**

Focus on:
- Security: all endpoints have `frappe.only_for("System Manager")`
- XSS: no server values interpolated into HTML
- SQL injection: all queries use parameterized `%s`
- Race conditions: quota checks before insert (not after)
- Performance: N+1 queries in get_admin_data (acceptable for admin page with <100 teams)

**Step 3: Fix all MUST FIX issues, commit**

```bash
git commit -m "fix(admin): apply code review fixes"
git push
```

---

## Summary

| Task | What | New files | TDD | Review |
|------|------|-----------|-----|--------|
| 1 | Custom Fields for quotas | `team_admin_setup.py` | Yes | Yes |
| 2 | Quota enforcement hooks | `team_quota_enforcement.py` + hooks.py | Yes | Yes |
| 3 | Admin API (teams, costs, features) | `admin_panel.py` | Yes | Yes |
| 4 | Admin Panel Vue page | `AdminPanel.vue` + router | Build test | Yes |
| 5 | Feature access check API | `feature_access.py` | Yes | Yes |
| 6 | Deploy + E2E verification | - | E2E checklist | - |
| 7 | Final clean code + deep review | - | - | Full review |

**Total new files:** 5 Python + 1 Vue
**Modified files:** hooks.py, router.js, navigation config
**Zero upstream modifications:** all sibling files + Custom Fields
