# Dev Actions Panel

The Dev Actions panel appears at `/dashboard/groups/<release-group>/actions` and gives developers per-bench tools for editing code on a Press-managed bench.

## What's in each bench section

For every bench in the release group, you see:

1. **Bench identity** — bench name (mono), helper text, and a status pill on the right showing whether Code Server is running.
2. **Code Server panel** — full bench code-server URL, current password (masked by default), expiry countdown, rotate / restart links, and an auto-rotate days input.
3. **Action tiles** — four per-bench actions:
   - **Open in VS Code** — launches your local VS Code Desktop over Remote-SSH.
   - **Mark as Dev Bench** — tags the bench as `is_development_bench`, used by other dashboards as a filter.
   - **Generate SSH Certificate** — opens the SSH cert dialog (PowerShell / bash one-liner).
   - **Restart Bench** — restarts all bench workers (web, scheduler, queues).

## Working with the Code Server password

The masked password row has two icon buttons:

- **Eye icon** — toggles between masked dots and the real password text. When revealed, the text is selectable; when masked, selecting the dots does nothing.
- **Copy icon** — copies the actual password to your clipboard regardless of mask state, with a "Code Server password copied" confirmation toast.

The Code Server password rotates automatically based on the **Auto-rotate every N days** setting (default 3 days). You can rotate manually with **Rotate now**.

## "Open in VS Code" — first-time setup

Clicking the tile opens a dialog that walks through three steps:

1. (Windows only) Set PowerShell encoding to UTF-8.
2. Install the SSH certificate locally (`echo '...' > ~/.ssh/id_ed25519-cert.pub`).
3. Click **Launch VS Code** — your browser asks to open VS Code Desktop, which then connects to the bench over Remote-SSH and opens `/home/frappe/frappe-bench`.

Certificates are valid for 6 hours. Reopen the dialog when one expires.

## Backend method

The dialog calls `press.press.doctype.bench.bench_dev_overview.get_vscode_remote_url` which returns:

```
vscode://vscode-remote/ssh-remote+<bench>@<proxy_server>:2222/home/frappe/frappe-bench
```

The `proxy_server` is read from the bench's `Server` document (fetched via `frappe.db.get_value("Server", bench.server, "proxy_server")`). Port `2222` is the user-facing SSH proxy port (cert-based) — distinct from the `22000+offset` admin port used by direct bench-server SSH.

## Related files

- Component: `dashboard/src/components/group/ReleaseGroupActions.vue`
- VS Code dialog: `dashboard/src/components/group/VSCodeLaunchDialog.vue`
- SSH cert dialog: `dashboard/src/components/group/SSHCertificateDialog.vue`
- Backend APIs: `press/press/doctype/bench/bench_dev_overview.py`

## Troubleshooting

**"Open in VS Code" tile shows nothing after cert install** — the URL fetch failed. Check:
1. The bench's `Server` document has `proxy_server` set.
2. The bench is on a `Release Group` you have read access to.
The dialog now surfaces these errors via an `<ErrorMessage>` block inline.

**Password copy gives wrong text** — fixed in the redesign. The previous UI had a single-string label `'•••••••••• copy password'` which copied the literal text when selected with the cursor. The new UI uses two explicit icon buttons (eye toggle + copy) and the masked dots are not selectable.

**`vscode://` link doesn't open the editor** — VS Code Desktop must be installed locally. Browsers prompt for permission the first time. Click "Always allow" or use the copy-URL fallback shown beneath the Launch button.
