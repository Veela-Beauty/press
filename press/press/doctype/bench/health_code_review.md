# Code Health Audit Report
Generated: 2026-04-03

---

## File Inventory

| File | Lines | Status |
|------|-------|--------|
| `dashboard/src/pages/CodeHealth.vue` | 247 | OK |
| `dashboard/src/components/BenchCodeHealth.vue` | 697 | WARNING (3 lines under hard limit) |
| `press/press/doctype/bench/bench_code_health.py` | 400 | OK |
| `press/press/doctype/bench/health_scoring.py` | 101 | OK |
| `press/press/doctype/bench/health_tree.py` | 49 | OK |
| `press/press/doctype/bench/health_inventory.py` | 69 | OK |
| `press/press/doctype/bench/health_analysis.py` | 105 | OK |
| `press/press/doctype/bench/test_health_analysis.py` | 286 | OK |

---

## Functions Over 60 Lines

### BenchCodeHealth.vue

**`renderCirclePack()`** — lines ~542–603 (~62 lines)
Just over the limit. The D3 rendering, tooltip wiring, filter counting, and zoom controls are all bundled here. Decomposable into `_buildHierarchy()`, `_bindTooltip()`, `_bindZoom()`.

**`scan()`** — lines ~505–541 (~37 lines)
Within limit, but noted: two sequential `Promise.all` blocks and a `$nextTick` chain. Not a violation yet, but the next feature added here will push it over.

**`_drawRadar()`** — lines ~683–693 (~11 lines)
Fine.

**`_showSidebar()`** — lines ~633–643 (~11 lines)
Fine. HTML concatenation is inelegant but not a length issue.

No functions over 60 lines in any Python file.

---

## MUST FIX

### [CRITICAL] Security — `health_scoring.py` `score_security()`: unquoted grep arguments (lines 96–97)

```python
r = _exec(bench, f"grep -r -l {keyword} apps/{app}/ --include={glob} 2>/dev/null | wc -l")
```

`keyword` and `glob` are passed without shell-quoting. `keyword` comes from the hardcoded `checks` list, and `app` comes from `_list_apps()` which reads `ls apps/` output from inside a Docker container. If `app` contains a space or shell metacharacter (unlikely in practice but possible with malicious bench names), this is a shell injection vector. The `--include={glob}` is also unquoted, though `glob` is hardcoded.

**Fix:** Quote the interpolated values:
```python
r = _exec(bench, f"grep -r -l '{keyword}' apps/{app!r}/ --include='{glob}' 2>/dev/null | wc -l")
```
Or better, build the `checks` list using already-quoting patterns and ensure `app` is validated as alphanumeric before use.

---

### [CRITICAL] Security — `bench_code_health.py` `get_health_summary()`: unquoted `grep` search patterns (line 216)

```python
sec_r = _exec(bench, "grep -r -l 'api_key\\|password\\|secret_key\\|AKIA\\|ghp_\\|sk-' "
                     "apps/ --include='*.py' 2>/dev/null | "
                     "grep -v node_modules | grep -v __pycache__ | wc -l")
```

This command is a hardcoded string with no user input, so there is no injection risk here directly. However, it is a **false-positive security scanner**: it will flag any `.py` file that contains the *word* `password` — including Frappe's own `password_field`, `update_password`, etc. This inflates `security_alerts` and makes the metric misleading.

**Fix:** Narrow the pattern to detect assignments and string literals:
```bash
grep -r -l "password\s*=\s*['\"][^'\"]\{8,\}" apps/ --include='*.py'
```

---

### [HIGH] Security — `health_analysis.py` `analyze_app_code()`: no URL validation before passing to external service (line 83)

```python
data = _call_analysis_service(git_url, commit_hash, config)
```

`git_url` is stripped and checked for emptiness (lines 57–62), but there is no SSRF guard. A System Manager can supply `http://169.254.169.254/latest/meta-data/` (AWS metadata endpoint) or `http://localhost:5000/internal-admin` and the Press server will fetch it via `requests.post`. The `only_for("System Manager")` check reduces but does not eliminate the risk (internal users can still trigger SSRF).

**Fix:** Validate `git_url` against an allowlist of schemes and hostnames before calling the service:
```python
from urllib.parse import urlparse
parsed = urlparse(git_url)
if parsed.scheme not in ("https", "git") or not parsed.hostname:
    return {"error": "Invalid or disallowed git URL"}
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "169.254.169.254", "::1", "[::1]"}
if parsed.hostname in BLOCKED_HOSTS:
    return {"error": "Disallowed host"}
```

---

### [HIGH] File Size — `BenchCodeHealth.vue`: 697 lines (3 lines under hard limit)

This file is effectively at the hard limit. It contains a full Vue component with D3 circle-packing, radar chart rendering, 8-tab data management, and deep analysis logic. Any small addition will trigger a forced split.

**Action required now (before next PR):** Extract D3 rendering into a composable or separate file:
- `useBenchCirclePack.js` — D3 pack init, zoom, filter, sidebar (~120 lines)
- `useBenchRadar.js` — radar draw logic (~50 lines)
- `BenchCodeHealth.vue` drops to ~520 lines (still in warning zone, but safe from the hard limit)

---

### [HIGH] Anti-pattern — `bench_code_health.py` `scan_bench_health()`: shell command uses `app_filter` without sanitization (lines 164–173)

```python
filter_path = f"apps/{app_filter}" if app_filter else "apps"
cmd = f"find {filter_path} -type f ..."
```

`app_filter` is a `@whitelist` parameter directly concatenated into a shell `find` command executed inside a Docker container. A malicious `app_filter` value like `apps; rm -rf /` would be executed. The `frappe.only_for("System Manager")` reduces but does not eliminate this — a compromised admin account would have arbitrary command execution.

**Fix:** Validate `app_filter` against the known apps list before use:
```python
if app_filter:
    allowed = _list_apps(bench)
    if app_filter not in allowed:
        frappe.throw("Invalid app filter")
    filter_path = f"apps/{app_filter}"
```

---

## SHOULD FIX

### [MEDIUM] Anti-pattern — `health_inventory.py` `scan_app_interactions()` and `scan_scripts_inventory()`: duplicate `ls apps/` call

Both functions independently run `_exec(bench, "ls apps/")` (lines 13 and 47). Each call is a separate `docker exec` — two round trips. The callers in `bench_code_health.py` already have `_list_apps(bench)` available. The `bench` object could carry the app list, or both functions should accept an `apps` parameter.

**Fix:** Add an `apps=None` parameter to both functions and pass the pre-fetched list from the caller.

---

### [MEDIUM] Performance — `BenchCodeHealth.vue` `scanAll()` (CodeHealth.vue lines 231–243): sequential scans

```javascript
for (const b of this.benches) {
    const summary = await call(`${API}.get_health_summary`, { bench_name: b.name });
    ...
}
```

Scans run one bench at a time. For 20 benches this is 20 sequential `docker exec` round trips. The UI already shows `scanningAllBench` progress, so the sequential approach is intentional for UX feedback — but it is slow.

**Fix (optional):** Use a concurrency-limited queue (e.g., 3 simultaneous) instead of fully sequential. Low priority if bench count is small.

---

### [MEDIUM] Anti-pattern — `BenchCodeHealth.vue`: internal state stored as `_` prefixed data properties

```javascript
_focus: null, _packed: null, _view: null, _els: null, _leaves: null,
```

These are declared as reactive Vue data but are never rendered. D3 state does not need reactivity — making it reactive adds overhead and can cause unexpected re-renders if Vue's proxy wraps D3 objects.

**Fix:** Move these to `created()` as plain instance properties:
```javascript
created() {
    this._focus = null; this._packed = null; // etc.
}
```

---

### [MEDIUM] Correctness — `health_scoring.py` `score_clean()`: penalty formula can produce negative scores for large apps

```python
return max(0, min(round(under / len(nums) * 100) - over * 2, 100))
```

`over * 2` is subtracted from the percentage but `over` is an absolute count, not a fraction. A 1000-file app with 10 violations scores `98 - 20 = 78` while a 50-file app with 10 violations scores `80 - 20 = 60`. The penalty is disproportionately large for small apps.

**Fix:** Normalize the penalty relative to total files:
```python
penalty = round(over / len(nums) * 100) * 2
return max(0, min(round(under / len(nums) * 100) - penalty, 100))
```

---

### [MEDIUM] Correctness — `bench_code_health.py` `list_bench_health()`: compliance_pct display bug in `CodeHealth.vue` (line 160 of BenchCodeHealth.vue)

```html
{{ b.health.compliance_pct || '---' }}%
```

If `compliance_pct` is `0`, this renders `---` instead of `0%`. Using `|| '---'` treats falsy zero the same as null/undefined.

**Fix:**
```html
{{ b.health.compliance_pct != null ? b.health.compliance_pct : '---' }}%
```

---

### [LOW] Missing i18n — `BenchCodeHealth.vue` and `CodeHealth.vue`: user-facing strings not wrapped in `__()`

Strings like `'Not scanned yet'`, `'Scanning…'`, `'No scan data yet'`, `'All clear'`, `'Run scan first'` are bare English strings rendered directly in the template. Per project conventions, all user-facing strings must use `__()`.

**Fix:** Wrap all static UI strings in `__()`. Example:
```html
{{ scanning ? __('Scanning…') : __('⟳ Scan Now') }}
```

---

### [LOW] Correctness — `test_health_analysis.py`: `test_requires_system_manager` mutates shared stub and may not restore on failure (lines 72–75)

```python
_frappe_stub.only_for = MagicMock(side_effect=Exception("Not permitted"))
with self.assertRaises(Exception):
    _ha.analyze_app_code(...)
_frappe_stub.only_for = MagicMock()  # restore
```

If `analyze_app_code` does not raise (test logic error) or raises for the wrong reason, the restore line on the last line still runs. However if the `assertRaises` context itself raises unexpectedly the stub is left in broken state, polluting subsequent tests.

**Fix:** Use `addCleanup` or a `try/finally`:
```python
original = _frappe_stub.only_for
self.addCleanup(setattr, _frappe_stub, 'only_for', original)
```

---

## NICE TO HAVE

- **`health_analysis.py` line 85**: `except Exception as e: return {"error": str(e)}` swallows all errors including programming mistakes. Consider logging before returning: `frappe.log_error(str(e), "Code Analysis Service Error")`.

- **`BenchCodeHealth.vue` `_showSidebar()`**: innerHTML is built via string concatenation with `d.data.name` and `d.data.lines` injected directly. These values come from Docker container output and could contain `<script>` or other HTML if a file was named maliciously. Use DOM APIs or a sanitization step instead.

- **`bench_code_health.py` `list_bench_health()`**: the `import json` at line 133 is inside a loop. Move it to the top of the function or module level.

- **`BenchCodeHealth.vue` `deepApps` computed**: filters `stackInfo` by `a.repository || a.commit_hash`. Any app with a commit hash but no GitHub remote will appear in the Deep Analysis tab but fail when clicked (no git URL → error shown). Either filter by `a.repository` only, or show a tooltip explaining why some apps are disabled.

---

## Summary by Severity

| Severity | Count | Files |
|----------|-------|-------|
| CRITICAL | 2 | `health_scoring.py`, `bench_code_health.py` |
| HIGH | 3 | `health_analysis.py`, `BenchCodeHealth.vue`, `bench_code_health.py` |
| MEDIUM | 5 | `health_inventory.py`, `CodeHealth.vue`, `BenchCodeHealth.vue`, `health_scoring.py` |
| LOW | 2 | `BenchCodeHealth.vue`, `CodeHealth.vue`, `test_health_analysis.py` |
| NICE TO HAVE | 4 | various |

## Verdict

**NEEDS CHANGES** — two critical shell injection risks and one SSRF risk must be fixed before this code handles production traffic. The file size issue in `BenchCodeHealth.vue` must be resolved before any further additions to that file.
