# Team Onboarding — GitHub Access for Benches

**3-step setup, once per team member. After that, git works automatically in every bench you SSH into.**

---

## Step 1 — Connect your GitHub account to Press (1 minute)

1. Open the Press dashboard:  **https://autodeploypanel.mvpstorm.com/dashboard/settings/developer**
2. Scroll to **GitHub Connection**.
3. Click **Connect GitHub**.
4. GitHub will ask you to authorize the **mvpstorm-deploy** App. Click **Authorize**.
5. You'll land back on the dashboard with a green panel: **"✓ Connected as `<your-github-username>`"**.

Done. You don't need to repeat this for each bench — it's one-per-person, not one-per-bench.

![Developer Settings → GitHub Connection — connected state](#)

---

## Step 2 — First time in a bench: run `bench-git-setup`

Each SSH session asks once for your Press email (so the bench knows which dev you are). After that, git just works.

```bash
# SSH to any bench your team owns
ssh -A bench-0011-NNNNNN-press-f1@press-f1.sandbox.mvpstorm.com -p 2222

# (Don't know the bench name? Check the Press dashboard → Benches → click the bench → SSH Access)

# Inside the bench shell:
bench-git-setup
# First time per session only, it asks:
#   > enter your Press email: 
# Type your email, hit Enter.
# Expected output: "✓ Git configured as <gh-username> — valid ~480 min"
```

If it says **"GitHub not connected"**, go back to Step 1.

---

## Step 3 — Use git normally

```bash
cd ~/frappe-bench/apps/<your-app>

# First time in a bench, if the remote isn't SSH already:
git remote -v                                                         # check current URL
git remote set-url origin https://github.com/Veela-Beauty/<repo>.git  # switch to HTTPS (not git@)

git fetch origin
git pull origin main
git push origin my-branch
```

**All commits are attributed to YOU** — name + email from your Press profile are auto-configured on `git-setup`, so `git log` shows your name just like on your laptop.

---

## FAQ

### Do I need to run `bench-git-setup` every time?

Only once per SSH session. The token is cached in RAM (`/dev/shm`) and wiped when you log out. Next SSH session, run it again.

### Can my token leak?

The token lives only in `/dev/shm/git-creds-<session>` (RAM, not disk) inside the bench container, is 0600 mode, and expires in 8 hours. When you `exit` the SSH session, `~/.bash_logout` wipes it. No disk persistence anywhere.

### What if I forget and already pushed to the wrong branch?

Same as always — use `git push origin :branch` to delete, or `git reset` to rewrite. The token just authenticates; it doesn't change how git works.

### Can I use `git@github.com:...` (SSH) instead of HTTPS?

For Option C, stick with HTTPS. The token Press gives you is HTTPS-based. If you need SSH, that's the `ssh -A` agent-forwarding path (older docs); both work but don't mix them in the same session.

### I want to revoke access to a specific dev (I'm the admin)

Today: have them click **Disconnect** in their Developer settings, OR go to the GitHub App page and revoke their authorization.
Coming soon (T15-T17): one-click revoke from **Settings → Team SSH** in the Press dashboard.

### My token expired mid-session — do I lose work?

No. Just re-run `bench-git-setup` and retry the failed git command. The refresh is invisible — old tokens are auto-swapped for new ones (Frappe cache-locked so 10 devs refreshing simultaneously only hit GitHub once).

### Something's broken — who do I ping?

1. Check the `[bench-git-setup]` output in your shell — it will usually print the reason (`needs_connect`, `refresh_failed`, etc.).
2. If it says "Press API config missing" — the bench container is new and hasn't synced yet; wait 2 minutes and retry.
3. Otherwise, ping @eslam or open a ticket with: the bench name, your Press email, and the exact error text.

---

## For team owners only

- **See who's connected**: (coming soon) **Settings → Team SSH** will show a GitHub Connected column per team member.
- **Revoke a member's GitHub access**: ask them to click Disconnect, OR revoke via the GitHub org admin panel. Auto-revoke-on-removal is pending (T17).
- **Audit log of every token mint**: Frappe desk → `/app/git-credential-session-log` — shows user, bench, timestamp, success/error for every SSH session that touched git. Pruned to last 90 days.

---

## Reference links

- **Full architecture (for developers who want to understand what's happening):** `docs/wiki/03-integrations/github-app-user-tokens.md` in the press repo
- **SRS:** `docs/srs/2026-04-22-option-c-github-app-user-tokens.md`
