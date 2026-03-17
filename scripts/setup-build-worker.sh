#!/bin/bash
# setup-build-worker.sh
#
# PURPOSE: Add a dedicated "build" queue worker to the Frappe bench.
#          This replaces the developer_mode=1 workaround (lesson 16).
#
#          Without this: builds use "default" queue and block all other background jobs.
#          With this: builds get their own worker with a 40-minute timeout.
#
# DEPLOY on press-ctrl:
#   chmod +x setup-build-worker.sh
#   ./setup-build-worker.sh
#
# AFTER running this script:
#   1. Remove developer_mode=1 from site_config.json
#   2. bench --site demo.mvpstorm.com set-config -d developer_mode
#   3. Verify builds still work: create a Deploy Candidate and build

set -euo pipefail

BENCH_DIR="/home/frappe/frappe-bench"
PRESS_SITE="demo.mvpstorm.com"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "=== Setting up dedicated build worker ==="

# Step 1: Add build worker to common_site_config.json
log "Step 1: Configuring build worker in common_site_config.json..."
sudo -u frappe bash -c "cd ${BENCH_DIR} && python3 << 'EOF'
import json, os

config_file = 'sites/common_site_config.json'
with open(config_file) as f:
    cfg = json.load(f)

# Add build worker with 40-minute timeout (builds can take 20-30 min)
workers = cfg.get('workers', {})
workers['build'] = {'timeout': 2400}
cfg['workers'] = workers

with open(config_file, 'w') as f:
    json.dump(cfg, f, indent='\t')

print('common_site_config.json updated with build worker')
print('Workers config:', json.dumps(cfg['workers'], indent=2))
EOF"

# Step 2: Regenerate supervisor config to include build worker
log "Step 2: Regenerating supervisor config..."
sudo -u frappe bash -c "cd ${BENCH_DIR} && bench setup supervisor --yes 2>&1 | tail -5"

# Step 3: Re-link supervisor config (may have been overwritten)
if [ ! -L /etc/supervisor/conf.d/frappe-bench.conf ]; then
  ln -sf "${BENCH_DIR}/config/supervisor.conf" /etc/supervisor/conf.d/frappe-bench.conf
fi

# Step 4: Reload supervisor to pick up new worker
log "Step 3: Reloading supervisor..."
supervisorctl reread
supervisorctl update

# Step 5: Verify build worker is running
log "Step 4: Verifying build worker..."
sleep 2
if supervisorctl status | grep -q "build.*RUNNING"; then
  log "  Build worker: RUNNING"
else
  log "  WARNING: Build worker not showing as RUNNING. Check: supervisorctl status"
  supervisorctl status | grep -i "build" || echo "  (no build worker found in supervisor status)"
fi

# Step 6: Remove developer_mode workaround
log "Step 5: Removing developer_mode workaround..."
sudo -u frappe bash -c "cd ${BENCH_DIR} && bench --site ${PRESS_SITE} set-config -d developer_mode 2>/dev/null && echo 'developer_mode removed from site_config.json' || echo 'WARNING: Could not remove developer_mode — remove manually'"

log ""
log "=== Build worker setup complete ==="
log ""
log "VERIFICATION:"
log "  supervisorctl status | grep build"
log "  Create a Deploy Candidate and trigger a build — should use 'build' queue now"
log "  Check: bench --site ${PRESS_SITE} execute frappe.utils.background_jobs.get_jobs --args '[\"build\"]'"
