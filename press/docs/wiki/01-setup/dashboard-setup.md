# Dashboard Setup

Configure Press so the dashboard at `/dashboard` works end to end — bench creation, site creation, app marketplace, and team access.

---

## Required Records (in order)

### 1. Root Domain

`Press > Root Domain > New`

| Field | Value |
|-------|-------|
| Name | `demo.mvpstorm.com` |
| Default Cluster | `Default` |
| Cloudflare API Token | `(your token)` |
| Cloudflare Zone ID | `(zone ID for mvpstorm.com)` |

### 2. Cluster

`Press > Cluster > New`

| Field | Value |
|-------|-------|
| Name | `Default` |
| Title | `Default` |
| Public | `1` |

**Warning:** The `public` flag resets to 0 on save (known bug in Press). Set it via direct DB after saving:

```python
frappe.db.set_value("Cluster", "Default", "public", 1)
frappe.db.commit()
```

### 3. Database Server

| Field | Value |
|-------|-------|
| Name | `press-f1.demo.mvpstorm.com` |
| Cluster | `Default` |
| Team | `<team_hash>` |
| MariaDB Root Password | `(root DB password)` |

### 4. Proxy Server

| Field | Value |
|-------|-------|
| Name | `press-f1.demo.mvpstorm.com` |
| Cluster | `Default` |
| Team | `<team_hash>` |

### 5. Server

| Field | Value |
|-------|-------|
| Name | `press-f1.demo.mvpstorm.com` |
| Cluster | `Default` |
| Team | `<team_hash>` |
| Database Server | `press-f1.demo.mvpstorm.com` |
| Proxy Server | `press-f1.demo.mvpstorm.com` |
| Use for Builds | `1` |

### 6. Frappe Version

Ensure "Version 15" exists and is public:

```python
fv = frappe.get_doc("Frappe Version", "Version 15")
fv.public = 1
fv.save()
```

### 7. App + App Source + App Release

For each app (frappe, erpnext, hrms, payments, webshop, lending):

**App:**
```python
frappe.get_doc({
    "doctype": "App",
    "name": "frappe",
    "title": "Frappe Framework",
    "scrubbed": "frappe"
}).insert()
```

**App Source:**
```python
frappe.get_doc({
    "doctype": "App Source",
    "app": "frappe",
    "app_title": "Frappe Framework",
    "repository_url": "https://github.com/frappe/frappe",
    "branch": "version-15",
    "public": 1,
    "frappe": 1,      # flags it as official Frappe app
    "enabled": 1,
    "team": "<team_hash>",
    "versions": [{"version": "Version 15"}]
}).insert()
```

**App Release:** (created automatically when a source is refreshed, or manually)
```python
frappe.get_doc({
    "doctype": "App Release",
    "app": "frappe",
    "source": "<app_source_name>",
    "hash": "<latest_commit_hash>",
    "status": "Approved"
}).insert()
```

### 8. Marketplace App

Required for apps to appear in the dashboard marketplace:

```python
frappe.get_doc({
    "doctype": "Marketplace App",
    "app": "frappe",
    "title": "Frappe Framework",
    "frappe_approved": 1,
    "status": "Published"
}).insert()
```

### 9. Site Plan

```python
frappe.get_doc({
    "doctype": "Site Plan",
    "__newname": "Free Trial",   # autoname = "prompt"
    "title": "Free Trial",
    "price_usd": 0,
    "price_inr": 0,
    "cpu_time_per_day": 3600,
    "max_database_usage": 1024,
    "max_storage_usage": 10240,
    "cluster": "Default"
}).insert()
```

---

## Visibility Flags (All Required)

The dashboard runs many queries with `filters={"public": 1}` or `filters={"frappe_approved": 1}`. All of these must be set or the dashboard shows empty dropdowns.

| DocType | Field | Required Value | Why |
|---------|-------|----------------|-----|
| App Source | `public` | 1 | Dashboard only shows public sources |
| App Source | `frappe` | 1 | Required for "official app" filter |
| App Source | `enabled` | 1 | Disabled sources are hidden |
| Frappe Version | `public` | 1 | Version dropdown only shows public versions |
| Cluster | `public` | 1 | Cluster dropdown only shows public clusters |
| Marketplace App | `frappe_approved` | 1 | Pre-approved apps shown without review |
| Marketplace App | `status` | `Published` | Unpublished apps are hidden |

---

## Team Assignment

Press is multi-tenant. Every resource (Server, Release Group, Site, App Source) must belong to the dashboard user's team.

**Find the team hash:**
```python
team = frappe.get_all("Team", filters={"user": "test@mvpstorm.com"}, pluck="name")[0]
print(team)  # e.g., "f6o5jtfht1"
```

**Transfer records to the team:**
```python
team = "f6o5jtfht1"
for dt in ["Server", "Database Server", "Proxy Server"]:
    frappe.db.set_value(dt, "press-f1.demo.mvpstorm.com", "team", team)
frappe.db.commit()
```

Records created via the Admin backend default to Administrator's team and are **invisible** to the dashboard user.

---

## Release Group

The Release Group is the top-level object users interact with in the dashboard ("New Bench"):

```python
frappe.get_doc({
    "doctype": "Release Group",
    "title": "ERPNext v15",
    "version": "Version 15",
    "team": "<team_hash>",
    "cluster": "Default",
    "apps": [
        {"app": "frappe", "source": "<frappe_source_name>"},
        {"app": "erpnext", "source": "<erpnext_source_name>"}
    ],
    "servers": [{"server": "press-f1.demo.mvpstorm.com"}]
}).insert()
```

---

## Verification

1. Log into `/dashboard` as `test@mvpstorm.com`
2. Click "New Bench" — Version 15 should appear in dropdown
3. Frappe + ERPNext should be pre-selected
4. Cluster "Default" should appear
5. Submit build — status should update automatically within 10 seconds

If version dropdown is empty: re-check all visibility flags above.
