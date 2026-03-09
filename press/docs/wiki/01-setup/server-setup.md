# Server Setup

Step-by-step guide for provisioning both servers from a fresh Ubuntu 22.04 VPS.

## Architecture Recap

| Server | Hostname | IP | Role |
|--------|----------|----|------|
| press-ctrl | press-ctrl | 89.167.116.92 | Press controller, Docker registry |
| press-f1 | press-f1.demo.mvpstorm.com | 89.167.57.21 | App server, DB, Proxy (standalone) |

---

## Server 1 — Press Controller

### 1. Install Frappe Bench

```bash
# Install system deps
apt-get update && apt-get install -y git python3-pip python3-dev redis-server mariadb-server \
  nodejs npm curl wkhtmltopdf

# Node 20+ required (Press dashboard uses Vite)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Install bench CLI
pip3 install frappe-bench

# Create frappe user
useradd -m -s /bin/bash frappe
```

### 2. Install Press

```bash
su - frappe
bench init frappe-bench --frappe-branch version-15
cd frappe-bench

# Get Press fork (cloudflare-dns branch)
bench get-app press https://github.com/accurate-systems/press --branch cloudflare-dns

# Create site
bench new-site demo.mvpstorm.com --db-root-password <mariadb-root-pass>

# Install Press
bench --site demo.mvpstorm.com install-app press

# CRITICAL: run migrate to create 142+ Scheduled Job Types
bench --site demo.mvpstorm.com migrate
```

### 3. Fix Python Dependencies

```bash
# Pin setuptools — razorpay uses pkg_resources (removed in setuptools 82+)
env/bin/pip install "setuptools<81"
```

### 4. Production Setup

```bash
# Run as root from /home/frappe/frappe-bench
pip3 install frappe-bench  # bench must be available to root
bench setup production frappe --yes

# Verify supervisor picked up config
ls -la /etc/supervisor/conf.d/
# If missing:
ln -sf /home/frappe/frappe-bench/config/supervisor.conf /etc/supervisor/conf.d/frappe-bench.conf
supervisorctl reread && supervisorctl update
```

### 5. SSL Certificates

```bash
# Install certbot + cloudflare plugin
apt-get install -y certbot python3-certbot-dns-cloudflare

# Create credentials file
mkdir -p /root/.cloudflare
cat > /root/.cloudflare/credentials.ini << EOF
dns_cloudflare_api_token = YOUR_TOKEN
EOF
chmod 600 /root/.cloudflare/credentials.ini

# Issue wildcard cert for dashboard subdomains
certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials /root/.cloudflare/credentials.ini \
  -d '*.demo.mvpstorm.com' -d 'demo.mvpstorm.com'

# Issue wildcard cert for sandbox (needed by additional servers like u4)
certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials /root/.cloudflare/credentials.ini \
  -d '*.sandbox.mvpstorm.com'

# Fix permissions so frappe user can read certs
chmod -R 755 /etc/letsencrypt/live/ /etc/letsencrypt/archive/
```

### 6. Docker Registry

```bash
# Start local registry on port 5000
docker run -d -p 5000:5000 --restart=always --name registry registry:2
```

### 7. site_config.json

```json
{
  "developer_mode": 1,
  "disable_mail_notifications": 1
}
```

`developer_mode = 1` routes build jobs to the "default" queue instead of the non-existent "build" queue. Required for self-hosted.

---

## Server 2 — App Server (Standalone)

### 1. Trigger Ansible Provisioning

From Press controller console:

```python
server = frappe.get_doc("Server", "press-f1.demo.mvpstorm.com")
server.setup_server()
# After setup_server completes:
server.setup_standalone()
```

**Order matters:** `setup_server` first, then `setup_standalone`. The standalone playbook assumes `/home/frappe/agent` already exists.

### 2. SSH Access from Server 1

```bash
# On Server 1: generate key if not present
ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519

# Add to Server 2
ssh-copy-id root@89.167.57.21
# Also add frappe user key
su - frappe -c "ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519"
# Copy frappe pub key to Server 2's frappe authorized_keys manually
```

### 3. Fix Server Status After Partial Ansible Failure

```python
# If status stuck at "Broken" but core setup completed:
server = frappe.get_doc("Server", "press-f1.demo.mvpstorm.com")
server.status = "Active"
server.is_server_setup = 1
server.save(ignore_permissions=True)
# Same for Database Server and Proxy Server records
```

### 4. Docker Insecure Registry

```bash
# On Server 2 — allow HTTP registry on Server 1
cat > /etc/docker/daemon.json << EOF
{"insecure-registries": ["89.167.116.92:5000"]}
EOF
systemctl restart docker
```

### 5. MariaDB Configuration

```bash
# Install if not installed by Ansible
apt-get install -y mariadb-server

# Allow remote connections
sed -i 's/bind-address.*/bind-address = 0.0.0.0/' /etc/mysql/mariadb.conf.d/50-server.cnf
systemctl restart mariadb

# Grant root from any host
mysql -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' IDENTIFIED BY '<password>' WITH GRANT OPTION; FLUSH PRIVILEGES;"
```

### 6. Agent Configuration

```bash
# /home/frappe/agent/config.json
{
  "name": "press-f1.demo.mvpstorm.com",
  "press_url": "https://demo.mvpstorm.com",    # MUST point to self-hosted Press
  "access_token": "<pbkdf2-sha256-hash>",
  "agent_type": "Server"
}
```

### 7. Agent SSL Certificate

Agent binds on port 443 using certs in `/home/frappe/agent/tls/`. The cert must match the server's hostname in Press.

```bash
# For press-f1.demo.mvpstorm.com — uses *.demo.mvpstorm.com cert
scp /etc/letsencrypt/live/demo.mvpstorm.com/fullchain.pem root@89.167.57.21:/home/frappe/agent/tls/
scp /etc/letsencrypt/live/demo.mvpstorm.com/privkey.pem root@89.167.57.21:/home/frappe/agent/tls/
chown frappe:frappe /home/frappe/agent/tls/*.pem
```

**Important:** If the server's DNS name is on a different subdomain (e.g., `*.sandbox.mvpstorm.com`), use the matching cert. A `*.demo.mvpstorm.com` cert does NOT cover `press-f1.sandbox.mvpstorm.com`.

---

## Agent Authentication

Press stores agent passwords in the `__Auth` table (encrypted). The agent stores a PBKDF2-SHA256 hash of that password in `config.json`.

### Fixing Mismatched Passwords

```python
# 1. Get plaintext password from Press DB
import frappe
frappe.init(site="demo.mvpstorm.com")
frappe.connect()
pwd = frappe.get_decrypted_password("Server", "press-f1.demo.mvpstorm.com", "agent_password")
print(pwd)
```

```python
# 2. Generate the PBKDF2 hash (run on agent server)
from passlib.hash import pbkdf2_sha256
new_hash = pbkdf2_sha256.using(rounds=29000).hash("PLAINTEXT_PASSWORD")
print(new_hash)
```

```bash
# 3. Update agent config
# Edit /home/frappe/agent/config.json — set access_token to new_hash
supervisorctl restart agent:web
```

```bash
# 4. Verify
curl -u 'press-f1.demo.mvpstorm.com:PLAINTEXT_PASSWORD' http://127.0.0.1:25052/ping
# Expected: {"message": "pong"}
```

**Critical:** In standalone mode, Server and Proxy Server are separate records — each has its own `agent_password` in `__Auth`. Both must match the single `access_token` in agent config.

---

## Certbot Renewal Hooks

If a server uses a cert from a different domain (e.g., sandbox cert deployed to press-f1), install a deploy hook to auto-sync on renewal:

```bash
# /etc/letsencrypt/renewal-hooks/deploy/sync-sandbox-cert-to-press-f1.sh
#!/bin/bash
CERT_DIR="/etc/letsencrypt/live/sandbox.mvpstorm.com"
PRESS_F1="root@89.167.57.21"
AGENT_TLS="/home/frappe/agent/tls"
[ "$RENEWED_LINEAGE" != "$CERT_DIR" ] && [ -n "$RENEWED_LINEAGE" ] && exit 0
scp -o StrictHostKeyChecking=no "$CERT_DIR"/{fullchain,chain,privkey}.pem "$PRESS_F1:$AGENT_TLS/"
ssh "$PRESS_F1" "chown frappe:frappe $AGENT_TLS/*.pem && nginx -t && systemctl reload nginx"
```

```bash
chmod +x /etc/letsencrypt/renewal-hooks/deploy/sync-sandbox-cert-to-press-f1.sh
```
