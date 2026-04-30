#!/usr/bin/env bash
# /home/frappe/scripts/lib.sh — shared helpers for the bench-update-safe family.
# Sourced by pre-flight.sh, post-flight.sh, rollback.sh, bench-update-safe.
# Do not execute directly.

set -euo pipefail

BENCH_HOME="${BENCH_HOME:-/home/frappe/frappe-bench}"
VENV="${BENCH_HOME}/env"
PIP="${VENV}/bin/pip"
PYTHON="${VENV}/bin/python"
SNAPSHOTS_DIR="${SNAPSHOTS_DIR:-/home/frappe/snapshots}"
LOG_DIR="${LOG_DIR:-/home/frappe/snapshots}"
RULES_FILE="/etc/sanad/press-ctrl-rules.md"

APPS_TO_IMPORT=(frappe press daman_backup frappe_theme_switcher sanad_business_intelligence_ai)

HEALTH_HOST="autodeploypanel.mvpstorm.com"
HEALTH_PATH="/api/method/ping"
HEALTH_LOCAL="http://127.0.0.1${HEALTH_PATH}"

EXPECTED_SUPERVISOR_PROCESSES=8

log() {
  printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "${RUN_LOG:-/dev/null}" >&2
}

die() {
  log "FATAL: $*"
  exit 1
}

as_frappe() {
  if [ "$(id -un)" = "frappe" ]; then
    "$@"
  elif [ "$(id -u)" -eq 0 ]; then
    sudo -u frappe "$@"
  else
    die "must be run as root or frappe (current: $(id -un))"
  fi
}

as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo "$@"
  fi
}

# Build "import a, b, c" string from APPS_TO_IMPORT
_import_stmt() {
  local IFS=", "
  echo "import ${APPS_TO_IMPORT[*]}"
}

# Returns 0 if all configured apps import cleanly, 1 otherwise.
# On failure, prints the traceback to stderr.
check_apps_import() {
  local stmt
  stmt="$(_import_stmt)"
  if as_frappe "$PYTHON" -c "${stmt}; print('IMPORT OK')" 2>&1; then
    return 0
  else
    return 1
  fi
}

# Returns 0 if pip dependency tree is consistent, 1 otherwise.
# Prints conflicts to stderr.
check_pip_consistency() {
  if as_frappe "$PIP" check 2>&1; then
    return 0
  else
    return 1
  fi
}

# Counts files in venv NOT owned by frappe. Returns the count via stdout.
# Wrapped in a subshell that disables pipefail so find/grep non-zero exits
# (unreadable subdirs, no matches) don't kill the caller's `set -euo pipefail`.
count_root_owned_files() {
  ( set +e +o pipefail
    find "${VENV}/" \! -user frappe 2>/dev/null | wc -l
  ) || echo 0
}

# Counts RUNNING supervisor processes. Returns the count via stdout.
# Pure-bash loop avoids all pipefail/grep-no-match interactions.
count_running_supervisor() {
  local count=0 line
  while IFS= read -r line; do
    [[ "$line" == *"pkg_resources"* ]] && continue
    [[ "$line" == *" RUNNING "* ]] && count=$((count + 1))
  done < <(as_root supervisorctl status 2>/dev/null || true)
  printf '%d\n' "$count"
}

# HTTP code from a local healthcheck via nginx. Echoes the code (e.g. 200).
local_healthcheck() {
  curl -sS -o /dev/null \
    -m 10 \
    -H "Host: ${HEALTH_HOST}" \
    -w "%{http_code}" \
    "${HEALTH_LOCAL}" \
    || echo "000"
}

# Ensure required directories exist with frappe ownership.
ensure_dirs() {
  if [ ! -d "${SNAPSHOTS_DIR}" ]; then
    mkdir -p "${SNAPSHOTS_DIR}"
    chown frappe:frappe "${SNAPSHOTS_DIR}"
    chmod 755 "${SNAPSHOTS_DIR}"
  fi
}

# Generate a timestamped snapshot path for a given context (pre-update, pre-rollback, ...).
snapshot_path() {
  local context="${1:-manual}"
  printf "%s/%s-%s.txt" "${SNAPSHOTS_DIR}" "${context}" "$(date '+%Y%m%d-%H%M%S')"
}

# Write current pip freeze to the given path. Echoes the path on success.
take_snapshot() {
  local path="$1"
  ensure_dirs
  as_frappe "$PIP" freeze > "${path}"
  chown frappe:frappe "${path}"
  chmod 644 "${path}"
  log "snapshot: ${path} ($(wc -l < "${path}") packages)"
  echo "${path}"
}

# Find the most recent snapshot in SNAPSHOTS_DIR. Echoes the path or empty.
latest_snapshot() {
  ls -t "${SNAPSHOTS_DIR}"/*.txt 2>/dev/null | head -1
}

# Kill any frappe-bench python workers that supervisor failed to stop.
# Best-effort: matches the worker entry-point pattern, won't kill bench CLI.
force_kill_frappe_workers() {
  local pids
  pids="$(pgrep -f "/home/frappe/frappe-bench/env/bin/python.*frappe.utils.bench_helper.*worker" 2>/dev/null || true)"
  if [ -n "${pids}" ]; then
    log "force-killing stuck frappe workers: $(echo ${pids} | tr '\n' ' ')"
    echo "${pids}" | xargs -r kill -9 2>/dev/null || true
  fi
}

# Stop a list of supervisor groups with a hard timeout. Force-kills stragglers.
# Args: timeout_sec, group_specs...   (e.g. safe_stop 15 frappe-bench-web: frappe-bench-workers:)
# Always returns 0 (best-effort).
safe_stop() {
  local timeout_s="$1"; shift
  log "supervisorctl stop (timeout=${timeout_s}s): $*"
  # `as_root` is a shell function — invoke it OUTSIDE timeout. Timeout is a binary
  # and can't run shell functions; so we put `timeout` INSIDE the elevated context.
  ( as_root timeout "${timeout_s}" supervisorctl stop "$@" 2>&1 | grep -v pkg_resources ) || \
    log "stop did not complete within ${timeout_s}s — will force-kill"
  force_kill_frappe_workers
  sleep 1
  return 0
}

# Start a list of supervisor groups, wait for them to be RUNNING.
# Args: timeout_sec, group_specs...
# Returns 0 if all expected processes RUNNING within timeout, 1 otherwise.
safe_start() {
  local timeout_s="$1"; shift
  log "supervisorctl start (timeout=${timeout_s}s): $*"
  if ! as_root timeout "${timeout_s}" supervisorctl start "$@" 2>&1 | grep -v pkg_resources; then
    log "start command failed or timed out"
    return 1
  fi
  local elapsed=0 running
  while [ "${elapsed}" -lt "${timeout_s}" ]; do
    running="$(count_running_supervisor)"
    if [ "${running}" -eq "${EXPECTED_SUPERVISOR_PROCESSES}" ]; then
      log "supervisor RUNNING (${running}/${EXPECTED_SUPERVISOR_PROCESSES}) after ${elapsed}s"
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  log "only ${running}/${EXPECTED_SUPERVISOR_PROCESSES} RUNNING after ${timeout_s}s"
  return 1
}

# Poll the local healthcheck endpoint until it returns 200, or timeout.
# Args: timeout_sec
# Returns 0 on first 200, 1 if never healthy.
wait_for_health() {
  local timeout_s="$1"
  local elapsed=0 code
  while [ "${elapsed}" -lt "${timeout_s}" ]; do
    code="$(local_healthcheck)"
    if [ "${code}" = "200" ]; then
      log "healthcheck OK (HTTP 200) after ${elapsed}s"
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  log "healthcheck never returned 200 (last code: ${code:-???}) within ${timeout_s}s"
  return 1
}

# Graceful supervisor restart: stop with timeout + force-kill, start with verify,
# then wait for healthcheck. THIS is what bench-update-safe and rollback should
# call instead of `supervisorctl restart` (which can hang on stuck workers).
# Returns 0 on full success, 1 if anything fails (caller should rollback).
safe_restart() {
  local stop_timeout="${1:-15}"
  local start_timeout="${2:-30}"
  local health_timeout="${3:-30}"
  local groups=("frappe-bench-web:" "frappe-bench-workers:")

  safe_stop "${stop_timeout}" "${groups[@]}"
  if ! safe_start "${start_timeout}" "${groups[@]}"; then
    return 1
  fi
  if ! wait_for_health "${health_timeout}"; then
    return 1
  fi
  return 0
}
