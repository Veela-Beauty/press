# Frappe Press Self-Hosted — Lessons Learned & Gotchas

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
