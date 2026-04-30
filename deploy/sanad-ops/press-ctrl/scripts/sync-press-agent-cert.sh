#!/bin/bash
# sync-press-agent-cert.sh — certbot post-renewal hook
#
# Copies the renewed LE wildcard cert from /etc/letsencrypt/live/<DOMAIN>/
# into /home/frappe/agent/tls/{fullchain,privkey,agent-only-fullchain,
# agent-only-privkey}.pem, then reloads nginx.
#
# Drop into /etc/letsencrypt/renewal-hooks/deploy/ on every Press agent
# server. certbot calls every script in that dir on successful renewal.
#
# Idempotent: safe to run any time, not just from certbot.
#
# Logs to /var/log/cert-sync.log.

set -euo pipefail

DOMAIN="${PRESS_CERT_DOMAIN:-sandbox.mvpstorm.com}"
LE_DIR="/etc/letsencrypt/live/${DOMAIN}"
AGENT_TLS="/home/frappe/agent/tls"
LOG="/var/log/cert-sync.log"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "${LOG}" >&2
}

[ -d "${LE_DIR}" ] || { log "FATAL: ${LE_DIR} not found"; exit 1; }
[ -d "${AGENT_TLS}" ] || { log "FATAL: ${AGENT_TLS} not found"; exit 1; }

log "syncing ${DOMAIN} cert into ${AGENT_TLS}"

install -o frappe -g frappe -m 644 "${LE_DIR}/fullchain.pem" "${AGENT_TLS}/fullchain.pem"
install -o frappe -g frappe -m 600 "${LE_DIR}/privkey.pem"   "${AGENT_TLS}/privkey.pem"
install -o frappe -g frappe -m 644 "${LE_DIR}/fullchain.pem" "${AGENT_TLS}/agent-only-fullchain.pem"
install -o frappe -g frappe -m 600 "${LE_DIR}/privkey.pem"   "${AGENT_TLS}/agent-only-privkey.pem"

log "reloading system nginx"
nginx -t >/dev/null 2>&1 || { log "FATAL: nginx -t failed; not reloading"; exit 1; }
nginx -s reload || { log "FATAL: nginx reload failed (exit $?)"; exit 1; }

log "cert sync OK"
