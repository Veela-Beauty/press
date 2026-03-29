"""
Post-provisioning fixes for new servers on self-hosted Press without Hetzner private network.
Called automatically after setup_unified_server() or setup_server() completes.

Fixes:
1. Private IP: Add as interface alias (no Hetzner vSwitch)
2. DNS: Add /etc/hosts entry on press-ctrl
3. Docker: Add insecure-registries for local registry
4. Agent: Patch docker_login to skip empty credentials
5. Agent failures: Clear accumulated request failures
6. Proxy: Add nginx server block for agent routing
"""
import frappe
import subprocess


def _ssh(ip, cmd, user="root"):
    """Run SSH command on a remote server."""
    key = "/home/frappe/.ssh/id_ed25519"
    r = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key, user + "@" + ip, cmd],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return r.returncode == 0, r.stdout.strip(), r.stderr.strip()


def post_provision_server(server_name):
    """Run all post-provisioning fixes for a new server."""
    server = frappe.get_doc("Server", server_name)
    public_ip = server.ip
    private_ip = server.private_ip
    results = []

    # 1. Add private IP as interface alias
    ok, out, _ = _ssh(public_ip, f"ip addr show | grep -q {private_ip} && echo exists || (ip addr add {private_ip}/32 dev eth0 && echo 'network:\\n  version: 2\\n  ethernets:\\n    eth0:\\n      addresses:\\n        - {private_ip}/32' > /etc/netplan/99-private-ip.yaml && netplan apply 2>/dev/null; echo added)")
    results.append(f"1. Private IP: {out}")

    # 2. Add /etc/hosts entry on press-ctrl (localhost)
    ok, out, _ = _ssh("127.0.0.1", f"grep -q '{server_name}' /etc/hosts && echo exists || (echo '{public_ip} {server_name}' >> /etc/hosts && echo added)")
    results.append(f"2. DNS/hosts: {out}")

    # 3. Docker insecure-registries
    registry_url = frappe.db.get_single_value("Press Settings", "docker_registry_url")
    if registry_url:
        ok, out, _ = _ssh(public_ip, f"grep -q 'insecure-registries' /etc/docker/daemon.json && echo exists || (python3 -c \"import json; c=json.load(open('/etc/docker/daemon.json')); c['insecure-registries']=['{registry_url}']; json.dump(c,open('/etc/docker/daemon.json','w'),indent=4)\" && systemctl restart docker && echo added)")
        results.append(f"3. Docker registry: {out}")

    # 4. Patch agent docker_login
    ok, out, _ = _ssh(public_ip, "grep -q 'if not registry.get' /home/frappe/agent/repo/agent/server.py && echo exists || (sed -i '/def docker_login(self, registry):/a\\        if not registry.get(\"username\") or not registry.get(\"password\"):\\n            return' /home/frappe/agent/repo/agent/server.py && supervisorctl restart agent: && echo patched)")
    results.append(f"4. Agent patch: {out}")

    # 5. Clear agent request failures
    frappe.db.sql("DELETE FROM `tabAgent Request Failure` WHERE server = %s", server_name)
    frappe.db.commit()
    results.append("5. Agent failures: cleared")

    # 6. Proxy nginx block (from do_retry.py)
    if server.proxy_server:
        add_server_nginx_proxy(server_name, server.proxy_server)
        results.append("6. Proxy: configured")

    for r in results:
        print(r)
    return results


def add_server_nginx_proxy(server_name, proxy_server_name):
    """Add nginx server block on proxy for agent routing."""
    server = frappe.get_doc("Server", server_name)
    public_ip = server.ip
    proxy = frappe.get_doc("Proxy Server", proxy_server_name)
    proxy_ip = proxy.ip
    slug = server_name.split(".")[0]
    domain = server.domain

    cert_base = f"/home/frappe/agent/nginx/hosts/*.{domain}"
    conf_path = f"/etc/nginx/conf.d/{slug}-agent.conf"

    conf = f"""server {{
    listen 443 ssl http2;
    server_name {server_name};
    ssl_certificate {cert_base}/fullchain.pem;
    ssl_certificate_key {cert_base}/privkey.pem;
    ssl_trusted_certificate {cert_base}/chain.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    client_max_body_size 0;

    location /agent/ {{
        proxy_http_version 1.1;
        proxy_set_header Host {server_name};
        proxy_pass https://{public_ip}:443/agent/;
        proxy_ssl_verify off;
        proxy_ssl_protocols TLSv1.3;
        proxy_ssl_server_name on;
        proxy_ssl_name {server_name};
    }}

    location / {{ return 404; }}
}}
"""
    # Write conf via python3 to avoid shell quoting
    import base64
    b64 = base64.b64encode(conf.encode()).decode()
    ok, out, err = _ssh(proxy_ip, f"echo {b64} | base64 -d > {conf_path} && nginx -t 2>&1 && systemctl reload nginx && echo ok")
    print(f"Proxy nginx: {out}")

    # Also register upstream in Press
    server.add_upstream_to_proxy()
    frappe.db.commit()
