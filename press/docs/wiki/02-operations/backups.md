# Backups & Restore

How Press handles site backups, how to configure them, and how to restore from a backup.

---

## How Press Backups Work

Press uses Agent Jobs to trigger backups on the app server. The flow:

1. Scheduler runs `backup_sites` task (every 6 hours by default)
2. Press enqueues an Agent Job of type "Backup Site" for each active site
3. Agent on the app server runs `bench --site <name> backup --with-files`
4. Backup files (.sql.gz, files.tar, private-files.tar) are uploaded to an S3-compatible store
5. Press records the backup in the `Site Backup` DocType

---

## Backup Storage Configuration

Press Settings > Backup Storage:

| Field | Value |
|-------|-------|
| `offsite_backups_provider` | `AWS S3` or `Backblaze B2` |
| `aws_s3_bucket` | Bucket name |
| `aws_access_key_id` | Access key |
| `aws_secret_access_key` | Secret key |
| `aws_s3_region` | Region (e.g., `eu-central-1`) |

For self-hosted without S3, backups stay on the app server in `/home/frappe/frappe-bench/sites/<site>/private/backups/`.

---

## Manual Backup Trigger

### Via Dashboard

Dashboard → Site → Backups tab → "Backup Now"

### Via Console

```python
site = frappe.get_doc("Site", "mysite.demo.mvpstorm.com")
site.backup()
```

### Via Agent Direct Call

```bash
# On press-ctrl — trigger backup via agent API
curl -u 'press-f1.demo.mvpstorm.com:AGENT_PASSWORD' \
  -X POST https://press-f1.demo.mvpstorm.com/api/site/mysite.demo.mvpstorm.com/backup \
  -H "Content-Type: application/json" \
  -d '{"with_files": true}'
```

---

## Checking Backup Status

```bash
# List recent backups
bench --site demo.mvpstorm.com execute frappe.client.get_list \
  --kwargs '{"doctype": "Site Backup", "filters": {"site": "mysite.demo.mvpstorm.com"}, "fields": ["name", "status", "creation", "database_size"], "order_by": "creation desc", "limit_page_length": 10}'
```

```python
# In console
backups = frappe.get_all("Site Backup",
    filters={"site": "mysite.demo.mvpstorm.com", "status": "Success"},
    fields=["name", "creation", "database_url", "private_url"],
    order_by="creation desc",
    limit=5
)
for b in backups:
    print(b)
```

---

## Backup Schedule

The default schedule (in `hooks.py`):

```python
scheduler_events = {
    "cron": {
        "0 */6 * * *": ["press.press.doctype.site.site.backup_sites"]
    }
}
```

This runs at midnight, 06:00, 12:00, 18:00.

To adjust, modify the cron expression in `hooks.py` and run `bench migrate`.

---

## Site Restore

### Restore from Backup (within Press)

```python
# Get the backup record
backup = frappe.get_doc("Site Backup", "<backup_name>")

# Restore to the same site
site = frappe.get_doc("Site", backup.site)
site.restore(backup.name)
```

### Restore from Backup Files (manual)

If restoring outside Press or from downloaded files:

```bash
# On the app server
ssh press-f1

# Download and extract backup
cd /tmp
# Upload .sql.gz, files.tar, private-files.tar to /tmp/

# Restore
sudo -u frappe bash -c '
  cd /home/frappe/frappe-bench
  bench --site mysite.demo.mvpstorm.com restore /tmp/backup.sql.gz \
    --with-public-files /tmp/files.tar \
    --with-private-files /tmp/private-files.tar
'
```

---

## Backup Retention

By default, Press keeps the last 3 daily, 3 weekly, and 1 monthly backup offsite. Local backups on the server are retained for 24 hours before Frappe's cleanup removes them.

To check retention settings:
```python
ps = frappe.get_doc("Press Settings")
print(ps.offsite_backup_count)  # Default: 3
```

---

## Troubleshooting

**"Backup Site" Agent Job fails**

```bash
# Check the job output
bench --site demo.mvpstorm.com execute frappe.client.get_list \
  --kwargs '{"doctype": "Agent Job", "filters": {"job_type": "Backup Site", "status": "Failure"}, "fields": ["name", "output", "traceback"], "order_by": "creation desc", "limit_page_length": 3}'
```

Common causes:
- Disk full on app server (`df -h` on press-f1)
- S3 credentials expired or wrong bucket
- Site is suspended or inactive

**Backups not running automatically**

```bash
# Check if backup_sites scheduled job is active
bench --site demo.mvpstorm.com execute frappe.client.get_list \
  --kwargs '{"doctype": "Scheduled Job Type", "filters": {"method": "press.press.doctype.site.site.backup_sites"}, "fields": ["name", "last_execution", "stopped"]}'
```

If `stopped = 1`, enable it:
```python
frappe.db.set_value("Scheduled Job Type",
    {"method": "press.press.doctype.site.site.backup_sites"},
    "stopped", 0)
frappe.db.commit()
```

**No disk space for backup**

```bash
# On press-f1 — find and clean old backups
find /home/frappe/frappe-bench/sites/*/private/backups/ -mtime +7 -delete
```

---

## Offsite backups to MinIO (or any S3-compatible store)

Press supports any S3-compatible object store — MinIO, Backblaze B2, Wasabi, Alibaba OSS — via a per-bucket `endpoint_url` on the `Backup Bucket` doctype. This is what wires our self-hosted MinIO at `http://89.167.116.92:9002` to act as the offsite store.

### Required configuration (3 places)

**1. Press Settings** — credentials and default bucket:

| Field | Value |
|-------|-------|
| `offsite_backups_access_key_id` | MinIO access key (e.g. `pressadmin`) |
| `offsite_backups_secret_access_key` | MinIO secret key (encrypted, written via `set_encrypted_password`) |
| `aws_s3_bucket` | Default bucket name (e.g. `press-uploads`) |
| `backup_region` | A non-empty placeholder (e.g. `us-east-1`) — MinIO ignores it but boto3 requires it |

**2. Backup Bucket row** — per-bucket endpoint override:

```python
frappe.get_doc({
    "doctype": "Backup Bucket",
    "bucket_name": "press-uploads",      # autoname = field:bucket_name
    "endpoint_url": "http://89.167.116.92:9002",
    "region": "us-east-1",
    "cluster": "Default",
}).insert(ignore_permissions=True)
```

**3. Agent fork must be ≥ commit `809e9c2`** — upstream `frappe/agent` does NOT pass `endpoint_url` to its boto3 client, so uploads silently default to real AWS S3 and fail with `InvalidAccessKeyId`. Our fork at `Veela-Beauty/press-agent` reads `auth["ENDPOINT_URL"]` in `agent/site.py:upload_offsite_backup`.

### Verifying the full path works

```python
# 1. Press Settings carries the credentials
import frappe
from frappe.utils.password import get_decrypted_password
ps = frappe.get_single("Press Settings")
print(ps.offsite_backups_access_key_id)
print(get_decrypted_password("Press Settings", "Press Settings", "offsite_backups_secret_access_key"))

# 2. boto3 round-trip against MinIO
import boto3
s3 = boto3.client(
    "s3",
    aws_access_key_id=ps.offsite_backups_access_key_id,
    aws_secret_access_key=get_decrypted_password("Press Settings", "Press Settings", "offsite_backups_secret_access_key"),
    endpoint_url="http://89.167.116.92:9002",
    region_name="us-east-1",
)
s3.head_bucket(Bucket="press-uploads")           # → 200
s3.put_object(Bucket="press-uploads", Key="smoke-test.txt", Body=b"ok")
s3.delete_object(Bucket="press-uploads", Key="smoke-test.txt")

# 3. Press → agent payload should include ENDPOINT_URL
job_row = frappe.db.get_value("Agent Job", "<recent-backup-site-job>", "request_data")
print(job_row)
# expect: "offsite": {"auth": {..., "ENDPOINT_URL": "http://89.167.116.92:9002", ...}}
```

### Symptom → cause map

| Symptom | Cause | Fix |
|---|---|---|
| `Password not found for Press Settings offsite_backups_secret_access_key` | Field never set in `__Auth` | `set_encrypted_password("Press Settings", "Press Settings", value, fieldname="offsite_backups_secret_access_key")` |
| Agent step `Upload Site Backup to S3` fails with `InvalidAccessKeyId` and the message ends `"in our records"` | Agent's boto3 client is hitting real AWS, not MinIO — `endpoint_url` is not flowing through | Verify Press ≥ commit `462ef02133` (sends ENDPOINT_URL) AND agent fork ≥ `809e9c2` (consumes it). Restart agent web + workers after agent update |
| `Too many pending backups` when triggering | Pending/Running Site Backup in last 2h blocking new insert | Mark the stuck row Failure (Press's poll catches up usually; if truly stuck, `frappe.db.set_value("Site Backup", name, "status", "Failure")`) |
| Clone Site dialog "No usable offsite backup found" | No `Site Backup` exists with `status=Success AND files_availability=Available AND offsite=1` | Take a fresh offsite backup first (Clone dialog's `fresh_backup` mode does this, then re-run with `latest_backup` once it lands) |

### Files involved

- `press/agent.py:_get_offsite_backup_config` — builds the payload Press sends to agent (adds ENDPOINT_URL since `462ef02133`)
- `press/press/doctype/site_backup/site_backup.py:get_backup_bucket` — fetches `name`, `region`, `endpoint_url` from `Backup Bucket` rows
- `press/press/doctype/remote_file/remote_file.py` — already supports `endpoint_url` for downloads / deletes (the pattern we mirrored for uploads)
- `agent/site.py:upload_offsite_backup` (in `Veela-Beauty/press-agent`) — consumes `auth["ENDPOINT_URL"]`

---

## Clone Site dialog

Dashboard → Site → Actions → **Clone site**. Replaces the old text-input prompt with a proper dialog (since commit `63c5a0d5fc`, refined by `462ef02133` + `5eb0a94f4a` + `cc417f2cc7`).

### What the dialog does

1. **Target Bench** — combobox listing only benches whose app set is a superset of the source site's apps. First option is `➕ Create a new bench` which pivots to `CloneBenchPrompt` against the source's release group.
2. **New subdomain** — live availability check on blur via `press.api.site.exists` (rate-limited 10/min). Green/red inline feedback.
3. **Site Plan** — preselected to the source site's plan; dropdown of enabled `Site Plan` rows ordered by `price_usd`. Without this, Press's `_new` would silently drop unknown plan values and leave `Site.plan = None`.
4. **Disk-space pre-check** — once a real bench is picked, calls `check_bench_space(target_bench, required_bytes)` where `required_bytes = source.current_disk_usage * 1.2`. Public servers auto-extend so the check short-circuits to OK. Submit is blocked on insufficient space.
5. **Data mode** — `latest_backup` (default), `fresh_backup`, or `empty`.

### Backend methods (`press/press/doctype/site/site_clone.py`)

| Method | Purpose |
|---|---|
| `clone_site(site, target_bench, new_subdomain, mode, plan=None)` | Main entrypoint. Returns `{site, job}` (the standard `_new` response shape). |
| `list_compatible_benches(site)` | Returns benches whose app set ⊇ source apps. Team-scoped for non-System Users. |
| `get_clone_options(site)` | Single-shot fetch for the dialog (benches + plans + source_plan + source_disk_usage). |
| `check_bench_space(target_bench, required_bytes)` | Returns `{server, free_bytes, required_bytes, sufficient, is_public_server}`. Mirrors `press.api.site.validate_restoration_space_requirements`. |

