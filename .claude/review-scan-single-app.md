## Summary

The per-app incremental scan feature is mostly correct and well-structured, but has one high-severity performance issue (redundant `_get_app_commits` per call), one medium-severity Vue reactivity risk (spread pattern on large arrays in a loop), and two test coverage gaps worth noting.

---

## Issues

- **[HIGH] Performance — bench_code_health.py, line 460**: `_get_app_commits` runs a `docker exec` command on every `scan_single_app` call. When the frontend calls this function for each of the 9 apps in a loop (both in `scan()` and `loadCachedData`), that is 9 separate `docker exec` shell-outs just to get commit hashes — before any scoring begins. If caching is warm this is cheap, but on a cold run or after a commit, all 9 calls pay this cost individually.
  **Fix**: Accept an optional `commit` parameter from the caller, or implement a short-lived (30s) Redis cache keyed only to `bench_name` for the commits map. The frontend already knows the app name; the backend could expose a `get_app_commits` endpoint that the frontend calls once and passes results into each `scan_single_app` call.

- **[MEDIUM] Performance/Reactivity — BenchCodeHealth.vue, lines 557, 597**: The spread pattern `this.appScores = [...this.appScores, ...]` is used inside a loop. For 9 apps this allocates a new array 9 times. Vue 3's reactivity handles this correctly, but a simple `.push()` call also triggers reactivity on a reactive array and is O(1) instead of O(n). At 9 apps the difference is negligible, but if the bench ever has 20-30 apps this will generate measurable GC pressure during the scan loop.
  **Fix**: Replace `this.appScores = [...this.appScores, { ... }]` with `this.appScores.push({ ... })` and same for `this.compliance`. Both are declared as reactive refs/data; `.push()` triggers Vue's reactive interceptor.

- **[MEDIUM] Correctness — BenchCodeHealth.vue, line 545**: `triggerD3()` is called once after `loadAppScores()` completes in `loadCachedData()`. Since `loadAppScores` loads results one-by-one sequentially, D3 only renders after all apps finish loading. This is inconsistent with the `scan()` path where `triggerD3()` is called after each individual app. The cache-warm path will show a blank chart for longer than necessary if the bench has many apps.
  **Fix**: Move `triggerD3()` inside the per-app loop in `loadAppScores()`, or accept a callback parameter so `loadCachedData` controls when to trigger.

- **[LOW] Correctness — bench_code_health.py, line 481**: The `overall` score averages values by excluding the key `"app"`. This relies on the dict iteration order being exactly 8 numeric keys plus `"app"`. If a future scorer accidentally adds a second non-numeric key (e.g. a label or metadata field), the denominator stays hardcoded at `8` while the actual sum changes, silently producing wrong averages.
  **Fix**: Sum values explicitly: `sum(scores[k] for k in ("claude_md","readme","documentation","tests","clean_code","code_patterns","lessons","security")) / 8`. This is self-documenting and immune to future dict changes.

- **[LOW] Tests — test_scan_single_app.py**: Two gaps in coverage:
  1. No test for the case where `app_name` is not found in `commits` (i.e. `commit = ""`). The code skips caching silently when commit is empty — a test confirming `_set_cached` is NOT called (and no exception is raised) would pin this behavior.
  2. No test verifying that `_get_app_commits` is called exactly once per `scan_single_app` call (not zero, not more). Given the HIGH issue above, a test using `mock_commits.assert_called_once()` would catch any future refactor that accidentally calls it in a loop.

---

## Verdict

PASS WITH NOTES — no blocking correctness or security issues. The `_safe()` guard on line 458 correctly validates `app_name` before shell interpolation, and `frappe.only_for` is present. The HIGH performance issue should be addressed before this goes to a bench with 10+ apps, but it will not cause incorrect behavior in the current form.
