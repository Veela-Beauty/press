# Site Restore & Backup Upload System

How the backup restore dialog uploads files and triggers site restoration — including the direct/chunked upload system that works without S3.

Related: [Backup Integration](../03-backup-integration/overview.md) | [Architecture](../00-getting-started/architecture.md)

---

## Overview

Press allows users to restore a site from a backup by uploading database, public files, private files, and site config through the dashboard. The upload system supports two modes:

| Mode | When Used | How It Works |
|------|-----------|--------------|
| **S3 Presigned URL** | S3 configured in Press Settings | Frontend uploads directly to S3 bucket, then notifies Press |
| **Direct/Chunked Upload** | No S3 configured | Frontend uploads to Press server via API endpoint |

The system auto-detects which mode to use. If S3 credentials are missing, it falls back to direct upload automatically.

---

## Architecture

```
Browser (SiteDatabaseRestoreDialog.vue)
    |
    v
FileUploader.vue
    |
    +-- is_s3_configured? -----> YES --> S3FileUploader.js
    |                                       |
    |                                       v
    |                               S3 Presigned POST
    |                                       |
    |                                       v
    |                            uploaded_backup_info API
    |
    +-- is_s3_configured? -----> NO --> DirectFileUploader.js
                                          |
                                +---------+---------+
                                |                   |
                           < 100MB              >= 100MB
                                |                   |
                                v                   v
                        upload_backup_file    Chunked Upload:
                        (single POST)        1. init_chunked_upload
                                             2. upload_chunk (x N)
                                             3. finalize_chunked_upload
                                                    |
                                                    v
                                            Remote File record
                                                    |
                                                    v
                                          press.api.site.restore
                                                    |
                                                    v
                                            Agent Job (on server)
```

---

## Upload Modes

### S3 Presigned URL (default when configured)

1. Frontend calls `get_upload_link(file_name)` -> gets presigned POST URL + fields
2. Frontend POSTs file directly to S3 bucket (progress via XHR)
3. On success, calls `uploaded_backup_info(file, path, type, size)` -> creates Remote File record
4. Returns Remote File name to parent dialog

**Requires**: `remote_access_key_id`, `remote_secret_access_key`, `remote_uploads_bucket` in Press Settings.

### Direct Upload (< 100MB files)

1. Frontend POSTs file to `/api/method/press.api.site.upload_backup_file`
2. Server streams file to disk in 8MB chunks (no memory load)
3. Creates Remote File record with local path
4. Returns Remote File name

### Chunked Upload (>= 100MB files)

For large files (database dumps, private file tars), the file is split into 50MB chunks:

1. **Init**: `init_chunked_upload(file_name, file_size, file_type)` -> returns `upload_id` + `chunk_size`
2. **Upload**: For each chunk, `upload_chunk(upload_id, chunk_index, file)` -> streams chunk to temp directory
3. **Finalize**: `finalize_chunked_upload(upload_id)` -> reassembles chunks into final file, creates Remote File record, cleans up temp chunks

**Benefits**:
- Works for files up to 100 GiB
- Per-chunk progress tracking (real-time speed + ETA)
- Only failed chunks need retry (not the whole file)
- Each chunk is a separate HTTP request (no timeout issues)

---

## API Endpoints

### Detection

| Endpoint | Purpose |
|----------|---------|
| `press.api.site.is_s3_configured` | Returns true/false -- cached on frontend per page load |

### Direct Upload

| Endpoint | Purpose |
|----------|---------|
| `press.api.site.upload_backup_file` | Single-request file upload, streams to disk |

### Chunked Upload

| Endpoint | Purpose |
|----------|---------|
| `press.api.site.init_chunked_upload` | Start session, get upload_id and chunk_size |
| `press.api.site.upload_chunk` | Upload one chunk (multipart, 50MB default) |
| `press.api.site.finalize_chunked_upload` | Reassemble chunks, create Remote File record |

### Restore

| Endpoint | Purpose |
|----------|---------|
| `press.api.site.validate_restoration_space_requirements` | Pre-flight disk space check |
| `press.api.site.restore` | Trigger site restoration with uploaded files |

---

## Frontend Components

### SiteDatabaseRestoreDialog.vue

The main restore dialog with:
- **4 file upload slots**: database (.sql.gz), public files (.tar), private files (.tar), config (.json)
- **Upload progress panel**: overall progress bar, per-file status, upload speed, ETA
- **Status phases**: Checking disk -> Connecting -> Uploading -> Complete
- **Stall detection**: 120s timeout if no progress detected
- **Error handling**: Shows specific error messages for each file

### FileUploader.vue

Generic file upload component. Key behavior:
- Accepts `s3` prop (boolean) from parent
- On first upload, calls `is_s3_configured` (result cached globally via `checkS3Available()`)
- Creates appropriate uploader: `S3FileUploader` or `DirectFileUploader`
- Emits: `start`, `progress`, `finish`, `error` events

### DirectFileUploader.js

Upload controller that handles both direct and chunked modes:
- `CHUNK_THRESHOLD = 100MB` -- files below this go direct, above go chunked
- `_directUpload(file)` -- single XHR POST with progress
- `_chunkedUpload(file)` -- init -> chunks -> finalize with per-chunk progress
- `_uploadSingleChunk()` -- XHR POST for one chunk with progress aggregation

---

## Server Configuration

For large file uploads, these limits must be set:

| Config | Location | Value | Purpose |
|--------|----------|-------|---------|
| `client_max_body_size` | `/etc/nginx/conf.d/frappe-bench.conf` | `6g` | Nginx request size limit |
| `proxy_read_timeout` | `/etc/nginx/conf.d/frappe-bench.conf` | `1800` | 30min timeout for slow uploads |
| `max_file_size` | `sites/common_site_config.json` | `6442450944` | Frappe internal file size limit (6GB) |
| Gunicorn `-t` | `config/supervisor.conf` | `1800` | Worker timeout for long requests |

**Note**: These limits apply to individual HTTP requests. Chunked uploads send 50MB per request, so they work within normal limits. The high limits are needed for direct uploads of files under 100MB threshold and for the finalize step.

---

## File Storage

Uploaded backup files are stored at:
```
{site_path}/private/files/backup_uploads/
  {hash}-{safe_filename}           # Final assembled files
  {upload_id}/                     # Temporary chunk directory (during upload)
    meta.json                      # Upload session metadata
    chunk_000000                   # Individual chunks
    chunk_000001
    ...
```

Chunks are cleaned up automatically after finalization. Final files persist until the restore completes.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Error Uploading File" on large files | nginx `client_max_body_size` too low | Increase to `6g` in nginx config |
| Upload stalls at "Connecting..." | S3 not configured, old code path | Update to latest with DirectFileUploader |
| "Upload stalled -- server not responding" | Gunicorn timeout | Increase `-t` in supervisor.conf |
| Config file uploads but database fails | Size limit difference | Check all 4 limits in table above |
| Progress stuck at 0% | CSRF token issue | Hard refresh the page |
