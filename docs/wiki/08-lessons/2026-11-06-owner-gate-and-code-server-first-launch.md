# Lessons Learned: 2026-11-06: a team owner could not switch Dev Mode or open Code Server

> The owner of team Accurate Systems (`uibc5n8ho1`, server u5) hit four failures in a row on
> engoffice: Enable Dev Mode refused, Launch Code Server refused, the first Code Server launch
> broke, and the Dev Mode card kept saying "Disabled" after it was enabled. Fixed in press 0.7.8
> and 0.7.9 and in press-agent on all four app servers.

**Second time for Lesson 3.** `dashboard_fields` as a silent whitelist was written down on
2026-04-29 ([lesson](2026-04-29-bench-watch-and-log-server.md)); a new card read a field that was
never in the list.

## Lesson 1: the dashboard and the server disagreed about the owner

### How it bit us

`press/api/account.py` sets `admin = is_owner or ...`, so the owner saw Enable Dev Mode and Mark
bench as development. The server gate `require_team_role_flag` accepted only System Managers or a
Press Role with the flag. The owner's role on his own team was Developer (`admin_access=0`), so
both buttons ended in "Required role flag: ...".

### Fix

`require_team_role_flag(team, flag, owner_passes=False)`. Only `Site.set_development_mode` and
`Bench.set_development_bench` pass `owner_passes=True`. Letting the owner through every caller was
rejected: the same gate protects the Confidential flag and the global admin PIN.

### Rule

When a dashboard shows a button, find the server gate behind it and check it accepts the same
people. When adding a gated action, choose `owner_passes` on purpose.

## Lesson 2: "not enabled for your role" was a team setting

`has_feature()` checks `Team.enabled_features` before the role. A non-empty JSON is an allowlist,
so a missing `code_server` key blocked every role on the team while the toast blamed the role.
Read `enabled_features` first when a feature toast appears.

## Lesson 3: a card read a field the API never sent

`SiteDevTab.vue` computed Dev Mode from `doc.developer_mode ?? doc.set_development_mode`. Neither
is a Site field, and the real one, `is_development_site`, was not in `Site.dashboard_fields`. The
card was always "Disabled" and its button could only ever enable. Fix (0.7.9): add the field to
`dashboard_fields`, read it directly.

### Rule

A status shown in the dashboard must come from a field in `dashboard_fields` (or an API that
returns it). Check the field in the network response, not in the DocType.

## Lesson 4: two agent jobs queued together run in parallel

Press queues Update Bench Configuration and Setup Code Server at the same moment, and the agent
runs them on different workers. Setup started code-server before supervisor knew the program
(exit 2), then a second race: it edited `~/.config/code-server/config.yaml` a moment before
code-server had written it (sed exit 2). The plain Start (dashboard Restart) skips the first
start, so the file could never appear. Each failure also stored the new password in the job step.

### Fix

press-agent `agent/code_server.py`: wait up to 300 s for the supervisor program, start once and
wait up to 60 s for `config.yaml` if missing, send the password on stdin, restart. Deployed on u5
(`63bdcf69`), u4, press-f1 (`506ea95e`) and accurate-portainer (`b83650a3`). The dashboard card
now polls while Starting and offers Restart when a code server failed.

### Rule

Never assume two Press jobs for the same bench run in order. A step that needs another job's
result must wait for that result, with a time limit.

## Lesson 5: do not hand a password to a shell command line

The agent logs every step's command, and Press stores failed steps' tracebacks. A password inside
the command ends up in both. Pass secrets on stdin (`execute(..., input=...)`).
