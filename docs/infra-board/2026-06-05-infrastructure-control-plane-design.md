# Infrastructure Control Plane: design spec (2026-06-05)

A single panel inside the Press dashboard to monitor and control **every Linux box** the company owns, replacing Portainer Business for daily ops. Builds on the shipped Plan 1 backend (`get_infra_tree`, `service_action`, `host_probes`) and the approved before/after prototype (`docs/infra-board/press-server-before-after.prototype.html`).

## 1. Goal and non-goals
- **Goal:** one "Infrastructure" view listing Press-provisioned servers AND externally-managed hosts, with live health, CPU/Mem/Disk, container/service state, logs, and lifecycle control (start/stop/restart/kill). Admin-only. Drop Portainer BE for monitoring + control.
- **Non-goals (v1):** stack deploy/redeploy, image/volume/network management, `exec` into containers, multi-team exposure. Deferred to later phases.

## 2. Locked decisions
1. **Scope:** every Linux box (Press benches + the Compose fleet on 95.217.109.117 + sandbox + dev box + storage boxes + future).
2. **Reach:** hybrid - agentless SSH by default, optional socket-proxy "agent" on heavy Docker fleets.
3. **Home:** a new `Managed Host` registry inside the Press dashboard; the existing server area is renamed/extended to **"Infrastructure"** and merges `Server` + `Managed Host` rows. Press `Server` rows untouched.
4. **v1 surface:** monitor + control (start/stop/restart/kill) + logs.
5. **D1 Docker access:** docker-socket-proxy (Tecnativa) + Docker HTTP API. No raw socket, no shell on Docker hosts.
6. **D2 SSH auth:** SSH CA issuing short-TTL (~8h) certificates with per-host principals. No shared static keys.

## 3. Architecture
```
Press dashboard (Vue)  ->  press/api/infra_board.py (System-Manager gated, 15s cache)
                              |
                    normalized adapter interface: enumerate(host) -> {units[], metrics}
                              |
   +--------------------------+---------------------------+----------------------+
   | press adapter            | ssh_docker adapter        | ssh_plain adapter    | agent adapter (Phase 2)
   | get_dev_overview_benches | SSH cert tunnel ->        | SSH cert + forced-   | poll-home tunnel ->
   | + get_processes (DONE)   | socket-proxy -> Docker API| command validator    | socket-proxy
   +--------------------------+---------------------------+----------------------+
```
Transport to every host is **SSH authenticated by a short-TTL CA cert**. On Docker hosts the cert is tunnel-only (`permitopen` to the proxy port); we speak the **Docker HTTP API** to the socket-proxy (no shell). On plain hosts the cert maps to a **forced-command validator** running only allowlisted read commands.

## 4. Data model
New doctype **`Managed Host`** (System-Manager perms only):
- `host_name` (Data, unique label), `ssh_host` (Data), `ssh_port` (Int, default 22), `ssh_user` (Data)
- `host_type` (Select: `docker` | `plain`)
- `proxy_port` (Int, the socket-proxy localhost port on docker hosts, e.g. 2375)
- `reach` (Select: `ssh` | `agent`, default `ssh`)
- `host_principal` (Data, the SSH-cert principal for this host)
- `tls_fingerprint` (Data, pinned on first connect / agent)
- `status` (Select: `Active` | `Unreachable` | `Pending`), `last_seen` (Datetime)
- `tags` (Small Text), `notes` (Small Text)
- NO secret fields. The SSH CA private key lives in **Infisical**, never in this doctype.

The Infrastructure list is the union of `Server` (kind=`press`) and `Managed Host` (kind=`managed`), normalized to `{id, name, kind, reach, health, cpu, mem, disk, units_up, units_down}`.

## 5. Backend components (Python, press app)
- `press/infra/adapters/base.py` - the `enumerate(host)` + `control(host, unit, action)` + `logs(host, unit)` interface returning normalized dicts.
- `press/infra/adapters/press_adapter.py` - wraps shipped `get_dev_overview_benches` + `get_processes` + `service_action` + log_browser. (reuse)
- `press/infra/adapters/ssh_docker.py` - opens an SSH cert tunnel (paramiko or `ssh -L`) to the host's socket-proxy port, then calls the **Docker Engine API**: `GET /containers/json`, `GET /containers/{id}/logs?tail=N`, `POST /containers/{id}/{start|stop|restart|kill}`. Container id validated `^[a-f0-9]{12,64}$` and enumerated-then-validated. `docker stats --no-stream` equivalent via API for cpu/mem; host disk via a single read command.
- `press/infra/adapters/ssh_plain.py` - SSH cert + forced-command validator: `systemctl list-units`, `df`, `free`, `journalctl -u <unit>` (unit validated against enumerated set).
- `press/infra/ssh_ca.py` - pulls the CA private key from Infisical, signs a short-TTL (~8h) cert with `-n <host_principal>` per connection; never writes the CA key to disk. KRL-based revocation.
- `press/api/infra_board.py` (extend Plan 1):
  - `get_infra_tree()` -> merge `Server` rows (press adapter) + `Managed Host` rows (ssh_docker/ssh_plain adapter), each best-effort, 15s cache, System-Manager gated. Unreachable host = health `unknown` (never false-green, per the shipped fix).
  - `host_unit_action(host, unit, action)` -> route to the host's adapter; action allowlist `{start,stop,restart,kill}`; unit validated against live enumeration; System-Manager only; writes an audit log; returns the new state.
  - `get_host_log(host, unit, file=None)` -> press log_browser OR Docker API logs OR journalctl; rendered in the existing drawer.
  - `add_managed_host(...)` / `test_connection(host)` -> signs a cert, runs the fixed `echo OK` (+ Docker API ping for docker hosts), pins `tls_fingerprint`, sets status. Admin-only.
- **Audit:** new `Infra Action Log` doctype (append-only): actor, session, host, unit id+name, action, outcome, ts. Every `host_unit_action` and `get_host_log` writes one. Shipped off-host later (Phase 2).

## 6. Frontend (extends the approved before/after prototype)
- The existing Servers list/detail gains `Managed Host` rows with a small **kind tag** (Press / Managed); same card/list toggle, metric columns, drill, container/service table, log drawer, restart - all reused from the prototype.
- **"Add host" dialog**: host_name, ssh_host/port/user, host_type, (docker) proxy_port -> **Test Connection** -> save. Mirrors Portainer "Add environment."
- Managed-host detail shows only applicable tabs (Containers/Services + Logs + Info); no Press-only tabs (analytics/snapshots/firewall).
- Confirm dialog on stop/kill (R10). Auto-refresh ~12s (cached).

## 7. Security requirements (hard, from the risk register)
- **R1:** SSH CA short-TTL certs (~8h) + per-host principals; control plane isolated; admin MFA recommended. CA key in Infisical.
- **R2:** Docker hosts run docker-socket-proxy with `EXEC=0 BUILD=0 VOLUMES=0 NETWORKS=0 SECRETS=0`, `POST=1 ALLOW_START=1 ALLOW_STOP=1 ALLOW_RESTARTS=1 CONTAINERS=1 IMAGES=1 INFO=1`; proxy port never published (private net / localhost only); control plane reaches it only via the cert tunnel.
- **R3:** Docker control via the Docker API (no shell); on the agentless/plain path use forced-command validator + `^[a-f0-9]{12,64}$` id validation + enumerate-then-validate.
- **R4:** no key reuse; per-host principals; KRL revocation propagated via CA trust; private/CA keys only in Infisical, never in a doctype or memory file.
- **R5:** structured append-only `Infra Action Log` on every control + log-read; ship off-host in Phase 2.
- **R6:** `Managed Host` doctype + every infra endpoint System-Manager only; managed hosts never enter a team scope.
- **R7:** Test-Connection runs only fixed literals; pin host key on first connect; record who added each host.
- **R8:** pinned socket-proxy image; per-host token + TLS fingerprint pin; no insecure-poll equivalent.
- **R9:** status reads bypass Watch Tower `should_send_alert`.
- **R10:** confirm dialog on destructive actions; read-only default posture.

## 8. Onboarding ladder
1. **Plain host:** issue cert with `restrict,command="validator.sh"`; read-only systemctl/df/free/journalctl. Instant.
2. **Docker host (agentless):** issue cert with `restrict,permitopen="127.0.0.1:<proxy_port>"` (tunnel-only, no shell); deploy the socket-proxy; control plane uses Docker API over the tunnel.
3. **Heavy Docker fleet:** same socket-proxy, optionally with the poll-home agent tunnel for NAT'd boxes (Phase 2).

## 9. Testing
- **Unit:** each adapter (mock SSH/Docker-API output -> normalized units + metrics); `host_unit_action` validation (rejects bad action/unit, calls the right adapter, writes audit, never acts on a non-enumerated id); merged `get_infra_tree` (press + managed, unreachable -> unknown); `ssh_ca` signs with correct principal + TTL (mock Infisical).
- **Integration/live smoke:** once SSH-CA trust + socket-proxy are provisioned on one target (e.g. 95.217.109.117), enumerate its stacks, read a container log, restart a container, confirm the audit log row.
- **Human-flow (Playwright):** admin adds a host via the UI -> appears in the merged list -> drill -> restart a container -> read its log -> see the confirm dialog and the audit entry.

## 10. Phasing
- **Phase 1 (this spec):** `Managed Host` + Add-host + ssh_docker(socket-proxy+API) + ssh_plain + ssh_ca + extend tree/control/logs + audit log + merged Infrastructure UI. Result: Portainer-replaceable monitor+control+logs for every box.
- **Phase 2:** poll-home agent for NAT'd fleets; ship audit logs off-host.
- **Phase 3:** stack deploy/redeploy (Portainer-parity for deployment).

## 11. Open dependencies (must be provisioned, not code)
- SSH CA infrastructure: CA keypair generated, public key + `TrustedUserCAKeys`/`AuthorizedPrincipalsFile` placed on each managed host; CA private key stored in Infisical.
- SSH access to 95.217.109.117 (currently `Permission denied`) - host must trust the CA.
- socket-proxy image pinned + deployed on each Docker host as part of onboarding.
- Decision on where the CA signer runs (Press backend pulling the key vs a dedicated signer / Vault SSH engine) - default: Press backend pulls from Infisical at sign time.
