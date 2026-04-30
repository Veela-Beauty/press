#!/usr/bin/env bash
# /home/frappe/scripts/post-flight.sh — gate after pip changes, BEFORE bench restart.
#
# This is THE script that prevents the 2026-04-29 incident: it import-tests every
# Frappe app in a fresh subprocess. If anything fails, the caller MUST roll back
# instead of restarting supervisor. Restarting on a broken env is what caused 10h
# of downtime.
#
# Usage:
#   post-flight.sh                  # full check
#   post-flight.sh --no-pip-check   # skip pip check (useful right after partial install)
#
# Exit 0 on success, 1 on failure.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

DO_PIP_CHECK=1

while [ $# -gt 0 ]; do
  case "$1" in
    --no-pip-check) DO_PIP_CHECK=0; shift ;;
    *) die "unknown arg: $1" ;;
  esac
done

log "=== post-flight start ==="

# 1. pip dependency consistency — informational only; boot test is the real gate.
# (Same accumulated conflicts may exist pre and post; we don't try to detect
# regressions here — the boot test catches what actually matters.)
if [ "${DO_PIP_CHECK}" -eq 1 ]; then
  log "checking pip consistency..."
  if ! check_pip_consistency >/tmp/.pip-check-post 2>&1; then
    conflicts="$(grep -c "has requirement" /tmp/.pip-check-post 2>/dev/null || echo 0)"
    log "WARNING: ${conflicts} pip dependency conflicts (informational; see /tmp/.pip-check-post)"
  else
    log "pip consistency OK"
  fi
  rm -f /tmp/.pip-check-post
fi

# 2. Boot test in a fresh subprocess — this is the critical gate.
# It re-imports every app fresh, no warm in-memory state can hide a bad install.
log "boot test: importing ${#APPS_TO_IMPORT[@]} apps in a fresh subprocess..."
if ! check_apps_import; then
  die "BOOT TEST FAILED — DO NOT RESTART. The env is broken; supervisor will FATAL on restart. Roll back NOW."
fi
log "boot test OK"

# 3. Try to load the WSGI entry point that gunicorn actually uses
# (frappe.app:application). This catches errors that surface only at WSGI load,
# beyond plain `import frappe`.
log "WSGI entry-point load test..."
if ! as_frappe "$PYTHON" -c "
import os
os.chdir('${BENCH_HOME}/sites')
from frappe.app import application
print('WSGI OK')
" 2>&1; then
  die "WSGI load FAILED — gunicorn will not boot. Roll back NOW."
fi
log "WSGI entry point loads OK"

log "=== post-flight OK — safe to restart supervisor ==="
