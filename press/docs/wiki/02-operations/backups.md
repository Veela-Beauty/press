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
