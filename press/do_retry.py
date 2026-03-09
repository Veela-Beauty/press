import frappe
import subprocess


def _ssh(ip, cmd, user="root"):
    key = "/home/frappe/.ssh/id_ed25519"
    r = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key, user + "@" + ip, cmd],
        capture_output=True,
        text=True,
        timeout=60,
    )
    print("STDOUT:", r.stdout.strip())
    if r.stderr.strip():
        print("STDERR:", r.stderr.strip())
    return r.returncode == 0, r.stdout.strip()


def bootstrap_new_server(server_name):
    """
    One-shot bootstrap for a new bare server with virtual_machine_image=NULL.
    Adds private IP to loopback (needed when cluster has no Hetzner private network),
    restarts MariaDB so it can bind, then enqueues setup_unified_server().
    """
    server = frappe.get_doc("Server", server_name)
    private_ip = server.private_ip
    public_ip = server.ip
    print("Server:", server_name, "public_ip:", public_ip, "private_ip:", private_ip)

    ok, out = _ssh(public_ip, "ip addr add " + private_ip + "/32 dev lo 2>/dev/null; echo loopback_done")
    print("loopback:", out)

    ok2, out2 = _ssh(public_ip, "systemctl restart mariadb && echo mariadb_ok || echo no_mariadb")
    print("mariadb:", out2)

    server.reload()
    server.setup_unified_server()
    frappe.db.commit()
    print("setup_unified_server enqueued for", server_name)
    return "bootstrapped"


def add_server_nginx_proxy(server_name, proxy_server_name="press-f1.sandbox.mvpstorm.com"):
    """
    Adds Nginx server block on press-f1 to route /agent/ to new server public IP.
    Required because add_upstream_to_proxy() uses private IP (unreachable on default cluster).
    Also calls server.add_upstream_to_proxy() to register the upstream in Press DB.
    """
    server = frappe.get_doc("Server", server_name)
    public_ip = server.ip
    slug = server_name.split(".")[0]

    proxy = frappe.get_doc("Proxy Server", proxy_server_name)
    proxy_ip = proxy.ip

    cert_base = "/home/frappe/agent/nginx/hosts/*.sandbox.mvpstorm.com"

    lines = [
        "server {",
        "    listen 443 ssl http2;",
        "    server_name " + server_name + ";",
        "    ssl_certificate " + cert_base + "/fullchain.pem;",
        "    ssl_certificate_key " + cert_base + "/privkey.pem;",
        "    ssl_trusted_certificate " + cert_base + "/chain.pem;",
        "    ssl_protocols TLSv1.2 TLSv1.3;",
        "    ssl_prefer_server_ciphers off;",
        "    client_max_body_size 0;",
        "",
        "    location /agent/ {",
        "        proxy_http_version 1.1;",
        "        proxy_set_header Host " + server_name + ";",
        "        proxy_pass https://" + public_ip + ":443/agent/;",
        "        proxy_ssl_verify off;",
        "        proxy_ssl_protocols TLSv1.3;",
        "        proxy_ssl_server_name on;",
        "        proxy_ssl_name " + server_name + ";",
        "    }",
        "",
        "    location / { return 404; }",
        "}",
    ]
    conf = "\n".join(lines) + "\n"
    conf_path = "/etc/nginx/conf.d/" + slug + "-agent.conf"

    # Write via python3 on the proxy to avoid shell quoting issues
    escaped = conf.replace("\\", "\\\\").replace('"', '\\"')
    write_cmd = 'python3 -c "open(\'' + conf_path + "', 'w').write(\"" + escaped + '")"'
    ok, out = _ssh(proxy_ip, write_cmd)
    print("write conf:", ok, out)

    test_ok, test_out = _ssh(proxy_ip, "nginx -t 2>&1 && systemctl reload nginx && echo nginx_reloaded")
    print("nginx:", test_out)

    server.reload()
    server.add_upstream_to_proxy()
    frappe.db.commit()
    print("Nginx proxy added for", server_name, "->", public_ip)
    return conf_path


def update_agent_press_url(server_name, press_url="https://demo.mvpstorm.com"):
    """
    Updates agent config.json press_url on the server and restarts the agent.
    Required because Ansible templates hardcode frappecloud.com.
    """
    server = frappe.get_doc("Server", server_name)
    public_ip = server.ip

    cmd = (
        "python3 -c \""
        "import json; "
        "p = '/home/frappe/agent/config.json'; "
        "c = json.load(open(p)); "
        "c['press_url'] = '" + press_url + "'; "
        "json.dump(c, open(p, 'w'), indent=2); "
        "print('updated to', c['press_url'])"
        "\""
    )
    ok, out = _ssh(public_ip, cmd)
    print("config update:", out)

    ok2, out2 = _ssh(public_ip, "supervisorctl restart all && echo agent_restarted || echo restart_failed")
    print("agent restart:", out2)
    return "press_url updated"


def ping_server_agent(server_name):
    """Test that the agent is reachable from press-ctrl via HTTPS."""
    import ssl
    import urllib.request
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    url = "https://" + server_name + "/agent/ping"
    try:
        resp = urllib.request.urlopen(url, context=ctx, timeout=10)
        body = resp.read().decode()
        print("ping:", body)
        return body
    except Exception as e:
        print("ping failed:", str(e))
        return str(e)


def post_ansible_setup(server_name, press_url="https://demo.mvpstorm.com", proxy_server_name="press-f1.sandbox.mvpstorm.com"):
    """
    Run this after the Ansible unified_server.yml job completes successfully.
    Steps: add Nginx proxy on press-f1, update agent press_url, verify ping.
    """
    add_server_nginx_proxy(server_name, proxy_server_name)
    update_agent_press_url(server_name, press_url)
    result = ping_server_agent(server_name)
    print("Final ping:", result)
    return result


def get_agent_password(server_name):
    """Get decrypted agent password from Press DB."""
    server = frappe.get_doc("Server", server_name)
    return server.get_password("agent_password")


def ping_server_agent_authed(server_name):
    """Ping agent with auth credentials from Press DB."""
    import ssl
    import urllib.request
    import base64
    server = frappe.get_doc("Server", server_name)
    token = server.get_password("agent_password")
    creds = base64.b64encode(("Administrator:" + token).encode()).decode()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    url = "https://" + server_name + "/agent/ping"
    req = urllib.request.Request(url, headers={"Authorization": "Basic " + creds})
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=10)
        body = resp.read().decode()
        print("ping:", body)
        return body
    except Exception as e:
        print("ping failed:", str(e))
        return str(e)
