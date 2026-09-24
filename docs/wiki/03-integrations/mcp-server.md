# Press MCP Server — Token Issuance Guide

The Press MCP server lets agents (Claude Code, automation scripts) call Press
APIs with scoped, time-limited tokens. Tokens are issued from the dashboard at
`/dashboard/dev-tools/mcp` and verified server-side per request.

## Token TTL

- **Range**: 1 to 90 days (default 7).
- **Backend**: `TTL_MAX = 60 * 24 * 90` minutes in
  [press/mcp_server/auth.py](../../press/mcp_server/auth.py). The UI sends
  `ttl_minutes = days * 24 * 60`; backend clamps to the range.
- **History**: was capped at 24h (1440 min) until 2026-05-12. Bumped to 90 days
  for long-lived agent use cases. Existing tokens are untouched — only new
  tokens benefit from the wider range.
- **Reissue dialog** uses the same days unit for consistency.

## Re-authentication: password OR email OTP

Issuing a token requires re-auth even when a dashboard session is active. Two
methods are accepted:

### Password (default)
Same as before — verified via Frappe's `check_password()`.
Returns `HTTP 417` on wrong password (translated from `AuthenticationError` →
`ValidationError`) so the Vue dashboard shows an inline error instead of
force-logging-out the session.

### Email OTP (alternative)
For users on SSO / forgot-password flows who can't supply a password:

1. Click **"Forgot password? Use email OTP instead"** in the dialog.
2. Click **Send code**. A 6-digit code is mailed to the user's `User.email`.
3. Enter the code; click **Issue Token**.

Mechanics:
- Codes are 6 random digits, generated with `secrets.choice`.
- Stored hashed via `passlibctx.hash` in the **Press MCP Email OTP** doctype.
- Valid for **10 minutes**, **one-shot consume** (`consumed=1` after use).
- Server throttle: max one OTP per username per **30 seconds**.
- Requesting a new code invalidates prior unconsumed codes for that user.
- IP-level brute-force protection (5 fails / 5 min → 60 min block) applies.

### API contract

```python
# Request a code
press.mcp_server.auth.request_email_otp(username="user@example.com")
# -> {"sent": True, "expires_in_minutes": 10}

# Issue a token (one of password or otp is required)
press.mcp_server.auth.issue_token(
    username="user@example.com",
    password="",           # leave blank if using OTP
    otp="123456",          # leave blank if using password
    scope=[...],
    ttl_minutes=10080,     # 7 days = 7 * 24 * 60
    label="agent-claude",
    risky_tools_enabled=False,
)
```

If both `password` and `otp` are empty, raises
`ValidationError("Either password or email OTP is required")`.

## DocType: Press MCP Email OTP

Lightweight, hash-named, transient. Fields:

| Field | Type | Notes |
|---|---|---|
| `username` | Data | Indexed |
| `code_hash` | Data(255) | `passlibctx.hash` of the 6-digit code |
| `expires_at` | Datetime | Now + 10 min |
| `consumed` | Check | Set to 1 after successful verify |

Permissions: read-only for System Manager. No web/dashboard exposure.
Auto-named by Frappe (hash).

## Operational notes

- **Email delivery** depends on Press's outgoing Email Account. If
  `disable_mail_notifications=1` is set in `site_config.json`, OTP mails are
  suppressed too — turn off this flag if rolling out OTP.
- **Cleanup**: consumed and expired OTP rows accumulate. They're tiny but a
  daily delete by `expires_at < now() - 1 day` is reasonable hygiene (no
  scheduler hook ships with this feature).
- **Audit**: each issuance writes a `Press MCP Auth Attempt` row (success or
  failure). OTP failures count toward the IP brute-force gate the same way
  password failures do.

## Team isolation (since 2026-09-24)

Every token belongs to exactly one team, and every MCP call stays inside it. MCP tools run
as the token's user, and Frappe skips its own permission checks for System Users, so the
MCP layer enforces the team itself.

**Which team a token has.** Set when the token is issued: the team the dashboard is showing,
if the user belongs to it, otherwise the user's oldest team. A token without a team is
refused on every call.

**What is checked, in `press/mcp_server/server.py` `handle()`:**

1. `refuse_undeclared_resource_args`: a resource argument the tool does not declare, or a
   non-string value for one, is refused. The scope check can then never read a different
   value from the one the tool acts on.
2. `assert_safe_args`: letters, digits and `_ . -` only for arguments that reach the agent's
   host shell (app names, titles, GitHub owner, file paths).
3. `verify_token`: the Site or Release Group target must be in the token team. It also
   records the team for the call (`frappe.local.mcp_token_team`), which `get_current_team`
   prefers over any `X-Press-Team` header.
4. `assert_call_in_team`: every other resource the arguments name must be in the team too.
   Public App Sources are allowed, and so are public servers for placing a new bench.
   Tools that run inside a bench container are refused on a bench that also hosts another
   team's sites.
5. `filter_to_team`: responses whose handler lists without a team filter are cut to the
   team's own rows.

A refusal reads `<Doctype> '<name>' was not found, or is not in this token's team`. It is
the same for a missing object and for another team's, so a token cannot use it to find
names in another team.

**Dashboard logins for browser tests.** `mint_dashboard_login_url` logs in the team's test
user, never the token's own user. A team names one by giving exactly one Website User of
the team the role **Press MCP Test User** (Desk > User > Roles). That account must belong to
no other team. Without one, the tool refuses and says how to set it up.

Code: `press/mcp_server/scope/` (`targets.py`, `teams.py`, `call_guard.py`, `results.py`,
`arg_safety.py`, `test_login.py`). Background: [the 2026-09-24 lesson](../08-lessons/2026-09-24-mcp-cross-team-leak.md).

## Files

- [press/mcp_server/auth.py](../../press/mcp_server/auth.py) — `issue_token`,
  `request_email_otp`, `_verify_email_otp`, `_check_password`.
- [press/press/doctype/press_mcp_email_otp/](../../press/press/doctype/press_mcp_email_otp/) — new doctype.
- [dashboard/src/components/mcp/IssueTokenDialog.vue](../../dashboard/src/components/mcp/IssueTokenDialog.vue) — issue UI.
- [dashboard/src/pages/devtools/mcp/MCPPanel.vue](../../dashboard/src/pages/devtools/mcp/MCPPanel.vue) — reissue dialog.
