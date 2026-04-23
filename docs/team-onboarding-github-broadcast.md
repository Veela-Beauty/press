# Team Broadcast — `git pull`/`git push` inside benches

Short version (paste into Slack / email / whatever):

---

## 🚀 Quick version (copy/paste this)

> **Heads-up team:** `git pull` / `git push` inside any Press bench now works with your own GitHub identity. One-time setup, 60 seconds:
>
> 1. Go to **https://autodeploypanel.mvpstorm.com/dashboard/settings/developer**
> 2. Click **Connect GitHub** → authorize `mvpstorm-deploy` → done.
> 3. Next time you SSH into a bench: run `bench-git-setup`, enter your Press email once, and git works. Commits show your name.
>
> Full guide: `docs/team-onboarding-github.md` in the press repo. Problems? Ping @eslam.

---

## Long version (for the README / wiki / announcements channel)

> **New — GitHub in Bench, the proper way**
>
> We finally killed "enter your password", "copy this SSH key", and "git credential manager" inside bench containers. Here's what changed:
>
> **What you do once (per person, ~60 s):**
> - Open https://autodeploypanel.mvpstorm.com/dashboard/settings/developer
> - Click **Connect GitHub** (new green section on that page)
> - Authorize `mvpstorm-deploy` when GitHub asks.
> - You'll see "✓ Connected as `<your-username>`". Done.
>
> **What you do every SSH session (~5 s):**
> - SSH into the bench as normal.
> - Run `bench-git-setup` — it asks once for your Press email, then configures git.
> - `git pull`, `git push`, `git fetch` work with your identity. Commits show your name + email.
>
> **What we got rid of:**
> - ❌ Storing SSH keys inside bench containers
> - ❌ Deploy keys (the GitHub org blocks them anyway)
> - ❌ Shared PATs in `.git/config`
> - ❌ Copy-pasting long tokens on every login
>
> **Security highlights:**
> - Tokens are 8 h, stored in RAM-only (`/dev/shm`), wiped on SSH logout
> - All commits attributed to the real dev's GitHub account
> - Admins can disconnect any dev from Settings → Developer on their side, or via GitHub org
> - 14 automated unit tests cover the boundary
>
> **Docs:**
> - User guide: `docs/team-onboarding-github.md`
> - Architecture: `docs/wiki/03-integrations/github-app-user-tokens.md`
> - If it breaks: output of `bench-git-setup` tells you what's wrong. Ping @eslam with that + bench name.
>
> **Owners only** (team admins): Audit log at `/app/git-credential-session-log` shows every token mint with user + bench + timestamp. Kept 90 days.

---

## Tiny version (for a DM)

> `git` inside benches now works with your own GitHub. One-time: Press dashboard → Settings → Developer → Connect GitHub. Then in bench: `bench-git-setup`. That's it.

---

**Note to self** — follow up when T15-T17 ships:
> **Update**: Team SSH tab now also shows a "GitHub Connected" column per member. Owners can disable/revoke any member's GitHub access from there directly.
