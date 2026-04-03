# Site Type Field — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `site_type` Select field (Production, Staging, Dev, Demo) to the Site DocType, show it in the New Site form and site list, and enforce that Dev/Demo sites can only be created on development benches.

**Architecture:** Custom Field on Site DocType (avoids modifying upstream site.json). Validation in `site.py.validate()` checks `bench.is_development_bench` when `site_type` is Dev or Demo. Dashboard NewSite.vue gets a step for type selection. Site list shows a colored badge.

**Tech Stack:** Frappe Custom Fields (Python), Vue.js (Press dashboard), MariaDB

---

### Task 1: Add Custom Field via fixtures

**Files:**
- Create: `press/press/doctype/site/site_type_setup.py`
- Modify: `press/hooks.py` (add to fixtures or after_migrate)

**Step 1: Write the test**

```python
# In bench console — verify field exists after setup
import frappe
meta = frappe.get_meta("Site")
field = meta.get_field("site_type")
assert field is not None, "site_type field missing"
assert field.fieldtype == "Select"
assert "Production" in field.options
```

**Step 2: Create the setup script**

File: `press/press/doctype/site/site_type_setup.py`
```python
import frappe

def add_site_type_field():
    """Add site_type custom field to Site DocType if it doesn't exist."""
    if frappe.db.exists("Custom Field", {"dt": "Site", "fieldname": "site_type"}):
        return

    frappe.get_doc({
        "doctype": "Custom Field",
        "dt": "Site",
        "fieldname": "site_type",
        "label": "Site Type",
        "fieldtype": "Select",
        "options": "Production\nStaging\nDev\nDemo",
        "default": "Production",
        "insert_after": "cluster",
        "in_list_view": 1,
        "in_standard_filter": 1,
        "reqd": 0,
    }).insert(ignore_permissions=True)
    frappe.db.commit()
```

**Step 3: Run setup on press-ctrl**

```bash
bench --site demo.mvpstorm.com console
>>> from press.press.doctype.site.site_type_setup import add_site_type_field
>>> add_site_type_field()
```

**Step 4: Verify field exists**

```bash
bench --site demo.mvpstorm.com console
>>> frappe.get_meta("Site").get_field("site_type").options
'Production\nStaging\nDev\nDemo'
```

**Step 5: Commit**

```bash
git add press/press/doctype/site/site_type_setup.py
git commit -m "feat(site): add site_type custom field (Production/Staging/Dev/Demo)"
```

---

### Task 2: Backend validation — Dev/Demo only on dev benches

**Files:**
- Create: `press/press/doctype/site/site_type_validation.py`
- Test: manual console test

**Step 1: Write the failing test**

```python
# In bench console — this should raise
import frappe
# Find a non-dev bench
bench = frappe.get_all("Bench", {"is_development_bench": 0, "status": "Active"}, limit=1)
if bench:
    site = frappe.get_doc({
        "doctype": "Site",
        "subdomain": "test-dev-validation",
        "group": frappe.get_value("Bench", bench[0].name, "group"),
        "site_type": "Dev",
    })
    try:
        site.validate()
        print("FAIL — should have thrown")
    except frappe.ValidationError as e:
        print("PASS —", str(e))
```

**Step 2: Create the validation module**

File: `press/press/doctype/site/site_type_validation.py`
```python
import frappe

def validate_site_type(site):
    """Dev and Demo sites can only be created on development benches."""
    if site.site_type not in ("Dev", "Demo"):
        return

    bench_name = site.bench
    if not bench_name and site.group:
        # Before insert, bench may not be set yet — check the group's latest bench
        bench_name = frappe.get_value(
            "Bench", {"group": site.group, "status": "Active"},
            "name", order_by="creation desc",
        )

    if not bench_name:
        return

    is_dev = frappe.get_value("Bench", bench_name, "is_development_bench")
    if not is_dev:
        frappe.throw(
            f"{site.site_type} sites can only be created on development benches. "
            f"Mark the bench as development first from the bench Actions tab.",
            frappe.ValidationError,
        )
```

**Step 3: Wire into site.py validate (monkey-patch approach)**

Rather than editing the 5000-line site.py, call from a hook.
Add to `press/hooks.py` in `doc_events`:

```python
# In hooks.py doc_events section:
"Site": {
    "validate": "press.press.doctype.site.site_type_validation.validate_site_type",
}
```

Wait — Press hooks.py already has Site doc_events. We need to ADD to them, not replace. 
Better approach: since we control the server, add it via Custom Doc Events or 
call directly from the setup script as an override.

**Alternative: Use frappe.get_hooks approach or just add to existing site validate.**

Simplest: Add a one-line call inside site.py's validate method.

**Step 4: Verify validation works**

Run the test from Step 1 — should print "PASS".

**Step 5: Commit**

```bash
git add press/press/doctype/site/site_type_validation.py
git commit -m "feat(site): validate Dev/Demo sites only on development benches"
```

---

### Task 3: Dashboard — Add site_type selector to New Site page

**Files:**
- Modify: `dashboard/src/pages/NewSite.vue`

**Step 1: Add site_type step between Region and Plan**

After the region selector section (~line 221), add:

```vue
<!-- Site Type -->
<div class="mt-6" v-if="benchPrivate">
    <label class="text-lg font-semibold">What type of site is this?</label>
    <div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <button v-for="t in siteTypes" :key="t.value"
            class="flex flex-col items-center gap-2 rounded-lg border p-4 text-sm transition-colors"
            :class="siteType === t.value ? 'border-blue-500 bg-blue-50 text-blue-900' : 'border-gray-200 hover:border-gray-300'"
            @click="siteType = t.value">
            <span class="text-2xl">{{ t.icon }}</span>
            <span class="font-medium">{{ t.label }}</span>
            <span class="text-xs text-gray-500">{{ t.desc }}</span>
        </button>
    </div>
    <p v-if="siteTypeWarning" class="mt-2 text-sm text-orange-600">{{ siteTypeWarning }}</p>
</div>
```

**Step 2: Add data properties**

```javascript
siteType: 'Production',
siteTypes: [
    { value: 'Production', label: 'Production', icon: '🏢', desc: 'Live client site' },
    { value: 'Staging', label: 'Staging', icon: '🧪', desc: 'Pre-production testing' },
    { value: 'Dev', label: 'Dev', icon: '💻', desc: 'Development only' },
    { value: 'Demo', label: 'Demo', icon: '🎯', desc: 'Client demo' },
],
```

**Step 3: Add computed siteTypeWarning**

```javascript
siteTypeWarning() {
    if (['Dev', 'Demo'].includes(this.siteType) && !this.isDevBench) {
        return 'Dev and Demo sites require a development bench. Mark the bench as development first.';
    }
    return '';
},
isDevBench() {
    // Check if selected bench/group is a dev bench
    if (!this.selectedBench) return false;
    return this.selectedBench.is_development_bench;
},
```

**Step 4: Pass site_type in the create API call**

In the bench (private) submit path, add `site_type: this.siteType` to the doc object.
In the shared submit path, add `site_type: this.siteType` to the site object.

**Step 5: Disable create button when validation fails**

Add `:disabled="!!siteTypeWarning"` to the Create Site button.

**Step 6: Commit**

```bash
git add dashboard/src/pages/NewSite.vue
git commit -m "feat(ui): site type selector on New Site page with dev-bench validation"
```

---

### Task 4: Dashboard — Show site_type badge in site list

**Files:**
- Modify: `dashboard/src/objects/site.js`

**Step 1: Add site_type to list fields**

In the `fields` array, add `'site_type'`.

**Step 2: Add site_type column after Status**

```javascript
{
    label: 'Type',
    fieldname: 'site_type',
    type: 'Badge',
    width: '100px',
    theme(value) {
        const map = { Production: 'blue', Staging: 'orange', Dev: 'green', Demo: 'purple' };
        return map[value] || 'gray';
    },
},
```

**Step 3: Add site_type to filter controls**

```javascript
{
    type: 'select',
    label: 'Type',
    fieldname: 'site_type',
    options: ['', 'Production', 'Staging', 'Dev', 'Demo'],
},
```

**Step 4: Build and verify**

```bash
bench build --app press
# Check /dashboard/sites — should show Type column with colored badges
```

**Step 5: Commit**

```bash
git add dashboard/src/objects/site.js
git commit -m "feat(ui): show site_type badge and filter in site list"
```

---

### Task 5: Set existing sites to Production

**Step 1: Bulk update existing sites**

```sql
UPDATE tabSite SET site_type = 'Production' WHERE site_type IS NULL OR site_type = '';
```

**Step 2: Verify**

```sql
SELECT site_type, COUNT(*) FROM tabSite GROUP BY site_type;
```

---

### Task 6: Deploy and verify end-to-end

**Step 1: Deploy backend**

```bash
scp files to press-ctrl
bench build --app press
bench --site demo.mvpstorm.com migrate
supervisorctl restart frappe-bench-web:* frappe-bench-workers:*
```

**Step 2: Test new site creation**

1. Go to bench-0014 (non-dev bench) → New Site → should see Production/Staging options, Dev/Demo disabled
2. Go to a dev bench → New Site → all 4 options available
3. Create a Dev site on dev bench → should succeed
4. Try creating a Dev site on non-dev bench → should get validation error

**Step 3: Test site list**

1. Go to /dashboard/sites → should see Type column with colored badges
2. Filter by Type = Dev → should show only dev sites

**Step 4: Final commit and push**

```bash
git add -A
git commit -m "feat(site): complete site type feature — field, validation, UI, list"
git push
```
