#!/bin/bash
# /etc/letsencrypt/renewal-hooks/post/fix-letsencrypt-permissions.sh
#
# PURPOSE: Certbot resets /etc/letsencrypt permissions to 700 after every renewal.
#          The frappe user needs 755 to read certs for TLS provisioning.
#          This post-hook runs after EVERY cert renewal and restores the permissions.
#
# DEPLOY:
#   cp fix-letsencrypt-permissions.sh /etc/letsencrypt/renewal-hooks/post/
#   chmod +x /etc/letsencrypt/renewal-hooks/post/fix-letsencrypt-permissions.sh
#   certbot renew --dry-run  # verify it runs

set -e

chmod -R 755 /etc/letsencrypt/live/
chmod -R 755 /etc/letsencrypt/archive/

echo "[$(date)] letsencrypt permissions restored: /etc/letsencrypt/live/ and /archive/ set to 755"
