# Ops Toolkit (press/do_retry.py)

`press/do_retry.py` on **press-ctrl** is the operations script for self-hosted Press server management. All functions are callable via `bench execute`.

## Usage Pattern

```bash
bench --site demo.mvpstorm.com execute press.do_retry.FUNCTION_NAME --args '["arg1", "arg2"]'
```

---

## Functions

### `bootstrap_new_server(server_name)`

One-shot bootstrap for a new bare server (no cloud-init). Adds private IP to loopback, restarts MariaDB, then enqueues `setup_unified_server()`.

```bash
bench --site demo.mvpstorm.com execute press.do_retry.bootstrap_new_server \
  --args '["u5-default.sandbox.mvpstorm.com"]'
```

### `post_ansible_setup(server_name, press_url, proxy_server_name)`

Run after Ansible unified_server.yml completes. Adds Nginx proxy block on press-f1, updates agent press_url, verifies ping.

```bash
bench --site demo.mvpstorm.com execute press.do_retry.post_ansible_setup \
  --args '["u5-default.sandbox.mvpstorm.com"]'
# Optional: override press_url and proxy server name
bench --site demo.mvpstorm.com execute press.do_retry.post_ansible_setup \
  --args '["u5-default.sandbox.mvpstorm.com", "https://demo.mvpstorm.com", "press-f1.sandbox.mvpstorm.com"]'
```

### `add_server_nginx_proxy(server_name, proxy_server_name)`

Writes `/etc/nginx/conf.d/{slug}-agent.conf` on press-f1 and reloads Nginx. Proxies `/agent/` to the server's public IP. Also calls `server.add_upstream_to_proxy()` to register in Press DB.

### `update_agent_press_url(server_name, press_url)`

Updates `press_url` in `/home/frappe/agent/config.json` on the server and restarts the agent.

```bash
bench --site demo.mvpstorm.com execute press.do_retry.update_agent_press_url \
  --args '["u5-default.sandbox.mvpstorm.com", "https://demo.mvpstorm.com"]'
```

### `ping_server_agent_authed(server_name)`

Pings the agent endpoint with auth credentials from Press DB. Returns `{"message":"pong"}` if agent is reachable and running.

```bash
bench --site demo.mvpstorm.com execute press.do_retry.ping_server_agent_authed \
  --args '["u5-default.sandbox.mvpstorm.com"]'
```

### `get_agent_password(server_name)`

Returns the decrypted agent password from Press DB (the `agent_password` Password field).

### `ping_server_agent(server_name)`

Unauthenticated ping — returns 401 if agent is running (routing works), connection error if unreachable.

### `_ssh(ip, cmd, user)`

Internal SSH helper. Runs a command on a remote host via subprocess. Used by all functions above.

---

## Notes

- All SSH calls use `/home/frappe/.ssh/id_ed25519` (the key registered in Hetzner)
- Default proxy server: `press-f1.sandbox.mvpstorm.com`
- Default press URL: `https://demo.mvpstorm.com`
- Agent auth uses HTTP Basic with `Administrator:AGENT_PASSWORD`
- Agent password is stored encrypted in Press DB; use `doc.get_password("agent_password")` to decrypt
