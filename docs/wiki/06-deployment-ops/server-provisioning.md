# Self-Hosted Server Provisioning Guide

## Overview

When a new server is created via the Press dashboard on a self-hosted cluster **without a Hetzner private network** (`cluster.vpc_id = NULL`) and **without a VM snapshot image** (`virtual_machine_image = NULL`), the server boots as bare Ubuntu and requires a manual bootstrap process.

This guide covers the complete bootstrap workflow and the automated scripts in `press/do_retry.py`.

---

## Why Manual Steps Are Needed

| Condition | Effect | Workaround |
|---|---|---|
| `cluster.vpc_id = NULL` | No Hetzner private network, no `eth1`, private IP not on any interface | Add private IP to loopback |
| `virtual_machine_image = NULL` | No cloud-init, bare Ubuntu, no agent/MariaDB/Redis | Run `setup_unified_server()` |
| Ansible `press_url` hardcoded | Agent config points to `frappecloud.com` | Update `config.json` post-install |
| `add_upstream_to_proxy()` uses private IP | Press-f1 proxy cannot route to new server | Add Nginx server block manually |

---

## Bootstrap Commands (Quick Reference)

Run on **press-ctrl** as the `frappe` user:

```bash
# Step 1: Add loopback IP + enqueue Ansible unified_server.yml
bench --site demo.mvpstorm.com execute press.do_retry.bootstrap_new_server \
  --args '["NEW_SERVER_NAME.sandbox.mvpstorm.com"]'

# Wait for the Press Job to complete (check Press > Jobs in dashboard)
# All steps must show Success or Skipped

# Step 2: Add Nginx proxy on press-f1 + fix press_url + verify ping
bench --site demo.mvpstorm.com execute press.do_retry.post_ansible_setup \
  --args '["NEW_SERVER_NAME.sandbox.mvpstorm.com"]'

# Confirm: should print {"message":"pong"}
bench --site demo.mvpstorm.com execute press.do_retry.ping_server_agent_authed \
  --args '["NEW_SERVER_NAME.sandbox.mvpstorm.com"]'
```

---

## Step-by-Step Detail

### Step 1: Bootstrap (before Ansible)

`bootstrap_new_server(server_name)` does:
1. SSH to the server's public IP as root
2. `ip addr add PRIVATE_IP/32 dev lo` — makes private IP available on loopback
3. `systemctl restart mariadb` — MariaDB can now bind to private IP
4. Calls `server.setup_unified_server()` — enqueues the Ansible `unified_server.yml` playbook

The Ansible playbook takes 5–15 minutes and runs ~190 tasks: installs agent, MariaDB config, Redis, Nginx, supervisor, SSL cert.

### Step 2: Post-Ansible Setup

`post_ansible_setup(server_name)` does:
1. `add_server_nginx_proxy()` — writes `/etc/nginx/conf.d/{slug}-agent.conf` on press-f1
   - Routes `https://SERVER_NAME/agent/` to `https://PUBLIC_IP:443/agent/`
   - Requires `proxy_ssl_protocols TLSv1.3` (agent Nginx is TLS 1.3 only)
2. `update_agent_press_url()` — updates `/home/frappe/agent/config.json` on the server
   - Changes `press_url` from `frappecloud.com` to your Press domain
   - Restarts agent via `supervisorctl restart all`
3. `ping_server_agent_authed()` — verifies agent responds with `{"message":"pong"}`

---

## Monitoring the Ansible Job

In the Press dashboard go to Press > Ansible Plays (or check Press Jobs). Find the latest play for your server. Status should progress: Running to Success.

Or via bench:
```bash
bench --site demo.mvpstorm.com execute frappe.client.get_list \
  --kwargs '{"doctype":"Ansible Play","fields":["name","status","server"],"order_by":"creation desc","limit_page_length":5}'
```

---

## Known Issues and Patches Applied

### 1. SSH CA Key (server.py + Ansible role)

**Problem:** `unified_server.yml` downloads CA key from `frappecloud.com/files/ca.pub` — returns HTTP 308 on self-hosted.

**Fix applied:**
- `press/playbooks/roles/user_ssh_certificate/tasks/main.yml` — accepts `ca_public_key` variable instead of downloading
- `press/press/doctype/server/server.py` — `_setup_unified_server()` passes the CA public key from `/home/frappe/.ssh/ssh_ca.pub` on press-ctrl

To regenerate the CA key:
```bash
ssh-keygen -t ed25519 -f /home/frappe/.ssh/ssh_ca -N "" -C "press-ca@demo.mvpstorm.com"
# Then update the hardcoded key in server.py _setup_unified_server() vars dict
```

### 2. Hetzner Network Null Guard (virtual_machine.py)

**Problem:** `attach_to_network()` called with `Network(id=0)` when `cluster.vpc_id = NULL` — Hetzner 422 error.

**Fix applied:** `if cluster.vpc_id:` guard around `attach_to_network()` call.

### 3. Security Group None Values (virtual_machine.py)

**Problem:** `get_security_groups()` returned `[None]` when `security_group_id = NULL` — resulted in `Firewall(id=0)`.

**Fix applied:** `return [g for g in groups if g]` filters out None values.

---

## Permanent Fixes (to eliminate manual steps)

| Fix | What it eliminates |
|---|---|
| Create Hetzner Network, set `cluster.vpc_id` | Loopback IP workaround for all future servers |
| Create Hetzner snapshot with full stack, set `virtual_machine_image` | Ansible bootstrap (servers boot ready) |
| Set correct `press_url` in Ansible vars | `update_agent_press_url()` step |
| Add private network routing to press-f1 | Nginx proxy manual step |
