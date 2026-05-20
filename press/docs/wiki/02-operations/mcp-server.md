# MCP Server — Operations & Agent Recipes

The MCP (Model Context Protocol) server lets external AI agents drive Press through scoped, audited HTTP calls. This page covers operating it and the recipes agents need.

> **Code lives at**: `press/mcp_server/` on the `cloudflare-dns` branch. **All Vue UI** at `dashboard/src/components/mcp/` and `dashboard/src/pages/devtools/mcp/`. Tests at `press/mcp_server/test_*.py` (70 tests green as of 2026-05-10).

## Endpoint

```
POST https://<your-press>/api/method/press.mcp_server.server.handle
Content-Type: application/x-www-form-urlencoded
```

**Critical:** the token goes in the request **BODY**, never the `Authorization` header. Frappe's `validate_auth()` rejects any `Authorization: token <opaque>` because it expects `key:secret` format. MCP's custom token scheme parses from the form body instead.

```bash
curl -X POST .../press.mcp_server.server.handle \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'tool=help' \
  -d 'token=<plaintext-token>'
```

## Discoverability

The agent shouldn't need to read this wiki to know what's available. Three calls cover everything:

```bash
# 1. Scoped catalog (what THIS token can call)
{ "tool": "help" }

# 2. Single-tool detail with example_call
{ "tool": "help", "args": { "tool": "clone_bench" } }

# 3. Full catalog (incl. tools your token CAN'T call — useful for "I need scope X")
{ "tool": "help", "args": { "scope_only": false } }
```

`help` and `list_tools` (alias) are always callable by any valid token — they bypass scope checks but still require auth (so anonymous callers can't enumerate the catalog).

Every successful response also includes a `_hint` field pointing agents to `help`. Suppress with `args.suppress_hints=true` for verbose tool chains.

## Tool catalog (57 tools, 5 categories)

Full live source: `press/mcp_server/tools.py`. Mirrored to UI in `dashboard/src/components/mcp/_tool_catalog.js` (a drift detector test enforces parity).

| Category | Risk | Count | Examples |
|---|---|---|---|
| Read-only | low | 19 | `list_release_groups`, `list_sites`, `site_status`, `agent_job_list`, `bench_recent_logs`, `app_git_status`, `audit_verify_chain`, `bench_read_app_file`, `bench_list_app_files`, `bench_ssh_instructions` |
| Bench / Release Group | medium | 11 | `clone_bench`, `bench_deploy`, `bench_restart`, `app_create_locally`, `app_init_github`, `release_group_create_deploy_candidate`, `bench_ssh_register_key` |
| Site lifecycle | medium | 13 | `clone_site`, `move_site_to_release_group`, `lock_acquire`, `lock_release`, `site_migrate`, `site_backup`, `site_install_app`, `site_*_domain`, `revoke_my_token` |
| File / Config | medium | 5 | `site_config_get`, `site_config_set`, `site_file_read`, `site_file_write`, `site_update_config_bulk` |
| Dangerous (high-risk) | high | 10 | `site_run_python` (RCE), `site_run_sql`, `app_git_push`, `site_uninstall_app`, `site_deactivate`, `bench_update`, `site_update`, `bench_ssh_cert_generate`, `bench_update_dependencies`, `bench_run_repo_script` |
| Built-in | n/a | 2 | `help`, `list_tools` |

## Issuing tokens

### Via dashboard (the standard path)
1. Log in as the user who needs the token at `/dashboard/dev-tools/mcp`
2. Click "+ Issue Token" (top-right)
3. Fill **Label** (any string), **TTL** (default 60min, max 1440), **Password** = your dashboard password
4. Pick a **preset** (Read-only / Standard agent / All clone / All deploy) or hand-pick tools
5. Optional: pick **Allowed Release Groups** + **Allowed Sites** to restrict the token to specific resources
6. For high-risk tools: check **"Enable risky (high-risk) tools"** — System Users auto-approve; non-System Users get a `pending` token approved later via Admin Panel → MCP
7. Click **Issue Token** → copy the token NOW (only shown once)

### Via console (when no dashboard session)
```python
# bench --site demo.mvpstorm.com console
from press.mcp_server.auth import issue_token
from press.mcp_server.tools import list_tool_names

frappe.set_user("Administrator")
r = issue_token(
    username="<email>",
    password="<dashboard-password>",
    scope=list_tool_names(),  # all 50 catalogued tools
    ttl_minutes=1440,
    label="agent-debug",
    risky_tools_enabled=True,  # System Users auto-approve
)
print(r["token"])  # plaintext — show ONCE
frappe.db.commit()
```

## SSH-via-MCP (the verified flow)

External agents can get full SSH access to a bench container without ever touching the dashboard:

```bash
# Local: generate keypair (one-time, no passphrase)
ssh-keygen -t ed25519 -f ~/.ssh/iss-mcp -N ''

# 1. Register your pubkey via MCP (medium-risk; idempotent; auto-defaults)
PUBKEY=$(cat ~/.ssh/iss-mcp.pub)
curl -X POST .../press.mcp_server.server.handle \
  --data-urlencode 'tool=bench_ssh_register_key' \
  --data-urlencode "args={\"public_key\":\"$PUBKEY\",\"label\":\"my-agent\"}" \
  -d "token=$TOKEN"

# 2. Generate cert (high-risk; signs your now-default key)
curl -X POST .../press.mcp_server.server.handle \
  --data-urlencode 'tool=bench_ssh_cert_generate' \
  --data-urlencode 'args={"bench_name":"<bench>"}' \
  -d "token=$TOKEN" \
  | jq -r '.message.data.certificate' > ~/.ssh/iss-mcp-cert.pub

# 3. Get connection details (low-risk)
curl -X POST .../press.mcp_server.server.handle \
  --data-urlencode 'tool=bench_ssh_instructions' \
  --data-urlencode 'args={"bench_name":"<bench>","site_name":"<site>"}' \
  -d "token=$TOKEN"
# → returns ssh_port (e.g. 22011 = 22000 + bench.port_offset), server_ip, useful_commands

# 4. SSH in — drops you DIRECTLY in the bench container at /home/frappe
ssh -p <port> -i ~/.ssh/iss-mcp \
    -o "CertificateFile=~/.ssh/iss-mcp-cert.pub" \
    frappe@<server_ip>

# Inside: cd to bench dir + use absolute bench path (PATH not loaded for non-interactive SSH)
cd /home/frappe/frappe-bench
/home/frappe/.local/bin/bench --site <site> mariadb
# Or just open an interactive shell which DOES load .bashrc:
bash -l
```

### Gotchas
- `bench_ssh_cert_generate` signs the user's **default** key only. New keys MUST be marked default; `bench_ssh_register_key` does this automatically (`make_default=True`).
- Port 22011 (or whatever `bench.port_offset` resolves to) lands you inside the **bench container** as user `frappe`, not on the press-f1 host.
- Non-interactive SSH commands don't load `.bashrc`, so `bench` isn't on PATH. Use `/home/frappe/.local/bin/bench` or wrap in `bash -lc 'bench ...'`.
- `bench` commands MUST be run from `/home/frappe/frappe-bench/`, not `/home/frappe/`.

## Editing app source + deploying via MCP

The agent should NEVER edit `apps/erpnext/` directly — it's git-managed and the next deploy wipes the changes. For ERPNext fixes, the agent should edit a **custom app** owned by your team. Full deploy chain:

```bash
# 1. SSH in (Path B above)
# 2. Edit + commit inside apps/<custom-app>:
cd /home/frappe/frappe-bench/apps/customer_care_client
vim ...
git add -A && git commit -m "fix: ..."

# 3. Push via MCP so Press records the release:
curl -X POST .../press.mcp_server.server.handle \
  --data-urlencode 'tool=app_git_push' \
  --data-urlencode 'args={"bench_name":"<bench>","app":"customer_care_client"}' \
  -d 'token=<TOKEN>'
# → returns release_name

# 4. Approve the Draft App Release
curl -X POST .../press.mcp_server.server.handle \
  --data-urlencode 'tool=app_release_approve' \
  --data-urlencode 'args={"release_name":"<from-step-3>"}' \
  -d 'token=<TOKEN>'

# 5. Build a new deploy candidate
curl -X POST .../press.mcp_server.server.handle \
  --data-urlencode 'tool=release_group_create_deploy_candidate' \
  --data-urlencode 'args={"name":"<release-group>"}' \
  -d 'token=<TOKEN>'

# 6. Schedule build + deploy
curl -X POST .../press.mcp_server.server.handle \
  --data-urlencode 'tool=deploy_candidate_schedule_build' \
  --data-urlencode 'args={"candidate_name":"<from-step-5>"}' \
  -d 'token=<TOKEN>'

# 7. Wait for the bench to flip
curl -X POST .../press.mcp_server.server.handle \
  --data-urlencode 'tool=wait_for_bench_flip' \
  --data-urlencode 'args={"site_name":"<site>","target_candidate":"<from-step-5>"}' \
  -d 'token=<TOKEN>'
```

That's the production-correct path. Press records the release, builds a new docker image, and atomically flips the bench. No drift.

## Hard rules (also returned by `bench_ssh_instructions` as `do_not`)

| ❌ Don't | ✅ Instead |
|---|---|
| Edit `apps/erpnext/` and `git push` directly | Use a custom app you own; or fork erpnext to your org first |
| Run `bench update` from SSH | Use `release_group_create_deploy_candidate` + `deploy_candidate_schedule_build` |
| `git pull` inside `apps/<app>` | Press owns the deploy lifecycle — let it pull during build |
| Modify `site_config.json` by hand for sensitive keys | Use `site_config_set` MCP tool (sensitive keys still blocked) |
| Restart workers manually | `bench_restart` MCP tool — Press tracks the action |

## Bugs fixed in 2026-05-10 session

These four were found and fixed in one session — kept here as the canonical "things to know" because each surfaces in subtle ways.

### Bug 1: auth_hook blocks the MCP endpoint (HTTP 401)
- **Symptom**: `POST .../press.mcp_server.server.handle` returns 401 from `press/auth.py:101` regardless of token, while `/api/method/ping` returns 200.
- **Root cause**: Press's `auth_hook` runs before any whitelisted method body and rejects URLs not in `ALLOWED_PATHS` or `ALLOWED_WILDCARD_PATHS`. `press.mcp_server.*` was missing.
- **Fix**: add `/api/method/press.mcp_server.` to `ALLOWED_WILDCARD_PATHS` (commit `4b775755d0`). One line.

### Bug 2: wrong password logs the user OUT of the dashboard
- **Symptom**: typing wrong password in Issue Token dialog redirects user to login screen.
- **Root cause**: `_check_password` raised `frappe.AuthenticationError`. Frappe's HTTP layer maps that to 401, which the Vue dashboard treats as "session expired" → force-logout.
- **Fix**: catch `AuthenticationError` inside `_check_password`, re-raise as `ValidationError` (HTTP 417). Dashboard shows inline error, session intact (commit `d5b5bf6ed0`). Also stopped using `frappe.local.login_manager` in production — uses stateless `frappe.utils.password.check_password` instead (`e95c4f8a37`).

### Bug 3: Vue sends `username=""` (empty), backend rejects
- **Symptom**: even with correct password, token issuance failed with "Incorrect User or Password".
- **Root cause**: `IssueTokenDialog.vue` reads `window.frappe?.session?.user` — undefined in the Vue context, so `username=""` was sent. Backend's `check_password("", "...")` always fails.
- **Fix**: backend defaults blank `username` to `frappe.session.user` (commit `ff98265409`).

### Bug 4: `docker_execute` "bench: not found" (returncode 127)
- **Symptom**: `site_run_python`, `site_run_sql`, `bench_read_app_file` all returned `/bin/sh: 1: bench: not found`.
- **Root cause**: cmd string `echo X | base64 -d | bench ...` got assembled into `docker exec <container> echo X | base64 -d | bench ...`. The HOST shell saw the `|` pipes and ran `base64`/`bench` on the HOST, not in the container. On press-f1 the host's frappe user PATH doesn't include `/home/frappe/.local/bin`.
- **Fix**: wrap the entire pipeline in `bash -lc '...'` so docker exec ships ONE arg to the container's bash, which loads the user profile (`-l`) and finds bench. Commits `6d6131c670` (run_python_on_site, run_sql_on_site), `dfaab39874` (bench_read_app_file `wc -c <` and `find | head` redirects).

## Adding a new tool

1. Add the entry to `press/mcp_server/tools.py:TOOLS`:
   ```python
   "my_new_tool": {
       "method": "press.module.path.my_function",
       "description": "...",
       "required_args": ["..."],
       "risk": "low|medium|high",
   },
   ```
2. Add the same to `dashboard/src/components/mcp/_tool_catalog.js` (UI mirror — agents see it in the dialog).
3. Add the category to `press/mcp_server/help.py:TOOL_CATEGORY`.
4. Run the drift detector test: `bench --site demo.mvpstorm.com run-tests --module press.mcp_server.test_help` — `test_every_tool_has_a_category_mapping` will fail if you skip step 3.
5. Add a test to `press/mcp_server/test_server.py` exercising the dispatch.

## Auth + audit

- Tokens stored as PBKDF2-SHA256 hash in `Press MCP Token` doctype (plaintext shown ONCE at issue).
- Every MCP call logged to `Press MCP Call Log` with sha-256 hash chain (verify via `audit_verify_chain` tool — System User only).
- Risky tokens for non-System users start in `pending` status, must be approved via Admin Panel → MCP → "Approve" button.
- Rate limit: ~100 calls/minute per token (`rate_limit.py`). Cleanup cron purges expired logs daily.
- `help` calls do NOT count against rate limit.

## Tests
```bash
bench --site demo.mvpstorm.com run-tests --module press.mcp_server.test_server   # 30
bench --site demo.mvpstorm.com run-tests --module press.mcp_server.test_help     # 13
bench --site demo.mvpstorm.com run-tests --module press.api.test_team_resources  # 7
bench --site demo.mvpstorm.com run-tests --module press.press.doctype.site.test_site_move           # 13
bench --site demo.mvpstorm.com run-tests --module press.press.doctype.release_group.test_release_group_clone  # 7
# → 70 tests, all green as of 2026-05-10
```

## Deploy method (Python-only changes)

```bash
# Local
git bundle create /tmp/x.bundle <prev-head>..HEAD
scp -i ~/.ssh/id_ed25519_old /tmp/x.bundle root@89.167.116.92:/tmp/x.bundle

# Apply on press-ctrl
ssh -i ~/.ssh/id_ed25519_old root@89.167.116.92 \
  "cd /home/frappe/frappe-bench/apps/press && \
   git fetch /tmp/x.bundle 'HEAD:refs/remotes/local/x' && \
   git cherry-pick refs/remotes/local/x && \
   supervisorctl restart frappe-bench-web:frappe-bench-frappe-web"
```

For Vue/dashboard changes, also `bench build --app press --force && bench --site demo.mvpstorm.com clear-cache` between cherry-pick and restart.

## Deploy workflow tools (shipped 2026-05-20)

Four new tools + four safety gates that close the "agent polls forever / restarts a busy worker" failure modes. Read this section if you're driving Press deploys/migrations from an LLM agent.

### The 4 new tools

| Tool | Use it when |
|---|---|
| `agent_health(server, lookback_minutes=10)` | BEFORE any "restart agent" thought. Verdict `healthy / slow / stuck / no_activity`. `slow` explicitly says DO NOT restart — the worker is mid-job and restarting will corrupt a live migrate. |
| `agent_job_traceback(job_name, output_chars=4000)` | Post-mortem on a Failure / Pending / Undelivered row. One-shot return of `{status, job_type, site, output_tail, traceback_tail, age_seconds}`. Replaces the 4-roundtrip ssh + bench console + get_doc dance. |
| `agent_job_progress(job_name, step_output_chars=1500)` | **Cursor-style live in-flight stream**. Poll every 3-10s while a job is running. Returns `{status, current_step, steps[], steps_summary, dashboard_url}` — same data the dashboard's `/dashboard/sites/<site>/jobs/<job>` page renders. Each step has its own status + output tail + duration. |
| `site_update_and_wait(site_name, target_candidate, ...)` | After `bench_deploy_and_wait` reports build Success, sites on **standalone Press** don't auto-flip. Call this per site to trigger the migrate + block until the site's bench == target_candidate. |

### The 4 safety gates inside `wait_for_bench_flip`

Server-enforced, no agent opt-out. Each gate returns a structured status + a `hint` field telling the agent exactly what to call next.

| Status | Meaning | Fix the gate hints at |
|---|---|---|
| `flipped` | Normal success — site is on `target_candidate`. | — |
| `pending` | Real in-flight pending (migrate is running or just queued). | Keep polling, or switch to `agent_job_progress` for step-level visibility. |
| `no_build` | The candidate has no Deploy Candidate Build. | Call `deploy_candidate_schedule_build` or `bench_deploy_and_wait`. |
| `flip_not_triggered` | Build is Success but no Update Site Migrate job exists in the last 60 min. | Call `site_update_and_wait(site_name=..., target_candidate=...)`. |
| `flip_failed` | The most recent Update Site Migrate FAILED (and optionally was rolled back by Recover Failed Site Migrate). Response includes `failed_migrate_job` + `recover_job`. | Call `agent_job_traceback(job_name=<failed_migrate_job>)` to see the error. |

Gate D is invisible — if Undelivered jobs >2min old exist for the site, the gate runs ONE `poll_pending_jobs` call before returning (idempotent, same thing Press's scheduler does every 60s). If the auto-kick resolves the flip, response includes `gate_d_triggered: true`.

### Canonical deploy chain (LLM-safe)

```
1. bench_deploy_information(name=<RG>)              # what's deployable?
2. app_release_approve(release_name=<rel>)          # if any apps[].releases[].status == 'Draft'
3. bench_deploy_and_wait(name=<RG>, apps=[...], site_name=<site>, max_wait_seconds=120)
   # short wait — this only watches the build; site won't auto-flip on standalone

4. (while building) agent_job_progress(job_name=<build job>)  # OPTIONAL — live stream
5. deploy_candidate_status(name=<candidate>)        # confirm Success

6. site_update_and_wait(site_name=<site>, target_candidate=<candidate>)
   # trigger the per-site migrate + block until the bench actually flips

7. wait_for_bench_flip(site_name=<site>, target_candidate=<candidate>)
   # If status != 'flipped': read the hint. Gates will tell you exactly what's wrong.

8. (on flip_failed) agent_job_traceback(job_name=<failed_migrate_job>)
   # See the migrate error → fix the underlying bug → redeploy.
```

### Anti-pattern: "many Undelivered jobs → agent is dead → restart"

This is **almost always wrong**. Restarting an agent mid-migrate corrupts the live DB. Check `agent_health` first:

```bash
curl ... --data-urlencode 'tool=agent_health' --data-urlencode 'args={"server":"press-f1.sandbox.mvpstorm.com"}'
```

If verdict is `slow` (worker has a Running job with fresh `modified`), wait. If `stuck` (Undelivered >2min and no recent activity), call `poll_pending_jobs` ONCE — the watchdog script does this safely:

```bash
ssh root@press-ctrl "sudo -u frappe /home/frappe/poll_watchdog.sh"
# or:
sudo -u frappe bench --site demo.mvpstorm.com execute press.press.doctype.agent_job.agent_job.poll_pending_jobs
```

## Related docs

- `press/docs/wiki/01-setup/` — getting Press running
- `press/docs/wiki/lessons-learned.md` — full lessons across the platform
- `press/mcp_server/_AUDIT.md` (if present) — code-level audit trail
- Source: `press/mcp_server/server.py:handle` (entry), `auth.py:_authenticate_token` (shared auth helper), `help.py:get_tool_help` (discoverability)
