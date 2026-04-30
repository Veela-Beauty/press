#!/usr/bin/env bash
# /home/frappe/scripts/rollback.sh — restore Python env to a prior snapshot.
#
# Reads a pip-freeze file and force-reinstalls every package at the captured
# version. Used by bench-update-safe when post-flight fails. Can also be run
# manually for emergency recovery.
#
# Usage:
#   rollback.sh                            # use latest snapshot in SNAPSHOTS_DIR
#   rollback.sh /path/to/snapshot.txt      # use specific snapshot
#   rollback.sh --no-restart               # restore env but don't restart supervisor
#
# Exit 0 on success, 1 on failure.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

DO_RESTART=1
SNAPSHOT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --no-restart) DO_RESTART=0; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      if [ -z "${SNAPSHOT}" ] && [ -f "$1" ]; then
        SNAPSHOT="$1"; shift
      else
        die "unknown arg or file not found: $1"
      fi
      ;;
  esac
done

if [ -z "${SNAPSHOT}" ]; then
  SNAPSHOT="$(latest_snapshot)"
  [ -z "${SNAPSHOT}" ] && die "no snapshot found in ${SNAPSHOTS_DIR}"
  log "no snapshot specified; using latest: ${SNAPSHOT}"
fi

[ -f "${SNAPSHOT}" ] || die "snapshot not found: ${SNAPSHOT}"

PKG_COUNT="$(wc -l < "${SNAPSHOT}")"
log "=== rollback start (snapshot=${SNAPSHOT}, ${PKG_COUNT} packages) ==="

# Take a snapshot of the CURRENT (broken) state before restoring, for forensics.
forensic="$(snapshot_path "pre-rollback")"
take_snapshot "${forensic}" >/dev/null
log "saved forensic snapshot of current broken state: ${forensic}"

# Restore. --no-deps + --force-reinstall + --upgrade together: force exact versions
# from the snapshot without re-resolving the dep graph (re-resolving is what got us
# into the mess in the first place).
log "running pip install --force-reinstall --no-deps -r ${SNAPSHOT} ..."
if ! as_frappe "$PIP" install --force-reinstall --no-deps -r "${SNAPSHOT}"; then
  die "pip install from snapshot FAILED — manual intervention required. Forensic: ${forensic}"
fi
log "pip restore OK"

# Verify the restore worked
log "verifying restored env imports..."
if ! check_apps_import; then
  die "rollback FAILED to restore working state — apps still don't import. Forensic: ${forensic}"
fi
log "imports OK"

if [ "${DO_RESTART}" -eq 1 ]; then
  log "clearing cache..."
  as_frappe bench --site all clear-cache 2>&1 | tail -5 || true
  log "safe restarting (stop=15s, start=30s, health=30s)..."
  if ! safe_restart 15 30 30; then
    die "rollback restart FAILED — supervisor or healthcheck never came up. Forensic: ${forensic}"
  fi
fi

log "=== rollback OK ==="
