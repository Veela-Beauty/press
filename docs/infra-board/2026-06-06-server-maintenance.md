# Server Maintenance - setup (host provisioning)

The **Server Maintenance** Single doctype (`/app/server-maintenance`, System-Manager only) drives two
jobs from the UI - Docker registry GC and offsite-backup retention - by shelling out to a root-owned
host script through a fixed sudoers grant. Config lives in the DB; the only thing on disk is this
audited helper. The controller calls `sudo -n /opt/sanad/maintenance.sh <action>`.

## Install on each host that runs the maintenance (e.g. press-ctrl)

```bash
sudo mkdir -p /opt/sanad
sudo cp press/infra/host/maintenance.sh /opt/sanad/maintenance.sh   # from this repo
sudo chown root:root /opt/sanad/maintenance.sh
sudo chmod 0755 /opt/sanad/maintenance.sh
# grant the bench user (frappe) password-less use of ONLY this script:
printf 'frappe ALL=(root) NOPASSWD: /opt/sanad/maintenance.sh\n' | sudo tee /etc/sudoers.d/sanad-maintenance
sudo chmod 0440 /etc/sudoers.d/sanad-maintenance
sudo visudo -c -f /etc/sudoers.d/sanad-maintenance      # must say "parsed OK"
```

The script is root-owned + non-writable by frappe and validates every argument (action allowlist,
`days` is a positive integer), so the grant cannot be abused even though it allows any args.

## What the jobs do
- **registry-gc**: copies the registry config out, `docker stop registry`, runs
  `registry garbage-collect --delete-untagged` against the volume, `docker start registry`. Only
  unreferenced blobs are deleted; tagged/active images are untouched. Brief registry downtime
  (a few minutes); does not affect running benches, only new deploys. Default cadence weekly.
- **backup-retention**: per site under `/opt/minio/data/press-uploads/<site>/<unixts>_<rand>/`,
  deletes backup folders older than `keep_days`, ALWAYS keeping the newest backup per site (no site
  is ever left with zero backups). Runs as a dry-run unless `--apply`. OFF by default (destructive).

## UI
`Server Maintenance` doctype: per job an Enabled toggle, schedule/keep-days, Last Run, Last Result.
"Run Now" buttons: Registry GC Now, Backup Retention (Dry Run), Backup Retention (Apply). The daily
Frappe scheduler runs the enabled jobs (`run_scheduled_registry_gc` honours the interval-days;
`run_scheduled_backup_retention` applies).

## Verified live (2026-06-06, press-ctrl)
- Manual registry GC freed 35 G (69 G -> 34 G; disk 52% -> 40%).
- `run_backup_retention(apply=0)` via the whitelisted method -> `dryrun, keep 7d, 24 sites: 88 old
  backups, 6073MB` (recorded to Last Result).
- `run_registry_gc()` via the whitelisted method -> stop/GC/start, registry healthy (`/v2/ 200`).
