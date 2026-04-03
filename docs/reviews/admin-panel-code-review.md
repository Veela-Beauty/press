## Summary

The admin panel feature is well-structured but has two critical security holes — a missing auth check on `feature_access.py` that lets any user read and overwrite another team's feature flags, and a password-reset endpoint that accepts any password without length validation. Several N+1 query patterns will make the main dashboard expensive at scale, and a Vue race condition can silently swallow load errors.

---

## Issues

### MUST FIX

**1. [high] Security — `feature_access.py` has no auth guard, any logged-in user can read any team's features**

`has_feature()` and `get_team_features()` both accept an arbitrary `team` parameter with zero authorization check. Any authenticated user can pass any team name and read its feature map. Worse, since `get_team_features` is called client-side to gate UI, an attacker can query team names from other endpoints and probe feature flags.

Fix: add ownership check — the caller must be a member of the requested team, or the request must be for their own team only:

```python
@frappe.whitelist()
def has_feature(team=None, feature_id=""):
    if not team:
        from press.utils import get_current_team
        team = get_current_team()
    else:
        # Ensure caller owns this team
        from press.utils import get_current_team
        if get_current_team() != team:
            frappe.only_for("System Manager")
    ...
```

---

**2. [high] Security — `reset_user_password` accepts any password, no minimum length enforced**

`doResetPw` in the Vue component checks `if (!this.resetPwValue) return` — an empty-string guard only. The backend `reset_user_password` applies the password immediately with no validation at all. A System Manager can set a 1-character password for any user.

Fix: enforce a minimum length server-side (not just client-side):

```python
@frappe.whitelist()
def reset_user_password(user, new_password):
    frappe.only_for("System Manager")
    if len(new_password) < 12:
        frappe.throw("Password must be at least 12 characters.")
    from frappe.utils.password import update_password
    update_password(user, new_password)
    return {"ok": True}
```

---

**3. [high] Security — `toggle_team` with an unrecognised `action` silently succeeds**

In `toggle_team`, if `action` is neither `"block"` nor `"unblock"`, the function does nothing but still calls `frappe.db.commit()` and returns `{"ok": True}`. An attacker who can call this endpoint (System Manager) with a crafted `action` value gets a success response for a no-op. This is a logical correctness bug that also obscures accidental misuse.

Fix: add an explicit else clause:

```python
else:
    frappe.throw(f"Unknown action: {action}", frappe.ValidationError)
```

---

**4. [high] Race condition — `check_site_quota` and `check_bench_quota` have a TOCTOU gap**

Both functions do a `count()` check then let Frappe proceed with the insert. Under concurrent requests (two users on the same team submitting at the same time), both will read the same count, both will pass validation, and both inserts will succeed — resulting in one extra site/bench above the limit.

Fix: use `SELECT ... FOR UPDATE` on the Team row to acquire a row-level lock during validation, or move the enforcement into `before_insert` with a DB-level counter using `frappe.db.sql` with `GET_LOCK`. The minimal fix for Frappe's architecture is to use a `frappe.cache()` lock keyed by team name with a short TTL.

---

### SHOULD FIX

**5. [medium] Performance — `get_admin_data` is an N+1 query factory**

For every team in the list, the function fires: 3 `frappe.db.count()` calls + 1 `frappe.db.sql()` + 1 `_calc_team_cost()` call. `_calc_team_cost()` itself fires 2 DB queries per server in `SERVER_COSTS` (currently 4 servers = 8 queries per team). With 20 teams, `get_admin_data` executes roughly 20 × (3 + 1 + 8) = 240 queries per page load.

Fix: batch the counts into aggregated SQL queries before the loop. Example for site counts:

```python
site_counts = {r.team: r.c for r in frappe.db.sql(
    "SELECT team, COUNT(*) as c FROM tabSite WHERE status NOT IN ('Archived') GROUP BY team",
    as_dict=True
)}
```

Apply the same pattern for bench counts, member counts, and cost calculation.

---

**6. [medium] Performance — `get_team_members` is a per-member N+1**

The function fetches all members, then for each member calls `frappe.get_value("User", ...)` inside a loop. With 50 members on a team, that is 51 queries.

Fix: fetch all user data in one query after getting the member list:

```python
users_in_team = [m.user for m in members]
user_data = {u.name: u for u in frappe.get_all(
    "User", {"name": ("in", users_in_team)},
    ["name", "full_name", "last_active", "creation"]
)}
```

---

**7. [medium] Performance — `get_team_benches` has nested per-server queries inside a loop**

For each bench, it calls `frappe.get_all("Bench", ...)` to get servers, then inside `any(...)` calls `frappe.get_value("Bench", ...)` once per server. This compounds into a deep N+1 for teams with many benches.

Fix: fetch all active benches for the team's release groups in one query, then build the server and `is_dev` maps in Python.

---

**8. [medium] Security — `allowed_site_types` is stored as newline-delimited free text, never sanitised**

The field is a `Small Text` stored verbatim and later split on `\n` in the quota enforcement check. If an admin pastes in a value with leading/trailing spaces or mixed line endings (`\r\n`), the enforcement silently becomes wrong — a site type that looks like `"Production"` won't match `"Production\r"`. This is already partially handled by `.strip()` in `check_site_quota`, but `update_team_quotas` passes the value straight through without normalisation.

Fix: normalise on save in `update_team_quotas`:

```python
if allowed_site_types is not None:
    normalised = '\n'.join(
        t.strip() for t in allowed_site_types.replace('\r\n', '\n').split('\n') if t.strip()
    )
    updates["allowed_site_types"] = normalised
```

---

**9. [medium] Correctness — `create_team_from_admin` does not set `team_title`**

The Team DocType likely has a `team_title` field (it is fetched in `get_admin_data`). When creating a team from the admin panel, `team_title` is never set, so the admin list will show blank titles for all admin-created teams.

Fix: accept and populate `team_title` in `create_team_from_admin`, defaulting to `full_name` if not provided.

---

**10. [medium] Vue — lazy-loaded tabs never refresh stale data**

The `watch` on `activeTab` only loads data `if (!this.members.length)` (and equivalent). If a team's members change while the panel is open, switching away and back will not reload. This is especially problematic for the Sites tab after a `suspendSite` or `unsuspendSite` action — those methods do call `this.loadSites()`, but `loadSites` sets `sitesLoading` only while loading, never guards against parallel calls, and does not reset the array first, so stale rows flash briefly.

Fix: add a `force` parameter or always reload on tab switch, clearing the array before fetch:

```js
async loadSites(force = false) {
    if (!force && this.sites.length) return;
    this.sitesLoading = true;
    this.sites = [];
    this.sites = await call(...);
    this.sitesLoading = false;
},
```

---

**11. [medium] Vue — `loadMembers`, `loadSites`, `loadBenches` silently swallow errors**

None of the three load methods have try/catch. If the API call fails (network error, permission denied), `membersLoading` / `sitesLoading` / `benchesLoading` stays `true` forever and the user sees a permanent "Loading..." spinner with no error message.

Fix: wrap each in try/catch and show a toast on failure, always reset the loading flag in a `finally` block.

---

### NICE TO HAVE

**12. [low] Readability — `_calc_team_cost` is called N times inside `get_admin_data` loop**

The function iterates over all servers in `SERVER_COSTS` on every call. Since the server site counts are stable within a single request, pre-computing them once before the loop and passing a lookup dict would be cleaner and faster.

---

**13. [low] Correctness — `setup_admin_fields` calls `frappe.db.commit()` unconditionally**

If no fields were missing (all already exist), the function still commits an empty transaction. This is harmless but triggers unnecessary DB round-trips on every call in a setup context. Move `frappe.db.commit()` inside the `if not frappe.db.exists(...)` block, or commit once after the loop only when at least one field was inserted.

---

**14. [low] Vue — `tabs` labels are computed once at component creation, never updated**

`Members (${this.team.member_count})` is evaluated in `data()`. If the parent reloads the team and passes a new `team` prop, the tab labels do not update because `data()` only runs once. Convert `tabs` to a computed property to keep counts reactive.

---

**15. [low] Vue — `unsuspendSite` has no confirmation dialog**

`suspendSite` correctly calls `confirm(...)` before acting. `unsuspendSite` does not — an admin can accidentally unsuspend a site with a single misclick. Add the same confirm guard for symmetry.

---

## Verdict

NEEDS CHANGES — Issues 1, 2, 3, and 4 are blocking security/correctness problems that must be fixed before this feature goes to production. Issues 5–11 are performance and reliability improvements that should be addressed in the same PR.
