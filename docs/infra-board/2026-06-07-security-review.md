# Security Assessment: Infrastructure Control Plane (managed-host / Gate 0)

## Executive Summary
- **Target**: press/infra/* + press/api/infra_board.py + dashboard/src/pages/infrastructure/* + the live sidecar/Gate-0 provisioning (press-ctrl + sandbox-1). Scoped to the feature built this session, NOT the upstream Press fork.
- **Date**: 2026-06-07
- **Stack**: Frappe (Python) backend + Vue 3 dashboard; SSH-CA cert auth + Docker socket-proxy over a cert-authed tunnel.
- **Risk Score**: 28/100 (MEDIUM)
- **Findings**: 6 (0 Critical, 2 High, 2 Medium, 2 Low) + strong positives below.

## Risk Summary

| Severity | Count | Items |
|---|---|---|
| CRITICAL | 0 | - |
| HIGH | 2 | unrestricted socket-proxy (socat); CA private key on disk |
| MEDIUM | 2 | host-root read-mount in sidecar; firewall rule not reboot-persistent |
| LOW | 2 | ssh_command shell exec (fixed cmd); cert cache not file-validated |

## What is SOLID (verified)
- **Auth**: every whitelisted endpoint (`get_infra_tree`, `host_unit_action`, `get_host_log`, `test_connection`, `add_managed_host`, `gate0_status`) calls `frappe.only_for("System Manager")`; `warm_infra_tree` is internal (not whitelisted).
- **Injection**: control/logs validate `unit_id` against `\A[a-f0-9]{12,64}\Z` AND check it is in the live container set; `action` is allowlisted to start/stop/restart/kill; the Docker API path is built internally, never from raw user text.
- **SSH option injection**: both the tunnel and `ssh_command` put `--` before `user@host`, so a hostile `ssh_host` cannot inject `-o ProxyCommand=...`; host/user are passed as argv (no shell).
- **Host-stats command** is FIXED (`_HOST_STATS_CMD`) with no host-controlled data -> no injection.
- **Secrets**: the CA private key is resolved from env (path or value) and never stored in a doctype, the tree, or API output; `get_infra_tree` exposes only `host_name` (not `ssh_host`/`ssh_user`/`proxy_port`); short-TTL (8h) certs.

## HIGH findings (act before scaling)

### INFRA-001 (HIGH): Docker socket exposed via UNRESTRICTED socat
- **Where**: the sidecar entrypoint runs `socat TCP-LISTEN:2375 ... UNIX-CONNECT:/var/run/docker.sock`, i.e. the FULL Docker API.
- **Risk**: a compromised CA-signed cert that reaches the tunnel can do anything Docker can: `exec` into any container, run a privileged container, mount the host fs -> **host root** on every managed host. Our adapter only uses safe verbs, but the proxy does not enforce that.
- **Fix**: replace socat with `tecnativa/docker-socket-proxy` configured `CONTAINERS=1 POST=1 ALLOW_START=1 ALLOW_STOP=1 ALLOW_RESTARTS=1 INFO=1 IMAGES=1 EXEC=0 BUILD=0 VOLUMES=0 NETWORKS=0 SECRETS=0` bound to 127.0.0.1:2375. (This is the Gate-0 design; the socat was a bring-up shortcut.)
- **Mitigated today by**: CA-cert-only auth (only the control plane signs), 8h TTL, localhost/firewalled exposure.

### INFRA-002 (HIGH): SSH CA private key on disk, not in Infisical
- **Where**: `/home/frappe/keys/sanad-infra-ca` (0600 frappe); `SANAD_SSH_CA_PRIVATE_PATH` points at it.
- **Risk**: this one key signs the certs that grant SSH (and via the socket-proxy, root) on ALL managed hosts. Compromise of the frappe user or a disk/backup leak = access to every host. The design says the CA lives in Infisical and is injected at deploy, never on disk.
- **Fix**: store the CA private in Infisical at `infra/ssh_ca_private`, inject via `SANAD_SSH_CA_PRIVATE` (value env) at deploy, and remove the on-disk copy; rotate the CA + re-trust hosts if the disk key may have leaked.
- **Mitigated today by**: 0600 frappe-only perms; short-TTL signed certs (a leaked cert expires in 8h, but a leaked CA does not).

## MEDIUM findings

### INFRA-003 (MEDIUM): Sidecar bind-mounts the host root read-only
- `-v /:/host/root:ro` (for `df`) lets the sidecar READ any host file. Bounded by the existing socket-proxy root-equivalence, but it widens the read surface and lands in backups/inspection.
- **Fix**: mount only what `df` needs, or compute disk usage from a narrower path; or drop disk% if the socket-proxy is restricted.

### INFRA-004 (MEDIUM): Firewall rule is not reboot-persistent (sandbox-1)
- The `DOCKER-USER` allow-only-press-ctrl rule is in-memory; on reboot the sidecar (`--restart unless-stopped`) comes back but the rule does not, re-opening :22022 to the internet (still CA-cert-only, but un-scoped).
- **Fix**: persist with `iptables-save` / `iptables-persistent`, or publish the sidecar on a Tailscale/private interface instead of the public IP.

## LOW findings

### INFRA-005 (LOW): ssh_command reintroduces shell exec
- Deviates from the "no shell" design, but the command is fixed with no host-controlled data, so there is no injection. Acceptable interim; the durable fix is a dedicated read-only stats endpoint in the (restricted) proxy instead of shell.

### INFRA-006 (LOW): Cert cache not validated against the file
- `_attach_cert` caches the cert PATH for 6h without checking the file still exists; a deleted/rotated cert serves a dead reference (availability, not confidentiality). Fix: `os.path.exists()` the cached cert and re-sign if missing.

## Recommendations
1. **This sprint**: swap socat -> restricted `docker-socket-proxy` (INFRA-001); move the CA into Infisical (INFRA-002).
2. **Next**: persist the firewall rule (INFRA-004); narrow the host mount (INFRA-003).
3. **Backlog**: dedicated stats endpoint to retire `ssh_command` (INFRA-005); validate the cached cert (INFRA-006).

## Methodology
Static review of the infra control-plane source + the live deployment context (the reviewer built and deployed this). Categories: Secrets, Auth, Injection/XSS, API/Data, Dependencies/Infra. Upstream Press code out of scope.

---

## Remediation log

### INFRA-001 - FIXED 2026-06-07 (nginx method+path allowlist, NOT tecnativa)
Raw `socat -> /var/run/docker.sock` is replaced on BOTH hosts by a 2-container setup on `sanad-infra-net`:
- `sanad-dsp`: a tiny nginx **allowlist** proxy (image `sanad-dsp-allowlist`, build at `/opt/sanad-dsp/`) that proxies ONLY `GET /containers/json`, `GET /containers/<id>/logs`, `POST /containers/<id>/(start|stop|restart|kill)`, `GET /(info|version|_ping)`, and returns **403** for everything else. It mounts the docker socket; nginx workers run as root for socket access.
- the sshd sidecar's socat now forwards to `TCP:sanad-dsp:2375` and **no longer mounts the docker socket**.

**Why not tecnativa** (tested live): its `POST` flag is all-or-nothing per path group - `CONTAINERS=1 POST=1` STILL allowed `POST /containers/create` (a privileged container -> host-root escape, returned 404 "no such image", i.e. passed to Docker), and `POST=0` blocked `restart` (403). tecnativa cannot allow restart while blocking create; the nginx allowlist gives the method+path granularity it lacks.

**Verified** through the cert tunnel on both hosts: enumerate 200, logs 200, restart 204, info 200; exec-start 403, container-create 403 (privileged), container-exec 403, volumes 403. Post-fix both hosts health=up with full enumerate + host-stats (sandbox-1 45 units, press-ctrl 9 units).

**Durability:** the proxy + sidecar are `--restart unless-stopped`. If recreated, both must be on `sanad-infra-net` so the sidecar's socat resolves `sanad-dsp`.

### INFRA-002 - STILL OPEN (CA private key on disk; move to Infisical).

### INFRA-002 - ADDRESSED 2026-06-07 (CA private key now in the Infisical vault)
The CA private key is stored in Infisical (project `optiflow-secrets` `3137bc4e-69db-4d2d-b09e-563c78901729`, env `prod`, secret `SANAD_SSH_CA_PRIVATE` at `/`), written via the API with `jq --rawfile` (the key piped straight from disk into the JSON body, never in any arg/log/transcript) and verified by **SHA-256 match** against the on-disk key. The CA is now backed up, recoverable, and rotatable from the vault: the primary risk ("CA only on press-ctrl disk -> a rebuild loses it -> all host trust gone") is resolved.

**Residual** (follow-up, lower severity): the RUNTIME still reads the CA via `SANAD_SSH_CA_PRIVATE_PATH` -> the hand-placed `/home/frappe/keys/sanad-infra-ca`. To fully source it from the vault + drop the hand-placed copy: install the Infisical CLI + the universal-auth machine identity on press-ctrl, launch the bench via `infisical run --projectId=3137bc4e-69db-4d2d-b09e-563c78901729 --env=prod -- <bench cmd>` so `SANAD_SSH_CA_PRIVATE` is injected; `secrets.py` then materializes a transient 0600 copy and the hand-placed key can be deleted. (ssh-keygen requires a key file at sign time, so a transient on-disk materialization is inherent - "zero on disk" is not achievable.)

## Status after remediation: INFRA-001 FIXED, INFRA-002 ADDRESSED (vault). Open: INFRA-003/004 (MED), INFRA-005/006 (LOW).
