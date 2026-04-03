## Summary

The Code Health module is well-structured with a clean stub/sibling pattern, but contains several
shell-injection vectors in scoring functions, a critical unescaped HTML sink in the deep-analysis
tab, N+1 docker calls across every tab, and a few correctness gaps in scoring math and tree
building.

---

## Issues

### SECURITY

- **[severity: critical]** security — **health_scoring.py:99 — Shell injection in `score_security`**
  The `keyword` and `glob` values are interpolated directly into the shell command without quoting:
  ```python
  r = _exec(bench, f"grep -r -l {keyword} apps/{app}/ --include={glob} 2>/dev/null | wc -l")
  ```
  `keyword` comes from the hardcoded `checks` list so the immediate risk is low, but the pattern is
  wrong. If the list is ever modified or a value is sourced dynamically, this becomes a full command
  injection. Quote both:
  ```python
  r = _exec(bench, f"grep -r -l '{keyword}' apps/{app}/ --include='{glob}' 2>/dev/null | wc -l")
  ```

- **[severity: critical]** security — **health_scoring.py:40 — Missing `_safe` on `app` in `score_docs`/`score_tests`/`score_clean`/`score_patterns`/`score_lessons`/`score_security`**
  `score_claude` and `score_readme` both call `app = _safe(app)` at the top. The remaining six
  scoring functions — `score_docs`, `score_tests`, `score_clean`, `score_patterns`, `score_lessons`,
  and `score_security` — accept `app` from the caller and interpolate it directly into shell
  commands without any validation. A bench app directory named e.g. `foo; rm -rf /` would execute
  arbitrary commands in the container. Add `app = _safe(app)` as the first line of every scorer
  that lacks it.

- **[severity: critical]** security — **BenchCodeHealth.vue:355 — Unescaped HTML from external service rendered with `v-html`**
  ```html
  <div v-html="deepAnalysis[deepSelectedApp].html" class="p-4"></div>
  ```
  The `html` field comes directly from the external analysis microservice response and is rendered
  without any sanitisation. If the service is compromised, returns an error with embedded HTML, or
  the cache is poisoned, this is a stored XSS that runs in the operator's browser session. Options
  in order of preference: (1) use a sandboxed `<iframe srcdoc="...">` with a strict `sandbox`
  attribute; (2) sanitise with DOMPurify before assigning; (3) render only the structured JSON
  field instead of the HTML field. Do not use `v-html` with third-party content.

- **[severity: high]** security — **health_analysis.py:27 — Cache key includes untrusted `git_url` verbatim**
  ```python
  def _cache_key(git_url, commit):
      return f"code_analysis:{git_url}:{commit}"
  ```
  Redis key length limits are generous, but a crafted long URL or one containing colons/newlines
  could corrupt the key namespace or trigger unexpected key collisions. Hash the inputs:
  ```python
  import hashlib
  def _cache_key(git_url, commit):
      h = hashlib.sha256(f"{git_url}:{commit}".encode()).hexdigest()[:16]
      return f"code_analysis:{h}"
  ```

- **[severity: high]** security — **bench_code_health.py:228-230 — Security grep is a false-positive machine and leaks pattern-matching weakness**
  ```python
  sec_r = _exec(bench, "grep -r -l 'api_key\\|password\\|secret_key\\|AKIA\\|ghp_\\|sk-' ...")
  ```
  This counts ANY file that contains the literal string "password" — including Frappe framework
  files, documentation, translation files, and test fixtures. The `security_alerts` number shown in
  the UI will almost always be a large non-zero integer on any real bench, making the "HIGH RISK"
  banner meaningless. The `score_security` function (health_scoring.py:91-102) has the same problem
  and will almost always score 0 for apps that import frappe. The patterns need to be tightened to
  match assignment context (e.g. `password\s*=\s*['"][^'"]{8,}`) or the result should be labelled
  clearly as "possible mentions" not "confirmed hardcoded secrets".

- **[severity: high]** security — **bench_code_health.py:354-388 — `get_app_stack_info` executes 7 docker commands per app with unquoted interpolation**
  Lines 354, 360, 365, 368, 371, 377, 380, 383: every `_exec` call interpolates `app` directly
  after `_safe()` is never called in this function. The app name is sourced from `_list_apps` which
  reads `ls apps/` output from inside the container — if a directory name contains shell
  metacharacters the validation in `_safe` would catch it, but `_safe` is not called here at all.
  Add `app = _safe(app)` at the top of the per-app loop.

---

### CORRECTNESS

- **[severity: high]** correctness — **health_scoring.py:18-20 — `score_claude` section detection uses OR on heading levels, can double-count**
  ```python
  if f"## {s}" in c or f"# {s}" in c:
      score += 13
  ```
  A file that has both `# Architecture` and `## Architecture` (e.g. a subsection inside a top-level
  section) will not double-count because the condition adds 13 only once per section. That part is
  fine. The real issue is that `score = 20` base + 6 sections × 13 = 98, not 100. The final score
  for a perfect CLAUDE.md is 98 unless it is clamped to 100 by `min(..., 100)`. That last 2% is
  unreachable. This is a minor arithmetic oversight — either set base to 22, or use 14 per section.

- **[severity: high]** correctness — **health_scoring.py:33-36 — `score_readme` same arithmetic gap**
  Base 20 + 7 keywords × 11 = 97. A perfect README scores 97. Same fix as above: use 12 per
  keyword or adjust the base.

- **[severity: high]** correctness — **bench_code_health.py:60-65 — `_get_app_commits` uses a single `split(":", 1)` but git short hashes can contain nothing unusual; the real issue is the subshell `$()` caveat**
  The CLAUDE.md warns explicitly: "docker_execute quirks: `$()` subshells expand on the HOST, not
  the container." The command at line 60:
  ```python
  "for d in apps/*/; do echo \"$(basename $d):$(git -C $d rev-parse ...)\"; done"
  ```
  uses `$d` which is a shell variable (safe), but `$(basename $d)` and `$(git -C $d ...)` are
  command substitutions. These are passed as a quoted string through `docker exec sh -c '...'`,
  so they execute inside the container — but only if the outer Python f-string does not evaluate
  them first. Since there are no Python f-string placeholders using `{}` around them they are fine.
  However, this is fragile. The safer approach documented in CLAUDE.md is to use `git -C apps/<app>
  rev-parse` per app in a separate call.

- **[severity: medium]** correctness — **health_tree.py:14-15 — Path stripping assumes `apps/` prefix always present**
  ```python
  if parts[0] == "apps":
      parts = parts[1:]
  ```
  If `wc -l` output ever includes a path that does NOT start with `apps/` (e.g. a relative path
  from a different working directory, or the `total` line slipped through), it will be inserted at
  the root level of the tree under its first path segment. The guard should `continue` on paths
  that lack the `apps/` prefix rather than silently include them:
  ```python
  if parts[0] != "apps":
      continue
  parts = parts[1:]
  ```

- **[severity: medium]** correctness — **health_inventory.py:29 — `doc_events` regex applied to the ENTIRE remainder of the file, not just the dict value**
  ```python
  info["doc_events"] = re.findall(
      r'["\']([A-Z][^"\']+)["\']:\s*\{', content[content.find("doc_events"):]
  )[:30]
  ```
  The slice `content[content.find("doc_events"):]` includes everything after the first occurrence
  of the string `"doc_events"` in the file. If there are other dicts or comments below that
  contain strings like `"Sales Invoice": {` those will be matched too. This is not shell-injection
  but produces incorrect output. Limit the slice to a reasonable window:
  ```python
  idx = content.find("doc_events")
  info["doc_events"] = re.findall(
      r'["\']([A-Z][^"\']+)["\']:\s*\{', content[idx:idx + 2000]
  )[:30]
  ```

- **[severity: medium]** correctness — **CodeHealth.vue:215-216 — `loadBenches` not called when navigating TO the bench listing from a drill-down**
  `mounted()` only calls `loadBenches()` if `!this.selectedBench`. If the user navigates directly
  to `?bench=X`, the bench list (`this.benches`) is never loaded, so `selectedBenchInfo` computed
  property returns `undefined` and the header subtitle is blank. Fix: always call `loadBenches()`
  in `mounted`, or add a watcher on `selectedBench` that calls it when the value clears.

---

### PERFORMANCE

- **[severity: high]** performance — **health_scoring.py — N+1 docker calls: 2 per app in `score_tests`, up to 4 in `score_security`, 3 in `score_patterns`**
  `get_app_scores` (bench_code_health.py:265-278) calls all 8 scorers sequentially for every app.
  For a bench with 10 custom apps, `score_security` alone issues 40 `docker_execute` calls, each a
  round-trip to the agent. Total across all scorers: ~16 docker calls per app × 10 apps = 160
  sequential docker calls for one API response. Combine all grep patterns into a single shell
  command per app:
  ```bash
  grep -r -c 'pattern1\|pattern2\|pattern3' apps/<app>/ ...
  ```
  Or batch the `find`/`grep` across all apps in one call and parse the output. This is the single
  biggest performance issue in the whole module.

- **[severity: high]** performance — **bench_code_health.py:312-313 — `get_docs_compliance` issues 7 docker calls per app (one per check)**
  The 7 `test -f`/`test -d` checks can be combined into a single shell one-liner that tests all
  paths and returns a delimited result string:
  ```bash
  for f in apps/{app}/CLAUDE.md apps/{app}/README.md ...; do test -f "$f" && echo P || echo F; done
  ```
  This reduces 7 docker round-trips to 1.

- **[severity: high]** performance — **BenchCodeHealth.vue:505-527 — Parallel first wave then parallel second wave is correct, but `scan()` fires 7 docker-heavy operations on every manual scan with no rate limiting**
  A user can click "Scan Now" multiple times rapidly. There is no guard preventing concurrent
  scans (the `scanning` flag is set but the button is only `disabled` while `scanning === true` —
  if they trigger it before the flag flips, two scans will run in parallel, each spawning 100+
  docker calls). Add an in-flight guard:
  ```js
  if (this.scanning) return;
  ```
  at the top of `scan()`.

- **[severity: medium]** performance — **bench_code_health.py:102-166 — `list_bench_health` deserialises JSON from Redis inside a loop**
  Lines 144-149 call `json.loads` inside a per-bench loop. With 200 benches this is negligible,
  but the `import json` is also inside the loop (line 145). Move the import to module level.

- **[severity: medium]** performance — **CodeHealth.vue:231-243 — `scanAll` scans benches serially in a `for` loop**
  Scanning 20 benches one at a time means the "Scan All" operation takes 20× the time of a single
  scan. Use `Promise.allSettled` with a concurrency limit (e.g. 3 at a time) instead of awaiting
  each sequentially.

---

### READABILITY

- **[severity: low]** readability — **bench_code_health.py:41 — `import re as _re` placed after module-level constants, not at the top**
  PEP 8 requires all imports at the top of the file. The `import re as _re` on line 41 is mixed
  into the body after constants. Move to the top with the other imports.

- **[severity: low]** readability — **bench_code_health.py:233-234, 246 — `import json` inside functions**
  `import json` appears three times inside function bodies (lines 145, 233, 246). Move to module
  level. Python caches imports so there is no performance penalty, but the style is inconsistent
  with the module-level `import frappe`.

- **[severity: low]** readability — **health_scoring.py:68-70 — `score_clean` variable named `l` shadows built-in `l` (ambiguous)**
  ```python
  under = sum(1 for l in nums if l < SOFT_LIMIT)
  over = sum(1 for l in nums if l > HARD_LIMIT)
  ```
  `l` is visually indistinguishable from `1` in many fonts and is a PEP 8 discouraged single-letter
  name. Use `n` or `lines`:
  ```python
  under = sum(1 for n in nums if n < SOFT_LIMIT)
  over  = sum(1 for n in nums if n > HARD_LIMIT)
  ```

- **[severity: low]** readability — **BenchCodeHealth.vue:636-642 — `_showSidebar` builds HTML via string concatenation**
  The sidebar content is assembled with raw string concatenation including `d.data.name` and
  `d.data.ext` which come from the docker scan output. While these values pass through `_safe()`
  on the Python side, the pattern of injecting data-derived strings directly into `innerHTML` via
  JS concatenation is fragile and hard to audit. Use a small render helper or `textContent`
  assignments to avoid the pattern entirely.

---

### VUE

- **[severity: high]** vue — **BenchCodeHealth.vue:566-568 — Direct mutation of reactive array items inside `forEach`**
  ```js
  this.healthFilters.forEach(f => { f.count = hCounts[f.key] || 0; });
  this.extFilters.forEach(f => { f.count = eCounts[f.ext] || 0; });
  ```
  In Vue 3 Composition API these mutations would be reactive, but this component uses the Options
  API. Mutating object properties directly inside a `forEach` on a reactive array works in Vue 2
  (via observer) and Vue 3 (via Proxy), so this is not a bug today, but it bypasses Vue's intended
  reactivity model. The `count` property being updated here is declared in `data()`, so it IS
  reactive — the issue is that d3's `renderCirclePack()` is called from `$nextTick`, which means
  this mutation runs synchronously during the tick before Vue processes it. In practice it works,
  but the correct pattern is to replace the array or use `Vue.set` equivalent. Low risk but worth
  noting.

- **[severity: high]** vue — **BenchCodeHealth.vue:597-598 — D3 event handlers hold direct closure over `this` with no cleanup**
  ```js
  svg.on('click', () => { ... this._zoom(...) ... });
  svg.on('wheel', (e) => { ... this.zoomIn() ... });
  ```
  These event listeners are attached to the D3 SVG element directly. When the component is
  destroyed (e.g. navigating away), `svg.selectAll('*').remove()` is called on the next
  `renderCirclePack()` but the SVG element itself persists in the DOM until Vue removes it.
  D3 listeners are not automatically cleaned up by Vue's `beforeUnmount`. If the component is
  mounted/unmounted repeatedly (e.g. inside a `v-if`), the closure over `this` will hold the
  component instance alive, preventing GC. Add a `beforeUnmount` hook:
  ```js
  beforeUnmount() {
      if (this._els?.svg) this._els.svg.on('click', null).on('wheel', null);
  }
  ```

- **[severity: medium]** vue — **BenchCodeHealth.vue:629 — Breadcrumb click handlers are added via `innerHTML` + `querySelectorAll`, bypassing Vue's event management**
  ```js
  bc.querySelectorAll('[data-bc-idx]').forEach(el => {
      el.onclick = (e) => { ... this._zoom(...) ... };
  });
  ```
  These `onclick` handlers are set imperatively on raw DOM elements and are never removed. Each
  call to `_zoom` replaces the `innerHTML` (removing old elements and their handlers), so there is
  no true leak, but the pattern holds a closure over `this` and mixes DOM manipulation with Vue
  reactivity. If `_bcNodes` is mutated between renders this could cause stale closures. Consider
  using a reactive `breadcrumbPath` data property and rendering the breadcrumb in the template
  instead.

- **[severity: medium]** vue — **BenchCodeHealth.vue:407 — `mounted()` before `data()` in the options order**
  Vue options order convention (and the official style guide) is: `name`, `components`, `props`,
  `data`, `computed`, `watch`, `mounted`/lifecycle, `methods`. Having `mounted` before `data` is
  not a bug but causes confusion when reading the component — the lifecycle hook references `data`
  properties that haven't been defined yet in the reader's mental model. Re-order.

---

## Verdict

NEEDS CHANGES — three critical security issues (shell injection in 6 scoring functions, missing
`_safe` call in `get_app_stack_info`, and unescaped `v-html` XSS from external service) must be
fixed before this feature ships. The N+1 docker call pattern is a high-severity performance
problem that will make scans extremely slow on real benches with many apps.
