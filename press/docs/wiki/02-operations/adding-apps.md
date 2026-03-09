# Adding Apps

How to register a new app in Press, create a bench, build it, and deploy sites.

---

## Step 1: Register the App

### 1a. Create App record

```python
frappe.get_doc({
    "doctype": "App",
    "name": "hrms",           # lowercase, matches GitHub repo name
    "title": "Frappe HR",
    "scrubbed": "hrms"
}).insert()
```

### 1b. Create App Source

```python
frappe.get_doc({
    "doctype": "App Source",
    "app": "hrms",
    "app_title": "Frappe HR",
    "repository_url": "https://github.com/frappe/hrms",
    "branch": "version-15",   # use version-tagged branch, NOT develop
    "public": 1,
    "frappe": 1,
    "enabled": 1,
    "team": "<team_hash>",
    "versions": [{"version": "Version 15"}]
}).insert()
```

**Branch selection:** Always use `version-15` (or `version-14`) — never `develop`. The `develop` branch targets the latest Frappe version and will break version-15 builds.

### 1c. Check App Compatibility

```bash
# Verify version-15 branch exists
git ls-remote --heads https://github.com/frappe/hrms.git version-15

# Check Python requirements
curl -s https://raw.githubusercontent.com/frappe/hrms/version-15/pyproject.toml \
  | grep requires-python
```

**Apps NOT compatible with v15** (v16+ only): print_designer, wiki, lms, builder, helpdesk, crm, insights, drive, gameplan.

### 1d. Create Marketplace App (for dashboard visibility)

```python
frappe.get_doc({
    "doctype": "Marketplace App",
    "app": "hrms",
    "title": "Frappe HR",
    "frappe_approved": 1,
    "status": "Published"
}).insert()
```

---

## Step 2: Create App Release

App Releases are snapshots of a branch at a specific commit. Press validates that an approved release exists before building.

```python
import subprocess

# Get latest commit hash
result = subprocess.run(
    ["git", "ls-remote", "https://github.com/frappe/hrms.git", "refs/heads/version-15"],
    capture_output=True, text=True
)
commit_hash = result.stdout.split()[0] if result.stdout else "HEAD"

frappe.get_doc({
    "doctype": "App Release",
    "app": "hrms",
    "source": "<app_source_name>",
    "hash": commit_hash,
    "status": "Approved"
}).insert()
```

Or trigger auto-release via the App Source "Fetch Releases" button in the UI.

---

## Step 3: Add App to Release Group

```python
rg = frappe.get_doc("Release Group", "<release_group_name>")
rg.append("apps", {
    "app": "hrms",
    "source": "<hrms_source_name>"
})
rg.save()
```

Or: Dashboard → Bench → Apps tab → Add App.

---

## Step 4: Build

### Via Dashboard

1. Go to Dashboard → Bench → Deploy tab
2. Click "Deploy" — creates a Deploy Candidate automatically
3. Monitor build steps

### Via Console

```python
rg = frappe.get_doc("Release Group", "<release_group_name>")
candidate = rg.create_deploy_candidate()
candidate.build()
```

### Monitor Build Progress

```bash
bench --site demo.mvpstorm.com execute frappe.client.get_list \
  --kwargs '{"doctype": "Deploy Candidate Build", "fields": ["name", "status", "creation"], "order_by": "creation desc", "limit_page_length": 5}'
```

### Build Takes Too Long / Stuck

```bash
# Check agent jobs
bench --site demo.mvpstorm.com execute frappe.client.get_list \
  --kwargs '{"doctype": "Agent Job", "filters": {"status": "Pending"}, "fields": ["name", "job_type", "creation"]}'

# Clear stuck jobs if needed
bench --site demo.mvpstorm.com execute frappe.db.sql \
  --args '["UPDATE \`tabAgent Job\` SET status = \"Failure\" WHERE status IN (\"Pending\", \"Undelivered\") AND creation < NOW() - INTERVAL 1 HOUR"]'
```

---

## Step 5: Deploy to Bench

After build succeeds:

```python
# Get the successful build
build = frappe.get_last_doc("Deploy Candidate Build", filters={"status": "Success"})
candidate = frappe.get_doc("Deploy Candidate", build.deploy_candidate)
candidate.deploy()
```

Or: Dashboard → Bench → Deploy tab → "Deploy to Production".

---

## Step 6: Create Site

### Via Dashboard

1. Dashboard → Sites → New Site
2. Select bench, subdomain, admin password
3. Select site plan

### Via Console

```python
site = frappe.get_doc({
    "doctype": "Site",
    "subdomain": "mysite",
    "domain": "demo.mvpstorm.com",
    "bench": "<bench_name>",
    "team": "<team_hash>",
    "plan": "Free Trial",
    "apps": [
        {"app": "frappe"},
        {"app": "erpnext"}
    ]
})
site.insert()
```

---

## Common Build Failures

| Error | Cause | Fix |
|-------|-------|-----|
| "Incompatible Python version" | App requires Python 3.14+ | Patched — `validations.py` warns instead of fails |
| "SyntaxError: type X = Y" | v16 app on Python 3.11 | Use Python 3.12+ or disable v16 |
| "Incompatible app version" | develop branch targets newer Frappe | Use version-tagged branch (version-15) |
| Docker push fails | Registry not in insecure-registries | Add `89.167.116.92:5000` to daemon.json |
| Agent steps stay Pending | agent `press_url` wrong | Update config.json → `https://demo.mvpstorm.com` |
