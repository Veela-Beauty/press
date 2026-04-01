# Dev SSH Key Management — Design

> **Status:** Approved design, not yet implemented
> **Priority:** Next after Dev Tab v2 ships
> **Effort:** Small (1 API + 1 UI component)

## Problem

The "Local VS Code" button on the Dev tab generates a `vscode://` SSH Remote URI,
but devs need their SSH public key registered in the bench container to connect.
Currently this requires manual `docker exec` to add keys — not self-service.

## Solution

Add an "SSH Keys" section to the Dev tab where devs can:
1. Paste their public SSH key
2. Click "Add Key" — calls API that appends to `~frappe/.ssh/authorized_keys` in the container
3. See list of registered keys (fingerprint + comment)
4. Remove a key

## API

```python
@frappe.whitelist()
def add_ssh_key(bench_name, public_key):
    """Append an SSH public key to frappe's authorized_keys in the bench container."""
    frappe.only_for("System Manager")
    # Validate key format (must start with ssh-rsa, ssh-ed25519, etc.)
    # Escape for shell safety
    # docker_execute: echo 'KEY' >> ~/.ssh/authorized_keys

@frappe.whitelist()
def list_ssh_keys(bench_name):
    """List SSH key fingerprints in the bench container."""
    # docker_execute: ssh-keygen -lf ~/.ssh/authorized_keys

@frappe.whitelist()
def remove_ssh_key(bench_name, fingerprint):
    """Remove an SSH key by fingerprint."""
    # Read authorized_keys, filter out matching key, write back
```

## Security

- System Manager only (existing pattern)
- Validate key format before adding (reject non-SSH-key strings)
- Key comment field identifies owner (e.g., `ssh-ed25519 AAAA... dev@laptop`)
- Audit: log who added/removed keys via frappe.logger

## UI

Small card below Quick Actions:
```
┌─ SSH Keys ──────────────────────────────────────────┐
│ Fingerprint          Owner           [Remove]       │
│ SHA256:abc123...     eslam@laptop    [×]            │
│ SHA256:def456...     mohammed@pc     [×]            │
│                                                     │
│ [textarea: paste public key]  [Add Key]             │
└─────────────────────────────────────────────────────┘
```

## Dev Onboarding Flow

1. Dev generates SSH key: `ssh-keygen -t ed25519 -C "name@device"`
2. Dev copies public key: `cat ~/.ssh/id_ed25519.pub`
3. Dev pastes in Dev tab → "Add Key"
4. Dev clicks "Local VS Code" → opens VS Code with SSH Remote
5. VS Code connects to `frappe@server:port` using the registered key
