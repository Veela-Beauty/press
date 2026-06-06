# Task 10 LIVE SMOKE - PASSED (2026-06-06)

Plan 2a is proven end-to-end against a real Docker engine. Ran on press-ctrl using a
disposable test-host (alpine + sshd trusting a throwaway CA + socat bridging
127.0.0.1:2375 -> the host docker.sock), with the Frappe bench (native on press-ctrl)
as the control plane. All smoke infra was torn down clean afterward.

## Result
- `add_managed_host(host_name=sanad, server_type=docker, ssh_host=127.0.0.1, ssh_user=sanad, ssh_port=2222, proxy_port=2375)` -> `{name: sanad, status: Pending}`
- `test_connection` -> `{ssh_ok: True, docker_ok: True, containers: 9}`; status flipped to **Active**, `last_seen` stamped. (Real cert signed by the CA, real SSH local-forward tunnel, real `GET /containers/json`.)
- `get_infra_tree` -> a `kind=managed, server_type=docker` node with **9 real units** (`sanad-smoke-host, log-kibana, portainer-press, ...`), overload `None`, health **up**.
- `host_unit_action(sanad, <victim_id>, restart)` -> `{ok: True}`; verified on the engine: the victim container `StartedAt` was 35s old (it really restarted).
- `get_host_log` -> succeeded (0 lines; the victim runs `sleep`, no stdout).
- `Infra Action Log` -> `add_host:created, test_connection:success, restart:success, logs:read` (every privileged action audited).

## The bug the smoke caught (mocked tests could not)
First run: `test_connection` worked but `get_infra_tree`/`restart`/`logs` failed with
`Permission denied (publickey)`. Root cause: the signed cert was wired onto the doc ONLY
inside `test_connection` (in-memory); the steady-state paths (`_enumerate_managed`,
`host_unit_action`, `get_host_log`) loaded a fresh doc with no cert. Fix (commit `94237cbb2`):
a shared `_attach_cert(host)` (signs principal = ssh_user, cached per-user in Redis, re-signed
before the 8h TTL) called by `_managed_doc` AND `_enumerate_managed`. Re-run: fully green.
Lesson: cert/identity wiring must live on the shared doc-load path, not one endpoint. 30 unit
tests now green.

## Setup gotchas (for the real Gate 0 rollout)
- alpine's sshd ships `AllowTcpForwarding no` UNCOMMENTED as the first line; sshd uses the first
  occurrence, so an appended `yes` is ignored. Set the first line to yes (or use a base image
  that defaults to yes). The socket-proxy host needs forwarding enabled to reach the proxy.
- The SSH cert principal must match the LOGIN user (ssh_user). We sign principal = ssh_user.
  Per-host cert scoping (principal = host_name + AuthorizedPrincipalsFile) is a Gate-0 hardening.
- `sign_cert` writes one shared `<INFRA_KEY>-cert.pub`; multiple distinct ssh_users would collide
  on that path. Fine for a single access user; carry for multi-user fleets.

## Status
Plan 2a: code-complete (Tasks 1-9) + LIVE-PROVEN (Task 10). The remaining Gate 0 items are a
PRODUCTION rollout concern (CA in Infisical, a socket-proxy per real docker host, per-host
forced-command) - the chain itself is validated. Next: Plan 2b (the Vue UI) can build on a
proven backend.
