# A long certificate needs a revocation list

## What happened

On 25 Nov 2026 the owner asked for longer SSH access for the team ("Islam's SSH changes every 6 hours"). Press signs
OpenSSH user certificates, and a signed certificate cannot be called back: the bench's sshd checks only the CA's
signature and the expiry date. At 6 hours that gap was small. At 30 days a member taken off the team, or a key a team
admin disabled, would keep SSH for up to a month.

## Root cause

Press had no revocation at all: no KRL, no RevokedKeys line in the bench's sshd_config, and nothing on member removal.
The 6-hour validity was the only limit.

## How we fixed it

0.7.73: 30 days only on development benches, and an every-minute job that writes a RevokedKeys file (plain public
keys) into every Active bench of those groups, then adds the line to that bench's sshd once (`sshd -t`, then a reload).
Proven on Quest Dev with a throwaway key: SSH worked, the key was disabled, the next sync refused the login.

## Lesson

Lengthening any credential's life means building its revocation in the same change: who can lose access, and how fast.

## Prevention

Before raising a validity, write down every way access should end (left the team, disabled user, disabled key, role
changed, team SSH off) and test each one end to end on a real bench. The Press agent reports a non-zero
`docker_execute` exit as status Success, so check `returncode == 0`.
