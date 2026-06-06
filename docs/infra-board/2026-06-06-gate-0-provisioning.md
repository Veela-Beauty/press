# Gate 0 - Infra control-plane provisioning runbook

Plan 2a's code is complete (Tasks 1-9, 29 unit tests). The live smoke (Task 10) needs the
operator to provision the four items below ONCE. None of this is code; it is host/secret setup.
After it is done, run the Task 10 commands at the end.

The SaaS principle still holds: end state is a "Add host" button in the dashboard (Plan 2b). This
runbook is the one-time operator bootstrap of the trust material that button relies on.

## 1. SSH Certificate Authority (signs short-TTL host-access certs)

```bash
# on a secure admin box, NOT committed anywhere
ssh-keygen -t ed25519 -f sanad_infra_ca -C "sanad-infra-ca" -N ""
# store the PRIVATE key in Infisical (path: infra/ssh_ca_private)
# keep sanad_infra_ca.pub - it goes on every managed host (step 3/4)
```

Inject the CA private key into the Press container. Two modes (the accessor
`press/infra/secrets.py` supports both):
- PREFERRED - mount the key file read-only and set the path:
  `SANAD_SSH_CA_PRIVATE_PATH=/run/secrets/ssh_ca` (declare it in docker-compose `environment:` +
  a `secrets:`/volume mount). The key is never copied onto the site disk.
- Fallback - set the key material directly: `SANAD_SSH_CA_PRIVATE="$(cat sanad_infra_ca)"`. The
  accessor materializes it to a 0600 file under `<site>/private/infra-secrets/`. Simpler, but the
  key lands on the site volume.

Until one of these is set, `test_connection` honestly fails the host to `Unreachable` (no false green).

## 2. Control-plane keypair (the identity the cert is minted for)

```bash
# on press-ctrl, as the frappe user
ssh-keygen -t ed25519 -f /home/frappe/.ssh/sanad-infra -N ""
```
`test_connection` signs `/home/frappe/.ssh/sanad-infra.pub` with the CA to get an 8h cert and presents
`-i /home/frappe/.ssh/sanad-infra -o CertificateFile=<cert>` on every adapter/tunnel connection.

## 3. Docker target - socket-proxy with the agreed ACL

On each `server_type=docker` host, run the tecnativa proxy bound to localhost only (the SSH forward
reaches it). It is the agent: it exposes ONLY the verbs we chose.

```yaml
# /opt/sanad-infra/docker-compose.yml on the docker host
services:
  socket-proxy:
    image: tecnativa/docker-socket-proxy:latest
    container_name: sanad-socket-proxy
    restart: unless-stopped
    ports:
      - "127.0.0.1:2375:2375"        # localhost ONLY - the SSH -L forward hits this
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      CONTAINERS: 1                  # GET /containers/json (enumerate)
      POST: 1                        # allow POST...
      ALLOW_START: 1                 # ...start
      ALLOW_STOPS: 1                 # ...stop / restart / kill
      ALLOW_RESTARTS: 1
      EXEC: 0                        # NO exec (no shell into containers)
      BUILD: 0
      VOLUMES: 0
      IMAGES: 0
      INFO: 1                        # GET /info (optional host metrics)
```
```bash
cd /opt/sanad-infra && docker compose up -d
```

## 4. Trust the CA on the host + restrict the principal

```bash
# on the docker/plain host, as root
mkdir -p /etc/ssh/sanad
cp sanad_infra_ca.pub /etc/ssh/sanad/infra_ca.pub
# trust CA-signed certs:
echo "TrustedUserCAKeys /etc/ssh/sanad/infra_ca.pub" >> /etc/ssh/sshd_config
# the access user (matches Managed Host.ssh_user, e.g. 'sanad'):
useradd -m -s /bin/bash sanad 2>/dev/null || true
systemctl reload sshd
```
For DOCKER hosts the user only needs to hold the `-L 2375` forward open (no shell commands run).
For PLAIN hosts, restrict the principal to read-only probes with a forced command / allowlist
(the adapter only runs `systemctl list-units`, `df`, `free`, `awk /proc/loadavg`).

## Carry (hardening, deferred): host-key pinning
The `tls_fingerprint` field on Managed Host is unused; the tunnel + ssh_plain use
`StrictHostKeyChecking=accept-new` (TOFU). After step 4, capture each host key
(`ssh-keyscan -p <port> <host>`), store it in `tls_fingerprint`, and switch the steady-state paths
to a pinned `UserKnownHostsFile` + `StrictHostKeyChecking=yes`.

## Run Task 10 (live smoke) once 1-4 are done
```bash
S=demo.mvpstorm.com   # or the real Press site
bench --site $S execute press.api.infra_board.add_managed_host --kwargs \
  "{'host_name':'sandbox-1','server_type':'docker','ssh_host':'<ip>','ssh_user':'sanad','proxy_port':2375}"
bench --site $S execute press.api.infra_board.test_connection --kwargs "{'host':'sandbox-1'}"
#   -> {'ssh_ok': True, 'docker_ok': True, 'containers': N>0}  (status flips to Active, last_seen set)
bench --site $S execute press.api.infra_board.get_infra_tree
#   -> a kind:managed, server_type:docker node for sandbox-1 with its containers under units
# then via the API: get_host_log('sandbox-1','<container_id>') returns lines;
#   host_unit_action('sandbox-1','<container_id>','restart') -> {'ok': True};
#   confirm an Infra Action Log row exists for the restart.
```
A failure at test_connection that mentions `Gate 0 pending` means the CA env var (step 1) is unset.
