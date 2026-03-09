#!/bin/bash
# /etc/letsencrypt/renewal-hooks/deploy/sync-sandbox-cert-to-press-f1.sh
#
# PURPOSE: When certbot renews *.sandbox.mvpstorm.com cert on press-ctrl,
#          the new cert must be deployed to press-f1's agent tls/ directory.
#          press-f1 serves *.sandbox.mvpstorm.com sites so nginx + agent both
#          need the updated cert/key.
#
# DEPLOY on press-ctrl:
#   cp sync-sandbox-cert-to-press-f1.sh /etc/letsencrypt/renewal-hooks/deploy/
#   chmod +x /etc/letsencrypt/renewal-hooks/deploy/sync-sandbox-cert-to-press-f1.sh
#   certbot renew --dry-run   # verify it runs

CERT_DIR="/etc/letsencrypt/live/sandbox.mvpstorm.com"
PRESS_F1="root@89.167.57.21"
AGENT_TLS="/home/frappe/agent/tls"

# Only run when the sandbox cert was renewed
if [ "$RENEWED_LINEAGE" != "$CERT_DIR" ] && [ -n "$RENEWED_LINEAGE" ]; then
    exit 0
fi

echo "[$(date)] Syncing *.sandbox.mvpstorm.com cert to press-f1..."

scp -o StrictHostKeyChecking=no \
    "$CERT_DIR/fullchain.pem" "$PRESS_F1:$AGENT_TLS/fullchain.pem" && \
scp -o StrictHostKeyChecking=no \
    "$CERT_DIR/chain.pem" "$PRESS_F1:$AGENT_TLS/chain.pem" && \
scp -o StrictHostKeyChecking=no \
    "$CERT_DIR/privkey.pem" "$PRESS_F1:$AGENT_TLS/privkey.pem" || {
    echo "[$(date)] ERROR: scp failed"
    exit 1
}

# Fix permissions
ssh -o StrictHostKeyChecking=no "$PRESS_F1" \
    "chown frappe:frappe $AGENT_TLS/*.pem && chmod 600 $AGENT_TLS/privkey.pem && chmod 644 $AGENT_TLS/fullchain.pem $AGENT_TLS/chain.pem"

# Reload nginx
ssh -o StrictHostKeyChecking=no "$PRESS_F1" "nginx -t && systemctl reload nginx"

echo "[$(date)] Done. press-f1 cert updated."
