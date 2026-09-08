# Handover: Infrastructure backend (Plan 2a) + press-ctrl disk fix (2026-06-06)

> **Superseded in part, 2026-09-01.** The disk sections below are kept as history, but the
> "STILL OWED" item "fix the 24h restore-test auto-drop" is DONE (it lives in `daman_backup`, not
> Press, and was closed by DR Restore Phase 3). The retention cron was also built, not missing;
> it had simply never been enabled. See
> [2026-09-01-press-ctrl-disk-and-maintenance-handover.md](2026-09-01-press-ctrl-disk-and-maintenance-handover.md).

## Where to resume FIRST
**Plan 2a, Task 5: `SshPlainAdapter.enumerate`** (systemd + df/free/load over SSH -> normalized units/metrics). Mock-tested, runs now.
Execution mode (user-set): task-by-task, **user check-in after each task**, subagent implements with TDD -> I review (spec+quality) -> push each task. No hurry, quality first.
Plan file: `docs/infra-board/2026-06-06-plan-2a-managed-host-backend.md`.

## What shipped this session (all pushed to Veela-Beauty/press cloudflare-dns)
Plan 2a (managed-host backend), Tasks 1-4 + review fixes + permission correction:
- T1 Managed Host doctype - System-Manager perms, no secret fields, autoname field:host_name, host_name charset validation (98914ff, a999c7c)
- T2 Infra Action Log doctype + `log_infra_action` - append-only audit, durable (commits its own row, survives rollback) (1c17e44, a999c7c)
- T3 `press/infra/ssh_ca.py` `sign_cert` - 8h per-principal certs, no-shell list (eb2afd5)
- T4 adapter interface + `get_adapter` factory (docker/plain) + ssh_docker/ssh_plain stubs; managed-hosts-only docstring + dict-safe host.get (b5762ce, a55dbad)
- PERMISSION CORRECTION (user directive): `service_action` no longer System-Manager-only - gated by `@protected("Bench")` so the team that OWNS a bench controls its own services (7c988b5). Model doc: `docs/infra-board/2026-06-06-permission-model-correction.md` (supersedes spec R6): team-scoped Press + role-gated infra.

Tests: `press/infra/tests/test_managed_backend.py` = 8 green. Plan-1 `press/api/tests/test_infra_board.py` = 9 green.

## What's pending (Plan 2a)
- T5 SshPlainAdapter.enumerate (NEXT) | T6 SshDockerAdapter enumerate/control/logs (Docker API via socket-proxy, id-validated) | T7 merge managed hosts into get_infra_tree + overload | T8 host_unit_action + get_host_log (role-gated for managed hosts) | T9 onboarding add_managed_host/test_connection/docker_tunnel | T10 live smoke (needs Gate 0).
- **Plan 2b (frontend)**: the two-nav UI from the approved prototype `docs/infra-board/press-infrastructure.prototype.html` (Servers = Press, Infrastructure = external). MUST team-scope `get_infra_tree` with a **per-team cache key** (global cache + team-scoping = cross-team leak - see permission-correction doc).
- Gate 0 (provisioning, not code): SSH CA + Infisical accessor `get_infisical_secret` (does NOT exist in Press yet - ssh_ca._ca_private_key is unwired), socket-proxy per docker host, forced-command keys, one live target.

## press-ctrl DISK - fixed + open follow-ups
**Fixed**: freed 107G, 92% -> 55% (131G free). Root cause = DR restore-test sites that should auto-drop after 24h but DON'T, plus no MinIO backup retention. Deleted `/opt/minio/data/press-uploads/gwis-restoretest-202605311200...` (94G), `...202605171005...` (13G), `halwan-egy-demo...` (2M orphan).
**Still open (user approved, NOT yet done)**:
1. Archive the Active `gwis-restoretest-202605311200` site - it still re-creates ~13G/day backups until dropped (Site.archive at site.py:1687).
2. Bi-weekly cron: prune each site's offsite backups to last 7 days + remove Archived/dropped-site orphan dirs in `/opt/minio/data/press-uploads/`.
3. Registry GC - the 66G `/registry` volume regrew (deploy-image cleanup not pruning); needs the safe read-only-mode GC recipe (see memory press-ctrl-disk-full-registry-2026-06-01).
4. Fix the 24h restore-test auto-drop (the real recurring root cause). No restore-test cleanup method found under press/press/doctype/*restore*.
5. Investigate slow Restore "Scanning/Analyzing backup" (the "skip tables to speed restore" step hangs) - separate perf issue the user raised.

## Known traps (this work)
- Push flow: commit on container -> `git bundle` -> fetch into a throwaway worktree off press_local -> merge origin -> push. SSH to GitHub is restored.
- New doctype needs `reload-doctype`/`reload_doc` + clear-cache before tests can use it.
- `frappe.only_for` is a NO-OP under `flags.in_test` - test the gate is CALLED, not that it raises.
- Audit `log_infra_action` commits - tests that touch it must delete+commit to clean up.

## Decisions locked
- Permission: team-scoped Press (Servers) + role-gated infra (Infrastructure). service_action relaxed accordingly.
- Adapter factory is managed-hosts-only by design; Press benches read via shipped get_dev_overview_benches/get_processes (two paths, documented).
