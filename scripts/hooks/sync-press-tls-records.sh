#!/bin/bash
# /etc/letsencrypt/renewal-hooks/deploy/sync-press-tls-records.sh
#
# PURPOSE: When certbot renews a wildcard cert, Press TLS Certificate records in the
#          DB still show the old expiry date. Press may try to re-renew unnecessarily,
#          or show stale cert warnings in the dashboard.
#          This hook reads the real expiry from the new cert and updates Press DB records.
#
# DEPLOY on press-ctrl:
#   cp sync-press-tls-records.sh /etc/letsencrypt/renewal-hooks/deploy/
#   chmod +x /etc/letsencrypt/renewal-hooks/deploy/sync-press-tls-records.sh
#   certbot renew --dry-run   # verify it runs

set -e

BENCH_DIR="/home/frappe/frappe-bench"
PRESS_SITE="demo.mvpstorm.com"

# Only run if there is a renewed cert
[ -z "$RENEWED_LINEAGE" ] && CERT_DIR="" || CERT_DIR="$RENEWED_LINEAGE"
[ -z "$CERT_DIR" ] && exit 0

CERT_FILE="${CERT_DIR}/fullchain.pem"
[ ! -f "$CERT_FILE" ] && exit 0

# Read actual expiry from the renewed cert
EXPIRES_ON=$(openssl x509 -noout -enddate -in "$CERT_FILE" 2>/dev/null \
  | sed 's/notAfter=//' \
  | python3 -c "import sys; from datetime import datetime; d = datetime.strptime(sys.stdin.read().strip(), '%b %d %H:%M:%S %Y %Z'); print(d.strftime('%Y-%m-%d'))")

CERT_DOMAIN=$(openssl x509 -noout -subject -in "$CERT_FILE" 2>/dev/null \
  | grep -o 'CN=[^,]*' | sed 's/CN=//' | sed 's/\*\.//')

if [ -z "$EXPIRES_ON" ] || [ -z "$CERT_DOMAIN" ]; then
  echo "[$(date)] sync-press-tls-records: Could not parse cert data from ${CERT_FILE}"
  exit 0
fi

echo "[$(date)] sync-press-tls-records: Cert for *.${CERT_DOMAIN} renewed, expires ${EXPIRES_ON}"

# Update matching Press TLS Certificate records
TMPSCRIPT=$(mktemp /tmp/press-tls-sync-XXXXXX.py)
cat > "${TMPSCRIPT}" << PYEOF
import sys
sys.path.insert(0, '${BENCH_DIR}/apps/frappe')
import frappe
frappe.init(site='${PRESS_SITE}', sites_path='${BENCH_DIR}/sites')
frappe.connect()

expires_on = '${EXPIRES_ON}'
cert_domain = '${CERT_DOMAIN}'

# Find TLS Certificate records whose domain matches the renewed cert
records = frappe.get_all('TLS Certificate',
    filters={'domain': ('like', f'%.{cert_domain}')},
    fields=['name', 'domain', 'expires_on', 'wildcard']
)

updated = 0
for rec in records:
    if rec['expires_on'] and str(rec['expires_on']) >= expires_on:
        continue  # already up to date
    frappe.db.set_value('TLS Certificate', rec['name'], {
        'expires_on': expires_on,
        'tls_certificate_renewal_failed': 0,
    })
    print(f"Updated TLS Certificate {rec['name']} ({rec['domain']}) expires_on → {expires_on}")
    updated += 1

frappe.db.commit()
print(f"Done. Updated {updated} of {len(records)} TLS Certificate records.")
frappe.destroy()
PYEOF

sudo -u frappe bash -c "cd ${BENCH_DIR} && python3 ${TMPSCRIPT}" 2>&1 \
  || echo "[$(date)] sync-press-tls-records: WARNING — failed to update Press DB records. Run manually."
rm -f "${TMPSCRIPT}"

echo "[$(date)] sync-press-tls-records: Done"
