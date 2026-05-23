# Frappe Press Self-Hosted — Lessons Learned & Gotchas

## Lesson Status Audit

Every lesson is classified by fix durability. Legend:
- **PERMANENT** — root cause eliminated, won't recur on this installation
- **PER-SERVER** — fixed for current servers, but must be repeated for every new server added
- **WORKAROUND** — underlying issue still exists, risk returns under specific conditions
- **ONGOING RISK** — not fully fixed, needs further action or active monitoring
- **KNOWLEDGE** — not a bug, reference information only

| # | Title | Status | Action Needed |
|---|-------|--------|---------------|
| 1 | Node 18 too old | PER-SERVER | Must use Node 20+ on every new Press install |
| 2 | setuptools < 81 | WORKAROUND | Depends on razorpay — check on every Press upgrade |
| 3 | bench CLI for root | PERMANENT | Done, documented |
| 4 | Supervisor symlink | PERMANENT | Done, documented |
| 5 | certbot certonly vs --nginx | PERMANENT | Done, documented |
| 6 | /etc/letsencrypt permissions | PERMANENT | Hook created: `scripts/hooks/fix-letsencrypt-permissions.sh` → deploy to `/etc/letsencrypt/renewal-hooks/post/` on press-ctrl |
| 7 | setup_standalone() order | PERMANENT | Documented |
| 8 | SSH CA dummy key | WORKAROUND | Functional — but SSH-via-Press won't work if ever needed |
| 9 | Server stuck "Broken" | PER-SERVER | Manual override needed every time Ansible partially fails |
| 10 | SSH keys between servers | PER-SERVER | Must set up for every new server pair |
| 11 | Team name is a hash | PERMANENT | Documented |
| 12 | App Source requires versions table | PERMANENT | Documented |
| 13 | App Releases must exist before deploy | PERMANENT | Documented |
| 14 | Build server required | PERMANENT | Set, documented |
| 15 | build_directory + clone_directory | PERMANENT | Set, documented |
| 16 | "build" queue — developer_mode workaround | PERMANENT | Dedicated worker added: `scripts/setup-build-worker.sh` — run on press-ctrl, then remove developer_mode |
| 17 | Python 3.14 hardcoded | PERMANENT | Patched in fork (app_release.py) |
| 18 | Docker insecure registry | PER-SERVER | Must set on every new server |
| 19 | Agent press_url = frappecloud.com | PER-SERVER | Must update config.json on every new server |
| 20 | MariaDB not installed by Ansible | PER-SERVER | Must verify + install on every new app server |
| 21 | Three records for standalone | PERMANENT | Documented |
| 22 | Site Plan autoname | PERMANENT | Documented |
| 23 | Secrets in git | PERMANENT | Rule established |
| 24 | Server.team is NULL | PER-SERVER | Must set team on every Ansible-provisioned server |
| 25 | Proxy Server separate agent_password | PER-SERVER | Must sync all three records on every new server |
| 26 | bench migrate after install | PERMANENT | Done — 142+ jobs created |
| 27 | press_url frappecloud.com | PER-SERVER | Same as #19 — must fix on every new server |
| 28 | Python version validation | PERMANENT | Patched in fork (validations.py) |
| 29 | v16+ app compatibility list | KNOWLEDGE | Reference only |
| 30 | Cluster.public resets on save | PERMANENT | Patched in `cluster.py` — `_preserve_public_flag()` in validate() prevents reset |
| 31 | Team mismatch on backend-created records | PER-SERVER | Must transfer ownership every time new resources are created via console |
| 32 | GitHub App full setup | PERMANENT | Done, documented |
| 33 | GitHub OAuth token not saved | PERMANENT | Fixed (OAuth during install enabled) |
| 34 | v16 disabled — Python 3.12+ needed | **ONGOING RISK** | **v16 builds impossible until build server upgraded to Python 3.12+** |
| 35 | develop branch targets v17 | KNOWLEDGE | Reference only — always use version-tagged branches |
| 36 | OutgoingEmailError | PERMANENT | disable_mail_notifications=1 set |
| 37 | Docker images tagged with old domain | PERMANENT | Historical, resolved |
| 38 | Port already allocated on deploy | PERMANENT | Daily cron cleanup: `scripts/hooks/docker-cleanup.sh` → deploy to `/etc/cron.daily/` on each app server |
| 39 | SSL cert mismatch | WORKAROUND | Fixed for current servers + renewal hooks installed — but stale Press TLS Certificate records still risk |
| 40 | Cloudflare zone ID mismatch | PERMANENT | Fixed, documented |
| 41 | Cloudflare token in one place | PERMANENT | Process established |
| 42 | Account-scoped token verify endpoint | KNOWLEDGE | Reference only |
| 43 | Programmatic DocTypes need migrate | KNOWLEDGE | Reference only |
| 44 | frappe.db.table_exists() without tab prefix | KNOWLEDGE | Reference only |
| 45 | Press Site controller guards | PERMANENT | Fixed in demo provisioning code |
| 46 | Agent PBKDF2 hash mismatch | PER-SERVER | Fixed on u4 + press-f1 — must follow for every new server |
| 47 | SSL cert hostname mismatch | PER-SERVER | Fixed on press-f1 + u4 — must verify for every new server |
| 48 | No certbot renewal hook | PER-SERVER | Hooks installed for press-f1 + u4 — must install for every new server |
| 49 | Fix one server → check all servers | KNOWLEDGE | Process rule |
| 50 | Fix symptoms ≠ fix root cause | KNOWLEDGE | Process rule |
| 51 | Scheduler stopped = silent failure | PERMANENT | Running — monitor weekly |
| 52 | Hetzner VPC attach crashes when vpc_id not set | PERMANENT | Patched in `virtual_machine.py` — guard added |
| 53 | Security group None values crash AWS API | PERMANENT | Patched in `virtual_machine.py` — filter added |
| 54 | Claude Code bash has no TTY — git credential prompts fail | PERMANENT | Push via press-ctrl SSH relay: bundle → SCP → cherry-pick → push |
| 55 | Certbot DNS propagation 10s too short — dry-run fails on staging | PERMANENT | Set `dns_cloudflare_propagation_seconds = 30` in all renewal configs |
| 56 | `_certbot_command()` missing propagation flag — new cert issuance fails via Press UI | PERMANENT | Patched `--dns-cloudflare-propagation-seconds 30` in `tls_certificate.py` |
| 57 | `provision-server.sh` Step 7 — SSH doesn't forward env vars, agent /ping always 401 | PERMANENT | Fixed: expand credential locally via `printf '%q'` |
| 58 | `sync-press-tls-records.sh` `grep 'CN=[^,]*'` fails on OpenSSL 3.0 — CERT_DOMAIN empty, hook silent no-op | PERMANENT | Fixed: `sed -E 's/.*CN\s*=\s*\*\.([a-zA-Z0-9.-]+).*/\1/'` |
| 59 | Python `IndentationError` in a module crashes ALL API calls — no partial import | PERMANENT | Documented — always syntax-check `.py` files before deploying: `python3 -c "import ast; ast.parse(open('file.py').read())"` |
| 60 | `bool("0") == True` — Python string zero is truthy | PERMANENT | Fixed in `bench_dev_overview.py`: use explicit `value in (True, 1, "1", "true")` for site config boolean checks |
| 61 | `Site Activity` action field is a fixed enum — custom action strings raise validation error | PERMANENT | Fixed `site.py set_development_mode`: replaced `log_site_activity("Dev mode enabled")` with `frappe.logger()` |
| 62 | Vue 3 `<template v-for>` — `:key` must be on `<template>`, not the child `<div>` | PERMANENT | Documented — when wrapping rows in `<template v-for="(item, idx)">`, put `:key` on the template tag |
| 63 | Standalone API file pattern for large doctypes — keep the fat file intact | PERMANENT | `bench_dev_overview.py` sits alongside `bench.py` without touching it. Hooks via `@frappe.whitelist()` directly. Avoids breaking a 5000-line controller. |

### Items Needing Action (open risks)

| Priority | # | Issue | Status | Deploy Command |
|----------|---|-------|--------|----------------|
| DONE | 6 | letsencrypt permissions | Script ready | `cp scripts/hooks/fix-letsencrypt-permissions.sh /etc/letsencrypt/renewal-hooks/post/ && chmod +x ...` |
| DONE | 30 | Cluster.public reset | Patched in cluster.py | Deploy fork update: `git pull && bench --site demo.mvpstorm.com migrate` |
| DONE | 16 | build queue workaround | Script ready | `bash scripts/setup-build-worker.sh` on press-ctrl |
| DONE | 38 | Docker port allocation | Script ready | `cp scripts/hooks/docker-cleanup.sh /etc/cron.daily/press-docker-cleanup && chmod +x ...` on each app server |
| OPEN | 34 | v16 disabled | Needs Python 3.12 | Install Python 3.12 on press-f1, re-enable Frappe Version v16 |
| MONITOR | 2 | setuptools pin | Check on upgrades | After every `bench update`: `env/bin/pip install "setuptools<81"` |
| AUTOMATED | 18,19,24,25,46,47,48 | PER-SERVER steps | Script ready | `bash scripts/provision-server.sh --ip X --hostname Y --cert-domain Z --team T` |

---

## Installation Gotchas

### 1. Node 18 is too old for Press develop branch
**What happened:** `@vitejs/plugin-vue@6.0.4` requires Node >=20.19.0
**Fix:** Upgrade to Node 20.20.1 via nodesource setup script
**Lesson:** Press develop branch targets latest Node. Always check package.json engines.

### 2. `pkg_resources` removed in setuptools 82+
**What happened:** `razorpay` package (Press dependency) uses `pkg_resources` which was removed
**Fix:** `env/bin/pip install "setuptools<81"` inside the bench virtualenv
**Lesson:** Pin setuptools < 81 when installing Press. This affects the bench venv, not system Python.

### 3. `bench setup production` needs root but bench is installed under frappe user
**What happened:** Running as root gives `ModuleNotFoundError: No module named 'bench'`
**Fix:** Install bench globally: `pip3 install frappe-bench` as root, then run `bench setup production frappe --yes` from `/home/frappe/frappe-bench`
**Lesson:** bench CLI must be available to the user running the production setup command.

### 4. Supervisor config not symlinked after production setup
**What happened:** `supervisorctl status` showed no processes — config was in `config/supervisor.conf` but not linked to `/etc/supervisor/conf.d/`
**Fix:** `ln -sf /home/frappe/frappe-bench/config/supervisor.conf /etc/supervisor/conf.d/frappe-bench.conf && supervisorctl reread && supervisorctl update`
**Lesson:** Always verify supervisor picks up the config after `bench setup production`.

### 5. certbot --dns-cloudflare and --nginx can't be used together
**What happened:** "Too many flags setting configurators/installers/authenticators"
**Fix:** Use `certbot certonly --dns-cloudflare ...` (certonly, no --nginx), then manually configure nginx SSL
**Lesson:** DNS challenge and nginx installer are separate authenticator/installer modes. Use certonly + manual nginx config.

### 6. `/etc/letsencrypt/` permissions block frappe user
**What happened:** Wildcard cert obtained but frappe user couldn't read it (PermissionError on /etc/letsencrypt/live/)
**Fix:** `chmod -R 755 /etc/letsencrypt/live/ /etc/letsencrypt/archive/`
**Lesson:** Certbot sets restrictive permissions. Fix after every cert issuance, or set up a post-hook.

## Ansible / Server Provisioning Gotchas

### 7. `setup_standalone()` must run AFTER `setup_server()`
**What happened:** Called setup_standalone first, all tasks failed because agent wasn't installed yet
**Fix:** Run `setup_server()` first (installs agent, MariaDB, Redis, Nginx), then `setup_standalone()`
**Lesson:** Standalone playbook assumes agent already exists at `/home/frappe/agent`. The sequence is: setup_server → setup_standalone.

### 8. SSH CA key download from frappecloud.com fails
**What happened:** Task "Setup certificate-authority key file" downloads from `https://frappecloud.com/files/ca.pub` which returns 308 redirect
**Fix:** Create dummy CA key on Server 2: `ssh-keygen -t ed25519 -f /tmp/ca_key -N '' && cp /tmp/ca_key.pub /etc/ssh/ca.pub`
**Lesson:** Self-hosted Press doesn't need Frappe Cloud's SSH CA. Create a dummy key or set `ssh_certificate_authority` in Press Settings.

### 9. Server status stuck on "Broken" after one Ansible task fails
**What happened:** 150/193 tasks succeeded but status set to "Broken" because of 1 failure
**Fix:** Manually update: `server.status = 'Active'; server.is_server_setup = 1; server.save()`
**Lesson:** Press marks server as Broken on ANY Ansible failure. For self-hosted, manually override if core setup succeeded.

### 10. SSH from Server 1 to Server 2 needs explicit key setup
**What happened:** Server 1 couldn't SSH to Server 2 (Permission denied)
**Fix:** Generate key on Server 1 (`ssh-keygen -t ed25519`), add public key to Server 2's `/root/.ssh/authorized_keys`. Do this for BOTH root and frappe users.
**Lesson:** Hetzner doesn't auto-propagate SSH keys between servers. Must manually set up Server1→Server2 SSH.

## Press Configuration Gotchas

### 11. Team name is NOT "Administrator"
**What happened:** Created records with `team='Administrator'`, got "Could not find Team: Administrator"
**Fix:** The actual team name is a hash like `f6o5jtfht1`. Find it with: `frappe.get_all('Team', filters={'user': 'Administrator'}, pluck='name')`
**Lesson:** In Press, the Team doctype uses auto-generated names, not the user name. Always look up the real team name.

### 12. App Source requires `app_title` and `versions` child table
**What happened:** MandatoryError when creating App Source without these fields
**Fix:** Include `app_title` and `versions: [{'version': 'Version 15'}]` in the doc dict
**Lesson:** App Source links apps to Frappe versions via child table. Must include at least one version.

### 13. App Releases must exist before creating Deploy Candidates
**What happened:** "Following apps not found. Potentially due to not approved App Releases."
**Fix:** Create App Release records with the latest commit hashes and `status='Approved'`
**Lesson:** Press validates that each app in the Release Group has an approved release before allowing deploy candidate creation.

### 14. Deploy needs a Build Server
**What happened:** "Server not found to run builds"
**Fix:** Set `press_settings.build_server = 'press-f1.demo.mvpstorm.com'` and `server.use_for_build = 1`
**Lesson:** Even for self-hosted, Press needs a designated build server. The standalone server can serve as both build and app server.

## Build & Deploy Gotchas

### 15. `build_directory` and `clone_directory` must be set in Press Settings
**What happened:** `TypeError: stat: path should be string, bytes, os.PathLike or integer, not NoneType` during build
**Fix:** Set `ps.build_directory = '/home/frappe/frappe-bench/builds'` and `ps.clone_directory = '/home/frappe/frappe-bench/clones'`, create both directories on disk.
**Lesson:** Press Settings has build_directory and clone_directory fields that default to None. Must set them AND create the directories.

### 16. "build" queue doesn't exist in standard Frappe — use developer_mode
**What happened:** `"Queue should be one of short, default, long"` when build job enqueued
**Fix:** Set `developer_mode = 1` in `site_config.json`. The code: `queue = "default" if frappe.conf.developer_mode else "build"`
**Lesson:** Press assumes a custom "build" queue exists (Frappe Cloud has it). For self-hosted, enable developer_mode to route builds to "default" queue. Or add a custom worker.

### 17. Python 3.14 hardcoded in `app_release.py`
**What happened:** `FileNotFoundError` — `get_python_path()` returns `/usr/bin/python3.14` which doesn't exist on Server 1
**Fix:** Patched fallback from `return "/usr/bin/python3.14"` to `return _get_python_path()` (uses bench python)
**Lesson:** Press develop branch (late 2025+) assumes Python 3.14 is available. For self-hosted with Python 3.11, patch the fallback.

### 18. Docker registry push fails: "http: server gave HTTP response to HTTPS client"
**What happened:** Server 2 Docker daemon tried HTTPS to reach HTTP-only registry on Server 1 (port 5000)
**Fix:** Add `"insecure-registries": ["89.167.116.92:5000"]` to `/etc/docker/daemon.json` on Server 2, restart Docker.
**Lesson:** Self-hosted Docker registry on port 5000 runs HTTP by default. Every machine that pushes/pulls must have it in `insecure-registries`.

### 19. Build steps stuck at Pending — agent doesn't update Press
**What happened:** Agent on Server 2 built the Docker image successfully, but build step statuses in Press stayed "Pending"
**Fix:** Update `/home/frappe/agent/config.json` to set `press_url: "https://demo.mvpstorm.com"`.
**Lesson:** Agent communicates back to Press via `press_url` in agent config. If that points to `frappecloud.com` (default), updates never reach self-hosted Press.

### 20. MariaDB server NOT installed by Ansible setup_server
**What happened:** `"Password not found for Database Server None mariadb_root_password"` — MariaDB wasn't running on Server 2
**Fix:** `apt-get install -y mariadb-server`, set root password, grant `root@'%'`, change bind-address to `0.0.0.0`
**Lesson:** Ansible `setup_server` may only install MariaDB client packages, not the server. Always verify `systemctl status mariadb` after provisioning.

### 21. Standalone mode needs THREE separate records for the same server
**What happened:** Deploy failed with "MandatoryError: server" — no Proxy Server record existed
**Fix:** Create Database Server record AND Proxy Server record both named `press-f1.demo.mvpstorm.com`. Link: `server.database_server = db_server.name`, `server.proxy_server = proxy.name`.
**Lesson:** Even in standalone mode (one physical server), Press requires Server + Database Server + Proxy Server records.

### 22. Site Plan uses autoname "prompt" — needs explicit `__newname`
**What happened:** Site Plan creation may fail or prompt for name if `__newname` isn't passed
**Fix:** Include `__newname: 'Free Trial'` (or similar) when creating via script
**Lesson:** Some Press DocTypes use `autoname = "prompt"` which requires an explicit name field in scripted creation.

## Site Creation & Agent Communication Gotchas

### 24. "You are not allowed to use this plan" — Server.team is NULL
**What happened:** Free plan site creation blocked for Administrator
**Fix:** `UPDATE tabServer SET team = "<team_hash>" WHERE name = "press-f1.demo.mvpstorm.com"` (also for Database Server, Proxy Server)
**Lesson:** `validate_plan()` requires `server.team == current_team` for free plans. Server records created by Ansible have `team = NULL`.

### 25. Agent auth 401 — Proxy Server has SEPARATE agent_password
**What happened:** Fixed Server's agent_password but "Add Site to Upstream" still got 401
**Fix:** Set the SAME password for both Server and Proxy Server records in `__Auth` table
**Lesson:** In standalone mode, Server and Proxy Server records point to the same physical agent, but each has its own `agent_password` in `__Auth`. ALL server type passwords must match the single `access_token` in agent config.

### 26. `bench migrate` required after installing Press — creates 142+ scheduled jobs
**What happened:** Dashboard status never updated automatically — `poll_pending_jobs` wasn't running
**Root cause:** Scheduled Job Type records were never created because `bench migrate` wasn't run
**Fix:** `bench --site demo.mvpstorm.com migrate`
**Lesson:** After installing Press, ALWAYS run `bench migrate`. This creates all Scheduled Job Type records from hooks.py.

### 27. Agent `press_url` defaults to frappecloud.com
**What happened:** Agent completed jobs but callbacks never reached self-hosted Press
**Fix:** Update `/home/frappe/agent/config.json` to set `"press_url": "https://demo.mvpstorm.com"`
**Lesson:** The agent config ships with `press_url: "https://frappecloud.com"`. Must be changed for self-hosted.

## Security Rules

### 23. NEVER push passwords/tokens to git
- Use `.env` files for secrets (already in .gitignore)
- Cloudflare token, DB passwords, admin passwords — all belong in `.env` or server-side config only
- Even private repos can be compromised. Secrets in git history are permanent.

## Dashboard & Build Gotchas

### 28. Python version validation blocks builds — `requires-python >= 3.14`
**What happened:** Build failed at "Pre-build: validate" because wiki app requires Python 3.14+
**Fix:** Patched `validations.py` — changed `_validate_python_version` from raising exception to emitting `BuildWarning`
**Lesson:** Press develop branch apps may require Python 3.14. For self-hosted with Python 3.11, patch the validation.

### 29. Many Frappe apps are v16+ only — no `version-15` branch
**Compatible with v15:** hrms, payments, webshop, lending
**NOT compatible (v16+ only):** print_designer, wiki, lms, builder, helpdesk, crm, insights, drive, gameplan
**Lesson:** Always check `git ls-remote --heads https://github.com/frappe/<app>.git version-15` before adding apps.

### 30. Dashboard "New Bench" flow requires multiple hidden settings
**Root causes (all must be set):**
1. `App Source.public = 1` — query filters on public sources
2. `App Source.frappe = 1` — "is official Frappe app" flag
3. `Frappe Version.public = 1` — version must be public
4. `Cluster.public = 1` — cluster must be public (resets on save!)
5. `Marketplace App.frappe_approved = 1` — apps shown as pre-approved
6. `Press Settings.default_apps` — frappe + erpnext auto-added to new benches
7. `Press Settings.erpnext_apps` — apps listed in marketplace

### 31. Dashboard team mismatch — resources invisible to dashboard user
**Fix:** Transfer all resources (Release Groups, Sites, App Sources, Servers) to dashboard user's team
**Lesson:** Press is multi-tenant. Resources created via backend scripts default to Administrator's team.

### 32. GitHub App integration — full setup checklist
**Required settings:**
1. `github_app_public_link`: `https://github.com/apps/mvpstorm-press` (correct slug!)
2. GitHub App permissions: Contents (Read-only), Metadata (Read-only)
3. Callback URL: `https://demo.mvpstorm.com/github/authorize`
4. Setup URL: `https://demo.mvpstorm.com/github/authorize`
5. Press Settings: `github_app_id`, `github_app_client_id`, `github_app_client_secret`, `github_app_private_key`

### 33. GitHub OAuth token not saved after App installation
**Root cause:** Installation and OAuth are separate GitHub flows
**Fix:** Navigate to OAuth URL directly: `https://github.com/login/oauth/authorize?client_id=CLIENT_ID&state=BASE64_STATE`
**Lesson:** Enable "Request user authorization (OAuth) during installation" in GitHub App settings.

### 34. Frappe v16 requires Python 3.12+ — `type X = Y` syntax
**What happened:** Build fails with SyntaxError on `type ConfType = _dict[str, Any]`
**Fix:** Cannot build v16 on Python 3.11. Disabled v16 from dashboard (`Frappe Version.public = 0`)
**Lesson:** Frappe v16+ uses Python 3.12+ type alias syntax. Need Python 3.12+ on build server for v16.

### 35. ERPNext `develop` branch now targets Frappe v17, not v16
**What happened:** Build failed: "erpnext requires frappe >= 17.0.0-dev, found 16.0.0-dev"
**Fix:** Use `version-16` tagged branches instead of `develop` for v16 apps
**Lesson:** `develop` is a moving target. Always use version-tagged branches for stable deployments.

### 36. OutgoingEmailError crashes build notifications
**What happened:** Build failure notification tries to send email, crashes because no Email Account configured
**Fix:** Create dummy Email Account with `default_outgoing=1` or set `disable_mail_notifications=1` in site_config.json
**Lesson:** Press notification system requires an Email Account even if emails are disabled in Press Settings.

## Domain & DNS Gotchas

### 37. Docker images tagged with old domain
**Fix:** `docker tag old new && docker push new`. Update `docker_image` + `docker_image_repository` in `tabDeploy Candidate Build`.

### 38. Port already allocated on deploy
**Fix:** `docker stop $(docker ps -q) && docker rm $(docker ps -aq)` — old containers hold ports.

### 39. SSL cert mismatch breaks agent callbacks
**Fix:** Update Nginx `ssl_certificate` path to new domain cert.

### 40. Cloudflare zone ID mismatch
**Fix:** `curl zones?name=mvpstorm.com` to find correct zone ID. Zone ID in Root Domain may be wrong.

### 41. Cloudflare API token management — save in ONE place
**Problem:** Token was changed 3 times across sessions. Had to hunt for it in certbot ini, Press Root Domain x2, memory files.
**Fix:** Single source of truth at `/root/.cloudflare/credentials.ini` on press-ctrl. When rotating:
1. Update `/root/.cloudflare/credentials.ini`
2. Update Press Root Domains via `bench execute` script
3. Update docs
**Lesson:** Centralize credentials. Never store the same secret in 3+ unlinked places.

### 42. Cloudflare token verify endpoint differs for account-scoped tokens
**Problem:** `/user/tokens/verify` returns "Invalid API Token" for account-scoped tokens.
**Fix:** Use `/accounts/{account_id}/tokens/verify` instead.

## Demo Provisioning Gotchas

### 43. Programmatically created DocTypes need `bench migrate` for tables
**Problem:** Creating DocType via script creates JSON but NOT the DB table.
**Fix:** Run `bench migrate` after. Never rely on lazy table creation in API endpoints.

### 44. `frappe.db.table_exists()` takes doctype name, NOT `tab` prefix
**Problem:** `frappe.db.table_exists("tabDemo Invite Code")` returns False even when table exists.
**Fix:** Use `frappe.db.table_exists("Demo Invite Code")` — Frappe adds `tab` prefix internally.

### 45. Press Site controller role guards run even with `ignore_permissions=True`
**Problem:** Guest user calling `site.insert(ignore_permissions=True)` hits `get_current_team()` AuthenticationError.
**Fix:** Wrap with `frappe.set_user("Administrator")` before insert, restore after.

---

## Multi-Tenant Risk Lessons

These lessons are different. They are not about one bug — they are about the **blast radius** of a bug on a shared platform. Every site on a server shares the same agent, the same SSL cert, and the same scheduler. One misconfiguration takes down all users on that server, not just one.

See [platform-risk-checklist.md](02-operations/platform-risk-checklist.md) for the full verification protocol.

---

### 46. Agent auth mismatch (PBKDF2 hash) — all sites on server go dark
**Risk:** P1 — ALL sites on the affected server. Jobs queue up and never complete. Users see sites stuck in "Pending" state forever.
**What happened:** u4 agent was added with a new `agent_password` in Press DB but the agent's `config.json` still had a stale hash. Every job sent to u4 returned HTTP 401.
**Root cause:** The agent stores a PBKDF2-SHA256 hash of the password. Press stores the plaintext (encrypted in `__Auth` table). If the hash was generated with wrong rounds or wrong plaintext, auth silently fails forever.
**Fix (steps):**
1. Get plaintext from Press: `frappe.get_decrypted_password("Server", "server_name", "agent_password")`
2. Regenerate hash on the agent server: `pbkdf2_sha256.using(rounds=29000).hash(plaintext)`
3. Update `config.json` → `access_token` with new hash
4. `supervisorctl restart agent:web`
5. Verify from inside the server: `curl -u 'server_name:plaintext' http://127.0.0.1:25052/ping` → must return 200
**Also check:** Database Server and Proxy Server each have a SEPARATE `agent_password` in `__Auth`. All three records must have matching passwords for the same physical agent.

### 47. SSL cert domain mismatch — agent unreachable from Press
**Risk:** P1 — ALL sites on the affected server. Press makes HTTPS callbacks to the agent. If the cert doesn't match the hostname, TLS verification fails and all agent jobs fail with `SSLCertVerificationError: Hostname mismatch`.
**What happened:** press-f1 was provisioned with `*.demo.mvpstorm.com` cert. When we added a second server with hostname `press-f1.sandbox.mvpstorm.com`, the cert didn't cover it — different second-level domain.
**Root cause:** `*.demo.mvpstorm.com` is a wildcard only for that one level. It covers `anything.demo.mvpstorm.com` but NOT `anything.sandbox.mvpstorm.com`. Separate wildcard cert required for each subdomain level.
**Fix (steps):**
1. Identify the hostname Press uses for the server (the DocType record name)
2. Check what cert is currently in `/home/frappe/agent/tls/` with: `openssl x509 -noout -subject < /home/frappe/agent/tls/fullchain.pem`
3. If mismatch: issue the correct wildcard cert on press-ctrl with certbot
4. SCP the matching cert to the agent's tls/ directory
5. `chown frappe:frappe /home/frappe/agent/tls/*.pem && nginx -t && systemctl reload nginx`
6. Verify: `openssl s_client -connect SERVER_IP:443 -servername HOSTNAME 2>/dev/null | grep "Verify return code"`
**Rule:** cert domain must match the server's hostname in Press, character for character.

### 48. No certbot renewal hook = cert expires silently, all ops fail
**Risk:** P1 — cert expiry is silent until the day it expires, then ALL operations on that server stop immediately.
**What happened:** press-f1 agent TLS cert was manually deployed. No renewal hook existed. When certbot renewed the `*.demo.mvpstorm.com` cert on press-ctrl, the new cert was NOT deployed to press-f1. The old cert on press-f1 would have expired without warning.
**Fix (steps):**
1. On press-ctrl, create `/etc/letsencrypt/renewal-hooks/deploy/<hook-name>.sh`
2. The hook checks `$RENEWED_LINEAGE` to only run for the relevant cert
3. SCPs the new cert to the target server's `/home/frappe/agent/tls/`
4. SSHs to the target and reloads nginx
5. `chmod +x` the hook, then `certbot renew --dry-run` to verify it runs
**Rule:** Every server that uses a cert issued on press-ctrl must have a deploy hook. Install the hook at the same time you deploy the cert — not later.

### 49. When you fix one server, check ALL servers for the same issue
**Risk:** Any level — P0 to P3. The same misconfiguration is often copy-pasted across servers.
**What happened:** We fixed the agent auth hash on u4. Before that, we fixed the same issue on press-f1. Both had the same root cause (stale hash after password rotation). If we had checked press-f1 when we first found it, we would have avoided a second incident on u4.
**Rule:** When you find a bug on one server, immediately ask: "Does this exist on every other server?" Run the verification steps on ALL servers before closing the task.
**Platform audit after any agent/cert change:**
1. Test `/ping` on every server from inside (not from press-ctrl)
2. Check SSL cert subject on every server
3. Check disk space on every server
4. Check recent Agent Job failures for every server

### 50. A fix that skips the root cause creates a future incident
**Risk:** Varies — you close the ticket but the problem recurs, often at a worse time.
**What happened:** Early in the setup, agent auth issues were "fixed" by resetting passwords manually without documenting the PBKDF2 hash requirement. The next time a server was added, we hit the exact same issue from scratch.
**Rule:** Every fix must answer three questions:
1. What was the actual root cause (not just the symptom)?
2. What prevents this from happening again on this server?
3. What prevents this from happening on any future server?
If you can't answer all three, the fix is incomplete. Add it to lessons-learned AND the setup checklist AND the platform-risk-checklist.

### 51. Scheduler stopped = silent failure across the entire platform
**Risk:** P0 — affects ALL users. Sites appear "Active" in the dashboard but nothing works: no backups, no status updates, no auto-renew, no monitoring.
**What happened:** `poll_pending_jobs` wasn't created because `bench migrate` wasn't run after install. All agent jobs completed on the server side but Press never polled for results.
**Symptoms:** Agent jobs stay "Pending" in Press. Sites stay in "Installing" or "Pending" indefinitely.
**Fix (steps):**
1. Check: `bench execute frappe.client.get_list --kwargs '{"doctype": "Scheduled Job Type", "filters": {"name": "agent_job.poll_pending_jobs"}, "fields": ["stopped", "last_execution"]}'`
2. If missing: `bench --site demo.mvpstorm.com migrate`
3. If stopped: `frappe.db.set_value("Scheduled Job Type", {"name": ...}, "stopped", 0)`
4. Manual trigger: `bench execute press.press.doctype.agent_job.agent_job.poll_pending_jobs`
5. Within 10 seconds, any completed agent jobs should update in Press
**Rule:** After ANY bench migrate, restart, or Press upgrade — always verify `poll_pending_jobs` is running and `last_execution` is updating every 5 seconds.

---

## Cloud Provider Integration Gotchas

### 52. Hetzner VPC attach_to_network crashes when cluster.vpc_id is not set
**Risk:** VM creation fails entirely — the server is created in Hetzner but never attached to the private network, leaving Press in an inconsistent state (server created, db.commit() done, but status update crashes).
**What happened:** `_provision_hetzner()` unconditionally called `servers.attach_to_network(network=Network(id=cint(cluster.vpc_id)))`. If `cluster.vpc_id` is None or empty, `cint(None)` = 0, and the hcloud API rejects `Network(id=0)` with an error. Self-hosted clusters often don't have a private VPC configured.
**Fix:** Added `if cluster.vpc_id:` guard before the `attach_to_network` call in `virtual_machine.py`.
**Lesson:** Optional cluster fields must always be guarded before passing to cloud APIs. The pattern `if field:` before any API call using that field is mandatory — never assume optional fields are always set.

### 53. Security group None values crash AWS API calls
**Risk:** Server creation fails for series "n" (proxy) servers when `proxy_security_group_id` is not configured on the cluster.
**What happened:** `get_security_groups()` appended `frappe.db.get_value(...)` result to the groups list without checking if it was None. If `proxy_security_group_id` is not set, `groups = [security_group_id, None]`. AWS API rejects None as a security group ID.
**Fix:** Changed return to `return [g for g in groups if g]` to filter out None/empty values.
**Lesson:** Always filter None out of lists before passing to external APIs. `frappe.db.get_value()` returns None when field is empty — never assume Link fields are always populated just because they exist on the DocType.

---

## Development Environment Gotchas

### 54. Claude Code bash has no TTY — Windows Credential Manager prompts fail silently
**What happened:** When trying to `git push` from Claude Code's bash terminal, the Windows Git Credential Manager (GCM) tries to open a GUI prompt to authenticate, but the bash shell has no TTY (`/dev/tty: No such device or address`). The push silently fails with a `fatal: could not read Username` error even when credentials ARE stored in Windows Credential Manager.
**Fix:** Push via press-ctrl instead — press-ctrl has an SSH key configured for GitHub:
```bash
# From local — create bundle, SCP to press-ctrl, apply and push from there
git bundle create /tmp/x.bundle BASE_COMMIT..HEAD
scp -i "E:/.ssh/new_id_ed25519" /tmp/x.bundle root@89.167.116.92:/tmp/x.bundle
ssh -i "E:/.ssh/new_id_ed25519" root@89.167.116.92 \
  "cd /home/frappe/frappe-bench/apps/press && \
   git fetch /tmp/x.bundle 'HEAD:refs/remotes/local/br' && \
   git cherry-pick refs/remotes/local/br && \
   git push upstream cloudflare-dns"
```
**Lesson:** press-ctrl has `upstream` remote pointing to `git@github.com:accurate-systems/press.git` with SSH key auth. Always use it as the push relay when the local terminal has no TTY. Document this in project CLAUDE.md — don't discover it again each session.

### 55. Certbot DNS propagation 10 seconds too short — dry-run fails on staging ACME server
**What happened:** `certbot renew --dry-run` failed for all 4 certificates with `The Certificate Authority failed to verify the DNS TXT records`. The default `dns_cloudflare_propagation_seconds = 10` is not enough time for the Let's Encrypt staging server to confirm Cloudflare DNS updates.
**Fix:** Add `dns_cloudflare_propagation_seconds = 30` to every renewal config:
```bash
for conf in /etc/letsencrypt/renewal/*.conf; do
  grep -q 'dns_cloudflare_propagation_seconds' "$conf" || \
    sed -i '/\[renewalparams\]/a dns_cloudflare_propagation_seconds = 30' "$conf"
done
```
**Lesson:** Always set propagation seconds to 30+ in certbot renewal configs for DNS challenges. After adding renewal hooks or changing certbot config, always verify with `certbot renew --dry-run` before assuming hooks will run on actual renewal. The permissions hook (`fix-letsencrypt-permissions.sh`) confirmed running in the log even when cert validation fails — deploy hooks only run on successful renewal.

### 56. `_certbot_command()` missing `--dns-cloudflare-propagation-seconds` — new cert issuance via Press UI silently uses 10s default
**Risk:** New wildcard certificate issuance triggered from the Press dashboard would fail with ACME DNS validation errors. Renewal config files have `dns_cloudflare_propagation_seconds = 30`, but `certbot certonly` (used for initial issuance) reads propagation seconds from the CLI flag, not the renewal config.
**What happened:** Lesson 55 fixed the renewal configs for `certbot renew`, but `_certbot_command()` in `tls_certificate.py` only builds `--dns-cloudflare --dns-cloudflare-credentials ...` for the DNS plugin — no `--dns-cloudflare-propagation-seconds` flag. New certs issued via Press would use the certbot default (10s), which was already proven insufficient.
**Fix:** Added `--dns-cloudflare-propagation-seconds 30` to the DNS plugin string in `_certbot_command()`:
```python
plugin = (
    f"--dns-cloudflare --dns-cloudflare-credentials {credentials_path}"
    " --dns-cloudflare-propagation-seconds 30"
)
```
**Lesson:** When patching a workaround (renewal configs), always trace the full code path to confirm the fix is complete. `certbot renew` reads the config; `certbot certonly` reads CLI flags. Both paths must be patched. A partial fix that only addresses one invocation path will surprise you at the worst time — during cert issuance for a new site.

### 57. `provision-server.sh` Step 7 — SSH doesn't forward local env vars, agent /ping always authenticates with empty password
**Risk:** The agent auth verification step in `provision-server.sh` always returns 401/000 even after a successful auth sync, masking whether the sync actually worked. Operators see a false "WARNING: check auth manually" message and may incorrectly suspect the sync failed.
**What happened:** Step 7 wrote:
```bash
PING_STATUS=$(AGENT_PWD="${PLAINTEXT}" run_on_server bash -c \
  "curl ... -u '${HOSTNAME}:\${AGENT_PWD}' ...")
```
`AGENT_PWD` set before `run_on_server` is a local-only env var. SSH (`ssh root@IP cmd`) does NOT forward local env vars by default — the remote shell never sees `AGENT_PWD`. The `\${AGENT_PWD}` (escaped `$`) reaches the remote shell literally as `${AGENT_PWD}`, expands to empty, and curl sends `HOSTNAME:` as credentials → 401.
**Fix:** Expand the credential locally using `printf '%q'` for safe shell escaping:
```bash
PING_STATUS=$(run_on_server bash -c \
  "curl -s -o /dev/null -w '%{http_code}' -u $(printf '%q' "${HOSTNAME}:${PLAINTEXT}") http://127.0.0.1:25052/ping" ...)
```
`printf '%q'` produces a single-quoted, shell-escaped string that safely handles passwords containing spaces, quotes, or special chars.
**Lesson:** SSH does not forward env vars unless `SendEnv`/`AcceptEnv` are both configured. For automation scripts: either expand credentials locally (with escaping), write them to a temp file on the remote, or use `ssh -o SendEnv=VAR` (requires remote sshd `AcceptEnv`). Never rely on `VAR=value ssh host cmd` to make `VAR` available inside the remote command.

### 58. `sync-press-tls-records.sh` CN parsing broken on OpenSSL 3.0 — `grep 'CN=[^,]*'` never matches, CERT_DOMAIN silently empty
**Risk:** After certbot renews a wildcard cert, the sync hook is supposed to update Press TLS Certificate records with the new expiry date. On Ubuntu 22.04 (OpenSSL 3.0), the hook does nothing — silently exits without updating any records. Press continues showing stale cert expiry dates and may try to re-renew unnecessarily.
**What happened:** `openssl x509 -noout -subject` output changed between OpenSSL versions:
- OpenSSL 1.1.1 (Ubuntu 20.04): `subject= /CN=*.demo.mvpstorm.com`
- OpenSSL 3.0 (Ubuntu 22.04): `subject=CN = *.demo.mvpstorm.com`

The hook used `grep -o 'CN=[^,]*'` which expects no spaces around `=`. On OpenSSL 3.0, `CN = value` has spaces — the pattern never matches. `CERT_DOMAIN` becomes empty string, hits `[ -z "$CERT_DOMAIN" ] && exit 0`, and exits silently. No error, no updated records.
**Fix:** Use `sed -E` with `\s*` to tolerate optional spaces, and strip wildcard prefix in the same expression:
```bash
CERT_DOMAIN=$(openssl x509 -noout -subject -in "$CERT_FILE" 2>/dev/null \
  | sed -E 's/.*CN\s*=\s*\*\.([a-zA-Z0-9.-]+).*/\1/')
```
**Lesson:** OpenSSL 3.0 changed the default subject output format from `/CN=value` to `CN = value`. Any script parsing `openssl` output with exact string matching for `CN=` will silently fail on Ubuntu 22.04. Use `\s*` around `=` or `-nameopt=oneline` to handle both formats. Always test shell hooks on a matching OS version — never just on the dev machine.

---

### 59. Python `IndentationError` crashes entire module — all API calls fail silently

**What happened:** `bench_dev_overview.py` had the `scheduler_map` assignment at 2-tab indent instead of 3-tab (inside the `for` body). Python raises `IndentationError` at compile time, so the entire module fails to import. Every call to `get_dev_overview_benches()` returned no data — UI showed "no bench found" with no error visible.

**Fix:** Fixed indentation. Added syntax check step before deploy.

**Lesson:** Always syntax-check any Python file before deploying:
```bash
python3 -c "import ast; ast.parse(open('file.py').read())" && echo OK
```
An IndentationError is not a runtime error — it kills the whole module at import time. The API returns empty/null with no stack trace visible to the caller.

---

### 60. `bool("0") == True` — Python string zero is truthy

**What happened:** Site config stores `pause_scheduler` as string `"0"` or `"1"`. Code used `bool(cfg.value)` to detect if scheduler was paused. `bool("0")` is `True` because it's a non-empty string — so the scheduler was incorrectly reported as always paused.

**Fix:** Use explicit membership test: `cfg.value in (True, 1, "1", "true")`

**Lesson:** Never use `bool()` to check truthy/falsy on values that might be string `"0"`. Site config values come back as strings. Always do explicit comparison.

---

### 61. `Site Activity` action field is a fixed enum — custom strings raise validation errors

**What happened:** `set_development_mode` in `site.py` called `log_site_activity(self.name, "Dev mode enabled")`. The Site Activity doctype's `action` field has a strict option list (26 valid values). "Dev mode enabled" is not in the list — raises `frappe.exceptions.InvalidValueError` visible to the user.

**Fix:** Replaced `log_site_activity(...)` with `frappe.logger().info(...)` for non-standard audit events.

**Lesson:** Before calling `log_site_activity()` with a custom action string, check the allowed options in `site_activity.json`. For anything outside the standard lifecycle actions, use `frappe.logger()` instead.

---

### 62. Vue 3 `<template v-for>` — `:key` goes on the template, not the child element

**What happened:** Wrapping bench rows in `<template v-for="(bench, idx) in list">` to add group header dividers. The child `<div class="bench-row">` retained `:key` — Vue warned and group state was lost on re-render.

**Fix:** Move `:key="bench.name"` to the `<template>` tag, not the `<div>`.

**Lesson:** When using `<template v-for>` to render multiple sibling elements per iteration, the `:key` must live on the `<template>`, not any child. Pattern for group headers:
```html
<template v-for="(item, idx) in list" :key="item.name">
  <div v-if="idx === 0 || list[idx-1].group !== item.group" class="group-header">
    {{ item.group_title }}
  </div>
  <div class="row">...</div>
</template>
```

---

### 63. Standalone API file pattern — add features alongside large controllers without touching them

**What happened:** Needed to add new whitelisted API methods for the Dev Overview. The obvious place was `bench.py` — but it's 5000+ lines. Editing it risks merge conflicts, hook order issues, and review overhead.

**Fix:** Created `bench_dev_overview.py` as a sibling file in the same doctype folder. Decorated with `@frappe.whitelist()` directly. Called from the frontend via the full dotted path:
```python
# bench_dev_overview.py
@frappe.whitelist()
def get_dev_overview_benches():
    ...
```
```javascript
// DevOverview.vue
const DEV_OVERVIEW_URL = 'press.press.doctype.bench.bench_dev_overview.get_dev_overview_benches';
```

**Lesson:** You don't need to put every whitelisted method inside the DocType controller. Sibling files in the same folder work perfectly — the dotted path just needs to resolve to the function. This keeps large controllers clean and makes feature code easier to test in isolation.

---

### 64. press-f1 disk full (100%) — build server needs room for Docker images
**Status:** PERMANENT  
**What happened:** Every deploy build failed at "Upload / Build Context" step. Blank screen on deploy page.  
**Root cause:** press-f1 had a 75G disk with 76G of Docker data (images + build cache + overlay layers). Zero bytes free.  
**Fix:** Cleaned 16G (build cache 8.5G, old images, /tmp backups, journal logs). Expanded disk 75G → 150G in Hetzner. Installed daily cleanup cron at `/etc/cron.d/docker-cleanup` (prune images >72h, build cache, /tmp, journals daily at 3 AM; Docker logs weekly).  
**Lesson:** Build servers need 2-3x headroom vs active images. Each bench image is 3-4G. With 11 images, 75G is too tight. Monitor with `df -h` and `docker system df`.

---

### 65. docker_execute $() subshells expand on the HOST, not inside the container
**Status:** KNOWLEDGE  
**What happened:** Git status script using `echo "app:$(git ...)"` showed raw script text as app names.  
**Root cause:** The Press agent runs `docker exec container sh -c 'command'` but `$()` in the command gets expanded by the HOST shell first (which has no `apps/` directory). The subshell returns empty/error.  
**Fix:** Replaced compound subshell scripts with individual `git -C apps/appname` commands — one `docker_execute()` call per git operation. Slower but reliable.  
**Lesson:** Never use `$()` subshells in docker_execute commands. Use `git -C path` instead of `cd path && git`. `&&` works (shell operator), but `cd` fails (not a binary). `set -e` fails (not a binary).

---

### 66. Deploy page blank screen — frappe-ui resource `.loading` vs `.get.loading`
**Status:** PERMANENT  
**What happened:** Deploy build page showed blank white screen. No loading indicator, no error.  
**Root cause:** Template had `v-if="deploy"` which is falsy when doc hasn't loaded. frappe-ui document resources have `.get.loading` not `.loading` at the top level. Accessing `$resources.deploy.loading` returned `undefined` (falsy), and the else branch for error state was also missing.  
**Fix:** Added 3 states: loading spinner (`$resources.deploy?.get?.loading`), error ("Build Not Found"), content (`v-else`). Added `immediate: true` to status watcher for timer init on page load.  
**Lesson:** Every resource-driven page needs 3 states: loading, error, content. Never assume a resource loads.

---

### 67. rg.add_app() expects {name, title, repository_url} — not {app, source}
**Status:** KNOWLEDGE  
**What happened:** Created app registered in Press (App + App Source + Release) but never appeared in the bench's app list. No error shown.  
**Root cause:** `Release Group.add_app()` checks `app.get("name")` for the app name. Passing `{"app": "x", "source": "y"}` returns `None` silently because `name` key is missing.  
**Fix:** Pass `{name, title, repository_url, branch, source}` matching the method's expected keys.  
**Lesson:** Read the actual method signature before calling Press APIs. Silent failures are common — always verify the result.

---

### 68. Test fixtures (_Test Notification) enabled on production — 15K email error loop
**Status:** PERMANENT  
**What happened:** Email Queue had 15,803 Error emails + 48,417 Error Log entries. Workers spent all time retrying failed SMTP sends. The error was `SMTPRecipientsRefused` on every retry.  
**Root cause:** Frappe test fixtures (`_Test Notification 1-6`) were enabled on the production site. These fire on every document New/Save/Value Change event, generating email notifications to invalid recipients. The test data was left behind from running `bench run-tests` on the production site (or from a restore that included test data).  
**Fix:**  
1. Disabled all `_Test Notification` records: `UPDATE tabNotification SET enabled=0 WHERE name LIKE '_Test%'`  
2. Deleted all test data: `_Test Notification 1-6`, `_Test Role 1-4`, `_Test Print Format 1`  
3. Purged 15,803 Error + 1,942 Not Sent emails from Email Queue  
4. Purged 48,417 Error Log entries from email retry spam  
**Lesson:**  
- **NEVER run `bench run-tests` on a production site** — test fixtures persist after tests finish  
- After any database restore to production, scan for `_Test%` records: `SELECT name FROM tabNotification WHERE name LIKE '_Test%'`  
- If test fixtures exist, delete them AND their child tables (e.g. `tabNotification Recipient`, `tabHas Role`)  
- Consider adding a Watch Tower rule to alert if `_Test%` records exist on production  
**Quick cleanup command:**  
```sql
SET SQL_SAFE_UPDATES=0;
DELETE FROM `tabNotification Recipient` WHERE parent LIKE '_Test%';
DELETE FROM `tabNotification` WHERE name LIKE '_Test%';
DELETE FROM `tabHas Role` WHERE role LIKE '_Test%';
DELETE FROM `tabRole` WHERE name LIKE '_Test%';
DELETE FROM `tabPrint Format` WHERE name LIKE '_Test%';
SET SQL_SAFE_UPDATES=1;
```

### 69. Press deploy keys are read-only — `git push` from Claude / agent sessions fails unless your SSH agent is forwarded
**What happened:**
Tried to push admin-panel commits from press-ctrl with `git push upstream cloudflare-dns` — got `ERROR: Permission to accurate-systems/press.git denied to deploy key`. Tried again as the `frappe` user with `github_ed25519` — same error. But other agent sessions running in parallel were successfully pushing commits to the same repo from the same machine.
**Root cause:**
Both keys deployed on press-ctrl (`/root/.ssh/id_ed25519` fingerprint `dgcuZD5inA9p8gJuCnfoyC0Fmvv+Ph7MApi7d4Wqy2c` and `/home/frappe/.ssh/github_ed25519` fingerprint `pPZnE/lteumqZYIJ5JRGcKF0RkmgzE+oE6Ft2pkj7HY`) are GitHub **deploy keys with read-only access**. Other sessions that succeed do so via **SSH agent forwarding** (`ssh -A press-ctrl`) — when a developer's terminal is connected, their personal GitHub-write key flows through `SSH_AUTH_SOCK` and `git push` picks it up automatically. This was enabled by commit `afe3171e04 feat(ssh): enable SSH agent forwarding for in-bench git access`.
**How we worked around it:**
- Bundle commits with `git bundle create` to a safe location (Hetzner dev disk) so work isn't lost.
- Apply patches with `git am` directly on press-ctrl so the live code is up to date.
- Wait for the user's `ssh -A` session to push to GitHub.
**Permanent fix:**
GitHub repo Settings → Deploy keys → find `press-ctrl@mvpstorm.com` (fingerprint `pPZnE/lteumqZYIJ5JRGcKF0RkmgzE+oE6Ft2pkj7HY`) → check **Allow write access**. Apply on both `accurate-systems/press` and `Veela-Beauty/press`.
**Lesson:**
- "Push works for them" doesn't mean "auth is configured" — it can mean "their terminal is forwarding an agent." Always check both.
- Bundle backups before any push retry, especially when multiple agents are committing in parallel.

### 70. Custom Fields pattern for admin overrides on upstream-owned doctypes
**Why:**
The Admin Panel needed to add `monthly_cost_override`, `is_decommissioned`, `admin_notes` to the upstream `Server` DocType (and similar for `Team`). Modifying the upstream JSON would conflict on every `bench update --reset` and complicate merges.
**Pattern:**
Sibling file `<doctype>_admin_setup.py` with an idempotent `setup_xxx_admin_fields()` function that creates `Custom Field` records via `frappe.get_doc({"doctype": "Custom Field", "dt": "Team", ...}).insert()` if they don't already exist. Examples: `press/press/doctype/team/team_admin_setup.py`, `press/press/doctype/server/server_admin_setup.py`.
**Reading custom fields safely:**
Wrap the lookup in `try/except` so the API still works on benches where the installer hasn't run yet:
```python
def _server_admin_overrides(server_name):
    try:
        row = frappe.db.get_value("Server", server_name,
            ["monthly_cost_override", "is_decommissioned", "admin_notes"], as_dict=True)
        return float(row.monthly_cost_override or 0), int(row.is_decommissioned or 0), row.admin_notes or ""
    except Exception:
        return 0, 0, ""
```
**Lesson:**
- Sibling installer + try/except read = no upstream conflicts, no first-deploy failure.
- Run the installer once via `bench --site <site> console` after the patch lands. Re-running is a no-op.

### 71. SSH-based stats collector: 60s cache + BatchMode = sub-second dashboard with real Linux numbers
**Use case:**
Servers tab needed live RAM/CPU/Disk per server. Press's built-in `get_cpu_and_memory_usage()` requires `Press Settings.monitor_server` (Prometheus + node_exporter) which wasn't configured on autodeploypanel.
**Approach (`press/api/admin_panel_stats.py`):**
Single SSH probe per machine. One-liner concatenates 4 sources, separated by `---`:
```bash
head -5 /proc/meminfo; echo ---; echo CPUS=$(nproc); echo ---; uptime; echo ---; df -B1G --output=size,used,avail / | tail -1
```
Parsed in `_parse_probe()`. Cached 60 s in `frappe.cache().set_value(key, value, expires_in_sec=60)` — first load is ~2-4 s for 3 servers in parallel, subsequent loads are instant.
**SSH flags that matter:**
- `BatchMode=yes` — die immediately on auth failure instead of prompting (would hang forever in non-interactive context)
- `ConnectTimeout=5` + outer `subprocess.timeout=8` — bounded latency; one slow / unreachable server can't stall the whole tab
- `StrictHostKeyChecking=no` — first-time hosts don't block (Press has firewall + key auth, so MITM risk is bounded)
**Frontend pattern:**
Stats are lazy-loaded per row via `Promise.all(servers.map(s => loadOneStats(s.name)))` — the table renders instantly, stats fill in over a few seconds. Color thresholds (green <70%, orange 70–85%, red ≥85%) make upsize candidates visually obvious.
**Lesson:**
- For "good enough" live infra metrics without full monitoring infra: SSH + `/proc` + cache is 30 minutes of work and gives real numbers. Use Prometheus for history and alerts later.
- Always cap timeouts — a single unreachable server should never block the dashboard.

### 72. In standalone-mode Press, group servers by IP — same machine has Server + Database Server + Proxy Server records
**Why:**
First version of `get_servers_admin()` returned 7 rows for 3 physical machines (3 app + 3 db + 1 proxy). Each pulled the same baseline cost from `SERVER_COSTS`, inflating the total by 2-3x. Confusing for admins, wrong for the cost summary.
**Fix:**
Group by `ip or name` (fallback to name when IP is empty, e.g. on `press-ctrl` which isn't in the Server doctype but appears in `SERVER_COSTS`). Each unified row carries a `roles: ['app', 'db', 'proxy']` array. Cost / sites / benches / admin overrides are sourced from the `app` role only:
```python
machines = {}
for kind, doctype in (("app", "Server"), ("db", "Database Server"), ("proxy", "Proxy Server")):
    for s in frappe.get_all(doctype, fields=["name", "ip", "status", "cluster"]):
        key = s.get("ip") or s["name"]
        if key not in machines:
            machines[key] = { ..., "roles": [] }
        machines[key]["roles"].append(kind)
        if kind == "app":
            # cost + admin fields owned by app role only
            ...
```
**Frontend:**
Kind column renders one Badge per role (`app` blue, `db` purple, `proxy` green). Stats / Edit / Decommission gate on `roles.includes('app')` instead of `kind === 'app'`.
**Lesson:**
- Press standalone mode = "one machine wears 3 hats." Don't model that as 3 rows in admin UIs — model it as 1 row with hat badges.
- Always check for double-counting when iterating multiple doctypes that may point at the same physical resource.

## Frappe Cache Wrapper Stale-Local Bug — 2026-05-04

**What happened:** Watch Tower's per-alert throttle (`should_send_alert`, capped 3 sends per 6h) was completely bypassed in production. One inbox got **700+ alert emails in 24h** (~30/hour) when the design called for **~12/day total**.

**Root cause:** `frappe.cache().set_value(key, val, expires_in_sec=N)` writes to Redis but **does not** update `frappe.local.cache`. `cache.get_value(key)` (no kwargs) reads `frappe.local.cache` FIRST and only falls through to Redis on miss — and on the fall-through, it populates `frappe.local.cache`. So:

```python
cache.set_value(k, 1, expires_in_sec=600)   # redis = 1, local = (unset)
cache.get_value(k)                          # local miss → redis = 1 → local POPULATED with 1
cache.set_value(k, 2, expires_in_sec=600)   # redis = 2, local = STILL 1
cache.get_value(k)                          # local hit → returns 1 ❌
```

Within one worker process, every subsequent read after the first returns the stale local value. Multiple workers each have their own `frappe.local.cache` so they each independently bypass the throttle. With Watch Tower's per-target-doc fan-out (27 sites × hourly tick = 27 attempts) and the throttle silently broken, the cap never kicks in.

**Fix:** pass `expires=True` to `get_value` whenever the matching write used `expires_in_sec`. That tells Frappe to skip the local cache for both read and write-back:

```diff
- raw = cache.get_value(key)
+ raw = cache.get_value(key, expires=True)  # force redis read; local cache is stale for expiring keys
```

Commit: `26e9ce16` in `Veela-Beauty/frappe_theme_switcher` (`frappe_theme_switcher/watch_tower/alerts/_helpers.py:96`).

**Lessons:**
- Anywhere you call `cache.set_value(..., expires_in_sec=...)` and later `cache.get_value(...)`, you MUST pass `expires=True` to the read. Audit any throttle / counter / lock pattern using `expires_in_sec`.
- **This is generic Frappe**, not Watch Tower–specific. Applies to any app using Frappe's redis wrapper for TTL-based state.
- Smoke test for any TTL-based cache code: `set 1 → get → set 2 → get`. Second get must return 2; if it returns 1 you have this bug.
- Watch Tower's `target_doctype` causes the engine to call the alert function ONCE PER target doc (e.g. once per Site). Alert functions that do their own internal scan (over all sites) AND get fanned out by the engine will fire N×N attempts. The throttle is the only thing standing between you and 700+ inbox emails — verify it actually works.

## MCP Server — 4 Bugs Fixed in 2026-05-10 Session

Press now ships an MCP (Model Context Protocol) server at `/api/method/press.mcp_server.server.handle` so external AI agents can drive Press through scoped audited tokens. Four bugs surfaced + were fixed in one session. Each was subtle. Full operational guide: [`02-operations/mcp-server.md`](02-operations/mcp-server.md). Status: **PERMANENT** for all four.

**Bug 1 — `auth_hook` blocks the MCP endpoint (HTTP 401 from `press/auth.py:101`)**
- Press's `auth_hook` runs before any whitelisted method body and rejects URLs not in `ALLOWED_PATHS` or `ALLOWED_WILDCARD_PATHS`. `press.mcp_server.*` was missing.
- **Fix**: add `/api/method/press.mcp_server.` to `ALLOWED_WILDCARD_PATHS` (commit `4b775755d0`). One line.
- **Lesson**: Press's auth hook is gate #0 — runs before token verification. Every new whitelisted module must be allowlisted.

**Bug 2 — Wrong password logs the user OUT of the dashboard**
- `_check_password` raised `frappe.AuthenticationError`. Frappe's HTTP layer maps that to 401, which the Vue dashboard treats as "session expired" → force-logout.
- **Fix**: catch `AuthenticationError` inside `_check_password`, re-raise as `ValidationError` (HTTP 417). Dashboard shows inline error, session intact (commit `d5b5bf6ed0`). Also replaced `frappe.local.login_manager` (request-bound, session-coupled) with stateless `frappe.utils.password.check_password` — that path was rejecting correct passwords because login_manager checks against the request's session user, not the username arg (`e95c4f8a37`).
- **Lesson**: Re-auth flows (token mint, sensitive action confirm) inside an authenticated session must NEVER raise `AuthenticationError`. The dashboard treats any 401 as session-expired. Use `ValidationError` so it surfaces inline.

**Bug 3 — Vue sends `username=""` (empty)**
- `IssueTokenDialog.vue` reads `window.frappe?.session?.user` — undefined in the Vue dashboard context, so `username=""` was sent. Backend's `check_password("", "...")` always fails.
- **Fix**: backend defaults blank `username` to `frappe.session.user` (commit `ff98265409`).
- **Lesson**: `window.frappe.session.user` exists on the OLD desk pages but NOT in the Vue dashboard. Either bind from the `session` store or default server-side.

**Bug 4 — `docker_execute` "bench: not found" (returncode 127)**
- The cmd string `echo X | base64 -d | bench ...` got assembled into `docker exec <container> echo X | base64 -d | bench ...` and the HOST shell saw the `|` pipes — `bench` ran on the HOST, not in the container. On press-f1 the host's frappe user PATH doesn't include `/home/frappe/.local/bin`.
- **Fix**: wrap the entire pipeline in `bash -lc '...'` so docker exec ships ONE arg to the container's bash, which loads the user profile (`-l`) and finds bench. Commits `6d6131c670` (run_python_on_site, run_sql_on_site), `dfaab39874` (`bench_read_app_file`'s `wc -c <` and `find | head` redirects).
- **Lesson**: ANY shell metacharacter (`|`, `<`, `>`, `&&`, `;`, `$()`) inside a `bench.docker_execute(cmd)` string gets interpreted by the HOST shell, not the container. Always wrap multi-token pipelines in `bash -lc '...'`. Single `docker exec` calls (no pipes) are fine.

## Press Team `press_role` is the Bench-Visibility Field — 2026-05-10

**Symptom:** Marco Maher (`markomaher333@gmail.com`) and Mahmoud Abdelmomen (`mahmoud2580mahmoud@gmail.com`) saw an empty Benches list in the Vue dashboard despite being members of team `sqkn1globp` (which owns 8 RGs).

**Root cause:** They had `Frappe role = 'Press Member'` (Frappe's User.roles), but their `Team Member.press_role` was empty/restrictive. The Vue dashboard's bench-list endpoint filters on `Team Member.press_role`, NOT on Frappe roles. `press_role` is a free-text field with values like `Platform Admin`, `Operator`, etc. used by Press's own permission layer.

Eslam (the team owner) had `press_role = 'Platform Admin'` on his Team Member rows for both teams; that's what gave him visibility.

**Fix:** updated `tabTeam Member` to set `press_role = 'Platform Admin'` for both users on both teams (`sqkn1globp` and `uibc5n8ho1`). They now see all 9 benches across both teams. **No System Manager role added** — the user explicitly said don't grant System Manager; `press_role = Platform Admin` on the Team Member row is enough.

**Lesson:**
- Press has TWO permission systems: Frappe's `User.roles` (System Manager, Press Member, etc.) AND Press's own `Team Member.press_role`. They are NOT the same thing.
- "User can see benches in dashboard" is gated by `Team Member.press_role`, not by Frappe roles. Bumping someone to `System Manager` ALSO works (System Manager bypasses team filtering) but is too broad — `Platform Admin` on the Team Member row is the right tool.
- When a user "lost access" after a deploy, the FIRST place to check is `tabTeam Member` rows for `press_role` value — not `tabHas Role`.

**Quick fix recipe:**
```sql
UPDATE `tabTeam Member`
SET press_role = 'Platform Admin'
WHERE user IN ('user1@example.com', 'user2@example.com');
```
Plus ensure they have a Team Member row on every team that owns benches they should see (insert with `press_role='Platform Admin'` if missing).

Status: **PERMANENT** (rows persist; doesn't repeat on deploy).

## Press Has 3 Permission Systems — sync ALL when "user can't do X" — 2026-05-10

**Symptom:** Marco + Mahmoud appeared as "DevOps Admin" in the dashboard's team panel BUT couldn't do any bench actions (Update / Restart / Deploy buttons missing/disabled).

**Root cause:** Press has THREE separate permission systems and they're all named "role" or "press_role":

1. **`User.roles`** (Frappe's standard) — child table on User. Values like "System Manager", "Press Member", "Press Admin". Controls Desk-level access. Used to gate `/api/method/frappe.client.*` and DocType-level perms. NOT what the Vue dashboard reads.

2. **`Team Member.press_role`** (free-text Data field) — what renders as the colored badge in the team panel ("Platform Admin", "DevOps Admin", "Developer", etc.). Pure UI label. Setting this changes what the user APPEARS to be but does NOT change what they CAN DO.

3. **`Press Role` doctype + `Press Role User` child table** — THE actual gate. Has 14 boolean flags (`admin_access`, `allow_apps`, `allow_bench_creation`, `allow_billing`, `allow_dashboard`, `allow_site_creation`, `allow_server_creation`, etc.). The dashboard's `press.api.account.user_permissions` endpoint queries:
   ```python
   SELECT * FROM `tabPress Role` pr
   INNER JOIN `tabPress Role User` pru ON pru.parent = pr.name
   WHERE pr.team = <current_team> AND pru.user = <session.user>
   ```
   Then ORs flags across all matching rows. If no Press Role doc exists for this user on this team → all flags False → no actions visible. **Result is cached 5 min** in `frappe.cache` under key `user_permissions.{team}.{user}`.

**Marco + Mahmoud's case:**
- Press Role docs existed on team `sqkn1globp` (titles "OptiFlowERP Developer" / "OptiFlow Flutter Developer") with `admin_access=1` + all flags=1. They could act on team `sqkn1globp`'s 8 RGs.
- BUT no Press Role docs existed for them on team `uibc5n8ho1` (Mohammed's team, 1 RG). Dashboard switching to that team → user_permissions returned all False → no buttons.
- The earlier fix that set `Team Member.press_role = "Platform Admin"` only changed the UI badge, not the actual permissions.

**Fix recipe:**
```python
# For each user, for each team they should admin:
# 1. Find existing Press Role they're in OR find any admin role on that team
# 2. Either update flags to 1, or insert Press Role User row, or create new Press Role
# 3. Clear cache: frappe.cache.delete_value(f"user_permissions.{team}.{user}")
```

After fix, calling `bench --site <site> execute press.api.account.user_permissions` as the user returns all `True`.

**Verification:** the dashboard caches user_permissions for 5 min. After fixing, either wait 5 min OR call `frappe.cache.delete_value(f"user_permissions.{team}.{user}")` for every (user, team) combo, OR have the user hard-refresh + switch team.

**Lesson:**
- "User can SEE benches but can't ACT on them" = Press Role flags problem (system #3), NOT a Frappe role problem.
- "User can't see benches at all" = Team Member missing or `press_role` field empty, OR no Press Role doc on the team.
- "User has the right role badge but actions are missing" = `Press Role` flags are off OR no `Press Role User` row.
- The badge color in the team panel comes from a static map in `dashboard/src/components/RoleCell.vue` keyed on the `Team Member.press_role` text — purely cosmetic.
- Don't grant `User.roles += System Manager` to "fix" this — it's the wrong knob (gives site-wide admin access). The right knob is the Press Role doctype + its users child.

Status: **PERMANENT**. Two helper scripts kept on press-ctrl at `/tmp/_press_role_diag.py` (read-only inspection) and `/tmp/_fix_press_role2.py` (idempotent ensure-admin-role + cache clear).


## MinIO Offsite Backups — Agent Drops `endpoint_url` Silently — 2026-05-17

**Symptom:** Click Clone Site → "Latest backup" mode → red `No usable offsite backup found for site X`. Or trigger offsite backup directly → agent records `Upload Site Backup to S3` as Failure with `botocore.exceptions.ClientError: An error occurred (InvalidAccessKeyId) when calling the CreateMultipartUpload operation: The AWS Access Key Id you provided does not exist in our records.`

**The clue is the error message phrasing**: `"in our records"` is real AWS S3 wording. Whenever you see `InvalidAccessKeyId` against MinIO, the agent is actually talking to real AWS — meaning `endpoint_url` never reached the boto3 client.

**Three places must all agree for MinIO offsite backups to work:**

1. **`Press Settings`** must carry `offsite_backups_access_key_id`, `offsite_backups_secret_access_key` (in `__Auth`), `aws_s3_bucket`, `backup_region`. Different from `remote_uploads_*` — Press has two independent S3-credential pairs and configuring one doesn't auto-configure the other.

2. **`Backup Bucket` doctype row** must exist with `bucket_name` (autoname field — pass `bucket_name=` NOT `name=`, otherwise Frappe throws `Bucket Name is required`), `endpoint_url`, `region`, `cluster`. Bug we hit: `get_backup_bucket()` in `site_backup.py` was selecting only `["name", "region"]` — even with the agent.py fix, `endpoint_url` never propagated. Fixed in commit `462ef02133`.

3. **Agent must be ≥ commit `809e9c2`** on `Veela-Beauty/press-agent`. Upstream `frappe/agent` does NOT consume `auth["ENDPOINT_URL"]` in `upload_offsite_backup` — it only reads `REGION`. Our fork reads `ENDPOINT_URL` and passes it to `boto3.client("s3", endpoint_url=...)`.

**Smoke test for "does the agent payload include ENDPOINT_URL":**
```python
rd = frappe.db.get_value("Agent Job", "<recent-Backup-Site-job>", "request_data")
# expect "ENDPOINT_URL": "http://..." inside the offsite.auth dict
```
If the field is missing, Press is on a build before `462ef02133`. If the field is present but the agent still fails with `InvalidAccessKeyId`, the agent on that server is pre-`809e9c2` — git pull + restart `agent:web agent:worker-0 agent:worker-1`.

Status: **PERMANENT** on press-f1 (Press patched, agent fork deployed). **PENDING** on u4 and u5 — same agent fork commit must be deployed there before their hosted sites can offsite-back-up to MinIO.


## Clone Site Bench Picker — `confirmDialog` Field Type Casing Trap — 2026-05-17

**Symptom:** A `confirmDialog({fields: [...]})` dialog renders dropdown fields as plain text inputs instead.

**Root cause:** The old `onCloneSite()` used `fieldtype: 'Select'` (Frappe DocType field-style casing) on the mode field. But frappe-ui's `<FormControl v-bind="field">` expects `type: 'select'` (lowercase, HTML-style) — `fieldtype` is silently ignored. Field falls through to default text input.

**Lesson — frappe-ui FormControl uses HTML-input type names, not Frappe DocType field names:**
- ❌ `fieldtype: 'Select'`, `fieldtype: 'Link'`, `fieldtype: 'Check'`
- ✅ `type: 'select'`, `type: 'combobox'`, `type: 'checkbox'`, `type: 'text'`

The `ConfirmDialog.vue` template branches on `field.type === 'link'` for a custom `<LinkControl>`, otherwise spreads to `<FormControl v-bind="field">`. So if you forget to set `type` OR you use the wrong casing, you silently get a text input. No warning, no error.

**Bench-picker pattern (preferred — proper SFC, not `confirmDialog`):** when the field needs a custom data fetch (e.g. "benches whose app set ⊇ source apps"), don't bolt onto `confirmDialog`. Build a proper SFC like `CloneSiteDialog.vue`:
```vue
<FormControl
  label="Target Bench"
  type="combobox"
  :options="benchOptions"
  v-model="targetBench"
/>
```
Pre-fetch options via `createResource({url: 'press.press.doctype.site.site_clone.get_clone_options', auto: true})`. Live availability checks and reactive cross-field validation work normally with `watch()` and `computed()`.

Status: **PERMANENT**. New dialog at `dashboard/src/components/site/CloneSiteDialog.vue`. The wider lesson — search the codebase for any other call site using `fieldtype:` inside a `confirmDialog({fields: [...]})` and fix to `type:`:
```bash
grep -rn "fieldtype:" dashboard/src/ | grep -v doctype | head
```


## Press API Method Returning Dict, Frontend Treating as String — 2026-05-17

**Symptom:** Clone Site dialog → click Clone → site IS created → redirect lands on `/sites/[object Object]` → 404 from `press.api.client.get` because no site is named `[object Object]`.

**Root cause:** `clone_site()` was declared `-> str` but returned whatever `press.api.site._new()` returns: a dict `{"site": site.name, "job": <agent_job_name>}`. The type hint is just documentation — Python doesn't coerce. The dashboard did `router.push(\`/sites/${newName}\`)` and JS stringified the dict to `"[object Object]"`.

**Lesson:**
- **Python return-type hints are non-binding.** A function declared `-> str` that returns a dict will pass static analysis but break every JS consumer that assumed a string.
- **When proxying through Press's `_new`, return what `_new` returns AND read it as a dict on the frontend.** Reference: `NewSite.vue:onSuccess(response) { router.push({name: 'Site Job', params: {name: response.site, id: response.job}}) }`.
- **Defensive pattern in the consumer:** `const newSite = response?.site || response;` handles both shapes (dict-with-site OR bare string) without crashing.

Status: **PERMANENT**. Fixed in `5eb0a94f4a`. Hint to spot the pattern fast: when a dashboard call ends up at `/sites/[object Object]` or `/x/[object Object]`, the server returned a dict and the frontend stringified it. Browser network tab will show the actual response shape; match the consumer.


## Clone Site `fresh_backup` Mode Silently Rolled Back — 2026-05-19

**Symptom:** Clone Site dialog in `fresh_backup` mode → click Clone → red toast "Fresh backup queued for source site. Wait for it to complete, then retry with mode='latest_backup'." → user waits 10 minutes → re-opens dialog in `latest_backup` mode → "No usable offsite backup found". Looks like the backup never ran.

**The check that proves it:** filter `Site Backup` for the source site with `offsite=1` after the click. If `count: 0`, the row was rolled back. The user got the "queued" message because it's a hard-coded `frappe.throw()` that fires regardless of whether the insert before it actually persisted.

**Root cause:** `clone_site()` in `press/press/doctype/site/site_clone.py`:
```python
elif mode == "fresh_backup":
    source.backup(with_files=True, offsite=True)  # inserts Site Backup row
    frappe.throw(...)                              # rolls back the request transaction
```
Both run inside the same HTTP request's DB transaction. `frappe.throw` rolls the whole transaction back — including the freshly-inserted `Site Backup` row and any side-effects fired by its `after_insert` hook (the Agent Job dispatch).

**Lesson — `frappe.throw()` after `.insert()` in the same request is destructive unless you commit first:**
- The fix is one line: `frappe.db.commit()` between the insert and the throw.
- The reference pattern is `press/press/doctype/site/backups.py:357` (`schedule_logical_backups_for_sites_with_backup_time` commits between each per-site backup call so a later failure doesn't unqueue earlier successes).
- Test discipline: mocking `Site.backup` in the unit test (as the original `test_clone_fresh_backup_triggers_backup_then_raises` did) hides this bug — the mock returns happily, the throw fires, the test passes. To catch transaction rollback you MUST run with real `Site.backup` and assert that the row count went up by exactly one. That's what the new `test_clone_fresh_backup_persists_site_backup_row` does.
- Wider rule: anywhere in Press's codebase that calls `.insert()` then `frappe.throw()` without an intervening commit is suspect. Search `grep -rnB3 'frappe.throw' press/ | grep -B1 'insert()'` and audit.

Status: **PERMANENT**. Fixed in <commit-this-pr>. The new regression test would have caught this on day one if it had existed. Lesson for future test authors: prefer real fixtures over mocks when the unit-under-test does database side-effects — mocks hide transactional bugs.


## Frappe Password Fields Wipe on Save When In-Memory Value Is Falsy — 2026-05-19

**Symptom:** Press operations that depend on encrypted credentials (offsite backups, Twilio, Stripe, etc.) suddenly start failing with `Password not found for Press Settings Press Settings <fieldname>` even though the credentials were configured and worked yesterday. Re-writing the credential fixes it. A few days later it breaks again.

**Root cause:** Frappe's `Document._save_passwords()` (in `frappe/model/base_document.py:1125`) does this on every `.save()`:
```python
for df in self.meta.get("fields", {"fieldtype": ("=", "Password")}):
    new_password = self.get(df.fieldname)
    if not new_password:
        remove_encrypted_password(self.doctype, self.name, df.fieldname)
    if new_password and not self.is_dummy_password(new_password):
        set_encrypted_password(...)
```

If the in-memory Password field is falsy at save time → DELETE the `__Auth` row, unconditionally. There are three common ways the in-memory value becomes falsy:

1. **Desk save without re-typing the password.** Desk renders Password fields as `••••` (a dummy mask). Some flows DO re-send the dummy back (preserved); some flows DON'T (e.g. if the password field is collapsed inside a tab that wasn't expanded → form submits empty for it). Then it's wiped.
2. **Console save (`frappe.get_doc("Press Settings").save()`).** `get_doc` does NOT auto-load Password values from `__Auth` into the doc. The in-memory value is `None`. Save → wipe.
3. **Patch / migration code that creates a fresh doc instance and saves it.** Same as console.

**Fix (one of two):**
- **(A) Per-doctype `before_save()` override that adds falsy Password fieldnames to `self.flags.ignore_save_passwords`.** This is what Press Settings does as of 2026-05-19:
  ```python
  def before_save(self):
      password_fields_to_preserve = [
          df.fieldname
          for df in self.meta.get("fields", {"fieldtype": ("=", "Password")})
          if not self.get(df.fieldname)
      ]
      if password_fields_to_preserve:
          existing = self.flags.get("ignore_save_passwords") or []
          if existing is True:
              return
          self.flags.ignore_save_passwords = list({*existing, *password_fields_to_preserve})
  ```
- **(B) Explicitly `set_encrypted_password()` after `.save()` instead of via the doc.** Bypass the password-field mechanism entirely. Verbose but absolute.

**When to use which:**
- Singletons holding system credentials (Press Settings, Email Account, integrations) → option (A), always-on protection. Tradeoff: clearing a password now requires `remove_encrypted_password()` explicitly, can't be done from desk.
- One-off config doctypes with rare saves → option (B) where the save happens.

**Test discipline:** test by seeding a known secret with `set_encrypted_password()`, calling `frappe.get_single(...).save()` after changing a non-password field, then calling `get_decrypted_password()` again. If the secret is gone, save is wiping. See `test_press_settings.py:test_password_preservation_on_save_without_password_resubmit`.

**The wider rule:** any DocType with Password fields used for system integrations needs option (A). On Press Settings alone there are 15 Password fields (offsite_backups_secret_access_key, aws_secret_access_key, twilio_api_key_secret, stripe_secret_key, razorpay_key_secret, remote_secret_access_key, asset_store_secret_access_key, docker_s3_secret_key, erpnext_api_secret, frappeio_api_secret, ic_key, plausible_api_key, press_monitoring_password, school_api_secret, spamd_api_secret). The fix is one `before_save()` that protects all of them at once.

Status: **PERMANENT** on Press Settings. **OPEN** elsewhere — any other Single or sysadmin-edited doctype with Password fields is still vulnerable. Audit candidates: `Email Account`, `Stripe Settings`, `Razorpay Settings`, `Twilio Settings`, any `*Settings` Single. Replicate the same `before_save()` to each.


## MCP Tools Without JSON Schema = Clients Guess Arg Names — 2026-05-19

**Symptom:** MCP tools fail with `ValidationError: missing required args: ['query']` (or `['site_name']`) even though the caller swears they sent those names. Multiple users hit the same failure across `site_run_sql` and `site_status`.

**The proof:** the actual JSON payloads in the call log:
```
site_run_sql: sent {"site_name": "...", "sql": "..."}  → required ["site_name", "query"]
site_status:  sent {"site": "..."}                      → required ["site_name"]
```
Callers used the SHORTER natural names (`sql`, `site`) instead of the canonical longer ones. Server's `description` field uses natural language ("Run SQL on the site database", "Site bench + status + recent agent jobs") — LLM clients (Claude Code, Cursor) inferred arg names from those descriptions and got it wrong every time.

**Root cause:** the MCP catalog published `required_args: [list of names]` but **no JSON Schema for parameters**. There was no machine-readable contract telling clients "the param name is exactly `site_name`". Clients had no choice but to guess.

**Lesson — for any MCP/RPC catalog accessible to LLM clients, publish a JSON Schema, not just a name list:**
- Per-tool `args_schema: {type: 'object', properties: {...}, required: [...]}` with arg descriptions and types.
- The `description` field is for humans; the `args_schema` is the contract.
- Use a shared fragment dict for common args (`site_name`, `bench_name`, etc.) so descriptions stay consistent across tools.
- Add a **registration-time consistency check** that fires on import: every `required_args` entry MUST appear in `args_schema.properties`. Without that, schemas drift from reality and you're back to clients guessing.
- Enrich the dispatcher's "missing args" error: show `Got: [keys sent]. Expected: [canonical names]. Call help for the schema.` Turns a black-box failure into self-explaining feedback.
- Add a test-call form to your admin UI (here: `/dashboard/dev-tools/mcp`) that reads the schema at runtime and renders typed inputs. Cures "I have to keep typing curl commands to test this" pain.

**Wider rule:** any time you expose a function to an LLM (via MCP or otherwise), assume the LLM will read the human-language description as the spec. Publish a typed schema — JSON Schema, Pydantic model, dataclass — that the LLM can introspect. If your tool's contract is "trust me, the param is called X", clients will infer Y and fail until they trial-and-error.

Status: **PERMANENT**. All 58 Press MCP tools now have `args_schema`; consistency enforced at module load; dashboard has a Test Tool Call form. Audit candidates: any other RPC surface in Press that LLMs hit (the GraphQL-ish dashboard API resources are mostly Frappe-validated already, but custom-built helpers like `bench_dev_overview.*` could benefit from explicit param-shape declarations too).


## Auth Allowlist Gap Keeps Recurring → Build the Audit Script — 2026-05-19

**Symptom (third time in two weeks):** Non-System team user clicks a dashboard button → "Access not allowed for this URL" or instant force-logout. Today's incident hit `ahmedmowafy74@gmail.com` on three different flows at once:
1. Clone Bench dialog → `release_group_clone.clone_release_group` not in allowlist → 401
2. Bench page → `Bench Shell Log` perm denial flooding every 10s (separate but compounding)
3. Open in VS Code → wrong dotted path AND `bench_vscode.*` not in allowlist

**Pattern:** every time we add a new whitelisted method under `press.press.doctype.<x>.<y>.<method>` and wire the Vue dashboard to call it, if we forget to add `press.press.doctype.<x>.<y>.` to `ALLOWED_WILDCARD_PATHS` in `press/auth.py`, non-System team users get a 401. Vue's auth handler maps 401 → "session expired" → force-logout. Documented previously in lesson 64 and `feedback_press-auth-allowlist.md`. The lesson was written. People still forgot. Documentation alone is not enough.

**Root-of-root cause:** there was no automated check. The lesson said "remember to add the allowlist entry" but humans forget. The fix has to be enforcement, not memory.

**The fix that should stop the recurrence:** ship a `scripts/audit_dashboard_allowlist.py` that walks every `dashboard/src/**/*.{vue,js,ts}` file, extracts every `press.api.*` / `press.press.*` / `press.saas.*` / `press.mcp_server.*` dotted-path call, diffs against the allowlist, fails with exit 1 if anything is missing. Then wrap it in a `bench run-tests` test (`press/test_auth.py:TestAuthAllowlistCoverage`) so CI fails before the bug ships.

**Lesson — when the same documented mistake happens 3+ times, write the linter instead of writing the doc:**
- Documentation tells humans what to do. Humans forget under deadline pressure.
- A test that fails CI is forcing. No commit goes through with the gap.
- The audit script took 30 minutes to write; the four 401-logout incidents cost more than that in user-frustration time.
- Make the linter cheap to run (`python3 scripts/audit_dashboard_allowlist.py` exits 0 in <1s on a healthy tree) so devs run it before pushing.

**Side lesson — audit logs must not gate on actor's perms:** the `Bench Shell Log` part of today's incident was caused by `create_bench_shell_log()` calling `.insert()` without `ignore_permissions=True`. Bench Shell Log's `create` perm is System-Manager-only, but every dashboard dev feature that uses `Bench.docker_execute` writes one of these rows on every call. Result: non-System team users blocked from triggering operations they're already authorised to trigger via the parent bench's team-access check. The audit log was BLOCKING the action it was supposed to OBSERVE. Audit logs should always `ignore_permissions=True` and rely on the parent operation's auth check — the `owner` field captures who did it for the audit trail.

Status: **PERMANENT**. Audit script in `scripts/audit_dashboard_allowlist.py`. Test in `press/test_auth.py`. Fix to `Bench Shell Log` insert in `press/press/doctype/bench_shell_log/bench_shell_log.py`. Going forward: when adding a new whitelisted method, the test will fail until you also add the allowlist entry. Documentation-only lessons get this status: **DOCUMENTED-NOT-ENFORCED** until paired with a test that fails CI.





## Contract-Drift Audit Suite — 2026-05-19

**Symptom (compound):** Multiple recurring bug families share the same root cause — implicit contracts between the Vue dashboard and the Python backend that drift over time without anything checking. Today's incident with Ahmed exposed four contracts that were ALL broken:

1. allowlist coverage (auth.py allowlist missing Vue caller's path)
2. method exists (Vue calls a method that's not in the named module)
3. whitelist decorator (Vue calls a method without `@frappe.whitelist`)
4. audit-log perm gate (`Bench Shell Log` blocked non-System users)
5. MCP catalog parity (`tools.py` ↔ `_tool_catalog.js` drift — flagged in `tools.py` header but unenforced)

**Lesson — when you find ONE instance of "contract X is documented but unenforced", invest the day to write the audit script.** Five audits authored in one afternoon: ~200 lines each, all under 2 seconds runtime combined, all wrapped by one bench test. Drift now fails CI before merge instead of in production for the next new team member.

**Lesson 2 — audit scripts find BUGS as a side effect.** The "method exists" audit caught 5 pre-existing broken Vue → Python links that would 500 on click. Those are tickets for follow-up. The audit itself is the deliverable; the bugs it discovers are bonus value.

**Lesson 3 — audit scripts ship with EXCLUSION lists, not skip flags.** Each known-broken case goes into `KNOWN_DYNAMIC` (or equivalent) with a comment naming the ticket. The exclusion list is normal; growing the exclusion list without a comment is the failure mode to catch in code review.

Status: **PERMANENT**. 5 scripts in `scripts/audit_*.py`, all wrapped by `press/test_auth.py:TestDashboardContracts`. Combined runtime <2s. Each script is independently invocable for local dev (no `bench run-tests` ceremony needed).

## MCP args_schema Must Match the Python Signature — 2026-05-19

A live agent (running `bench_deploy` against the wazin-build flow) hit a 3-error chain because the published `args_schema` lied about the method's actual signature:

- `bench_deploy` schema said `apps: array<string>`; method iterates `apps` expecting dicts with `{app, release, hash}`. Caller's first call → `'str' object has no attribute 'get'`.
- `wait_for_bench_flip` schema accepts `site_name` + `target_candidate`; caller guessed `candidate` + `timeout` from the description. Two errors before the right args.

The bare catalog-parity audit (`audit_mcp_catalog_parity.py`) only checks that tool NAMES match between Python and JS. It doesn't validate that each tool's `args_schema` matches the method's actual `inspect.signature()`.

**Fix:** added `scripts/audit_mcp_schema_vs_signature.py` — imports each tool's Python method, compares its `inspect.signature()` parameters to the schema's declared properties, fails if schema documents an arg the method doesn't accept OR marks a required arg optional. CI-enforced via `press/test_auth.py:test_audit_mcp_schema_vs_signature`. Caught 4 additional drift cases beyond the live failure: `agent_job_list`, `bench_list_app_files`, `bench_recent_logs`, `site_backup`.

**Lesson — when documenting an API for an LLM client, BOTH the description and the schema must be precise.** A correct schema + vague description still produces wrong calls (the LLM guesses arg names from the description). A vague schema + correct description still produces wrong calls (the LLM trusts the schema). Both pieces are the contract.

**Side-lesson — every audit so far has caught bugs that were already shipping in production.** The allowlist audit caught 4 gaps. The method-exists audit caught 5 broken Vue→Python links. The schema-vs-signature audit caught 5 drifts. Pattern: write the audit, find bugs, fix bugs, set baseline, CI keeps it clean. Each audit pays for itself on the first run.

Status: **PERMANENT**. 6 audit scripts under `scripts/audit_*.py`; 6/6 tests pass in `press.test_auth.TestDashboardContracts`. Total runtime <5s.

## LLM Agents in Tight Retry Loops Will Burst Your Rate Limit — 2026-05-20

A real agent ran a 30-iteration polling loop sending `wait_for_bench_flip(...timeout=25)` to the MCP server. The method doesn't accept `timeout`, so each call `TypeError`'d in <1ms. **30 errors in ~3 seconds blew through the per-token rate limit before the agent made any real progress.** Same pattern would fire for any kwarg-typo in any loop.

**The root cause isn't the typo — it's that microsecond-fast validation rejections give the loop no natural back-pressure.** A successful call takes ~50ms-2s; a validation rejection takes <1ms. So a broken loop spins 50-100x faster than a working one. By the time the agent's prompt-side LLM realises something's wrong, the budget is gone.

**Two server-side guardrails fix it at the source:**

### Guard 1 — Filter unknown args at the dispatcher

The MCP dispatcher now only forwards args declared in the tool's `args_schema.properties` (plus the meta-args `dry_run`/`suppress_hints`). Unknown args are dropped, logged via `frappe.log_error`, and never reach the Python method. The same `wait_for_bench_flip(..., timeout=25, bogus="x")` call now succeeds with `status: pending`; the extras are silently ignored.

Why this is better than per-method `**kwargs`: tool methods stay strict (good for human readers + the schema audit), all 60+ tools benefit from one fix, and the `audit_mcp_schema_vs_signature` audit keeps the schema honest so the filter never drops a real arg.

### Guard 2 — Fail-fast burst guard

Same `(token, tool, rejection_kind, signature)` rejected 3 times in <10 seconds → return `BURST-GUARD: ... Fix the call before retrying` and reset the counter so the agent can retry once it fixes the args. Tracks two rejection kinds today: `missing_required_args`, `unknown_args`. The Redis-backed rate limiter is still the cross-worker enforcement; this is a tighter local gate that fires earlier.

**Lesson — any RPC surface exposed to LLM agents needs both guards:**
- **Filter at the dispatcher**, not at the method. Method signatures should stay typed and strict. The dispatcher absorbs LLM noise.
- **Detect and halt burst-failure loops** before they exhaust the rate budget. A loop that fires the same error 3 times in 10 seconds is broken — return a hard-stop with a clear "fix before retrying" message instead of letting it continue.

**Anti-patterns to avoid:**
- Adding `**kwargs` to every whitelisted method (invasive, scattered, no central audit point).
- Logging a warning and forwarding the bad args anyway (the method still TypeError's).
- Raising 429 on a single bad call (false positives hurt more than they help).

**Wider rule — when an LLM client and a human typed-method-signature meet, the impedance mismatch lives at the dispatcher, not at the method.** Build the LLM-tolerance layer once, in front of the strict layer. Don't try to retrain the LLM.

Status: **PERMANENT**. Shipped 2026-05-20 in commit `1d7972a03c`. Verified live: a `wait_for_bench_flip(..., timeout=25, bogus="x")` call now returns `status: pending` cleanly. Three identical missing-args rejections trigger `BURST-GUARD`; 4th call back to normal. Combined runtime impact: <1ms per call for the filter, negligible memory for the burst dict (capped at 1000 entries with auto-prune).

## Press Deploy: Two-Stage Trap — Build Succeeds, Site Never Flips — 2026-05-20

On Press's standalone-bench architecture, a successful Deploy Candidate Build does NOT automatically flip live sites to the new bench. The build produces a ready-but-empty bench container; existing sites keep running on the OLD bench until you explicitly call `site_update` per site.

The trap: `bench_deploy_and_wait` polls `wait_for_bench_flip` after the build, but `wait_for_bench_flip` only checks whether the site's `bench` field has changed — Press doesn't change it on its own. The wait loop returns `status: pending` forever.

**Recipe to actually complete a deploy:**
1. `bench_deploy_and_wait` — triggers build, polls wait (will time out at default `max_wait_seconds=1500`)
2. After build = `Success`, call `site_update` for each site you want flipped
3. Re-poll `wait_for_bench_flip` until `status: flipped`

Or short-circuit: set `max_wait_seconds=120` on the deploy call to skip the futile wait, then call `site_update` immediately, then poll.

**Hardening candidate**: `bench_deploy_and_wait` should optionally call `site_update` mid-flow after the build hits `Success`, before entering the flip-poll loop. Single MCP call covers the full chain. Deferred until we hit this a third time (this is the first documented incident).

## Press Deploy: Draft App Releases Get Skipped — Build Succeeds With Old Code — 2026-05-20

Sister trap to the two-stage flip. When you push a new commit, Press auto-creates an `App Release` row with `status='Draft'`. Deploy Candidate Builds ONLY include `Approved` releases — so an immediate post-push build succeeds against the LATEST APPROVED release (potentially many commits behind HEAD), not your fresh commit.

The build's `Success` indicator is misleading: container deployed, site flipped, everything green — but the code is from a week ago.

**Verification before any deploy:**
```python
info = mcp("bench_deploy_information", {"name": "bench-X"})
for app in info["message"]["data"]["apps"]:
    drafts = [r for r in app.get("releases", []) if r.get("status") == "Draft"]
    if drafts:
        print(f"!! {app['app']} has Draft releases — approve before deploy:")
        for d in drafts:
            print(f"   - {d['name']} {d['hash'][:7]} {d['message'][:60]}")
```

**Fix:** `app_release_approve(release_name)` per Draft release, then create a new Deploy Candidate. The old candidate is still pointed at pre-approval state.

**Why this happens**: Drafts are Press's manual-review queue. The default-to-Draft behavior is conservative — Press would rather deploy old-known-good code than new-untested code. From the agent's perspective, this looks like silent staleness.

**Status indicator agents should check, but don't:**

| `bench_deploy_information.apps[].releases[].status` | Meaning |
|---|---|
| `Approved` | Will be included in the next Deploy Candidate Build |
| `Draft` | Sits in queue. Needs `app_release_approve()` before being deployed |
| `Yanked` | Blacklisted. Build will refuse to use it |

**Wider lesson — a "Success" status from a deploy tool tells you the build pipeline didn't error. It does NOT tell you which code is now running.** Always verify the deployed commit hash post-flip by running `git log -1` inside the bench container (via `site_run_python` or SSH). The build log doesn't include the commit hash, and `deploy_candidate_status` doesn't include it either.

Status: **DOCUMENTED**. Both traps recorded; hardening candidates flagged. Today's deploy was bitten by both: first build shipped old code (Draft trap), then second build's site wouldn't flip (two-stage trap).

## "Agent is Stuck" — Almost Always a Misdiagnosis — 2026-05-20

LLM agents looking at Press's Agent Job table see rows piling up as `Pending`/`Undelivered` and conclude "the press-f1 agent has frozen, restart it." This is **almost always wrong** and the recommended restart can corrupt in-flight migrations.

**Real diagnostic before any restart:**

1. **Check RQ worker state on the agent (via SSH, no MCP tool exposes this today):**
   - Workers `busy` with fresh heartbeat (<60s) → agent IS working, just on a long job (3-8min for v14+AI app migrates is legit).
   - Workers `idle` + queues=0 + heartbeats fresh → agent is HEALTHY, the pile-up is on Press's side.
   - Workers absent or heartbeats >5min stale → agent IS dead, restart is appropriate.

2. **Check `Scheduled Job Log` for `poll_pending_jobs` cadence:**
   - Normal: ~60s between runs.
   - Pathological: gaps of 5+ minutes. The scheduler stalled and jobs piled up DURING the gap.
   - Already recovered? Then ONE manual `bench execute press.press.doctype.agent_job.agent_job.poll_pending_jobs` syncs the backlog.

3. **Check the "stuck" Agent Job's `modified` timestamp:**
   - Recent (last few min) + `output` non-empty → job is still progressing.
   - Stale + no output → may genuinely be stuck.

**The trap**: today's incident had ALL of:
- Multiple `Pending` jobs (looked stuck)
- 9+ minutes since last `Success` (looked stuck)
- New jobs piling up (looked very stuck)

But the RQ workers were idle with fresh heartbeats and empty queues. The agent had ALREADY RUN the migrate; Press just hadn't synced the status callback. ONE manual `poll_pending_jobs` call flipped everything to Success/Failure within seconds.

**Side-finding from the manual poll**: the migrate flipped to `Failure` with a real traceback — `frappe.db.has_column("Storage Unit Move Process", "notes")` raised `TableMissingError` because the DocType didn't exist on the site. That's a real bug in the patch (needs `frappe.db.exists("DocType", X)` guard before `has_column`). The "stuck agent" misdiagnosis was HIDING this bug — agents looking at "Pending" can't see traceback content. The poll surfaced it.

**Anti-patterns:**
- `supervisorctl restart agent` on heuristics — kills in-flight migrate workers, corrupts data.
- `bench_restart` via MCP "to be safe" — same problem.
- Waiting forever — the scheduler may have recovered but in-flight jobs need explicit sync.

**Recipe:**
```bash
# Safe kick — runs ONE poll, doesn't touch the agent
ssh root@press-ctrl "sudo -u frappe bash -lc \
  'cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com execute \
   press.press.doctype.agent_job.agent_job.poll_pending_jobs'"
```

**Hardening candidate (deferred to next incident)**: an `agent_health(server)` MCP tool that derives `healthy/slow/stuck/no_activity` from Press-side Agent Job data alone. Skeleton drafted in `press/mcp_server/deploy_flow.py:agent_health` but not yet registered. Logic: any Success in window → healthy; Running with fresh `modified` → slow (wait); Undelivered >2min + no activity → stuck. Would have stopped today's misdiagnosis at the MCP layer.

Status: **DOCUMENTED**. Recipe known. Hardening candidate noted. Anti-restart wisdom encoded for the next agent that sees a "stuck" pattern.

---

## 2026-05-22 — Press-ctrl /apps/press divergent history (safe reset playbook)

### What happened
Routine deploy of `4c0c2fb230` (Site Type UI) + `82abdb535c` (decom schema) revealed press-ctrl's `apps/press` clone was **49 commits ahead, 116 behind** `veela/cloudflare-dns`, plus **44 uncommitted file modifications** and **5 stashes**.

Root cause: someone had cherry-picked / rebased commits **directly on press-ctrl** instead of pulling from GitHub, producing parallel histories with identical diffs but different commit SHAs. The uncommitted mods were from interrupted in-progress edits (probably from earlier debug sessions that never got committed back).

A naive `git pull` would have refused (divergence error) or produced a tangled merge. A naive `git reset --hard` would have silently lost the 44 uncommitted file mods + 5 stashes — could have been weeks of work.

### What I did (the safe reset playbook)

**1. Patch-id diff** — verify the 49 local-only commits are duplicates of origin:
```python
# Compare patch-ids (hash of diff content, ignoring commit SHA)
git log $MERGE_BASE..press-ctrl --format=%H | while read sha; do
  git show "$sha" | git patch-id --stable
done | sort -u > /tmp/press-ctrl-patch-ids.txt
git log $MERGE_BASE..origin --format=%H | while read sha; do
  git show "$sha" | git patch-id --stable
done | sort -u > /tmp/origin-patch-ids.txt
# Any patch-id in press-ctrl that's NOT in origin = real work to preserve
```
Result: **0 unique work** among the 49 commits. All were patch-id matches of origin commits.

**2. Triple backup of uncommitted state on press-ctrl** (before any destructive op):
```bash
BACKUP_DIR=/home/frappe/snapshots/press-presync-$(date -u +%Y%m%d-%H%M%S)
mkdir -p $BACKUP_DIR
tar --exclude=.git -czf $BACKUP_DIR/working-tree.tar.gz .   # untracked + modified
git stash list > $BACKUP_DIR/stash-list.txt
git diff > $BACKUP_DIR/uncommitted-diff.patch
for i in 0 1 2 3 4; do
  git stash show -p stash@{$i} > $BACKUP_DIR/stash-$i.patch
done
git tag pre-sync-snapshot-$(date -u +%Y%m%d-%H%M%S) HEAD
```

**3. Mirror backup to dev box** so it survives press-ctrl loss too:
```bash
scp -r root@press-ctrl:/home/frappe/snapshots/press-presync-* ~/backups/press-presync/
```

**4. Preservation branch on GitHub** — apply the uncommitted diff onto a fresh branch off press-ctrl HEAD and push it:
```bash
git fetch /tmp/press-divergent.bundle <press-ctrl-HEAD-SHA>:refs/heads/press-ctrl-snapshot
git checkout -b preserved-press-ctrl-wip-$(date +%Y%m%d) press-ctrl-snapshot
git apply --3way ~/backups/press-presync-*/uncommitted-diff.patch
git commit -am "preserve(press-ctrl): uncommitted state from <date>"
git push origin preserved-press-ctrl-wip-$(date +%Y%m%d)
```

**5. ONLY THEN reset press-ctrl + deploy:**
```bash
ssh press-ctrl "sudo -u frappe bash -lc 'cd /home/frappe/frappe-bench/apps/press && git reset --hard veela/cloudflare-dns'"
ssh press-ctrl "sudo -u frappe bench --site demo.mvpstorm.com migrate"
ssh press-ctrl "sudo -u frappe bash -lc 'cd /home/frappe/frappe-bench/apps/press/dashboard && yarn build'"
ssh press-ctrl "sudo supervisorctl restart frappe-bench-web:"
```

### Anti-patterns I avoided

| Anti-pattern | Why dangerous |
|---|---|
| `git pull` on diverged branch with WIP | Refuses, OR creates conflicted merge with WIP entangled |
| `git reset --hard` without saving WIP | Silently loses uncommitted files + stashes forever |
| `git stash drop` to "clean up" | Stashes can contain valuable work-in-progress |
| Force-push from press-ctrl to "fix" origin | Press-ctrl uses read-only deploy keys (PRESS-WORKFLOW.md rule) — would fail anyway, but the intent is wrong |
| Trusting commit subject lines to mean "same work" | Subjects matched but I still verified at patch-id level |

### Restore procedure (if needed later)

```bash
# Recover any specific file from the preservation branch
git fetch origin preserved-press-ctrl-wip-20260522
git checkout preserved-press-ctrl-wip-20260522 -- path/to/file

# OR re-apply a stash by hand
git apply ~/backups/press-presync-*/stash-3.patch

# OR full restore from tarball
cd /home/frappe/frappe-bench/apps/press
tar -xzf ~/backups/press-presync-*/working-tree.tar.gz
```

### Hardening to prevent recurrence

1. **CLAUDE.md rule**: "Never `git pull` on press-ctrl — pull bundles, cherry-pick, or hard-reset only after backup."
2. **Pre-deploy hook idea**: a script that refuses to run `git reset --hard` on `/apps/press` unless a `pre-reset-backup` exists for today.
3. **Periodic sync check**: a cron that pings press-ctrl + verifies its HEAD matches `origin/cloudflare-dns` and warns if drift > 5 commits or any uncommitted mods exist.

Status: **PERMANENT** — playbook documented + 4 backups exist (tarball x2 + GitHub branch + git tag). Hardening (3 items) deferred.

Companion memory: `~/.claude/projects/-home-eslam/memory/PRESS-WORKFLOW.md` updated with this playbook.

---

## 2026-05-22 — Mock-only DB tests miss schema mismatches (the "tag" column trap)

### What happened
Shipped `app_source_fetch_latest` + `list_pending_releases` MCP tools at commit `7d0e16dbc8`. Both threw `(1054, "Unknown column 'tag' in 'SELECT'")` on first user call. The bug: I asked for a `tag` field on `tabApp Release` that doesn't exist in our Press fork's schema.

The unit tests passed because they used `unittest.mock.patch` against `frappe.db.sql` and `frappe.client.get_value` — the mocks accepted any field list without checking it against the real schema.

### Lesson
**Mock-based unit tests for DB queries are necessary but not sufficient.** When the test mocks the DB call itself, fieldname typos slip through because the mock has no knowledge of the doctype's actual columns. Three ways to catch this earlier:

1. **At least one integration-style smoke test per new whitelisted method** — run against a real (test or dev) Frappe site, hit the real DB. Costs ~1 second per test; catches every schema mismatch.
2. **Schema-aware mock** — instead of `MagicMock`, mock `frappe.db.sql` with a fake that VALIDATES requested fields against `frappe.get_meta(doctype).get_fieldnames()`. Pure-Python, no DB needed; catches fieldname typos at test time.
3. **Pre-commit guard** — narrow grep on suspicious patterns. Too brittle alone, but a smoke test against real schema would have flagged it.

For this codebase, **option 1 is what to add** going forward for any new whitelisted MCP method that calls `frappe.db.sql` or `frappe.client.get_list`. See `press/mcp_server/test_deploy_flow.py` for the existing mock pattern; add a single `TestRealSchema` class with one test per tool that calls the function unmocked.

### Generalization
- Any tool doing `frappe.db.sql("SELECT a, b, c FROM tabFoo")` or `frappe.get_all("Foo", fields=[...])` — **the field list MUST be validated against the real schema before shipping**, not just mocked.
- Press's App Release schema (which I got wrong): `name, hash, message, author, code_server_url, output, source, cloned, clone_directory, app, team, public, status` — and that's it. No `tag`, no `version`, no `branch_at_release_time`.

Status: **PERMANENT** — fix shipped (commit `cd4a874fa8`); follow-up testing improvement noted but not yet implemented.

---

## 2026-05-22 — Bench provisioning UX gap: filesystem polling is the wrong signal

### What happened
During the `fingerprint_external` deploy, an agent monitor polled `ls /home/frappe/benches/<bench>/apps/` to know when the new bench was ready. The directory stayed empty for ~10 minutes, the monitor reported repeated "Still empty" lines, and the human (correctly) asked "why is it still empty?"

The directory was empty by design: Press creates the new bench dir first, then `agent setup-bench` clones each app SEQUENTIALLY into it. While the FIRST clone is running, the others don't exist yet → `ls` returns empty for 5-10 min on a heavy bench (10+ apps).

### Lesson
**Don't infer bench state from filesystem state. Use the Agent Job chain.**

Press records each provisioning phase as a separate Agent Job:
- `New Bench` — container started, dir mkdir'd (this is when "empty" starts)
- `Setup Bench` — sequential `git clone` of each app (this is when "empty" ends)
- `Update Site Migrate` — flip a site onto the new bench

The right signal is to query these rows and look at the chain, not the disk.

### Fix shipped (commit `8125233489`)
New MCP tool `bench_provision_progress(bench_name)` aggregates the chain into one dict with a `stage` field (`build | new_bench | setup_bench | site_migrate | ready | failed`) and a human-readable `stage_label`. Agents poll this instead of the filesystem.

The companion `watch_bench_provision` help recipe documents the right loop + the caveat: "setup_bench can show 'Running' for 5-10 min with no filesystem signal — that's NORMAL. Do NOT restart the agent."

Status: **PERMANENT** — tool shipped, recipe added, wiki documented.

---

## 2026-05-22 — MCP tokens have a frozen scope; new tools don't auto-propagate

### What happened
Shipped 4 new MCP tools at commits `7d0e16dbc8` + `8125233489`. Existing tokens (issued before this date) called the new tools and got back "not in scope" errors despite the tools being live on the server.

### Lesson
**MCP tokens carry a `scope` JSON list set at issue time. New tools don't auto-appear in existing tokens' allowlists.**

When you ship a new tool, ALSO update the scope of any existing Active token that should be able to call it. There are two paths:

1. **One-shot DB script** (what was done today) — find every Active token with a deploy-flow tool in scope, append the new tools. Idempotent. Done in 5 minutes via `bench execute` on press-ctrl. Tradeoff: future shipments need this step every time.

2. **Dynamic scope resolution** (not built yet) — change the dispatcher to read `PRESETS['All deploy']` from `_tool_catalog.js` at call time, instead of trusting the token's frozen scope. Then new tools shipped in the preset auto-propagate without a DB script. Tradeoff: more complexity in the auth path.

### Operational recipe (until dynamic scopes ship)

When adding a new MCP tool:
1. Code it + register in `tools.py` + `help.py` + `_tool_catalog.js`.
2. Decide: should existing deploy tokens auto-get this? If yes:
   - Write a small one-shot script that finds tokens with a known reference tool (e.g. `app_release_approve`) in scope, appends the new tool.
   - Run via `bench execute press.<somemodule>.run` on press-ctrl.
   - Verify with `curl ... tool=help` from one of the affected tokens — the new tool should appear `in_scope=True`.

### Press MCP Token schema gotcha
The `Press MCP Token` DocType has NO `status` field. "Active" is derived from `revoked=0 AND expires_at > NOW()`. Don't write queries assuming a `status` column.

Status: **PERMANENT** — pattern documented. Dynamic scope resolution noted as backlog.

---

## 2026-05-22 — "Could not find suitable Destination Bench" is a misleading error

### What happened
Agents called `site_update` and got back `ValidationError: Could not find suitable Destination Bench` from `press/press/doctype/site_update/site_update.py:143`. The message suggested a bench was missing — but actually the site was already on the newest candidate (no diff existed). Agents wasted cycles looking for a "missing bench" that wasn't actually the problem.

### Lesson
**The Press-side error message is wrong about what's missing.** It fires in two cases:
1. No `Deploy Candidate Difference` row exists between source candidate and any destination → no NEWER candidate to migrate to.
2. No Active Bench exists in the destination group with a different candidate than source → build hasn't finished yet.

Both cases get the same opaque message.

### Fix shipped (commit `a561b0be91`)
MCP-level wrapper `site_update_with_hint` in `press/mcp_server/deploy_flow.py` pre-checks both conditions and returns:
```python
{
  "ok": False,
  "reason": "no_destination_candidate" | "no_active_destination_bench",
  "hint": "<actionable next step>",
}
```
instead of throwing. The MCP catalog's `site_update` tool now points at this wrapper. Agents that check `result.ok` get a clear next step (e.g. "build first via release_group_create_deploy_candidate").

Status: **PERMANENT** — wrapper shipped. Could be backported into Press core's `site_update` itself but lower priority since the MCP path is the main consumer.

---

## 2026-05-23 — press-f1 MariaDB OOM took down 32 sites for 25 min

### What happened
At 13:29 UTC, Linux OOM killer killed `mariadbd` on press-f1 (16 GB RAM + 4 GB swap, 28 active benches, ~65 gunicorn workers). systemd's `Restart=on-abort` does NOT cover SIGKILL, so MariaDB stayed dead. All 32 sites returned HTTP 500 until manual SSH restart at ~13:55. Pre-trigger memory state: ~330 MB available, 100% swap used.

### Hidden contributors
1. **esbuild zombie** — a `node esbuild --watch` from May 21 left running, eating ~800 MB in RAM + CPU continuously. The bench it belonged to was in production traffic, the watcher wasn't being used.
2. **No per-bench `memory_max`** — every container was unlimited; one runaway query in one site could drain the host.
3. **No monitoring** — Prometheus has never been installed on this fork. `press.api.server.usage()` returns empty dicts. The dashboard Analytics tab on every server shows "No data".
4. **No alerting** — first signal of the problem was sites returning 500 to end users.
5. **No graceful degradation** — Frappe binds all bench gunicorns to host MariaDB on `127.0.0.1:3306`, so a single DB outage = total outage for everything on the server.

### Immediate fixes shipped
- `systemctl edit mariadb` drop-in on press-f1: `Restart=always` + `OOMScoreAdjust=-900`. Next OOM scenario: OOM killer picks gunicorn workers FIRST (restartable in 2s), MariaDB auto-restarts in 5s if it does die.
- Killed the esbuild zombie (PIDs 1136877, 1136864) — freed ~800 MB instantly.
- `docker builder prune` + `docker image prune -af` freed 36 GB (unrelated to OOM but reduced background noise).
- New cron `/usr/local/bin/mem-pressure-relief.sh` runs every 5 min on press-f1; logs (no kills) when `MemAvailable < 1.5 GB AND swap > 3.5 GB`. Logs to `/var/log/mem-pressure.log`.

### MCP tooling shipped
- `host_memory_pressure(server)` — SSH/Ansible-based snapshot. Verdict `ok` / `elevated` / `critical` / `unknown`, plus `memory_total_mb`, `memory_available_mb`, `swap_used_pct`, `recent_oom_kills`, `hint`. 60s cache so polling is cheap (80ms hit / 1.6s miss). Does NOT depend on Prometheus.
- Help recipe `host_memory_pressure_check` — canonical chain documented for agents.
- Dashboard: "Check Memory" row-action button on `/dashboard/admin` Servers tab — runs the same check from the UI, shows verdict + hint as a sticky toast (15s for critical, 4s for OK).

### Diagnostic findings (would not have been visible without today's work)
- Press default `set_bench_memory_limits = True` formula (150 MB × gunicorn + 240 MB × bg + 512 MB overhead) sums to **35 GB across 28 benches on press-f1**. The host has 16 GB. Default is sized for Frappe Cloud's larger production hosts.
- node_exporter IS installed on press-f1 but bound to `127.0.0.1:9100` (unreachable from press-ctrl). Prometheus binary is not installed anywhere.
- 5 of 5 sampled benches showed `NO memory limit set (unlimited)` in `docker inspect`.

### Phase 2 — deferred to a future session
Goals (in priority order):
1. **Enable `set_bench_memory_limits = True` on press-f1, with conservative caps** — Press default formula is too loose for this 16 GB host. Either lower per-worker memory in Press Settings (gunicorn 150 → 100, bg 240 → 150), OR set explicit per-bench `memory_max` manually until benches are right-sized.
2. **Pressure-event tracking on `tabBench`** — new fields `memory_pressure_alert`, `memory_high_water_mb`, `last_pressure_at`. Scheduler job polls each active bench's cgroup `memory.events` every 5 min via Ansible. When breach detected, set the flag + surface in `/dashboard/admin` benches list as a sortable column.
3. **Admin-gated OOM-kill** — never silently kill a customer site's worker. When a bench breaches `memory_high` (the soft floor), flag it + page admin. Admin chooses: raise cap, kill workers, or scale the host. Implemented as a `bench_memory_action` doc with status `Pending Admin Review`.
4. **Banner UI on Create-Site flow** — when target server's `host_memory_pressure().verdict in (elevated, critical)`, show a warning + "Contact admin" link before allowing site creation.
5. **Banner UI on bench detail page** — same banner pattern, shown at top.
6. **Right-size press-f1 to 32 GB OR move 1/3 of sites to a sibling host** — the underlying capacity is the real ceiling. Phase 2 caps buy months, not forever.
7. **Freeze deactivated sites** (user idea) — when a site has been Inactive for N days, freeze its bench container (`docker pause` or remove from supervisor). Wake on first request via a Press hook. Memory freed: ~80-200 MB per frozen site. Edge: requires a "site is being woken, please wait" page during the 2-3s unfreeze.
8. **Install Prometheus + node_exporter network config** — separate work (~2-3 hr). Would make the Analytics tab functional. Until then, `host_memory_pressure` MCP tool is the workaround.

### Anti-patterns to remember
- "Disk is full" looked like the root cause for the first 10 min of investigation (we were at 93%). It WAS a problem but NOT the cause of the 500s. The real cause was 3 levels deeper. Lesson: when sites are 500ing, **read the Frappe error log inside the bench container BEFORE poking at disk/memory metrics**. The traceback says `pymysql.err.OperationalError: Connection refused on :3306` — that's a one-line tell.
- We `docker prune`-d 36 GB without verifying it would help. It did clean things up but didn't restore sites. Lesson: distinguish "low-risk hygiene" from "actually fixing the user's problem"; don't conflate them.
- The systemd `Restart=on-abort` default is a footgun for OOM scenarios. ALL critical services on Press infrastructure should use `Restart=always` + `OOMScoreAdjust` negative.

Status: **PARTIAL** — immediate fixes shipped (zombie killed, systemd guard, mem-pressure logger, host_memory_pressure MCP tool, Check Memory button). Phase 2 (caps + alerts + admin gate + freeze-inactive + Prometheus) is documented but deferred.

### Phase 2 detailed spec (separate doc)

Full design — per-bench caps + idle-bench freeze + admin gate — lives at:
- **Internal:** `/home/eslam/docs/superpowers/phase2-bench-memory-resilience-spec.md`
- **Preview gallery (basic-auth):** https://sanad-preview.sanadeoi.mvpstorm.com/specs/phase2-bench-memory-resilience-spec.md

The spec covers: detection rules (3-day idle, Production-skip safety), freeze action (`docker stop` whole benches not individual sites), nginx wake-up handler, admin-gated approval for every OOM-kill + freeze, rollout order, risk register. Estimated build: 8-10 hr focused session.

Companion docs: `~/.claude/projects/-home-eslam/memory/PRESS-WORKFLOW.md`, `press/mcp_server/help.py` (host_memory_pressure_check recipe).
