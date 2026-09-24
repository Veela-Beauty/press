# 2026-09-24: an MCP token reached another team's sites

## What happened

We moved one server and its benches into a new private team so the main team's developers
would not see them. The dashboard hid them correctly. The MCP server did not: a token issued
for the main team called `site_status` on the private team's production site and got its
bench, status and recent jobs back. The same path reached `site_run_sql`, `site_file_write`,
backups, deploys and domain changes.

An audit of all 84 MCP tools (one auditor per handler group, every finding checked by two
independent verifiers) confirmed 59 cross-team paths.

## Root cause

Three separate gaps, each hiding the next:

1. **System Users skip Frappe permissions.** MCP tools run as the token's user. Ours is a
   System Manager, so `@protected`, `has_permission` and the team guards all return early.
   The MCP layer was the only check left.
2. **The scope check looked at one argument, and sometimes the wrong one.** `_extract_target`
   picks a single Site or Release Group, and it read `site` before `name`. For tools that take
   `name`, a call with `{site: <own site>, name: <other team's site>}` was checked against the
   first and run on the second: the dispatcher dropped the undeclared `site` after the check.
   Second resources (a clone's target bench, a move's destination, a redeploy's build, an App
   Source, a backup file, a raw `server`) were never checked at all.
3. **The check compared allow-lists, never teams.** `_check_resource_scope` enforced a token's
   optional allow-lists and nothing else.

Found on the way: a user who owns two teams gets whichever was modified last as their default
team, both in the dashboard and in MCP. Creating the private team switched every MCP call of
its owner to it until the default was fixed in code.

## How we fixed it

`press/mcp_server/scope/`, wired into `handle()` (PRs #9 to #12). The full sequence is in
[MCP Server: team isolation](../03-integrations/mcp-server.md#team-isolation-since-2026-09-24).
Every PR was verified before deploy with side-loaded modules against the live data, then
through the live MCP endpoint: the call that leaked is now refused, own-team calls still work.

## Lesson

- A permission layer that System Users bypass does not protect anything a System User's token
  can reach. Whatever sits in front of those calls has to enforce the team itself.
- Check the value the handler will use, not a value that happens to be nearby. Resolve the
  target from the declared arguments only, and refuse the rest.
- An error that says "not found" for missing objects and "not yours" for another team's tells
  the caller which names exist. Use one message.

## Prevention

- A new MCP tool that takes a resource argument must be covered by `assert_call_in_team`; the
  fail-closed guard in `scope/targets.py` still refuses unmapped resource arguments.
- A second audit ran against the fix and raised further gaps (Bench ownership read from a
  stale field, `apps` sent as a JSON string, uploaded Remote Files without an owner). The
  follow-up lives on branch `fix/mcp-isolation-hardening`.
