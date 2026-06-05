# Infrastructure control panel: security review + risk register (2026-06-05)

Threat model of the "Infrastructure" design (manage every Linux box, SSH-first + optional agent, monitor/control/logs) BEFORE build. The shipped Plan 1 backend is covered at the end. Grounded in a researched brief (Portainer agent internals, docker-socket-proxy, SSH-CA, command-injection, audit). This is a design gate: the mitigations below become hard requirements in the spec.

## The one architectural truth
A compromised control plane = root on EVERY managed host. The control plane holds (or can obtain) credentials that reach every server. Every decision below exists to shrink that blast radius. This is why "monitor + control only" (no exec/deploy) in v1 is itself a security choice.

## Risk register (ranked)

| # | Risk | Sev | Mitigation (becomes a spec requirement) |
|---|---|---|---|
| R1 | Control-plane compromise unlocks all hosts | CRITICAL | SSH **certificates, short TTL (~8h) + per-host principals** (SSH CA), not one static key. A stolen cert self-expires within a workday. Control plane isolated + admin MFA. |
| R2 | `docker.sock` access = root on the host (this is exactly what Portainer's agent grants) | CRITICAL | Never give the SSH user the `docker` group or raw socket. On Docker hosts run a **docker-socket-proxy** (Tecnativa) that allowlists ONLY list/inspect/logs/start/stop/restart/kill and BLOCKS `EXEC=0 BUILD=0 VOLUMES=0 NETWORKS=0 SECRETS=0`. Proxy port never published. |
| R3 | Command injection building `docker <verb> <id>` over SSH | HIGH | Prefer the **Docker HTTP API via the proxy** (no shell). On the agentless path, validate id `^[a-f0-9]{12,64}$`, enumerate-then-validate against live `docker ps`, AND a server-side **forced-command** wrapper that re-validates. Same injection-safe pattern as the shipped `service_action`. |
| R4 | SSH key sprawl / reuse opens every door | HIGH | No shared static key. SSH CA with host-specific principals; revocation via a KRL propagated to all hosts (not per-host key edits). Private/CA key custody in **Infisical/Vault**, never plaintext, never in a doctype field or memory file. |
| R5 | No audit trail; attacker (or mistake) is silent | HIGH | Structured JSON **audit log per control action** (actor, session, host, container id+name, action, outcome, ts), append-only, shipped off the control-plane host. Log `logs`-reads too (data access). |
| R6 | Non-admin teams seeing/controlling hosts (Press is multi-team) | HIGH | `Managed Host` doctype + every control endpoint **System-Manager only**; the merged infra tree already `frappe.only_for("System Manager")`. Managed hosts never appear in a team's scope. |
| R7 | "Add host" connects the control box to an arbitrary user-supplied host (SSRF/pivot) | MEDIUM | Admin-only action; Test-Connection runs only the fixed `echo OK`/`docker ps` literals; pin host key (TOFU) on first connect; record who added each host. |
| R8 | Agent onboarding supply-chain (curl|bash) + unauth agent port | MEDIUM | Onboarding installs a pinned socket-proxy image with the locked ACL; proxy bound to the private net only; trust bootstrapped by a per-host token + TLS fingerprint pin (Portainer's edge-key idea, done right). No `EDGE_INSECURE_POLL` equivalent. |
| R9 | Reads spamming Watch Tower alert emails on every refresh | LOW | Status reads bypass `should_send_alert` (already the rule). |
| R10 | Destructive action (kill/stop prod) by mistake or hijacked session | MEDIUM | Confirm dialog on stop/kill; consider a second factor/approval for write actions; read-only is the default posture. |

## How the agent sees Docker (your specific question), done safely
Portainer's agent simply mounts `/var/run/docker.sock` into a container = unrestricted root on the host; the Edge model only changes the *transport* (the agent polls home with an `EDGE_KEY` token and opens a TLS tunnel), not the *privilege*. We do the same shape but reduce the privilege:

- **The "agent" on a Docker host = a docker-socket-proxy** (HAProxy sidecar) in front of the socket, exposing ONLY the container lifecycle endpoints we need over a private-network TCP port. The control plane talks the **Docker HTTP API** to it (`GET /containers/json`, `/containers/{id}/logs`, `POST /containers/{id}/restart`) - no shell, so no injection, and exec/build/volumes/secrets are blocked at the proxy even if the control plane is fully compromised.
- **First-time setup on a server**: one onboarding step drops the pinned socket-proxy (locked ACL env) + registers the host with a per-host token and pins its TLS fingerprint. Reachability is either the agent's poll-home tunnel (behind NAT) or the SSH tunnel.
- **Agentless (plain hosts / instant onboarding)**: a **forced-command SSH key** (`command="validator.sh",restrict`) so the key itself can only run the allowlisted `docker/systemctl` verbs against a validated id - the key is near-useless if stolen.

Net: this is "like Portainer's agent" in shape, but strictly less privileged (proxy ACL + forced-command + short-TTL certs), which directly answers R2/R3.

## Recommended onboarding ladder (least effort -> most secure)
1. **Plain host (no docker)**: forced-command SSH key, read-only `systemctl/df/free/journalctl`. Instant.
2. **Docker host, agentless**: forced-command SSH key whose validator only runs allowlisted docker verbs with id-validation. No docker group; use `sudo` allowlist for the exact subcommands OR rootless docker.
3. **Heavy Docker fleet (the 211-container box)**: deploy the docker-socket-proxy "agent"; control plane uses the Docker API via the proxy over a tunnel. Fast real-time, blocked dangerous endpoints.

## Shipped Plan 1 posture (re-confirmed)
`service_action` = `@frappe.whitelist` + `@protected("Bench")` + `frappe.only_for("System Manager")` + action allowlist + program validated against live `get_processes` (no shell injection). `get_infra_tree` System-Manager-gated, 15s cache. `host_probes` uses `ssh_cmd` with the hardcoded literal `echo OK`. No secrets in code. Posture: solid; the new risks are all in the multi-host extension above.

## Two decisions the spec needs (security-critical forks)
- **D1 - Docker access method:** (a) docker-socket-proxy + Docker API [recommended; safest; one extra container per Docker host] vs (b) raw `docker` over SSH with a sudo-allowlist/forced-command [simpler, no proxy, but the SSH user can run docker subcommands].
- **D2 - SSH auth model:** (a) SSH CA + short-TTL certs + per-host principals [recommended; best blast-radius control; more setup] vs (b) per-host dedicated static keys stored in Infisical [simpler; rotate manually; bigger blast radius if one leaks].
