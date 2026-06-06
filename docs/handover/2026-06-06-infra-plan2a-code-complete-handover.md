# Handover: Infrastructure managed-host backend (Plan 2a) - CODE COMPLETE (2026-06-06)

## Status
Plan 2a (the managed-host control-plane backend) is **code-complete: Tasks 1-9 done, reviewed, pushed** to `Veela-Beauty/press` `cloudflare-dns` (HEAD `1ffd640878e`). **27 unit tests** green (`press.infra.tests.test_managed_backend`) + the 9 shipped Plan-1 tests (`press.api.tests.test_infra_board`) still green. **Only Task 10 remains and it is BLOCKED on Gate 0 (operator provisioning - see below).**

## What got built (Tasks 1-9)
- `Managed Host` + `Infra Action Log` doctypes (System-Manager perms, no secret fields, charset+port validation).
- `ssh_ca.sign_cert` (8h per-principal certs), `get_adapter` factory (docker/plain).
- `SshPlainAdapter.enumerate` (1 compound SSH probe + ControlMaster), `SshDockerAdapter` (Docker API via socket-proxy, control start/stop/restart/kill id-validated, logs).
- `get_infra_tree` merges managed hosts + `overload` (>=80 high / >=90 crit); failed enumerate -> health "unknown" (no false-green).
- `host_unit_action` / `get_host_log` (System-Manager gated, adapter-routed, every call + onboarding audited).
- onboarding `add_managed_host` + `test_connection` (honest reachability probe via the adapter; Active on real success, Unreachable on failure, last_seen stamped).
- `docker_tunnel.docker_request` (SSH local-forward + Docker API + stdcopy log demux + presents the signed cert via -i/CertificateFile).

## Reviews (this is why it took the tasks it did)
Each task ran a review; Tasks 6 + 9 got full multi-agent adversarial review workflows (4 lenses, every finding verified). They caught and we fixed: 2 HIGH state-mapping bugs in Task 6 (unhealthy->healthy inversion; OOM/crash exit masked as clean), and in Task 9 a dishonest `test_connection` (hardcoded ssh_ok, plain hosts Active with no probe, dead Unreachable/last_seen), unaudited onboarding, and an inert/unsafe cert path. The verification step also DISMISSED two overclaims (a non-reproducible `-oProxyCommand` RCE, a non-existent fd-leak) - so nothing spurious shipped.

## Task 10 is BLOCKED on Gate 0 (OPERATOR must provision - NOT code)
To run the live smoke (`add_managed_host` -> `test_connection` -> tree -> control/logs + audit), provision ONE docker target and these, then resume Task 10:
1. **Infisical CA**: an SSH CA keypair stored in Infisical at `infra/ssh_ca_private`, AND add a `get_infisical_secret(path)` accessor to `press/utils.py` (referenced by `ssh_ca._ca_private_key`, does NOT exist yet).
2. **Control-plane key**: a dedicated keypair on press-ctrl at `/home/frappe/.ssh/sanad-infra` (+ `.pub`). `test_connection` signs its pubkey -> short-TTL cert presented by the tunnel.
3. **Target host**: a tecnativa **docker-socket-proxy** on the docker host (POST + ALLOW_START/STOP/RESTARTS=1, CONTAINERS=1, EXEC=0 BUILD=0 VOLUMES=0), reachable at `127.0.0.1:<proxy_port>` over SSH.
4. **Forced-command key**: the CA-trusted principal mapped on the target (`TrustedUserCAKeys` + a forced-command allowlist for plain hosts).

## Carries (tracked, not lost)
- **Host-key pinning** (Gate 0 / hardening): the `tls_fingerprint` field on Managed Host is unused; the tunnel + ssh_plain currently use `StrictHostKeyChecking=accept-new` (TOFU). Capture the host key at onboarding into `tls_fingerprint` and switch the steady-state paths to a pinned `UserKnownHostsFile`. Deferred because it couples with the Gate-0 host provisioning.
- **Plan 2b (frontend)**: build the two-nav Vue UI (Servers = Press team-scoped, Infrastructure = managed role-gated) from `docs/infra-board/press-infrastructure.prototype.html`. MUST add a per-team cache key to `get_infra_tree` before team-scoping (global cache + team-scope = cross-team leak). State badge map needs tokens `unhealth/restart/dead/pause` (+ run/heal/exit0/exit2/stop). The UI uses each unit's `_id` (real container id) as the control handle passed to `host_unit_action`/`get_host_log`; consider renaming off the underscore.

## Key facts for the next session
- Push flow: commit on press-ctrl container -> `git bundle` -> throwaway worktree off `press_local` -> merge origin -> push (never push from press-ctrl; deploy keys are read-only).
- Tests: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend` (27) + `--module press.api.tests.test_infra_board` (9).
- `frappe.only_for` is a no-op under `flags.in_test`; `log_infra_action` commits its row (tests delete it).
- Permission model (locked): team-scoped Press (Servers) + System-Manager role-gated managed hosts (Infrastructure).
