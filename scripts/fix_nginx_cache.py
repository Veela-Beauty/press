"""Fix nginx config to add no-cache headers for dashboard HTML.
Run on press-ctrl: python3 /tmp/fix_nginx_cache.py
"""
import re

CONF = "/etc/nginx/conf.d/frappe-bench.conf"

with open(CONF) as f:
    content = f.read()

# Remove any existing dashboard cache block
lines = content.split("\n")
new_lines = []
in_block = False
for line in lines:
    if "# Prevent browser caching of dashboard HTML" in line:
        in_block = True
        continue
    if in_block:
        if line.strip() == "}":
            in_block = False
            continue
        continue
    new_lines.append(line)
content = "\n".join(new_lines)

# Extract proxy settings from @webserver block
m = re.search(r"location @webserver \{(.*?)\}", content, re.DOTALL)
if not m:
    print("ERROR: Could not find @webserver block")
    exit(1)

proxy_lines = [l for l in m.group(1).strip().split("\n") if l.strip()]

# Build dashboard location block
block = "\t# Prevent browser caching of dashboard HTML (JS/CSS have content hashes)\n"
block += "\tlocation = /dashboard {\n"
for line in proxy_lines:
    block += "\t" + line + "\n"
block += '\t\tadd_header Cache-Control "no-cache, no-store, must-revalidate" always;\n'
block += '\t\tadd_header Pragma "no-cache" always;\n'
block += "\t}\n\n"

target = "\tlocation /assets {"
if "location = /dashboard" not in content:
    content = content.replace(target, block + target)
    with open(CONF, "w") as f:
        f.write(content)
    print("Dashboard no-cache block added successfully")
else:
    print("Dashboard block already exists")
