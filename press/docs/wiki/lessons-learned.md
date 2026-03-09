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
