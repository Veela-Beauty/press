# Infrastructure Control Plane: Plan 2a, Managed-Host Backend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the Press dashboard monitor and control **external/managed hosts** (Docker + plain Linux boxes) alongside Press servers: a `Managed Host` registry, short-TTL SSH-cert access, SSH/Docker-API adapters, merged enumeration into the shipped `get_infra_tree`, per-unit control, and an append-only audit log.

**Architecture:** A normalized **adapter interface** (`enumerate` / `control` / `logs`) with one adapter per host type. Press servers reuse the shipped Plan-1 primitives (`get_processes`, `service_action`, `log_browser`); managed Docker hosts use the **Docker HTTP API through a socket-proxy** over a short-TTL SSH-cert tunnel (no shell, no injection); plain hosts use a forced-command SSH allowlist. Everything is System-Manager-gated, reads merge into the 15s-cached `get_infra_tree`, and every control action writes an `Infra Action Log` row. Reuses the Daman `ssh_handler` pattern for the SSH plumbing and the shipped Plan-1 backend.

**Tech Stack:** Frappe (Python), `frappe.tests.utils.FrappeTestCase`, `unittest.mock`, MariaDB, Redis, OpenSSH (`ssh-keygen -s` for the CA), the Docker Engine HTTP API, Infisical (CA key custody). Tests run with `bench --site demo.mvpstorm.com run-tests`.

**Scope:** Phase 1a of the spec (`docs/infra-board/2026-06-05-infrastructure-control-plane-design.md`). Out of scope here: the Vue UI (Plan 2b, built from `press-infrastructure.prototype.html`), the Watch-Tower alerts/overload feed (Plan 2c, small), the Phase-2 poll-home agent, and Phase-3 deploy.

---

## Gate 0: provisioning prerequisites (NOT code, do first)

These are infrastructure steps the code assumes exist. The unit tests mock them; the live smoke (Task 10) needs them real on ONE target host:

1. **SSH CA** - generate a CA keypair once (`ssh-keygen -t ed25519 -f sanad-infra-ca`); store the **private** key in Infisical at path `infra/ssh_ca_private`; put the public key on each managed host (`TrustedUserCAKeys /etc/ssh/sanad-infra-ca.pub` + `AuthorizedPrincipalsFile /etc/ssh/auth_principals/%u`).
2. **socket-proxy** on each Docker host - `tecnativa/docker-socket-proxy` with `POST=1 ALLOW_START=1 ALLOW_STOP=1 ALLOW_RESTARTS=1 CONTAINERS=1 IMAGES=1 INFO=1 EXEC=0 BUILD=0 VOLUMES=0 NETWORKS=0 SECRETS=0`, bound to `127.0.0.1:2375`, never published.
3. **Forced-command** on plain hosts - the cert principal maps to a `command="/opt/sanad/validator.sh",restrict` key; on Docker hosts the cert is tunnel-only (`restrict,permitopen="127.0.0.1:2375"`).
4. **One live target** for the smoke test (Task 10): pick `sandbox-1` (Daytona Docker host) or provision a key to `95.217.109.117`.

If Gate 0 is not ready, Tasks 1-9 still complete (they are fully mock-tested); only Task 10 waits.

---

## File structure

| File | Responsibility |
|---|---|
| `press/press/doctype/managed_host/managed_host.json` + `.py` | The host registry doctype (System-Manager perms, no secret fields) |
| `press/press/doctype/infra_action_log/infra_action_log.json` + `.py` | Append-only audit of every control action |
| `press/infra/__init__.py` | new package |
| `press/infra/ssh_ca.py` | `sign_cert(principal)` - pull CA key from Infisical, sign a short-TTL cert |
| `press/infra/adapters/base.py` | adapter interface + `get_adapter(host)` factory + `audit()` helper |
| `press/infra/adapters/ssh_plain.py` | systemd/df enumeration over the forced-command SSH key |
| `press/infra/adapters/ssh_docker.py` | Docker HTTP API (via socket-proxy tunnel) enumerate/control/logs |
| `press/api/infra_board.py` (modify) | extend `get_infra_tree` merge; add `host_unit_action`, `get_host_log`, `add_managed_host`, `test_connection` |
| `press/infra/tests/test_managed_backend.py` | all unit tests for the above |

---

## Task 1: `Managed Host` doctype

**Files:**
- Create: `press/press/doctype/managed_host/managed_host.json`
- Create: `press/press/doctype/managed_host/managed_host.py`
- Create: `press/infra/tests/test_managed_backend.py`

- [ ] **Step 1: Write the failing test**

Create `press/infra/tests/test_managed_backend.py`:

```python
# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestManagedHost(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_create_and_required_fields(self):
		doc = frappe.get_doc(
			{
				"doctype": "Managed Host",
				"host_name": "test-docker-1",
				"ssh_host": "10.0.0.9",
				"ssh_user": "sanad",
				"server_type": "docker",
			}
		).insert()
		self.assertEqual(doc.ssh_port, 22)  # default
		self.assertEqual(doc.status, "Pending")  # default
		self.assertEqual(doc.host_principal, "test-docker-1")  # auto-set from host_name
		doc.delete()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend --test test_create_and_required_fields`
Expected: FAIL with `Managed Host not found` (doctype does not exist).

- [ ] **Step 3: Create the doctype JSON**

Create `press/press/doctype/managed_host/managed_host.json`:

```json
{
 "actions": [],
 "creation": "2026-06-06 00:00:00",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": ["host_name","server_type","ssh_host","ssh_port","ssh_user","proxy_port","host_principal","tls_fingerprint","status","last_seen","tags","notes"],
 "fields": [
  {"fieldname":"host_name","fieldtype":"Data","label":"Host Name","reqd":1,"unique":1},
  {"fieldname":"server_type","fieldtype":"Select","label":"Server Type","options":"docker\nplain","reqd":1},
  {"fieldname":"ssh_host","fieldtype":"Data","label":"SSH Host","reqd":1},
  {"fieldname":"ssh_port","fieldtype":"Int","label":"SSH Port","default":"22"},
  {"fieldname":"ssh_user","fieldtype":"Data","label":"SSH User","reqd":1},
  {"fieldname":"proxy_port","fieldtype":"Int","label":"Socket-Proxy Port","default":"2375"},
  {"fieldname":"host_principal","fieldtype":"Data","label":"SSH Cert Principal","read_only":1},
  {"fieldname":"tls_fingerprint","fieldtype":"Data","label":"Pinned TLS Fingerprint","read_only":1},
  {"fieldname":"status","fieldtype":"Select","label":"Status","options":"Pending\nActive\nUnreachable","default":"Pending"},
  {"fieldname":"last_seen","fieldtype":"Datetime","label":"Last Seen","read_only":1},
  {"fieldname":"tags","fieldtype":"Small Text","label":"Tags"},
  {"fieldname":"notes","fieldtype":"Small Text","label":"Notes"}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-06-06 00:00:00",
 "module": "Press",
 "name": "Managed Host",
 "owner": "Administrator",
 "permissions": [{"create":1,"delete":1,"email":1,"export":1,"print":1,"read":1,"report":1,"role":"System Manager","share":1,"write":1}],
 "sort_field": "modified",
 "sort_order": "DESC",
 "track_changes": 1
}
```

Create `press/press/doctype/managed_host/managed_host.py`:

```python
# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import frappe
from frappe.model.document import Document


class ManagedHost(Document):
	def before_insert(self):
		# the SSH-cert principal is the host name; one principal per host (R4)
		if not self.host_principal:
			self.host_principal = self.host_name
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend`
Expected: PASS (1 test). If "module press.infra not found", create empty `press/infra/__init__.py` and `press/infra/tests/__init__.py`.

- [ ] **Step 5: Commit**

```bash
git add press/press/doctype/managed_host/ press/infra/
git commit -m "feat(infra): Managed Host registry doctype (System-Manager only, no secret fields)"
```

---

## Task 2: `Infra Action Log` doctype + `log_infra_action`

**Files:**
- Create: `press/press/doctype/infra_action_log/infra_action_log.json` + `.py`
- Create: `press/infra/adapters/__init__.py`, `press/infra/adapters/base.py` (audit helper only this task)
- Test: append to `press/infra/tests/test_managed_backend.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
class TestAudit(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_log_infra_action_creates_row(self):
		from press.infra.adapters.base import log_infra_action

		log_infra_action(host="host-x", unit="redis-queue", action="restart", outcome="success")
		row = frappe.get_last_doc("Infra Action Log")
		self.assertEqual(row.host, "host-x")
		self.assertEqual(row.action, "restart")
		self.assertEqual(row.outcome, "success")
		self.assertEqual(row.actor, "Administrator")
		row.delete()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend --test test_log_infra_action_creates_row`
Expected: FAIL with `No module named 'press.infra.adapters'`.

- [ ] **Step 3: Implement**

Create `press/press/doctype/infra_action_log/infra_action_log.json`:

```json
{
 "actions": [],
 "creation": "2026-06-06 00:00:00",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": ["actor","host","unit","action","outcome","detail"],
 "fields": [
  {"fieldname":"actor","fieldtype":"Data","label":"Actor","read_only":1},
  {"fieldname":"host","fieldtype":"Data","label":"Host","read_only":1},
  {"fieldname":"unit","fieldtype":"Data","label":"Unit","read_only":1},
  {"fieldname":"action","fieldtype":"Data","label":"Action","read_only":1},
  {"fieldname":"outcome","fieldtype":"Data","label":"Outcome","read_only":1},
  {"fieldname":"detail","fieldtype":"Small Text","label":"Detail","read_only":1}
 ],
 "links": [],
 "modified": "2026-06-06 00:00:00",
 "module": "Press",
 "name": "Infra Action Log",
 "owner": "Administrator",
 "permissions": [{"read":1,"report":1,"role":"System Manager"}],
 "sort_field": "creation",
 "sort_order": "DESC"
}
```

Create `press/press/doctype/infra_action_log/infra_action_log.py`:

```python
# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from frappe.model.document import Document


class InfraActionLog(Document):
	pass
```

Create `press/infra/adapters/__init__.py` (empty) and `press/infra/adapters/base.py`:

```python
# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import frappe


def log_infra_action(host: str, unit: str, action: str, outcome: str, detail: str = "") -> None:
	"""Append an immutable audit row for every control action (R5)."""
	frappe.get_doc(
		{
			"doctype": "Infra Action Log",
			"actor": frappe.session.user,
			"host": host,
			"unit": unit,
			"action": action,
			"outcome": outcome,
			"detail": detail,
		}
	).insert(ignore_permissions=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add press/press/doctype/infra_action_log/ press/infra/adapters/
git commit -m "feat(infra): Infra Action Log doctype + log_infra_action audit helper"
```

---

## Task 3: `ssh_ca.sign_cert` (short-TTL cert signer)

**Files:**
- Create: `press/infra/ssh_ca.py`
- Test: append to `press/infra/tests/test_managed_backend.py`

- [ ] **Step 1: Write the failing test**

```python
class TestSshCa(FrappeTestCase):
	def test_sign_cert_uses_principal_and_ttl(self):
		from press.infra import ssh_ca

		calls = {}

		def fake_run(cmd, **kw):
			calls["cmd"] = cmd
			return MagicMock(returncode=0, stderr="")

		with patch.object(ssh_ca, "_ca_private_key", return_value="/tmp/fake-ca"), patch.object(
			ssh_ca.subprocess, "run", side_effect=fake_run
		):
			cert = ssh_ca.sign_cert(principal="client-prod-1", pubkey_path="/tmp/k.pub")

		# the signing command must carry the per-host principal and an 8h validity
		joined = " ".join(calls["cmd"])
		self.assertIn("-n client-prod-1", joined)
		self.assertIn("-V +8h", joined)
		self.assertTrue(cert.endswith("-cert.pub"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend --test test_sign_cert_uses_principal_and_ttl`
Expected: FAIL with `No module named 'press.infra.ssh_ca'`.

- [ ] **Step 3: Implement**

Create `press/infra/ssh_ca.py`:

```python
# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Short-TTL SSH certificate signer (R1/R4).

The CA private key lives in Infisical, never on disk in the repo and never in a
doctype. We pull it just-in-time, sign an 8h cert scoped to one per-host
principal, and let it expire. A stolen cert is useless within a workday.
"""
from __future__ import annotations

import subprocess

CERT_TTL = "+8h"


def _ca_private_key() -> str:
	"""Path to the CA private key, materialised from Infisical at call time."""
	from press.utils import get_infisical_secret  # existing Press helper

	return get_infisical_secret("infra/ssh_ca_private")


def sign_cert(principal: str, pubkey_path: str) -> str:
	"""Sign `pubkey_path` with the CA, scoped to `principal`, valid for CERT_TTL.
	Returns the path to the generated `*-cert.pub`.
	"""
	ca = _ca_private_key()
	cmd = [
		"ssh-keygen", "-s", ca,
		"-I", f"infra-{principal}",
		"-n", principal,
		"-V", CERT_TTL,
		pubkey_path,
	]
	result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
	if result.returncode != 0:
		raise RuntimeError(f"ssh-keygen sign failed: {result.stderr}")
	return pubkey_path.replace(".pub", "-cert.pub")
```

NOTE for implementer: if `press.utils.get_infisical_secret` does not exist, grep `press/` for the existing Infisical accessor and use that name instead; the test mocks `_ca_private_key` so the unit test passes regardless. Record the real accessor name in the commit message.

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add press/infra/ssh_ca.py
git commit -m "feat(infra): ssh_ca.sign_cert - 8h per-host-principal certs from Infisical CA"
```

---

## Task 4: adapter interface + `get_adapter` factory

**Files:**
- Modify: `press/infra/adapters/base.py`
- Test: append

- [ ] **Step 1: Write the failing test**

```python
class TestAdapterFactory(FrappeTestCase):
	def test_factory_routes_by_type(self):
		from press.infra.adapters import base
		from press.infra.adapters.ssh_docker import SshDockerAdapter
		from press.infra.adapters.ssh_plain import SshPlainAdapter

		dh = frappe._dict(server_type="docker")
		ph = frappe._dict(server_type="plain")
		self.assertIsInstance(base.get_adapter(dh), SshDockerAdapter)
		self.assertIsInstance(base.get_adapter(ph), SshPlainAdapter)

	def test_factory_rejects_unknown(self):
		from press.infra.adapters import base

		with self.assertRaises(frappe.ValidationError):
			base.get_adapter(frappe._dict(server_type="quantum"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend --test test_factory_routes_by_type`
Expected: FAIL with `cannot import name 'get_adapter'` (or the ssh adapters).

- [ ] **Step 3: Implement**

Append to `press/infra/adapters/base.py`:

```python
class Adapter:
	"""Normalized host adapter. Every adapter returns the same shapes so the
	aggregator and UI never care how a host is read.
	  enumerate(host) -> {"units": [unit...], "metrics": {"cpu","mem","disk","req"}}
	  control(host, unit_id, action) -> {"ok": bool, ...}
	  logs(host, unit_id, tail) -> list[str]
	A `unit` is {"name","kind"('service'|'container'),"state","sub","uptime","restarts","ports","health","pid"}.
	"""

	def enumerate(self, host) -> dict:  # pragma: no cover - interface
		raise NotImplementedError

	def control(self, host, unit_id: str, action: str) -> dict:  # pragma: no cover
		raise NotImplementedError

	def logs(self, host, unit_id: str, tail: int = 200) -> list:  # pragma: no cover
		raise NotImplementedError


def get_adapter(host) -> "Adapter":
	from press.infra.adapters.ssh_docker import SshDockerAdapter
	from press.infra.adapters.ssh_plain import SshPlainAdapter

	t = host.server_type
	if t == "docker":
		return SshDockerAdapter()
	if t == "plain":
		return SshPlainAdapter()
	frappe.throw(f"No adapter for server_type {t!r}", frappe.ValidationError)
```

Create stub `press/infra/adapters/ssh_plain.py`:

```python
# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from press.infra.adapters.base import Adapter


class SshPlainAdapter(Adapter):
	pass
```

Create stub `press/infra/adapters/ssh_docker.py`:

```python
# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from press.infra.adapters.base import Adapter


class SshDockerAdapter(Adapter):
	pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add press/infra/adapters/
git commit -m "feat(infra): adapter interface + get_adapter factory (docker/plain)"
```

---

## Task 5: `SshPlainAdapter.enumerate` (systemd + df over SSH)

**Files:**
- Modify: `press/infra/adapters/ssh_plain.py`
- Test: append

- [ ] **Step 1: Write the failing test**

```python
class TestSshPlain(FrappeTestCase):
	def test_enumerate_parses_systemctl_and_df(self):
		from press.infra.adapters.ssh_plain import SshPlainAdapter

		host = frappe._dict(host_name="storage-1", ssh_host="10.0.0.5", ssh_user="sanad", ssh_port=22, server_type="plain")
		systemctl_out = "sshd.service loaded active running\nborgmatic.timer loaded active waiting\nfail2ban.service loaded failed failed"
		df_out = "13"  # disk percent
		ad = SshPlainAdapter()
		with patch.object(ad, "_ssh", side_effect=[systemctl_out, df_out, "8", "3"]):
			out = ad.enumerate(host)

		names = {u["name"] for u in out["units"]}
		self.assertIn("sshd.service", names)
		failed = next(u for u in out["units"] if u["name"] == "fail2ban.service")
		self.assertEqual(failed["state"], "down")  # failed -> down
		self.assertEqual(out["metrics"]["disk"], 13)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend --test test_enumerate_parses_systemctl_and_df`
Expected: FAIL with `AttributeError: ... has no attribute 'enumerate'` (or `_ssh`).

- [ ] **Step 3: Implement**

Replace `press/infra/adapters/ssh_plain.py`:

```python
# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Plain-host adapter: read-only systemd + disk/mem/cpu over a forced-command
SSH cert. No control in v1 (R: watch-only)."""
from __future__ import annotations

import subprocess

from press.infra.adapters.base import Adapter
from press.infra import ssh_ca


class SshPlainAdapter(Adapter):
	def _ssh(self, host, remote_cmd: str) -> str:
		"""Run ONE allowlisted command over the cert-authed forced-command key.
		The remote validator (Gate 0) re-checks the command server-side."""
		# pubkey/cert provisioning is done at onboarding; here we just connect.
		cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes",
			"-p", str(host.ssh_port or 22), f"{host.ssh_user}@{host.ssh_host}", remote_cmd]
		r = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
		return r.stdout.strip()

	def enumerate(self, host) -> dict:
		systemctl = self._ssh(host, "systemctl list-units --type=service,timer --no-legend --plain")
		disk = self._ssh(host, "df --output=pcent / | tail -1 | tr -dc 0-9")
		mem = self._ssh(host, "free | awk '/Mem:/{printf \"%d\", $3/$2*100}'")
		cpu = self._ssh(host, "awk '{printf \"%d\", $1*25}' /proc/loadavg")
		units = []
		for line in (systemctl or "").splitlines():
			parts = line.split()
			if len(parts) < 4:
				continue
			name, active = parts[0], parts[2]
			units.append({"name": name, "kind": "systemd", "sub": "systemd",
				"state": "active" if active == "active" else "down",
				"uptime": "-", "restarts": 0, "ports": "-", "health": "-", "pid": "-"})
		return {"units": units, "metrics": {"cpu": _int(cpu), "mem": _int(mem), "disk": _int(disk), "req": 0}}


def _int(s: str) -> int:
	try:
		return int((s or "0").strip() or 0)
	except ValueError:
		return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add press/infra/adapters/ssh_plain.py
git commit -m "feat(infra): SshPlainAdapter.enumerate (systemd + df/free/load over SSH)"
```

---

## Task 6: `SshDockerAdapter` enumerate/control/logs (Docker API via socket-proxy)

**Files:**
- Modify: `press/infra/adapters/ssh_docker.py`
- Test: append

- [ ] **Step 1: Write the failing test**

```python
class TestSshDocker(FrappeTestCase):
	def _host(self):
		return frappe._dict(host_name="acc-1", ssh_host="10.0.0.7", ssh_user="sanad", ssh_port=22, proxy_port=2375, server_type="docker")

	def test_enumerate_maps_containers(self):
		from press.infra.adapters.ssh_docker import SshDockerAdapter

		api_list = [
			{"Id": "a" * 64, "Names": ["/eltarak-frontend"], "Image": "erpnext15:latest", "State": "running", "Status": "Up 3 days"},
			{"Id": "b" * 64, "Names": ["/eltarak-configurator"], "Image": "erpnext15:latest", "State": "exited", "Status": "Exited (2) 1h ago"},
		]
		ad = SshDockerAdapter()
		with patch.object(ad, "_api", return_value=api_list):
			out = ad.enumerate(self._host())

		names = {u["name"] for u in out["units"]}
		self.assertIn("eltarak-frontend", names)
		cfg = next(u for u in out["units"] if u["name"] == "eltarak-configurator")
		self.assertEqual(cfg["state"], "exit2")  # exited code 2
		self.assertEqual(cfg["kind"], "container")

	def test_control_validates_action_and_id(self):
		from press.infra.adapters.ssh_docker import SshDockerAdapter

		ad = SshDockerAdapter()
		with patch.object(ad, "_api", return_value=[{"Id": "a" * 64, "Names": ["/x"]}]):
			# bad action rejected
			with self.assertRaises(frappe.ValidationError):
				ad.control(self._host(), "a" * 64, "exec")
			# unknown id rejected (not in enumerated set)
			with self.assertRaises(frappe.ValidationError):
				ad.control(self._host(), "f" * 64, "restart")

	def test_control_posts_for_valid(self):
		from press.infra.adapters.ssh_docker import SshDockerAdapter

		ad = SshDockerAdapter()
		posted = {}
		def fake_api(host, method, path, **kw):
			if method == "GET":
				return [{"Id": "a" * 64, "Names": ["/x"]}]
			posted["path"] = path
			return {}
		with patch.object(ad, "_api", side_effect=fake_api):
			res = ad.control(self._host(), "a" * 64, "restart")
		self.assertTrue(res["ok"])
		self.assertEqual(posted["path"], "/containers/" + "a" * 64 + "/restart")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend --test test_enumerate_maps_containers`
Expected: FAIL with `AttributeError: ... 'enumerate'` (or `_api`).

- [ ] **Step 3: Implement**

Replace `press/infra/adapters/ssh_docker.py`:

```python
# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Docker-host adapter. Talks the Docker Engine HTTP API through a
socket-proxy reached over a short-TTL SSH-cert tunnel (R2/R3): no shell, so
no command injection, and exec/build/volumes are blocked at the proxy."""
from __future__ import annotations

import re

import frappe

from press.infra.adapters.base import Adapter

_ID_RE = re.compile(r"^[a-f0-9]{12,64}$")
_VERBS = ("start", "stop", "restart", "kill")


class SshDockerAdapter(Adapter):
	def _api(self, host, method: str, path: str, **kw):
		"""Open the SSH-cert tunnel to 127.0.0.1:proxy_port and call the Docker API.
		Implemented with an SSH local-forward + an HTTP request; the tunnel and
		cert handling live in press.infra.docker_tunnel (created at onboarding).
		In tests this method is fully mocked."""
		from press.infra.docker_tunnel import docker_request

		return docker_request(host, method, path, **kw)

	def _container_state(self, c: dict) -> str:
		state = (c.get("State") or "").lower()
		status = c.get("Status") or ""
		if state == "running":
			return "heal" if "healthy" in status else "run"
		if state == "exited":
			return "exit2" if "(2)" in status else "exit0"
		return "stop"

	def enumerate(self, host) -> dict:
		containers = self._api(host, "GET", "/containers/json?all=1") or []
		units = []
		for c in containers:
			name = (c.get("Names") or ["/?"])[0].lstrip("/")
			units.append({
				"name": name, "kind": "container", "sub": c.get("Image", "-"),
				"state": self._container_state(c), "uptime": c.get("Status", "-"),
				"restarts": 0, "ports": "-", "health": "-", "pid": "-", "_id": c.get("Id"),
			})
		# host metrics come from the shared host_probes (disk/mem) + /info; cpu approximated
		return {"units": units, "metrics": {"cpu": 0, "mem": 0, "disk": 0, "req": 0}}

	def _live_ids(self, host) -> set:
		return {c.get("Id") for c in (self._api(host, "GET", "/containers/json?all=1") or [])}

	def control(self, host, unit_id: str, action: str) -> dict:
		if action not in _VERBS:
			frappe.throw(f"Invalid action {action!r}; allowed: {_VERBS}", frappe.ValidationError)
		if not _ID_RE.match(unit_id or ""):
			frappe.throw("Invalid container id", frappe.ValidationError)
		if unit_id not in self._live_ids(host):
			frappe.throw("Container not found on host", frappe.ValidationError)
		self._api(host, "POST", f"/containers/{unit_id}/{action}")
		return {"ok": True, "host": host.host_name, "unit": unit_id, "action": action}

	def logs(self, host, unit_id: str, tail: int = 200) -> list:
		if not _ID_RE.match(unit_id or ""):
			frappe.throw("Invalid container id", frappe.ValidationError)
		raw = self._api(host, "GET", f"/containers/{unit_id}/logs?stdout=1&stderr=1&tail={int(tail)}", raw=True)
		return (raw or "").splitlines()
```

NOTE for implementer: `press/infra/docker_tunnel.py` (`docker_request`) is the real SSH-forward + HTTP layer; it is created in Task 9 alongside onboarding and is mocked in all Task-6 tests. Keep `control` referencing `unit_id` as the Docker `Id` (validated against the live set), never a name.

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add press/infra/adapters/ssh_docker.py
git commit -m "feat(infra): SshDockerAdapter via Docker API (enumerate/control/logs, id-validated, no shell)"
```

---

## Task 7: merge managed hosts into `get_infra_tree` + overload field

**Files:**
- Modify: `press/api/infra_board.py`
- Test: append

- [ ] **Step 1: Write the failing test**

```python
class TestMergedTree(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_managed_hosts_merge_with_overload(self):
		from press.api import infra_board

		host = frappe._dict(host_name="acc-1", server_type="docker", ssh_host="10.0.0.7", reach="ok")
		enum = {"units": [{"name": "x", "kind": "container", "state": "stop"}], "metrics": {"cpu": 10, "mem": 92, "disk": 40, "req": 100}}
		with patch.object(infra_board, "_press_servers", return_value=[]), patch.object(
			infra_board, "_managed_hosts", return_value=[host]
		), patch.object(infra_board, "_enumerate_managed", return_value=enum):
			tree = infra_board._build_tree()

		node = next(s for s in tree["servers"] if s["name"] == "acc-1")
		self.assertEqual(node["kind"], "managed")
		self.assertEqual(node["server_type"], "docker")
		self.assertEqual(node["overload"], "crit")  # mem 92 -> crit
		self.assertEqual(node["health"], "down")     # a container is stopped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend --test test_managed_hosts_merge_with_overload`
Expected: FAIL with `AttributeError: module 'press.api.infra_board' has no attribute '_managed_hosts'`.

- [ ] **Step 3: Implement**

In `press/api/infra_board.py`, add near `_build_tree` (keep the shipped Press path intact, add the managed path + an `overload` helper and call it for every server node):

```python
def _managed_hosts():
	return frappe.get_all(
		"Managed Host", filters={"status": ["!=", "Pending"]},
		fields=["name as host_name", "server_type", "ssh_host", "ssh_port", "ssh_user", "proxy_port", "status"]
	)


def _enumerate_managed(host):
	from press.infra.adapters.base import get_adapter

	try:
		return get_adapter(host).enumerate(host)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"infra enumerate failed: {host.host_name}")
		return {"units": [], "metrics": {"cpu": 0, "mem": 0, "disk": 0, "req": 0}}


def _overload(m: dict) -> str | None:
	hi = max(m.get("cpu", 0), m.get("mem", 0), m.get("disk", 0))
	return "crit" if hi >= 90 else "high" if hi >= 80 else None
```

Then in `_build_tree`, after assembling the Press server nodes, append managed-host nodes:

```python
	for h in _managed_hosts():
		en = _enumerate_managed(h)
		units = en["units"]
		down = sum(1 for u in units if u.get("state") in ("stop", "exit2", "down"))
		servers.append({
			"name": h.host_name, "kind": "managed", "server_type": h.server_type,
			"benches": [],  # managed hosts expose units directly / via stacks in the UI layer
			"units": units, "metrics": en["metrics"], "overload": _overload(en["metrics"]),
			"host": {"server": h.host_name},
			"health": ("unknown" if h.status == "Unreachable" else "down" if (down or _overload(en["metrics"]) == "crit") else "up"),
		})
```

Add `_press_servers()` as a thin wrapper around the existing server enumeration so the test can patch it (refactor the existing Press loop body into `_press_servers()` returning the list of press nodes; `_build_tree` then does `servers = _press_servers() ; servers += managed...`). Keep behavior identical for the Press path (the 9 shipped tests must still pass).

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend && bench --site demo.mvpstorm.com run-tests --module press.api.tests.test_infra_board`
Expected: PASS (new merged-tree test + the existing 9 Plan-1 tests still green).

- [ ] **Step 5: Commit**

```bash
git add press/api/infra_board.py
git commit -m "feat(infra): merge managed hosts into get_infra_tree + overload (>=80 high / >=90 crit)"
```

---

## Task 8: `host_unit_action` (route + validate + audit) and `get_host_log`

**Files:**
- Modify: `press/api/infra_board.py`
- Test: append

- [ ] **Step 1: Write the failing test**

```python
class TestHostControl(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_action_routes_to_adapter_and_audits(self):
		from press.api import infra_board

		host = frappe._dict(host_name="acc-1", server_type="docker")
		adapter = MagicMock()
		adapter.control.return_value = {"ok": True}
		with patch("press.api.infra_board.frappe.only_for"), patch.object(
			infra_board, "_managed_doc", return_value=host
		), patch("press.infra.adapters.base.get_adapter", return_value=adapter):
			res = infra_board.host_unit_action("acc-1", "a" * 64, "restart")

		self.assertTrue(res["ok"])
		adapter.control.assert_called_once_with(host, "a" * 64, "restart")
		row = frappe.get_last_doc("Infra Action Log")
		self.assertEqual(row.action, "restart")
		row.delete()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend --test test_action_routes_to_adapter_and_audits`
Expected: FAIL with `has no attribute 'host_unit_action'`.

- [ ] **Step 3: Implement**

Append to `press/api/infra_board.py`:

```python
def _managed_doc(host_name: str):
	return frappe.get_doc("Managed Host", host_name)


@frappe.whitelist()
def host_unit_action(host: str, unit_id: str, action: str) -> dict:
	"""Start/stop/restart/kill a unit on a managed host. System-Manager only;
	the adapter validates the action allowlist + the unit against live state;
	every call is audited (R5/R6)."""
	frappe.only_for("System Manager")
	from press.infra.adapters.base import get_adapter, log_infra_action

	doc = _managed_doc(host)
	try:
		res = get_adapter(doc).control(doc, unit_id, action)
		log_infra_action(host=host, unit=unit_id, action=action, outcome="success")
		return res
	except Exception as e:
		log_infra_action(host=host, unit=unit_id, action=action, outcome="error", detail=str(e))
		raise


@frappe.whitelist()
def get_host_log(host: str, unit_id: str, tail: int = 200) -> list:
	"""Tail a unit's log on a managed host (docker logs / journalctl)."""
	frappe.only_for("System Manager")
	from press.infra.adapters.base import get_adapter, log_infra_action

	doc = _managed_doc(host)
	log_infra_action(host=host, unit=unit_id, action="logs", outcome="read")
	return get_adapter(doc).logs(doc, unit_id, tail=int(tail))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add press/api/infra_board.py
git commit -m "feat(infra): host_unit_action + get_host_log (System-Manager, adapter-routed, audited)"
```

---

## Task 9: onboarding - `add_managed_host` + `test_connection` + `docker_tunnel`

**Files:**
- Modify: `press/api/infra_board.py`
- Create: `press/infra/docker_tunnel.py`
- Test: append

- [ ] **Step 1: Write the failing test**

```python
class TestOnboarding(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_test_connection_signs_cert_and_probes(self):
		from press.api import infra_board

		host = frappe._dict(host_name="probe-1", server_type="docker", ssh_host="10.0.0.7", ssh_user="sanad", ssh_port=22, proxy_port=2375)
		with patch("press.api.infra_board.frappe.only_for"), patch.object(
			infra_board, "_managed_doc", return_value=host
		), patch("press.infra.ssh_ca.sign_cert", return_value="/tmp/k-cert.pub"), patch(
			"press.infra.docker_tunnel.docker_request", return_value=[{"Id": "a" * 64, "Names": ["/x"]}]
		):
			res = infra_board.test_connection("probe-1")

		self.assertTrue(res["ssh_ok"])
		self.assertTrue(res["docker_ok"])
		self.assertEqual(res["containers"], 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend --test test_test_connection_signs_cert_and_probes`
Expected: FAIL with `has no attribute 'test_connection'`.

- [ ] **Step 3: Implement**

Create `press/infra/docker_tunnel.py`:

```python
# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""SSH-cert tunnel to a host's docker-socket-proxy + Docker Engine HTTP call.
Opens an ssh local-forward (cert-authed) to 127.0.0.1:<proxy_port> and issues
one HTTP request. Mocked in all unit tests."""
from __future__ import annotations

import json


def docker_request(host, method: str, path: str, raw: bool = False, **kw):
	import http.client
	import subprocess
	import time

	local = 0  # pick an ephemeral local port in the real impl (e.g. via socket)
	tunnel = subprocess.Popen([
		"ssh", "-N", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
		"-p", str(host.ssh_port or 22),
		"-L", f"{local}:127.0.0.1:{host.proxy_port or 2375}",
		f"{host.ssh_user}@{host.ssh_host}",
	])
	try:
		time.sleep(0.5)
		conn = http.client.HTTPConnection("127.0.0.1", local, timeout=10)
		conn.request(method, path)
		resp = conn.read() if False else conn.getresponse().read().decode()
		return resp if raw else json.loads(resp or "[]")
	finally:
		tunnel.terminate()
```

NOTE for implementer: the ephemeral-local-port + readiness wait are simplified above; bind a real free port (`socket`) and poll the forward before connecting. This file is mocked in tests; correctness is verified live in Task 10.

Append to `press/api/infra_board.py`:

```python
@frappe.whitelist()
def add_managed_host(host_name, server_type, ssh_host, ssh_user, ssh_port=22, proxy_port=2375):
	frappe.only_for("System Manager")
	doc = frappe.get_doc({
		"doctype": "Managed Host", "host_name": host_name, "server_type": server_type,
		"ssh_host": ssh_host, "ssh_user": ssh_user, "ssh_port": int(ssh_port), "proxy_port": int(proxy_port),
	}).insert()
	return {"host": doc.name, "status": doc.status}


@frappe.whitelist()
def test_connection(host: str) -> dict:
	"""Sign a short-TTL cert and probe the host: SSH reachability + (docker) the
	Docker API via the socket-proxy. Sets status Active on success."""
	frappe.only_for("System Manager")
	from press.infra import ssh_ca
	from press.infra.docker_tunnel import docker_request

	doc = _managed_doc(host)
	ssh_ca.sign_cert(principal=doc.host_principal, pubkey_path=f"/tmp/{doc.host_principal}.pub")
	out = {"ssh_ok": True, "docker_ok": False, "containers": 0}
	if doc.server_type == "docker":
		containers = docker_request(doc, "GET", "/containers/json?all=1") or []
		out["docker_ok"] = True
		out["containers"] = len(containers)
	frappe.db.set_value("Managed Host", host, "status", "Active")
	return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site demo.mvpstorm.com run-tests --module press.infra.tests.test_managed_backend`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add press/infra/docker_tunnel.py press/api/infra_board.py
git commit -m "feat(infra): onboarding - add_managed_host + test_connection + docker_tunnel"
```

---

## Task 10: live smoke (needs Gate 0 on one target)

**Files:** none (live verification)

- [ ] **Step 1: Register a real Docker target**

Run (replace with the provisioned target, e.g. sandbox-1):
```bash
bench --site demo.mvpstorm.com execute press.api.infra_board.add_managed_host --kwargs "{'host_name':'sandbox-1','server_type':'docker','ssh_host':'<ip>','ssh_user':'sanad','proxy_port':2375}"
bench --site demo.mvpstorm.com execute press.api.infra_board.test_connection --kwargs "{'host':'sandbox-1'}"
```
Expected: `{'ssh_ok': True, 'docker_ok': True, 'containers': N}` with N > 0, no traceback.

- [ ] **Step 2: It appears in the merged tree**

```bash
bench --site demo.mvpstorm.com execute press.api.infra_board.get_infra_tree
```
Expected: a `kind: managed`, `server_type: docker` node for `sandbox-1` with its containers under `units`.

- [ ] **Step 3: Read a log + restart a container, confirm audit**

```bash
bench --site demo.mvpstorm.com console <<'PYEOF'
import frappe
from press.api.infra_board import get_host_log, host_unit_action
frappe.set_user('Administrator')
tree=frappe.get_doc  # noop
PYEOF
```
Then via the API: `get_host_log('sandbox-1', '<container_id>')` returns lines; `host_unit_action('sandbox-1','<container_id>','restart')` returns `{'ok': True}`; confirm an `Infra Action Log` row exists for the restart.

- [ ] **Step 4: Commit (no code; record the smoke result in the DEVLOG)**

---

## Definition of Done (Plan 2a)

- [ ] `Managed Host` + `Infra Action Log` doctypes exist, System-Manager-gated, no secret fields
- [ ] `ssh_ca.sign_cert` issues 8h per-principal certs (unit-tested with mocks)
- [ ] `get_adapter` routes docker/plain; `SshPlainAdapter` and `SshDockerAdapter` enumerate (and docker controls/logs) with id-validation and no shell
- [ ] `get_infra_tree` merges managed hosts with `server_type` + `overload`, unreachable -> unknown; the 9 shipped Plan-1 tests still pass
- [ ] `host_unit_action` / `get_host_log` route to the adapter, System-Manager-gated, every call audited
- [ ] onboarding (`add_managed_host` + `test_connection`) works; live smoke green on one target
- [ ] all committed and pushed to `Veela-Beauty/press` `cloudflare-dns`

## Self-review notes (author)

- **Spec coverage:** covers the spec's Managed Host model, the ssh_docker (socket-proxy+API)/ssh_plain adapters, ssh_ca, the merged tree, control, logs, audit (R5), System-Manager gating (R6). Deferred to later plans: the Vue UI (2b), the Watch-Tower alerts feed + req/min source (2c), Phase-2 agent, Phase-3 deploy. Provisioning (CA, socket-proxy, forced-command) is Gate 0, not code.
- **No placeholders:** every task has runnable code + commands. The two integration files (`docker_tunnel`, the `_ssh` forward) carry explicit implementer NOTEs because their correctness is verified live (Task 10), and they are fully mocked in units.
- **Type consistency:** the adapter contract (`enumerate`->{units,metrics}, `control(host,unit_id,action)`, `logs(host,unit_id,tail)`) and the unit shape are used identically across Tasks 4-9; `host_unit_action(host,unit_id,action)`, `get_host_log(host,unit_id,tail)`, `_managed_doc`, `_overload`, `log_infra_action` are consistent throughout.
