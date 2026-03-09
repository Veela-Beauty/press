# Adding Servers

How to add a new app server to Press and configure it for site hosting.

## TL;DR — Use the Provisioning Script

After creating the 3 DocType records and running Ansible, use `scripts/provision-server.sh`
to automate all 13 post-Ansible steps in one command:

```bash
# From press-ctrl
./scripts/provision-server.sh \
  --ip NEW_SERVER_IP \
  --hostname press-u4.sandbox.mvpstorm.com \
  --cert-domain sandbox.mvpstorm.com \
  --press-site demo.mvpstorm.com \
  --registry 89.167.116.92:5000 \
  --team TEAM_HASH
```

The script handles: SSL cert deploy, certbot renewal hook, press_url, agent PBKDF2 hash sync
(for all 3 server records), Docker insecure registry, MariaDB check, team assignment, and nginx reload.

See `scripts/README.md` for full details.

---

## When to Add a Server

- Scaling: the standalone server (press-f1) is at capacity
- Isolation: a customer needs a dedicated server
- Redundancy: distributing sites across servers
- Geo: hosting sites in a different region

---

## Step 1: Provision the VPS

Requirements:
- Ubuntu 22.04
- Minimum 4 vCPU, 8GB RAM (for production use)
- SSH key access from press-ctrl (Server 1)
- Public IP

```bash
# On press-ctrl: add SSH key to new server
ssh-copy-id root@NEW_SERVER_IP
ssh-copy-id -i /home/frappe/.ssh/id_ed25519.pub frappe@NEW_SERVER_IP  # if frappe user exists
```

---

## Step 2: Configure DNS

Add an A record in Cloudflare for the new server:

```
press-u4.sandbox.mvpstorm.com → NEW_SERVER_IP
```

Choose the hostname pattern based on the cluster:
- Main cluster: `press-f2.demo.mvpstorm.com`
- Sandbox cluster: `press-u4.sandbox.mvpstorm.com`

**SSL cert scope:** The TLS cert issued for the server must cover its hostname. `*.demo.mvpstorm.com` does NOT cover `*.sandbox.mvpstorm.com`. Issue a separate wildcard cert if needed:

```bash
# On press-ctrl
certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials /root/.cloudflare/credentials.ini \
  -d '*.sandbox.mvpstorm.com'

chmod -R 755 /etc/letsencrypt/live/ /etc/letsencrypt/archive/
```

---

## Step 3: Create Press Records

In standalone mode, each physical server needs THREE DocType records. All three must have the same `team` as the dashboard user.

```python
team = frappe.get_all("Team", filters={"user": "test@mvpstorm.com"}, pluck="name")[0]
server_name = "press-u4.sandbox.mvpstorm.com"

# 1. Database Server
db_server = frappe.get_doc({
    "doctype": "Database Server",
    "name": server_name,
    "title": "U4 Database Server",
    "ip": "NEW_SERVER_IP",
    "private_ip": "NEW_SERVER_IP",
    "cluster": "Default",
    "team": team,
    "mariadb_root_password": "<root-db-password>"
})
db_server.insert()

# 2. Proxy Server
proxy = frappe.get_doc({
    "doctype": "Proxy Server",
    "name": server_name,
    "title": "U4 Proxy Server",
    "ip": "NEW_SERVER_IP",
    "private_ip": "NEW_SERVER_IP",
    "cluster": "Default",
    "team": team
})
proxy.insert()

# 3. App Server (links to DB + Proxy)
server = frappe.get_doc({
    "doctype": "Server",
    "name": server_name,
    "title": "U4 App Server",
    "ip": "NEW_SERVER_IP",
    "private_ip": "NEW_SERVER_IP",
    "cluster": "Default",
    "team": team,
    "database_server": server_name,
    "proxy_server": server_name,
    "use_for_build": 0   # set 1 if you want builds here too
})
server.insert()

frappe.db.commit()
```

---

## Step 4: Run Ansible Provisioning

```python
# From bench console on press-ctrl
server = frappe.get_doc("Server", "press-u4.sandbox.mvpstorm.com")

# This installs agent, nginx, docker, redis on the new server
server.setup_server()

# Wait for setup_server to complete (check Agent Jobs), then:
server.setup_standalone()
```

Monitor:
```bash
bench --site demo.mvpstorm.com execute frappe.client.get_list \
  --kwargs '{"doctype": "Agent Job", "filters": {"server": "press-u4.sandbox.mvpstorm.com"}, "fields": ["name", "job_type", "status"], "order_by": "creation desc", "limit_page_length": 10}'
```

---

## Step 5: Fix Agent Authentication

After Ansible completes, the agent will have a random `access_token`. Press doesn't know it yet.

```python
# 1. Get the password Press generated for this server
import frappe
frappe.init(site="demo.mvpstorm.com")
frappe.connect()
pwd = frappe.get_decrypted_password("Server", "press-u4.sandbox.mvpstorm.com", "agent_password")
print(pwd)
```

```python
# 2. On the new server — update agent config with PBKDF2 hash
from passlib.hash import pbkdf2_sha256
new_hash = pbkdf2_sha256.using(rounds=29000).hash("PLAINTEXT_PASSWORD_FROM_ABOVE")

# Update /home/frappe/agent/config.json → access_token = new_hash
```

```bash
# 3. Restart agent on new server
supervisorctl restart agent:web

# 4. Verify
curl -u 'press-u4.sandbox.mvpstorm.com:PLAINTEXT_PASSWORD' http://127.0.0.1:25052/ping
```

**Remember:** Database Server and Proxy Server also have separate `agent_password` values in `__Auth`. All three must be synced to the single agent `access_token`.

---

## Step 6: Deploy SSL Cert to Agent

```bash
# From press-ctrl — copy matching wildcard cert to agent's TLS dir
scp /etc/letsencrypt/live/sandbox.mvpstorm.com/{fullchain,chain,privkey}.pem \
  root@NEW_SERVER_IP:/home/frappe/agent/tls/

ssh root@NEW_SERVER_IP \
  "chown frappe:frappe /home/frappe/agent/tls/*.pem && nginx -t && systemctl reload nginx"
```

---

## Step 7: Add Renewal Hook

Install a certbot deploy hook on press-ctrl to auto-sync the cert on renewal:

```bash
cat > /etc/letsencrypt/renewal-hooks/deploy/sync-sandbox-cert-to-u4.sh << 'EOF'
#!/bin/bash
CERT_DIR="/etc/letsencrypt/live/sandbox.mvpstorm.com"
TARGET="root@NEW_SERVER_IP"
AGENT_TLS="/home/frappe/agent/tls"
[ "$RENEWED_LINEAGE" != "$CERT_DIR" ] && [ -n "$RENEWED_LINEAGE" ] && exit 0
scp -o StrictHostKeyChecking=no "$CERT_DIR"/{fullchain,chain,privkey}.pem "$TARGET:$AGENT_TLS/"
ssh "$TARGET" "chown frappe:frappe $AGENT_TLS/*.pem && nginx -t && systemctl reload nginx"
EOF
chmod +x /etc/letsencrypt/renewal-hooks/deploy/sync-sandbox-cert-to-u4.sh
```

---

## Step 8: Fix Server Status

If Ansible had partial failures but core setup succeeded:

```python
for dt in ["Server", "Database Server", "Proxy Server"]:
    doc = frappe.get_doc(dt, "press-u4.sandbox.mvpstorm.com")
    doc.status = "Active"
    doc.is_server_setup = 1
    doc.save(ignore_permissions=True)
frappe.db.commit()
```

---

## Step 9: Add Docker Insecure Registry

On the new server:

```bash
cat > /etc/docker/daemon.json << EOF
{"insecure-registries": ["89.167.116.92:5000"]}
EOF
systemctl restart docker
```

---

## Step 10: Assign Sites to New Server

When creating a Release Group that targets the new server:

```python
rg = frappe.get_doc("Release Group", "<release_group_name>")
rg.append("servers", {"server": "press-u4.sandbox.mvpstorm.com"})
rg.save()
```

New sites created from this Release Group will be hosted on the new server.

---

## Verification

1. `/ping` on new agent returns 200 OK
2. Press Agent Jobs complete with "Success" status
3. Can create a site on the new server from dashboard
4. Site becomes "Active" and is accessible
