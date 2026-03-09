#!/bin/bash
# provision-server.sh
#
# PURPOSE: Automate all 13 PER-SERVER steps when adding a new app server to Press.
#          Run this from press-ctrl AFTER creating the 3 DocType records (Server,
#          Database Server, Proxy Server) and AFTER Ansible setup_server + setup_standalone.
#
# USAGE:
#   chmod +x provision-server.sh
#   ./provision-server.sh \
#     --ip 157.90.244.216 \
#     --hostname u4-default.sandbox.mvpstorm.com \
#     --cert-domain sandbox.mvpstorm.com \
#     --press-site demo.mvpstorm.com \
#     --registry 89.167.116.92:5000 \
#     --team <team_hash>
#
# PREREQUISITES:
#   - SSH key from press-ctrl to the new server is already set up
#   - Server, Database Server, Proxy Server DocType records already created in Press
#   - Ansible setup_server + setup_standalone already completed (or manually done)
#   - Wildcard cert for --cert-domain already issued by certbot on press-ctrl

set -euo pipefail

# --- Argument parsing ---
IP=""
HOSTNAME=""
CERT_DOMAIN=""
PRESS_SITE="demo.mvpstorm.com"
REGISTRY="89.167.116.92:5000"
TEAM=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ip) IP="$2"; shift 2 ;;
    --hostname) HOSTNAME="$2"; shift 2 ;;
    --cert-domain) CERT_DOMAIN="$2"; shift 2 ;;
    --press-site) PRESS_SITE="$2"; shift 2 ;;
    --registry) REGISTRY="$2"; shift 2 ;;
    --team) TEAM="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$IP" || -z "$HOSTNAME" || -z "$CERT_DOMAIN" || -z "$TEAM" ]]; then
  echo "ERROR: --ip, --hostname, --cert-domain, and --team are required"
  exit 1
fi

BENCH_DIR="/home/frappe/frappe-bench"
AGENT_TLS="/home/frappe/agent/tls"
CERT_DIR="/etc/letsencrypt/live/${CERT_DOMAIN}"

log() { echo "[$(date '+%H:%M:%S')] $*"; }
run_on_server() { ssh -o StrictHostKeyChecking=no "root@${IP}" "$@"; }

log "=== Provisioning ${HOSTNAME} (${IP}) ==="

# Step 1: Verify SSH access
log "Step 1/13: Verifying SSH access..."
run_on_server "echo 'SSH OK'"

# Step 2: Deploy SSL cert to agent tls/
log "Step 2/13: Deploying SSL cert (${CERT_DOMAIN}) to agent..."
scp -o StrictHostKeyChecking=no \
  "${CERT_DIR}/fullchain.pem" \
  "${CERT_DIR}/chain.pem" \
  "${CERT_DIR}/privkey.pem" \
  "root@${IP}:${AGENT_TLS}/"
run_on_server "chown frappe:frappe ${AGENT_TLS}/*.pem"
log "  SSL cert deployed"

# Step 3: Install certbot renewal hook for this server
log "Step 3/13: Installing certbot renewal hook..."
HOOK_FILE="/etc/letsencrypt/renewal-hooks/deploy/sync-${CERT_DOMAIN//\./-}-to-${IP//./-}.sh"
cat > "${HOOK_FILE}" << HOOKEOF
#!/bin/bash
CERT_DIR="/etc/letsencrypt/live/${CERT_DOMAIN}"
TARGET="root@${IP}"
AGENT_TLS="${AGENT_TLS}"
[ "\$RENEWED_LINEAGE" != "\$CERT_DIR" ] && [ -n "\$RENEWED_LINEAGE" ] && exit 0
scp -o StrictHostKeyChecking=no "\$CERT_DIR"/{fullchain,chain,privkey}.pem "\$TARGET:\$AGENT_TLS/"
ssh "\$TARGET" "chown frappe:frappe \$AGENT_TLS/*.pem && nginx -t && systemctl reload nginx"
HOOKEOF
chmod +x "${HOOK_FILE}"
log "  Hook installed: ${HOOK_FILE}"

# Step 4: Set press_url in agent config
log "Step 4/13: Setting press_url in agent config..."
run_on_server "python3 -c \"
import json
with open('/home/frappe/agent/config.json', 'r') as f:
    cfg = json.load(f)
cfg['press_url'] = 'https://${PRESS_SITE}'
with open('/home/frappe/agent/config.json', 'w') as f:
    json.dump(cfg, f, indent=2)
print('press_url set to https://${PRESS_SITE}')
\""

# Step 5: Get agent_password from Press DB and sync to agent (all 3 server records)
log "Step 5/13: Syncing agent auth (PBKDF2 hash) for Server + Database Server + Proxy Server..."

# Use a temp Python script — never interpolate passwords into shell/Python code strings.
# Passwords may contain quotes or special chars that break inline code execution.
TMPSCRIPT=$(mktemp /tmp/press-provision-XXXXXX.py)
cat > "${TMPSCRIPT}" << PYEOF
import sys, os
sys.path.insert(0, '${BENCH_DIR}/apps/frappe')
import frappe
frappe.init(site='${PRESS_SITE}', sites_path='${BENCH_DIR}/sites')
frappe.connect()
try:
    pwd = frappe.get_decrypted_password('Server', '${HOSTNAME}', 'agent_password')
    print(pwd)
except Exception as e:
    sys.stderr.write('ERROR: ' + str(e) + '\n')
    print('')
frappe.destroy()
PYEOF

PLAINTEXT=$(sudo -u frappe bash -c "cd ${BENCH_DIR} && python3 ${TMPSCRIPT}" 2>/dev/null | tail -1)
rm -f "${TMPSCRIPT}"

if [[ -z "$PLAINTEXT" ]]; then
  log "  WARNING: Could not read agent_password — sync manually:"
  log "    1. frappe.get_decrypted_password('Server', '${HOSTNAME}', 'agent_password')"
  log "    2. pbkdf2_sha256.using(rounds=29000).hash(PLAINTEXT) → write to agent config.json"
  log "    3. Repeat for 'Database Server' and 'Proxy Server' records"
else
  # Generate hash safely — password via env var, never interpolated into code
  NEW_HASH=$(AGENT_PWD="${PLAINTEXT}" python3 -c "
import os; from passlib.hash import pbkdf2_sha256
print(pbkdf2_sha256.using(rounds=29000).hash(os.environ['AGENT_PWD']))")

  # Update agent config.json on remote — hash passed via env var
  NEW_HASH="${NEW_HASH}" run_on_server bash -s << 'REMOTE'
python3 -c "
import json, os
with open('/home/frappe/agent/config.json') as f:
    cfg = json.load(f)
cfg['access_token'] = os.environ['NEW_HASH']
with open('/home/frappe/agent/config.json', 'w') as f:
    json.dump(cfg, f, indent=2)
print('access_token updated')
"
REMOTE
  log "  Agent access_token updated"

  # CRITICAL (Lesson 25): Proxy Server and Database Server each have a SEPARATE agent_password
  # in __Auth table. All three records must match the single agent access_token.
  log "  Syncing Database Server + Proxy Server __Auth passwords to same value..."
  for DOCTYPE in "Database Server" "Proxy Server"; do
    TMPSET=$(mktemp /tmp/press-setpwd-XXXXXX.py)
    cat > "${TMPSET}" << PYEOF2
import sys, os
sys.path.insert(0, '${BENCH_DIR}/apps/frappe')
import frappe
frappe.init(site='${PRESS_SITE}', sites_path='${BENCH_DIR}/sites')
frappe.connect()
frappe.set_value('${DOCTYPE}', '${HOSTNAME}', 'agent_password', os.environ['AGENT_PWD'])
frappe.db.commit()
print('${DOCTYPE} password synced')
frappe.destroy()
PYEOF2
    AGENT_PWD="${PLAINTEXT}" sudo -u frappe bash -c "cd ${BENCH_DIR} && python3 ${TMPSET}" 2>/dev/null \
      || log "  WARNING: Could not sync '${DOCTYPE}' — do manually"
    rm -f "${TMPSET}"
  done
  log "  All 3 record passwords synced"
fi

# Step 6: Restart agent
log "Step 6/13: Restarting agent..."
run_on_server "supervisorctl restart agent:web"
sleep 3

# Step 7: Verify agent /ping (only if we have the plaintext password)
log "Step 7/13: Verifying agent /ping..."
if [[ -n "$PLAINTEXT" ]]; then
  PING_STATUS=$(AGENT_PWD="${PLAINTEXT}" run_on_server bash -c \
    "curl -s -o /dev/null -w '%{http_code}' -u '${HOSTNAME}:\${AGENT_PWD}' http://127.0.0.1:25052/ping" 2>/dev/null || echo "000")
  if [[ "$PING_STATUS" == "200" ]]; then
    log "  Agent /ping: 200 OK"
  else
    log "  WARNING: Agent /ping returned ${PING_STATUS} — check auth manually"
  fi
else
  log "  SKIPPED: No plaintext password available — verify /ping manually after syncing auth"
fi

# Step 8: Verify SSL cert matches hostname
log "Step 8/13: Verifying SSL cert..."
CERT_CN=$(run_on_server "openssl x509 -noout -subject < ${AGENT_TLS}/fullchain.pem 2>/dev/null | grep -o 'CN=[^,]*' | head -1")
log "  Cert CN: ${CERT_CN}"

# Step 9: Configure Docker insecure registry
log "Step 9/13: Configuring Docker insecure registry..."
run_on_server "python3 -c \"
import json, os
daemon_file = '/etc/docker/daemon.json'
cfg = {}
if os.path.exists(daemon_file):
    with open(daemon_file) as f:
        cfg = json.load(f)
registries = cfg.get('insecure-registries', [])
if '${REGISTRY}' not in registries:
    registries.append('${REGISTRY}')
    cfg['insecure-registries'] = registries
    with open(daemon_file, 'w') as f:
        json.dump(cfg, f, indent=2)
    print('Added ${REGISTRY} to insecure-registries')
else:
    print('${REGISTRY} already in insecure-registries')
\""
run_on_server "systemctl restart docker && sleep 2 && docker info --format '{{.RegistryConfig.InsecureRegistryCIDRs}}' || true"
log "  Docker registry configured"

# Step 10: Verify MariaDB is running
log "Step 10/13: Verifying MariaDB..."
DB_STATUS=$(run_on_server "systemctl is-active mariadb 2>/dev/null || echo 'inactive'")
if [[ "$DB_STATUS" == "active" ]]; then
  log "  MariaDB: active"
else
  log "  WARNING: MariaDB is ${DB_STATUS} — installing..."
  run_on_server "apt-get install -y mariadb-server && systemctl enable --now mariadb"
  log "  MariaDB installed and started"
fi

# Step 11: Set team on Server records
log "Step 11/13: Setting team=${TEAM} on Server records..."
sudo -u frappe bash -c "cd ${BENCH_DIR} && bench --site ${PRESS_SITE} execute frappe.db.sql \
  --args '[\"UPDATE \\\`tabServer\\\` SET team=\\\"${TEAM}\\\" WHERE name=\\\"${HOSTNAME}\\\"\"]'" 2>/dev/null || true
sudo -u frappe bash -c "cd ${BENCH_DIR} && bench --site ${PRESS_SITE} execute frappe.db.sql \
  --args '[\"UPDATE \\\`tabDatabase Server\\\` SET team=\\\"${TEAM}\\\" WHERE name=\\\"${HOSTNAME}\\\"\"]'" 2>/dev/null || true
sudo -u frappe bash -c "cd ${BENCH_DIR} && bench --site ${PRESS_SITE} execute frappe.db.sql \
  --args '[\"UPDATE \\\`tabProxy Server\\\` SET team=\\\"${TEAM}\\\" WHERE name=\\\"${HOSTNAME}\\\"\"]'" 2>/dev/null || true
log "  Team set on all three records"

# Step 12: Check disk space
log "Step 12/13: Checking disk space..."
DISK_USAGE=$(run_on_server "df -h / | awk 'NR==2 {print \$5}' | tr -d '%'")
log "  Disk usage: ${DISK_USAGE}%"
if [[ "$DISK_USAGE" -gt 70 ]]; then
  log "  WARNING: Disk usage over 70% — consider cleanup before adding sites"
fi

# Step 13: Nginx reload to pick up new cert
log "Step 13/13: Reloading nginx..."
run_on_server "nginx -t && systemctl reload nginx"

log ""
log "=== Provisioning complete for ${HOSTNAME} ==="
log ""
log "POST-PROVISION CHECKLIST:"
log "  [ ] Create a test site on this server from the dashboard"
log "  [ ] Verify site reaches Active status"
log "  [ ] Run post-task verification: press/docs/wiki/02-operations/platform-risk-checklist.md"
log "  [ ] Add server to platform-risk-checklist.md server inventory table"
