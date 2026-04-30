#!/usr/bin/env bash
# /home/frappe/scripts/pre-flight.sh — gate before any bench update / pip operation.
#
# Validates current state, takes a pip-freeze snapshot, exits non-zero on any issue.
# Designed to be run standalone OR sourced/called by bench-update-safe.
#
# Usage:
#   pre-flight.sh                          # full check, take snapshot
#   pre-flight.sh --context pre-rollback   # tag the snapshot differently
#   pre-flight.sh --no-snapshot            # check only, don't write a file
#
# On success: prints snapshot path on the last line of stdout, exit 0.
# On failure: prints clear error, exit 1.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

CONTEXT="pre-update"
TAKE_SNAPSHOT=1
STRICT=0

while [ $# -gt 0 ]; do
  case "$1" in
    --context) CONTEXT="$2"; shift 2 ;;
    --no-snapshot) TAKE_SNAPSHOT=0; shift ;;
    --strict) STRICT=1; shift ;;
    *) die "unknown arg: $1" ;;
  esac
done

log "=== pre-flight start (context=${CONTEXT}) ==="

# 1. Venv ownership
log "checking venv ownership..."
non_frappe="$(count_root_owned_files)"
if [ "${non_frappe}" -gt 0 ]; then
  die "${non_frappe} files in ${VENV}/ are NOT owned by frappe — past 'sudo pip install' pollution. Run: chown -R frappe:frappe ${VENV}/"
fi
log "venv ownership OK (0 non-frappe files)"

# 2. pip dependency consistency — WARNING by default, FATAL with --strict.
# Multi-app benches commonly have transitive conflicts that don't break boot
# (press wants newer boto3, mcp wants newer pydantic, etc). The boot test
# (step 3) is the real safety gate.
log "checking pip consistency..."
if ! check_pip_consistency >/tmp/.pip-check-out 2>&1; then
  conflicts="$(grep -c "has requirement" /tmp/.pip-check-out 2>/dev/null || echo 0)"
  log "WARNING: ${conflicts} pip dependency conflicts present (see /tmp/.pip-check-out for details)"
  if [ "${STRICT}" -eq 1 ]; then
    cat /tmp/.pip-check-out >&2
    die "--strict was set; aborting on pip conflicts"
  fi
  log "non-strict mode: continuing (boot test in step 3 is the real gate)"
else
  log "pip consistency OK"
fi
rm -f /tmp/.pip-check-out

# 3. Boot test — all apps import
log "boot test: importing ${#APPS_TO_IMPORT[@]} apps..."
if ! check_apps_import; then
  die "boot test FAILED — at least one app fails to import. Cannot safely update on top of a broken env."
fi
log "boot test OK"

# 4. Supervisor state
log "checking supervisor processes..."
running="$(count_running_supervisor)"
if [ "${running}" -ne "${EXPECTED_SUPERVISOR_PROCESSES}" ]; then
  log "WARNING: ${running}/${EXPECTED_SUPERVISOR_PROCESSES} supervisor processes RUNNING"
  log "current state:"
  supervisorctl status 2>&1 | grep -v pkg_resources >&2 || true
  die "supervisor not in healthy state — fix before updating"
fi
log "supervisor OK (${running}/${EXPECTED_SUPERVISOR_PROCESSES} RUNNING)"

# 5. Snapshot
if [ "${TAKE_SNAPSHOT}" -eq 1 ]; then
  path="$(snapshot_path "${CONTEXT}")"
  take_snapshot "${path}" >/dev/null
  log "=== pre-flight OK ==="
  # Last line of stdout = snapshot path (parsed by bench-update-safe)
  echo "${path}"
else
  log "=== pre-flight OK (no snapshot taken) ==="
fi
