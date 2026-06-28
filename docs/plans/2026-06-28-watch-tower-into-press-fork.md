# Watch Tower → Press Fork (sole owner) + Uninstall Tamkeen - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the Watch Tower subsystem from `tamkeen_suite_app` into the **Press fork** (`press`, our `Veela-Beauty/press` fork) as a self-contained, license-free module, make press the sole owner on the control room (`demo.mvpstorm.com`), then **uninstall tamkeen entirely** - with no control-room outage and no loss of the 20 rules.

**Architecture:** Build `press/watch_tower/` in the dev-box `press_local` checkout (copied from tamkeen's current copy, de-coupled from tamkeen's licensing) → push to github → rsync the module onto press-ctrl's `apps/press` + surgically add it to press's `modules.txt` and `scheduler_events` → flip `Module Def "Watch Tower"` owner tamkeen→press + repoint the 18 rules → strip watch_tower from tamkeen → `bench migrate` → `uninstall-app tamkeen_suite_app`. Doctype JSON is unchanged (module stays `Watch Tower`), so the rules' data is preserved throughout.

**Tech Stack:** Frappe (Python), MariaDB, Frappe Bench, supervisor, SSH (`press-ctrl`), git, rsync.

---

## Definition of Done

- [ ] `Module Def "Watch Tower".app_name == "press"`
- [ ] All 18 method rules' `condition_method` start with `press.watch_tower.` (0 tamkeen, 0 FTS)
- [ ] `press/watch_tower/` exists on the bench, in `modules.txt`, with NO `from tamkeen_suite_app import` anywhere
- [ ] press `scheduler_events` runs `press.watch_tower.jobs.run_hourly_watch_tower` (registered, `stopped=0`)
- [ ] 20 `Watch Tower Rules` rows preserved; 3 new rules execute Success/No Matches via `press.watch_tower.engine.evaluate_rule`
- [ ] `tamkeen_suite_app` uninstalled from `demo.mvpstorm.com` (not in `frappe.get_installed_apps()`); its app_include_js gone from the desk
- [ ] Control room `https://autodeploypanel.mvpstorm.com/dashboard` returns 200 throughout
- [ ] `press_local` pushed to `Veela-Beauty/press`; tamkeen watch_tower removal committed

## Established facts (verified 2026-06-28)

- Bench `/home/frappe/frappe-bench`, site `demo.mvpstorm.com`, SSH `press-ctrl`.
- Current owner = tamkeen: `Module Def "Watch Tower".app_name = tamkeen_suite_app`; 20 rules, 18 with `condition_method LIKE 'tamkeen_suite_app.watch_tower.%'`; 6 tamkeen scheduler jobs.
- press_local: dev box `/home/eslam/data/erpnext-app-repos/press_local`, branch `cloudflare-dns`, push remote `git@github.com:Veela-Beauty/press.git`. Package `press_local/press/`; modules live at `press/<module>/` (e.g. `press/infrastructure/`, `press/incident_management/`). `modules.txt` at `press/modules.txt`; `scheduler_events` dict at `press/hooks.py:221`.
- press-ctrl `apps/press`: branch `cloudflare-dns`, remotes `govbundle` (/tmp bundle) + `upstream` (`accurate-systems/press`) - a DIFFERENT org than the dev-box push remote, so deploy is by **rsync of the module dir**, not git pull. Tree has ~11 unrelated dirty files - stage explicit paths only.
- Source module = tamkeen's current copy `tamkeen_suite_app/tamkeen_suite_app/watch_tower/` (11 .py modules + `alerts/` + `doctype/` for the 4 doctypes). Doctype `module` field = `Watch Tower` (unchanged by the move).
- **Tamkeen coupling to remove (the new work):**
  - `from tamkeen_suite_app import licensing` in `jobs.py:13`, `engine.py:12`, `doctype/watch_tower_rules/watch_tower_rules.py:7`.
  - Uses: `licensing.is_allowed("watch_tower")` (jobs.py:23,32,42) + `@licensing.gated("watch_tower")` (engine.py:450; watch_tower_rules.py:107,132,167,182).
  - Hardcoded enqueue paths `"tamkeen_suite_app.watch_tower.engine.evaluate_rule"` (engine.py:518; watch_tower_rules.py:114).
- Tamkeen data on the control room = **0 rows** in every tamkeen doctype (Business Flow, stepper, impersonation, GL rule, etc.) → uninstall drops nothing real.
- `bench backup` is broken on press-ctrl - use manual `mysqldump | gzip` for backups.

---

## Task 1: Backup + pre-flight (reversible, no changes)

**Files:** backup artifacts on the bench.

- [ ] **Step 1: manual full DB backup (bench backup is broken) + WT data export + tar tamkeen's watch_tower**

```bash
ssh press-ctrl 'cd /home/frappe/frappe-bench
read DB PW < <(python3 -c "import json;c=json.load(open(\"sites/demo.mvpstorm.com/site_config.json\"));print(c[\"db_name\"], c[\"db_password\"])")
mkdir -p /home/frappe/wt-press-backups; ts=$(date +%s)
mysqldump -u "$DB" -p"$PW" -h 127.0.0.1 --single-transaction --quick --no-tablespaces --routines "$DB" 2>/dev/null | gzip > /home/frappe/wt-press-backups/demo_$ts.sql.gz
gzip -t /home/frappe/wt-press-backups/demo_$ts.sql.gz && echo GZIP_OK
for dt in "Watch Tower Rules" "Watch Tower Alert Log" "Watch Tower Email Recipient" "Watch Tower Rule Action"; do
  bench --site demo.mvpstorm.com export-json "$dt" "/home/frappe/wt-press-backups/${dt// /_}_$ts.json"; done
tar czf /home/frappe/wt-press-backups/tamkeen_watch_tower_$ts.tar.gz -C apps/tamkeen_suite_app/tamkeen_suite_app watch_tower
ls -la /home/frappe/wt-press-backups/'
```
Expected: `GZIP_OK`, the json exports, and the tar listed.

- [ ] **Step 2: record baseline**

```bash
ssh press-ctrl 'cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com mariadb -N -e "SELECT (SELECT COUNT(*) FROM \`tabWatch Tower Rules\`), (SELECT app_name FROM \`tabModule Def\` WHERE name=\"Watch Tower\");"'
```
Expected: `20  tamkeen_suite_app`. Record `RULES_N=20`.

---

## Task 2: Build the de-coupled module in press_local (dev box)

**Files:**
- Create: `press_local/press/watch_tower/` (copied from tamkeen)
- Create: `press_local/press/watch_tower/_nolicense.py`
- Modify: `press_local/press/watch_tower/{jobs.py,engine.py,doctype/watch_tower_rules/watch_tower_rules.py}`
- Modify: `press_local/press/modules.txt`, `press_local/press/hooks.py`

- [ ] **Step 1: copy tamkeen's watch_tower into press_local**

```bash
rsync -a --exclude '__pycache__' --exclude '*.pyc' \
  /home/eslam/data/erpnext-app-repos/tamkeen_suite_app/tamkeen_suite_app/watch_tower/ \
  /home/eslam/data/erpnext-app-repos/press_local/press/watch_tower/
```

- [ ] **Step 2: add the no-op license shim** - create `press_local/press/watch_tower/_nolicense.py`:

```python
"""No-op license shim. Watch Tower is Press control-plane infra (our own), not a
licensed client product, so every feature is always allowed and gates are pass-through."""


def is_allowed(feature=None):
	return True


def require(feature=None):
	return True


def gated(feature=None):
	def deco(fn):
		return fn
	return deco
```

- [ ] **Step 3: rewrite the 3 licensing imports** - in each of `press_local/press/watch_tower/jobs.py`, `.../engine.py`, `.../doctype/watch_tower_rules/watch_tower_rules.py`, replace the line `from tamkeen_suite_app import licensing` with:

```python
from press.watch_tower import _nolicense as licensing
```

- [ ] **Step 4: fix the 2 hardcoded enqueue paths** - in `press_local/press/watch_tower/engine.py` and `.../doctype/watch_tower_rules/watch_tower_rules.py`, replace `"tamkeen_suite_app.watch_tower.engine.evaluate_rule"` with `"press.watch_tower.engine.evaluate_rule"`.

- [ ] **Step 5: verify zero tamkeen references remain + compiles**

```bash
cd /home/eslam/data/erpnext-app-repos/press_local
grep -rn "tamkeen_suite_app\|frappe_theme_switcher" press/watch_tower --include="*.py" | grep -v __pycache__
python3 -m compileall -q press/watch_tower && echo COMPILE_OK
```
Expected: grep prints NOTHING; `COMPILE_OK`.

- [ ] **Step 6: register the module in press modules.txt** - append a line `Watch Tower` to `press_local/press/modules.txt` (after `Incident Management`).

- [ ] **Step 7: merge the 6 scheduler events into press hooks.py** - in `press_local/press/hooks.py`, inside the existing `scheduler_events` dict (line ~221), add to the matching `"hourly"`, `"daily"`, `"weekly"` lists:

```python
		"press.watch_tower.jobs.run_hourly_watch_tower",            # -> hourly
		"press.watch_tower.jobs.run_daily_watch_tower",             # -> daily
		"press.watch_tower.press_alerts.cleanup_old_error_logs",    # -> daily
		"press.watch_tower.site_activity_sync.sync_site_activity",  # -> daily
		"press.watch_tower.site_lifecycle.run_site_lifecycle",      # -> daily
		"press.watch_tower.jobs.run_weekly_watch_tower",            # -> weekly
```
(The two Site-dependent daily jobs already self-skip via `frappe.db.exists("DocType","Site")`; press HAS Site, so they run.)

- [ ] **Step 8: compile hooks + commit + push press_local**

```bash
cd /home/eslam/data/erpnext-app-repos/press_local
python3 -m py_compile press/hooks.py && echo HOOKS_OK
git add press/watch_tower press/modules.txt press/hooks.py
git -c user.name="Sanad Agent" -c user.email="agent@sanad" commit -m "feat(watch-tower): add Watch Tower module to the Press fork (de-coupled from tamkeen)

Press-infra alerting now lives in press/watch_tower/ (was tamkeen_suite_app). Removed the
tamkeen licensing dependency via a no-op shim (press infra is unlicensed); fixed enqueue
paths to press.watch_tower.engine.evaluate_rule; registered the module + 6 scheduler jobs.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
git push origin HEAD && git log -1 --oneline
```
Expected: `HOOKS_OK`, pushed.

---

## Task 3: Deploy the module onto press-ctrl (additive, no cutover yet)

**Files:** new `apps/press/press/watch_tower/` on the bench; press `modules.txt` + `hooks.py` (bench-local edits).

- [ ] **Step 1: rsync ONLY the module dir onto the bench** (don't touch press's dirty tree)

```bash
rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' \
  /home/eslam/data/erpnext-app-repos/press_local/press/watch_tower/ \
  press-ctrl:/home/frappe/frappe-bench/apps/press/press/watch_tower/
ssh press-ctrl 'chown -R frappe:frappe /home/frappe/frappe-bench/apps/press/press/watch_tower'
```

- [ ] **Step 2: add `Watch Tower` to the bench's press modules.txt**

```bash
ssh press-ctrl 'cd /home/frappe/frappe-bench/apps/press/press
grep -qx "Watch Tower" modules.txt || printf "\nWatch Tower\n" >> modules.txt
tail -3 modules.txt'
```

- [ ] **Step 3: merge the 6 scheduler events into the bench's press hooks.py** - apply the SAME edit as Task 2 Step 7 to `apps/press/press/hooks.py` on the bench (add the 6 lines to the existing scheduler_events hourly/daily/weekly lists). Verify:

```bash
ssh press-ctrl 'grep -c "press.watch_tower" /home/frappe/frappe-bench/apps/press/press/hooks.py'
```
Expected: `6`.

- [ ] **Step 4: confirm importable on the bench (no cutover yet)**

```bash
ssh press-ctrl 'cd /home/frappe/frappe-bench && ./env/bin/python -c "import press.watch_tower.press_alerts as p; print(\"IMPORT_OK\", hasattr(p,\"check_scheduled_job_failures\"))"'
```
Expected: `IMPORT_OK True`.

---

## Task 4: Cutover - flip ownership + repoint rules (the irreversible bit)

**Files:** DB metadata + tamkeen code (bench-local).

- [ ] **Step 1: set Module Def owner press (its folder exists now)**

```bash
ssh press-ctrl 'cd /home/frappe/frappe-bench
bench --site demo.mvpstorm.com mariadb -e "UPDATE \`tabModule Def\` SET app_name=\"press\" WHERE name=\"Watch Tower\";"
bench --site demo.mvpstorm.com clear-cache
bench --site demo.mvpstorm.com execute frappe.get_module_path --kwargs "{\"module\":\"Watch Tower\"}"'
```
Expected: path resolves to `.../apps/press/press/watch_tower`.

- [ ] **Step 2: repoint the 18 rules tamkeen→press**

```bash
ssh press-ctrl 'cd /home/frappe/frappe-bench
bench --site demo.mvpstorm.com mariadb -e "SET SQL_SAFE_UPDATES=0; UPDATE \`tabWatch Tower Rules\` SET condition_method=REPLACE(condition_method,\"tamkeen_suite_app.watch_tower.\",\"press.watch_tower.\") WHERE condition_method LIKE \"tamkeen_suite_app.watch_tower.%\";"
bench --site demo.mvpstorm.com mariadb -N -e "SELECT SUM(condition_method LIKE \"tamkeen%\"), SUM(condition_method LIKE \"press.watch_tower%\") FROM \`tabWatch Tower Rules\`;"'
```
Expected: `0   18`.

- [ ] **Step 3: strip watch_tower from tamkeen** (folder + modules.txt + the 6 scheduler events from tamkeen hooks) so tamkeen no longer claims the module before uninstall. On the bench:

```bash
ssh press-ctrl 'cd /home/frappe/frappe-bench/apps/tamkeen_suite_app/tamkeen_suite_app
python3 -c "import re;p=\"hooks.py\";s=open(p).read();s=re.sub(r\"scheduler_events = \{.*?\n\}\",\"scheduler_events = {}\",s,1,flags=re.DOTALL);open(p,\"w\").write(s)"
grep -vx "Watch Tower" modules.txt > m.new && mv m.new modules.txt
rm -rf watch_tower
cd /home/frappe/frappe-bench && ./env/bin/python -c "import tamkeen_suite_app.hooks; print(\"TAM_HOOKS_OK\")"'
```
Expected: `TAM_HOOKS_OK` (tamkeen imports clean without watch_tower).

Also apply the same removal in the dev-box tamkeen repo + commit/push (durability):
```bash
cd /home/eslam/data/erpnext-app-repos/tamkeen_suite_app
git rm -r tamkeen_suite_app/watch_tower; # edit hooks.py scheduler_events -> {} ; remove Watch Tower from modules.txt
git -c user.name="Sanad Agent" -c user.email="agent@sanad" commit -am "refactor(watch-tower): remove module - ownership moved to the press fork"
git push origin HEAD
```

---

## Task 5: Migrate (settle hooks + scheduler jobs)

- [ ] **Step 1: migrate** (rebuilds the app_hooks cache that clear-cache won't, registers press's WT jobs, deregisters tamkeen's)

```bash
ssh press-ctrl 'cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com migrate --skip-failing 2>&1 | tail -8'
```
Expected: completes, `Updating Dashboard for press ... tamkeen_suite_app`, no traceback.

- [ ] **Step 2: confirm press WT jobs registered, tamkeen WT jobs gone**

```bash
ssh press-ctrl 'cd /home/frappe/frappe-bench
bench --site demo.mvpstorm.com mariadb -N -e "SELECT CONCAT(\"press=\",(SELECT COUNT(*) FROM \`tabScheduled Job Type\` WHERE method LIKE \"press.watch_tower%\"),\" tamkeen=\",(SELECT COUNT(*) FROM \`tabScheduled Job Type\` WHERE method LIKE \"tamkeen_suite_app.watch_tower%\"));"'
```
Expected: `press=6 tamkeen=0`.

- [ ] **Step 3: control-room restart + smoke** (workers reload; a 500 here = stale workers, same as before)

```bash
ssh press-ctrl 'cd /home/frappe/frappe-bench && bench restart >/dev/null 2>&1; sleep 5; curl -s -o /dev/null -w "dashboard=%{http_code}\n" https://autodeploypanel.mvpstorm.com/dashboard'
```
Expected: `dashboard=200` (if 500, wait + re-curl; restart can lag).

---

## Task 6: Uninstall tamkeen from the control room

**Files:** none - drops tamkeen's (empty) doctypes.

- [ ] **Step 1: re-confirm tamkeen has no data + no longer owns Watch Tower**

```bash
ssh press-ctrl 'cd /home/frappe/frappe-bench
bench --site demo.mvpstorm.com mariadb -N -e "SELECT app_name FROM \`tabModule Def\` WHERE name=\"Watch Tower\";"
for t in "Business Flow" "Tamkeen Impersonation Session" "Action Center Drawer Config"; do echo -n "$t="; bench --site demo.mvpstorm.com mariadb -N -e "SELECT COUNT(*) FROM \`tab$t\`;" 2>/dev/null; done'
```
Expected: `press`, and all counts `0`. If Module Def is not `press`, STOP.

- [ ] **Step 2: uninstall tamkeen** (no backup needed - Task 1 has the dump; tamkeen data is empty)

```bash
ssh press-ctrl 'cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com uninstall-app tamkeen_suite_app --no-backup --yes 2>&1 | tail -15'
```
Expected: removes tamkeen's doctypes/modules; NO mention of removing `Watch Tower` doctypes (press owns them now). If it tries to drop `Watch Tower Rules`, STOP and restore.

- [ ] **Step 3: drop tamkeen from the bench (apps.txt + pip) + restart**

```bash
ssh press-ctrl 'cd /home/frappe/frappe-bench
grep -vx tamkeen_suite_app sites/apps.txt > a.new && mv a.new sites/apps.txt
./env/bin/pip uninstall -y tamkeen_suite_app 2>&1 | tail -1
bench restart >/dev/null 2>&1; sleep 5
bench --site demo.mvpstorm.com execute frappe.get_installed_apps 2>&1 | tail -1'
```
Expected: `tamkeen_suite_app` NOT in the installed-apps list.

---

## Task 7: End-to-end verification

- [ ] **Step 1: rules intact + owned by press + resolve**

```bash
ssh press-ctrl 'cd /home/frappe/frappe-bench
bench --site demo.mvpstorm.com mariadb -N -e "SELECT (SELECT COUNT(*) FROM \`tabWatch Tower Rules\`), (SELECT app_name FROM \`tabModule Def\` WHERE name=\"Watch Tower\"), (SELECT SUM(condition_method LIKE \"press.watch_tower%\") FROM \`tabWatch Tower Rules\`);"'
```
Expected: `20  press  18`.

- [ ] **Step 2: execute the 3 new rules via press engine**

```bash
ssh press-ctrl 'cd /home/frappe/frappe-bench
for R in WT-RULE-31215 WT-RULE-31216 WT-RULE-31217; do
  bench --site demo.mvpstorm.com execute press.watch_tower.engine.evaluate_rule --kwargs "{\"rule_name\":\"$R\",\"triggered_by\":\"PressVerify\"}" 2>&1 | grep -oE "\"status\": \"[A-Za-z /]+\"" | head -1 | sed "s/^/$R /"; done'
```
Expected: each prints Success / No Matches (no Traceback/AttributeError).

- [ ] **Step 3: control room + desk smoke**

```bash
ssh press-ctrl 'curl -s -o /dev/null -w "dash=%{http_code}\n" https://autodeploypanel.mvpstorm.com/dashboard; curl -s -o /dev/null -w "app=%{http_code}\n" https://autodeploypanel.mvpstorm.com/app'
```
Expected: `dash=200`, `app=200|301`.

---

## Task 8: Docs + memory

- [ ] Update memory `watch-tower-press-alerting-2026-06-28.md`: owner now `press` (fork `Veela-Beauty/press`), de-coupled from tamkeen via `_nolicense` shim, tamkeen uninstalled. Update condition_method examples to `press.watch_tower.*`.
- [ ] Tick this plan's DoD + write a Resume block. Mark the prior tamkeen-consolidation plan superseded.
- [ ] CHANGELOG entries on press_local + tamkeen.

---

## Rollback (per phase)

- **Before Task 4:** nothing live changed - just `rm -rf apps/press/press/watch_tower`, revert the bench press modules.txt/hooks.py edits, `bench restart`.
- **After Task 4/5 (cutover):** repoint rules back (`press.watch_tower.` → `tamkeen_suite_app.watch_tower.`), restore tamkeen's watch_tower from the Task 1 tar, set Module Def app_name back to `tamkeen_suite_app`, `bench migrate`, `bench restart`.
- **After Task 6 (tamkeen uninstalled):** re-install tamkeen (`bench install-app tamkeen_suite_app --force`) from the bench copy, then the above. Or nuclear: `bench --site demo.mvpstorm.com restore <Task-1 dump>`.

## Decisions

### 2026-06-28: Move to the Press fork + uninstall tamkeen
Watch Tower is Press-infra monitoring (it reads Site / Deploy Candidate Build / TLS Certificate and sits beside press's `Infrastructure` + `Incident Management` modules), so the Press fork is its correct, github-durable home. Moving here also lets us uninstall tamkeen (a client suite) from the control room, removing ~15 empty doctypes + its desk `app_include_js`. The tamkeen licensing gate is dropped (press infra is unlicensed) via a no-op `_nolicense` shim, keeping all 9 call sites working with minimal edits.

## Resume here (2026-06-28)
- Status: PLAN WRITTEN, not started. Supersedes the tamkeen-consolidation plan (that move is done; this relocates it to press + uninstalls tamkeen).
- Next up: Task 1 (backup + pre-flight).
