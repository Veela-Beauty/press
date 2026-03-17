# Root-Cause Patches Applied

All patches are on the `cloudflare-dns` branch of `accurate-systems/press`.

## Patch 1: Python version-aware syntax check
**File:** `press/press/doctype/app_release/app_release.py`
**Function:** `check_python_syntax()`
**Problem:** Frappe v16 requires Python 3.14. The syntax check ran with Python 3.11 → SyntaxError → App Release flagged as invalid → builds blocked permanently.
**Fix:** If the app's `requires-python` spec doesn't match the installed Python version, skip the syntax check (return `""` = no error).
**Trigger:** Any new bench with apps requiring Python > 3.11 (e.g., Frappe v16).

## Patch 2: Python version validation — warn not raise
**File:** `press/press/doctype/deploy_candidate/validations.py`
**Function:** `_validate_python_version()`
**Problem:** Raised `BuildWarning` as exception, blocking builds.
**Fix:** Changed to emit warning only, not raise.

## Patch 3: Release Group enabled=1 after_insert
**File:** `press/press/doctype/release_group/release_group.py`
**Problem:** New Release Groups had `enabled=0` by default → invisible in My Benches and New Site flow.
**Fix:** Added `after_insert()` that calls `self.db_set("enabled", 1)`.
**Trigger:** Every new bench created from dashboard.

## Patch 4: Root Domain auto-links Proxy Server Domains
**File:** `press/press/doctype/root_domain/root_domain.py`
**Function:** `after_insert()`
**Problem:** New Root Domains were not linked to Proxy Servers → `_new()` in site.py got empty proxy_servers list → `IN ()` SQL error → Internal Server Error on site creation.
**Fix:** `after_insert()` now calls `self.add_to_proxies()` automatically.
**Trigger:** Every new Root Domain added to Press.

## Patch 5: Analytics daily_usage handles missing log server
**File:** `press/press/api/analytics.py`
**Function:** `daily_usage()`
**Problem:** `get_usage()` returns `{"datasets":[], "labels":{}}` (dict) when no log server. Iterating dict keys → `AttributeError: 'str' has no attribute 'max'`.
**Fix:** `data = request_data if isinstance(request_data, list) else []` before list comprehensions.
**Trigger:** Any site analytics page when no log server (Elasticsearch) is configured.

## Patch 6: Cloud Provider Self-Hosted image
**Data fix:** `tabCloud Provider` record `Generic` had `image=/assets/press/images/generic.png` (missing file).
**Fix:** Created `generic.svg` server icon, updated DB record to point to SVG.

## Patch 7: Cloudflare DNS (replaces Route53/boto3)
**Files:** `press/utils/dns.py`, `press/press/doctype/root_domain/root_domain.py`, `tls_certificate.py`, `root_domain.json`
**Why:** Self-hosted Press uses Cloudflare, not AWS Route53. Removed all boto3 dependencies.

## Patch 8: Python 3.14 fallback in app_release.py
**File:** `press/press/doctype/app_release/app_release.py`
**Function:** `get_python_path()`
**Problem:** Hardcoded `/usr/bin/python3.14` fallback — doesn't exist on Python 3.11 server.
**Fix:** Falls back to `_get_python_path()` (bench's own python3).


## Patch 9: Agent docker_login skips null credentials
**File:** `agent/server.py` (on press-f1 AND u4)
**Function:** `docker_login()`
**Problem:** Press Settings had null `docker_registry_username`/`docker_registry_password`. Agent passed these as `None` → ran `docker login -u None -p None` → failed → bench creation blocked.
**Fix:** Added early return if username or password is falsy:
```python
def docker_login(self, registry):
    if not registry.get("username") or not registry.get("password"):
        return
    # ... original code
```
**Trigger:** Any bench creation when Press Settings has no docker registry credentials.
**Persistence:** Post-merge hook on press-f1 (`/home/frappe/agent/repo/.git/hooks/post-merge`) auto-reapplies after `git pull`.

## Patch 10: Proxy nginx template missing `hostnames;` directive
**File:** `agent/templates/proxy/nginx.conf.jinja2` (on press-f1)
**Block:** `map $host $actual_host`
**Problem:** Without `hostnames;`, nginx treats wildcard patterns (`*.sandbox.mvpstorm.com`) as literal strings. `$actual_host` is always empty → `$upstream_server_hash` defaults to `http://site_not_found` → all cross-server sites get 307 redirect to dashboard signup page.
**Fix:** Added `hostnames;` after `map $host $actual_host {`:
```jinja2
map $host $actual_host {
	hostnames;
{% for host in hosts.values() -%}
	...
```
**Fix script:** `/tmp/fix_all.py` on press-f1 (idempotent — fixes both template and live proxy.conf, reloads nginx).
**Persistence:** Post-merge hook at `/home/frappe/agent/repo/.git/hooks/post-merge` runs `fix_all.py` after every `git pull`.
**Impact:** All cross-server sites (sites on u4 proxied through press-f1) were broken. Local sites (on press-f1 itself) worked because bench nginx.conf has exact server_name matches.
