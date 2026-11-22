# Lessons Learned: 2026-11-22: Watch Tower alert emails were never sent

> On press-ctrl no Watch Tower alert email had ever left the server. Fixed in Press 0.7.39. The hub
> change that cut the volume is Control Center hub 0.2.16.

## What happened

Every send logged `Alert email not sent (SMTP unavailable)` in `logs/watch_tower.log`. At the same time the
rule's alert log said Success and the finding's `alerted` flag was set. Nobody saw the problem because the
Email Queue was empty either way: `press/watch_tower/email_branding.py` sends by direct SMTP on purpose. The
Email Queue once grew to 104K error rows, so the module bypasses it.

## Root cause

Two faults, both in `press/watch_tower/email_branding.py`:

1. **Wrong login.** The direct SMTP login used the Email Account's address. The Brevo relay account has
   `login_id_is_different = 1`, so it logs in with its own login id. Frappe's own queue uses that id, which is why
   every other email on the site worked.
2. **A bad read was cached.** When the Email Account could not be read, a fallback config with an empty password
   was cached in `_smtp_config` for the life of the worker. Every later alert in that worker was unsent.

## How we fixed it

Press 0.7.39:

- Use the login id when the account has one (`login_id_is_different` and `login_id`), else the address.
- Cache only a working config. A failed read returns an empty config and caches nothing.
- Clear the cache after a send failure, so a changed password or login is read again.
- Log why the account could not be read, to `logs/watch_tower.log`.

Verified on press-ctrl with three test emails to the owner:

1. Direct SMTP with the account's login id.
2. Through the fixed `send_alert_email`.
3. From a background worker on the short queue, which is the real path.

The owner confirmed delivery to the inbox.

Hub 0.2.16 also changed the client-finding rule to one summary email per read. Before, about 66 single emails
a day were due, and 82 of 133 were one client's "API key created".

## Lesson

An alert log that says Success and an empty Email Queue do not prove an email went out. For a module that
sends by direct SMTP, the only evidence is `logs/watch_tower.log` and the inbox.

## Prevention

- After any change to alert sending, read `logs/watch_tower.log` and look for `Alert email not sent`.
- Test the worker path, not only a console call: enqueue `press.watch_tower.email_branding.send_alert_email`
  on the short queue and check the inbox.
- Never cache a failed or empty config. A cached failure lasts as long as the worker.
