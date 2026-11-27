# Handover, 27 Nov 2026: site logins follow-ups and press-ctrl disk

## What shipped
- Press 0.7.80 "Logins and sharing" card, live since 09:38 Riyadh. The owner first used it at 12:52 on basher-training. Its share user now has the HR role profile, checked by logging in as it.
- 0.7.82: a new site keeps its plan on a public server, and the MCP `site_create` requires a plan. The 63 sites without one got USD 25. Watch Tower rule WT-RULE-123892 reports any site with no plan.
- A team test user for dashboard pictures: `dashboard-test@optiflowsys.com`, Viewer role with basher-training as its resource. Each picture needs a new token, revoked afterwards.
- press-ctrl disk went from 89% to 71% (85 GB free):
  - bench images are kept 3 days instead of 7;
  - offsite backups are kept at most 3 per site (`offsite_backups_count` 3, the owner's call);
  - 116 old uploads deleted;
  - 4 GWIS restore-test backups whose files were gone are marked Unavailable.
  - The disk alert stays at 90%, because GWIS staging needs about 28 GB at 03:00.

## What's pending (owner)
- About 15 GB of uploads of sites that no longer exist, plus hash-named folders in press-uploads: keep or delete.
- The CPU % field reads 0 because the log shipper's agent name (press-f1.demo.mvpstorm.com) differs from the server name.
- Measuring the share job's clicks on the live screen needs a narrow 1-day token.
- Emailed codes wait on Brevo.

## Where to resume
- Scripts:
  - press-ops `scripts/site-logins-2026-11-27/` (checks 06 to 37);
  - press-ops `scripts/disk-2026-11-27/` (01 to 14; 08 is the retention dry run, 10 applies the per-site limit, 12 trims archived sites).
- Records:
  - press-ops CHANGELOG, 27 Nov;
  - wiki `06-deployment-ops/known-issues-and-fixes.md` (Sites with no plan);
  - wiki `01-backend-development/site-logins-sharing.md`.

## Known traps
- `offsite_backups_count` 0 is the FIFO fallback of 30, not "forever". Press never expires an Archived site's backups.
- Remote File `file_size` totals overstate MinIO disk use about 3x. Measure with `du`.
- MinIO frees a deleted object through `.minio.sys/tmp` a few minutes after the delete.
- Every Role save (a migrate does it) logs out System Users who hold desk-less roles, the owner included.
- `bench console < file` ends a block at its first blank line. Use `run_on_console.sh`.
- In a shell, backticks inside `su -c "..."` run as commands. Send SQL on stdin.

## Open questions
- Should restore points reach back more than 3 days for client production sites? The setting covers every site alike.
