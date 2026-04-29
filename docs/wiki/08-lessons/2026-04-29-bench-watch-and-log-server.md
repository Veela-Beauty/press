# Lessons Learned — 2026-04-29 Session

> A long session: bench-watch polish + Site Overview usage + Log Server end-to-end.
> 23 commits, 3 layers (Python + Vue + infra), 5 repeating-pattern bugs.
> Captured here so we don't re-learn them.

## Lesson 1 — `dashboard_fields` is a silent failure mode

### What it is
Press defines a class-level tuple `dashboard_fields` on every Doctype. When the dashboard fetches a doc via `press.api.client.get*`, this tuple acts as a **whitelist** — fields not listed get **silently stripped** from the API response. No error, no warning, no log.

Example from `Bench.dashboard_fields`:
```python
class Bench(...):
    dashboard_fields = (
        "apps", "name", "group", "status", "cluster",
        "is_ssh_proxy_setup", "inplace_update_docker_image",
        # FORGOT: is_development_bench
    )
```

### How it bit us
- "Mark/Unset Dev Bench" button text never reflected reality (always said "Mark").
- New Watch panel never appeared even after marking dev.
- Site Overview's Storage / Database / CPU panels stayed at 0 despite real data in DB.

In all three cases, the DB had the right value. The dashboard never saw it.

### How to spot it
When a UI panel inexplicably shows 0/null/false/wrong-state, **check the doctype's `dashboard_fields` BEFORE debugging anywhere else**. Cheap test:

```javascript
// In browser dev tools on the dashboard:
fetch('/api/method/press.api.client.get', {
  method: 'POST', credentials: 'include',
  headers: {'Content-Type':'application/json','X-Frappe-CSRF-Token':'token'},
  body: JSON.stringify({ doctype: 'Bench', name: '<bench-name>' })
}).then(r=>r.json()).then(j => console.log(Object.keys(j.message)));
```

If the field you expect isn't in the keys list → it's filtered. Add it to `dashboard_fields`.

### Regression test pattern
```python
class TestBenchDashboardFieldsRegression(FrappeTestCase):
    def test_is_development_bench_in_dashboard_fields(self):
        from press.press.doctype.bench.bench import Bench
        self.assertIn(
            "is_development_bench",
            Bench.dashboard_fields,
            "is_development_bench MUST be in Bench.dashboard_fields — "
            "the dashboard depends on it for the Mark/Unset Dev Bench toggle "
            "and the Auto-Rebuild watch panel.",
        )
```

Lock contracts that span doctype + UI in tests like this. They run in milliseconds.

---

## Lesson 2 — Catch-all `except Exception: return 0` hides config bugs

### What it is
`press.api.analytics.get_current_cpu_usage`:
```python
def get_current_cpu_usage(site):
    try:
        # ... build URL, query ES ...
        response = requests.post(url, json=query, auth=("frappe", password)).json()
        # ... extract counter ...
    except Exception:
        return 0  # ← swallows EVERYTHING
```

Auth failures, connection errors, JSON parse errors, missing fields — all return 0. Silently.

### How it bit us
Spent 30 minutes debugging "Compute panel still 0" when ES was up, indices had docs, and Filebeat was shipping. Root cause: `Log Server.kibana_password` was wrong (drift from htpasswd). Press got 401 → returned 0 → user saw nothing wrong.

### How to spot it
When a Press function silently returns a falsy default, **bypass the function and call the underlying API directly**:

```bash
# Replicate Press's exact request:
curl -u frappe:$STORED_PASSWORD https://logs.sandbox.mvpstorm.com/elasticsearch/_cluster/health

# vs. Press's call (with the password Press would use):
import requests
from frappe.utils.password import get_decrypted_password
pwd = get_decrypted_password('Log Server', 'logs.sandbox.mvpstorm.com', 'kibana_password')
print(requests.post(url, json=q, auth=('frappe', pwd)).status_code)
```

If the curl returns 200 but `requests.post` returns 401, the stored password doesn't match nginx's. Fix the doc.

### Lesson
When introducing new code that calls external services, **don't** wrap with `except Exception: return default`. At minimum log the exception. Better: re-raise on auth/4xx and only suppress connection errors.

---

## Lesson 3 — Filebeat needs ingest pipelines deployed BEFORE shipping

### What it is
Filebeat's `inputs.d/monitor.yml` declares `pipeline: monitor`. When Filebeat ships an event, it tells ES "use this pipeline". If the pipeline doesn't exist in ES, ES drops the event with 404. Filebeat retries forever.

### How it bit us
Filebeat was running for weeks (since April 3) but never indexed anything useful. We assumed Filebeat was wrong; turns out the ES side was missing the pipeline definitions.

Press's playbook installs them at `playbooks/roles/filebeat_elasticsearch/files/{monitor,nginx}.json`. We bypassed the playbook (we self-hosted ES on press-ctrl), so we never installed them.

### Fix
```bash
curl -sk -u frappe:$PWD -XPUT \
  https://logs.sandbox.mvpstorm.com/elasticsearch/_ingest/pipeline/monitor \
  -H "Content-Type: application/json" \
  --data-binary @press/playbooks/roles/filebeat_elasticsearch/files/monitor.json
```

Same for `nginx`.

### Lesson
**When skipping Press's Ansible playbook, audit it for what it actually does** before assuming you can replace it with Docker Compose. Pipelines, index templates, ILM policies, GeoIP databases — all live there.

---

## Lesson 4 — Filebeat ILM PUT 405 through nginx reverse proxy

### What it is
Filebeat 7.x tries to PUT to a date-math URL like `<filebeat-7.17.29-{now/d}-000001>` during ILM rollover alias setup. ES expects POST for these specific URLs. Through a generic nginx proxy this becomes 405 Method Not Allowed and Filebeat gives up entirely.

### Workaround
Add to `/etc/filebeat/filebeat.yml`:
```yaml
setup.ilm.enabled: false
setup.template.enabled: false
```

Filebeat falls back to creating daily indices by date suffix (e.g. `filebeat-7.17.29-2026.04.29`). Manual cleanup via cron once volume becomes a concern.

### Lesson
**Filebeat 7.x ILM through reverse proxy is fragile.** Either configure nginx to allow PUT on those URLs, or disable ILM and roll your own retention. We chose the latter for simplicity.

---

## Lesson 5 — `frappe.get_doc("Bench", name)` in a hot path costs N×fields

### What it is
`get_watch_status` was running on every 10s poll, calling `frappe.get_doc("Bench", bench_name)` just to read `is_development_bench` (one column). Bench has dozens of fields + child tables. That's a lot of DB work for a single-bit check.

### Fix
```python
# Before:
bench = frappe.get_doc("Bench", bench_name)
if not bench.is_development_bench:
    return {...}

# After:
if not frappe.db.get_value("Bench", bench_name, "is_development_bench"):
    return {...}
bench = frappe.get_doc("Bench", bench_name)  # only when actually needed
```

### Lesson
**Use `frappe.db.get_value` for single-column reads in hot paths.** Reserve `frappe.get_doc` for when you need lifecycle methods or multiple fields. The difference is one indexed lookup vs. a full doc fetch with all child tables.

---

## Lesson 6 — Ghost-pending sites: failed New Site job leaves status=Pending forever

### What it is
A site's initial `New Site` agent job failed once on April 13. Press never advanced status from `Pending` to `Active`. Site was fully functional (16 days of green backups + migrations) but dashboard hid plan / install-app / usage panels because they're gated on `status='Active'`.

### Fix
Daily scheduler `recover_ghost_pending_sites` detects:
- `status='Pending'` AND
- `setup_wizard_complete=1` AND
- ≥1 successful Backup Site agent job in last 7 days AND
- No in-flight provisioning jobs

→ flips status to Active.

### Lesson
**Press's site status FSM doesn't always recover from initial-provisioning failures.** Ghost-pending sites are a common shape. Periodic auto-correction catches them.

---

## Lesson 7 — Windows-built node_modules in a Linux Docker build

### What it is
Developer ran `npm install playwright` on Windows. The resulting `node_modules/` contained `package.json` files with absolute Windows paths (`C:/Users/VICTUS/...`). They committed it. Renaming `node_modules/` → `node_modules-backup/` doesn't help — yarn scans subdirs of the bench's app source during `bench get-app`.

Build error:
```
error Package "" refers to a non-existing file
'"/home/frappe/frappe-bench/apps/sales_force_server_app/C:/Users/VICTUS/AppData/Roaming/npm/.../@playwright/test"'
```

### Fix
- Removed all `*-backup/` dirs and `*-backup` files
- Added `node_modules/`, `node_modules-*/`, `*-backup`, `playwright-report*/`, `test-results*/` to `.gitignore`

### Lesson
**Every app's `.gitignore` MUST include `node_modules/` and Playwright artifacts** before any team member ever runs `npm install` locally. The cost of forgetting is broken builds for days.

---

## Lesson 8 — Press `dashboard_fields` is one of several "field-passes-through" gates

When a Press dashboard panel doesn't show the data you expect, audit these in order:

1. **Doctype `dashboard_fields` whitelist** — this session's biggest source of pain.
2. **`get_list_query` static method** on the Doctype — overrides the SQL Frappe auto-generates and may exclude rows or columns.
3. **`@redis_cache(ttl=60)` decorators** on Press methods — old cached value persists for the TTL even after data changes.
4. **`@dashboard_whitelist()` permissions** — return None silently for non-team users.
5. **Frontend computed properties** — sometimes mask backend data with a fallback like `?? 0`.

Run the API call manually first. If response has the value, the problem is frontend. If not, walk this list.

---

## Lesson 9 — Press is shaped around dedicated Log Server VMs; self-hosting needs deliberate replication

We saved €7/mo by running ES on press-ctrl instead of provisioning a new VM. But Press's Ansible playbook (`log.yml`) does ~12 things:

- Installs ES + Kibana + Filebeat receiver
- Sets up TLS + nginx
- Installs the `monitor` and `nginx` ingest pipelines
- Creates GeoIP databases for nginx logs
- Configures ILM policy
- Wires SSH access for Press's agent
- Sets up Prometheus exporter
- ... and more.

We replicated ~6 of those. Re-discovered the missing pipelines manually (Lesson 3). Skipped the GeoIP / ILM / Prometheus pieces.

### Lesson
**Skipping a managed-infrastructure playbook saves money but costs investigation time.** Document exactly what you skipped so the cost comes out of the savings, not the next session.

---

## Lesson 10 — `frappe.utils.password.get_decrypted_password` is the contract surface

When Press's analytics fails with auth, the actual stored password is `get_decrypted_password("Log Server", server_name, "kibana_password")`. Compare its first 8 chars to your htpasswd password. If they differ, that's your bug.

```python
from frappe.utils.password import get_decrypted_password
p = get_decrypted_password('Log Server', 'logs.sandbox.mvpstorm.com', 'kibana_password')
print(p[:8])
```

vs.
```bash
grep FRAPPE_QUERY_PASSWORD /opt/log-server/.env | head
```

Should match. Drift = silent 401.
