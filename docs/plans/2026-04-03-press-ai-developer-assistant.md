# Press AI Developer Assistant — Plan

**Document ID:** AS-SRS-AIDA-001  
**Version:** 0.3 — Final  
**Date:** April 2026  
**Author:** Eslam (Technical Lead)  
**Status:** Ready for implementation  
**Part of:** `docs/plans/2026-04-03-admin-panel.md`  
**Admin panel ref:** `autodeploypanel.mvpstorm.com/assets/press/admin_panel_prototype.html`  
**Team:** 20 Developers + 10 Implementors

---

## Table of Contents

1. [Document Relationship](#1-document-relationship)
2. [Overview & Principles](#2-overview--principles)
3. [User Stories](#3-user-stories)
4. [AI Dev Tab — Functional Requirements](#4-ai-dev-tab--functional-requirements)
5. [Non-File Actions, Traceability & Rollback](#5-non-file-actions-traceability--rollback)
6. [Token Budget, Cost Tracking & Provider Management](#6-token-budget-cost-tracking--provider-management)
7. [Destructive Action Guardrails](#7-destructive-action-guardrails)
8. [AI Governance — Admin Panel Integration](#8-ai-governance--admin-panel-integration)
9. [Compliance Policy — AI Usage Rules](#9-compliance-policy--ai-usage-rules)
10. [Tech Debt Assessment](#10-tech-debt-assessment)
11. [Resource Planning](#11-resource-planning)
12. [All Gaps — Resolution Summary](#12-all-gaps--resolution-summary)
13. [Success Metrics](#13-success-metrics)
14. [Sign-Off & Next Steps](#14-sign-off--next-steps)

---

## 1. Document Relationship

This plan is a child document of `docs/plans/2026-04-03-admin-panel.md`. It defines the AI Developer Assistant feature only. The admin panel plan defines the overall Press platform roadmap.

### What this plan adds to the admin panel

| Admin panel section | New AI addition | Integration point |
|---|---|---|
| Teams → Quotas & Features | AI Rules tab per team | New tab inside existing team expansion |
| Top navigation | AI Governance, Escalations, Usage & Cost tabs | New nav tabs alongside Teams/Servers |
| Feature Access toggles | `AI Dev Tab` toggle per team | New toggle in existing Feature Access section |
| Resource Quotas | Token cap per user, project pool, daily reset | New fields in existing quota section |

---

## 2. Overview & Principles

The AI Developer Assistant is embedded in the Press Fork Dev Tab. It enables developers and implementors to generate, debug, and extend Frappe/ERPNext customizations using natural language — directly inside their branch environment, without leaving the platform.

### Five core principles

| Principle | What it means |
|---|---|
| Zero context switch | AI lives inside the branch — reads logs, apps, DocType schema automatically |
| Multi-provider | Each user or company configures their own LLM provider and key |
| Safe by default | dev: open · staging: explicit confirm · production: hard block |
| Full traceability | Every AI action (file or DB) logged with session metadata in Press DB |
| Governed | Token budgets, destructive guardrails, escalation chain, policy acknowledgment |

---

## 3. User Stories

### 3.1 Team breakdown

| Persona | Count | v1 capability | v2 target |
|---|---|---|---|
| Senior Developer | ~8 | All features — scaffold, debug, multi-file patch, milestone rollback | Advanced: upgrade analysis |
| Junior Developer | ~12 | Debug tracebacks, add fields, server scripts — with diff review gate | Independent module scaffold |
| Implementor | 10 | Works alongside dev — describes requirement, dev reviews AI output | Independent via Prompt Library |
| Team Leader | varies | Reviews escalations, sees team usage report, approves Category 2 actions | Budget allocation per member |
| Admin | 1 | Global rules, anomaly alerts, full usage & cost, final escalation decision | Multi-team benchmarking |

> **v1 scope note:** Implementors are NOT independent in v1. Full independence requires v2 Prompt Library. Do not promise implementor self-service in v1 communications.

### 3.2 Core user stories

**US-01 — Debug from log**  
As a developer, I want to load the latest traceback with one click, get an explanation and a code patch, preview the diff, and apply it directly to the branch with an auto-structured git commit.

**US-02 — Generate module scaffold**  
As a developer, I describe a new feature in plain language and receive a complete Frappe module: DocType JSON, Python controller, hooks.py entries, and security CSV — ready to commit.

**US-03 — Extend existing DocType**  
As a developer or implementor (with dev review), I select an existing DocType, request specific fields or validation logic, review the tabbed diff, and apply per-file.

**US-04 — Demo data / DB operations on dev site**  
As a developer, I ask the AI to insert demo records or run bench execute commands on a dev site. Every operation is logged in Press DB with a rollback snapshot. Staging requires explicit confirm. Production is hard-blocked.

**US-05 — Work from VS Code (Remote SSH)**  
As a developer, I connect VS Code to the bench via Remote SSH. The AI panel runs in the browser alongside. Patches applied by AI appear immediately in VS Code — same filesystem.

**US-06 — Multi-provider configuration**  
As a developer, I configure my personal API key (Anthropic, Z.AI, OpenAI, or custom). As a company admin, I set a shared fallback key.  
Resolution chain: `Personal -> Company -> Error`

**US-07 — Milestone rollback**  
As a developer, I can roll back all AI actions (file patches + DB operations) to any milestone snapshot taken in the last 60 minutes, selected from a timeline view.

---

## 4. AI Dev Tab — Functional Requirements

### 4.1 Chat panel & context

| REQ | Requirement | Priority |
|---|---|---|
| FR-01 | Collapsible right panel (340px) in Dev Tab — toggleable | Must Have |
| FR-02 | Auto-inject context: installed apps, Frappe version, site name | Must Have |
| FR-03 | One-click 'Load last error' — pulls latest traceback | Must Have |
| FR-04 | DocType selector — schema injected on user selection | Should Have |
| FR-05 | Syntax-highlighted code blocks (Python / XML / JSON) | Must Have |
| FR-06 | Tabbed diff viewer — one tab per file, per-file approve/reject | Must Have |
| FR-07 | git status check before apply — warn on uncommitted changes | Must Have |
| FR-08 | Apply to branch — write patch, structured git commit, show hash | Must Have |
| FR-09 | Bench restart approval banner — never auto-restart | Must Have |
| FR-10 | Quick prompt bar — 4 pre-built prompts (debug, scaffold, add field, server script) | Should Have |
| FR-11 | Token usage indicator per message | Must Have |
| FR-12 | Session reset / new session button | Must Have |

### 4.2 Context injector

| Context layer | Source | Included by default |
|---|---|---|
| Frappe version | `bench version` | Always |
| Installed apps | `frappe.get_installed_apps()` | Always |
| Site name | site config | Always |
| Latest error log | `frappe-error.log` last 50 lines | On user trigger only |
| DocType schema | `frappe.get_doc('DocType', name)` | On user selection |
| Site config (filtered) | `site_config.json` — allowlist only | Always — no credentials |

> **Security:** DB credentials, private keys, and full site_config are NEVER injected into any AI prompt.

### 4.3 IDE integration — 3 scenarios

| Scenario | Description | Press work needed |
|---|---|---|
| A — Press only | All work in browser. Default scenario. | None |
| B — VS Code Remote SSH | VS Code connected to bench. AI panel in browser. Same filesystem. | SSH tab with connection string |
| C — Both simultaneously | VS Code + Press AI open at same time. git status guard prevents overwrites. | SSH tab + git status guard |

> **v1.1:** VS Code Extension (webview iframe) planned for v1.1.

### 4.4 Git traceability

**Commit identity:**
- `git user.name` = `Press AI`
- `git user.email` = `ai@press.yourdomain.com`
- AI commits allowed on `dev-*` branches only — enforced in Press backend

**Commit message structure:**
```
[Press AI] fix: handle missing custom_approval_status field

Provider : Anthropic (claude-sonnet-4-20250514)
Session  : sess_a7f3b2
Branch   : dev-payment-fix
User     : developer@accuratesystems.com
Files    : accubuild/models/payment.py
Prompt   : "explain the last error"
```

Session JSON committed alongside patch under `.press-ai/sessions/`.

---

## 5. Non-File Actions, Traceability & Rollback

### 5.1 Site scope guard

| Site type | AI behavior | Override |
|---|---|---|
| `dev-*` | Proceed after diff/action preview | Not needed |
| `staging` | Confirm modal: "Real production data — confirm?" | Explicit user confirm |
| `production` | HARD BLOCK — AI panel read-only, Apply hidden | None — ever |

### 5.2 Press DB action log schema

```sql
press_ai_action_log
-- session_id         VARCHAR(32)   -- links to AI session
-- action_type        ENUM          -- demo_data | migrate | bench_execute | config | module_install
-- site_name          VARCHAR(255)  -- validated against site type before execute
-- branch             VARCHAR(255)  -- branch at time of action
-- command            TEXT          -- exact command executed
-- payload_json       JSON          -- data sent
-- rollback_snapshot  JSON          -- previous values for undo
-- status             ENUM          -- pending | executed | rolled_back
-- executed_at        DATETIME
-- executed_by        VARCHAR(255)  -- user email + AI session ID
-- milestone_id       INT FK        -- parent milestone snapshot
```

### 5.3 Milestone rollback

| Action type | Rollback method | Feasibility |
|---|---|---|
| Demo data insert | `frappe.delete_doc()` using saved doc names | Full |
| `frappe.db.set_value` / `set_config` | Restore from `rollback_snapshot` | Full |
| bench migrate | Restore site backup taken before migrate | Partial |
| module install | bench uninstall-app — manual verification required | Manual only |

- Snapshots every **60 minutes**
- Soft-deleted after 60 minutes
- Background cleanup job runs hourly
- Storage estimate: ~2MB per milestone per site

---

## 6. Token Budget, Cost Tracking & Provider Management

### 6.1 Hybrid budget model

Both limits enforced simultaneously before every API call:

| Layer | What it controls | Who sets it | Default |
|---|---|---|---|
| Per-user cap | Maximum tokens per user per day | Admin only | 100K tokens/day |
| Project pool | Total tokens across all users in project per day | Admin only | Configurable |
| Soft threshold | Warning shown — continues working | Admin only | 80% of either |
| Hard threshold | Block — next request refused | System | 100% of either |

> **Mid-session exhaustion:** Current in-flight request always completes. The NEXT request is blocked.

### 6.2 Optimistic token reservation

Race condition prevention: system reserves estimated tokens from both user cap and project pool before sending API call. Reconciles with actual tokens after response.

### 6.3 Cost rate management

| Source | When used | Priority |
|---|---|---|
| Provider API (auto) | Live rates from provider pricing API | 1 — highest |
| Manual override | Admin sets custom rate for shared subscriptions | 2 |
| Last known rate (fallback) | Cached from last successful fetch | 3 — lowest |

> **Shared subscription:** Company buys Claude Max at $200/month, shared across 5 devs. Admin sets manual rate = $200 / (5 x estimated_tokens). Used for cost attribution only.

### 6.4 Provider resolution chain

```
Personal Key  ->  Company Shared Key  ->  Show setup prompt (no platform default)
```

| Provider | Endpoint | Notes |
|---|---|---|
| Anthropic (Claude) | `api.anthropic.com/v1/messages` | `claude-sonnet-4-20250514` default |
| Z.AI | `api.z.ai/v1` (OpenAI-compatible) | Company shared key primary use case |
| OpenAI | `api.openai.com/v1/chat/completions` | Standard format |
| OpenAI-compatible | Custom base URL + `/v1/chat/completions` | Covers Groq, Together, Ollama |

> **Tech debt:** Route all providers through LiteLLM. Pin version — upgrade only in dedicated sprint.

### 6.5 Usage reports by role

| Role | Sees | Cannot see |
|---|---|---|
| User | My tokens today/month, my cost estimate, my sessions, my budget remaining | Other users' data |
| Team Leader | Full team: tokens per user, cost per project, branch activity, anomaly alerts | Other teams |
| Admin | All teams, all providers, all costs, anomaly alerts, escalation queue | N/A — full access |

---

## 7. Destructive Action Guardrails

### 7.1 Three-category classification

#### Category 1 — Hard block
Examples: `DROP/DELETE` SQL, `uninstall app`, `bench destroy`, `rm -rf`, any action on production  
Behavior: Linter removes from response. Escalation starts automatically. **AI never executes — even if all parties approve.**

#### Category 2 — Approval required
Examples: `bench migrate` on staging, bulk delete >50 docs, module install on staging, permission changes  
Behavior: Response shown with action flagged. User submits escalation with written reason. TL approves -> Admin decides.

#### Category 3 — Warning + confirm
Examples: Delete single doc on dev, `bench clear-cache`, `git reset`, non-critical config change  
Behavior: Warning shown inline. User clicks explicit confirm. Logged in action log.

### 7.2 Post-generation linter patterns

| Pattern | Category | Action |
|---|---|---|
| `frappe.db.sql()` with DELETE/DROP/TRUNCATE | 1 — Hard block | Remove from response + escalation |
| `bench uninstall-app` / `bench destroy` | 1 — Hard block | Remove from response + escalation |
| `rm -rf` / `shutil.rmtree` | 1 — Hard block | Remove from response + escalation |
| `DROP TABLE` / `TRUNCATE TABLE` | 1 — Hard block | Remove from response + escalation |
| Bulk `frappe.delete_doc()` loop >50 | 2 — Approval | Flag in response + escalation prompt |
| Direct `site_config.json` credential modification | 1 — Hard block | Remove from response + escalation |

### 7.3 Escalation message — UX principle

When linter detects Category 1 or 2, show the response minus the dangerous part, with a clear explanation of what was removed and why, plus instructions for escalation.

### 7.4 Escalation chain

| Step | Actor | Action | Outcome |
|---|---|---|---|
| 1 | System (linter) | Detects pattern, removes from response | ESC record created in Press DB |
| 2 | User | Submits escalation with mandatory written reason | ESC status: Pending TL |
| 3 | Team Leader | Real-time notification — Approve or Reject | Approve -> step 4, Reject -> closed |
| 4 | Admin | Full context review — decides manual execution | Manual only — AI never executes Cat. 1 |
| 5 | System | ESC record closed with all decisions and timestamps | Full audit trail in Press DB |

> **Audit requirement:** Every escalation requires a written reason. Submission blocked if reason field is empty.

---

## 8. AI Governance — Admin Panel Integration

### 8.1 New admin panel tabs

| Tab | Who sees it | Content |
|---|---|---|
| AI Governance | Admin | Global rules, anomaly alerts, token pool overview, today's stats |
| Escalations | Admin + TL (filtered to their team) | Open escalation queue, audit trail, approve/reject |
| Usage & Cost | Admin (all) + TL (their team) + User (self) | Tokens per user, cost per provider, session count |

### 8.2 Per-team AI settings (inside team expansion)

New **AI Rules** tab added inside existing team expansion — alongside Quotas & Features, Members, Sites, Benches.

| Setting | Type | Default |
|---|---|---|
| AI Dev Tab enabled for team | Toggle (Admin only) | Enabled |
| Daily token pool for project | Number | 500K tokens/day |
| Per-user token cap | Number | 100K tokens/day |
| Allowed providers | Multi-select | Company key + Personal key |
| Require policy acknowledgment | Toggle | On — mandatory |
| Team Leader for AI escalations | Member select | Owner by default |

### 8.3 Anomaly detection signals

| Signal | Definition | Alert goes to |
|---|---|---|
| Token spike | User consumes 3x daily average in 1 hour | Admin + Team Leader |
| Repetition pattern | Same prompt sent >5 times in 20 minutes | Admin + Team Leader |
| Off-hours usage | AI usage outside configured working hours | Admin |
| Context stuffing | File injected into context >500KB | Admin + Team Leader |
| Client key on client code | Personal key used with client app code in context | Admin + TL (immediate) |
| Production data in prompt | PII patterns in context injector output | Admin (immediate block) |

---

## 9. Compliance Policy — AI Usage Rules

Every user must acknowledge this policy before first use of the AI Dev Tab. Acknowledgment stored in Press DB with timestamp. AI panel locked until acknowledged.

### 9.1 Technical rules

| Rule | Enforcement | Level |
|---|---|---|
| No Raw SQL (DELETE/DROP/TRUNCATE) | Linter — removes from response + escalation | Hard block |
| No uninstall app or destroy | Linter — removes from response + escalation | Hard block |
| No modifications on Production — AI read-only | Backend enforcement before any write | Hard block |
| Max tokens/day — 80% warning, 100% block | Optimistic reservation + gateway check | Soft then hard |

### 9.2 Behavioral rules

| Rule | Enforcement | Level |
|---|---|---|
| No AI for code outside project scope | Audit log flag — TL notified | Soft |
| All AI output reviewed before apply | Diff review gate — mandatory for implementors | Enforced |
| No sharing sessions or API keys | Policy acknowledgment + audit trail | Policy |

### 9.3 Compliance rules

| Rule | Enforcement | Level |
|---|---|---|
| Client code — company key only, not personal | Anomaly detection: client code + personal key -> alert | Hard block |
| Production data blocked from any prompt | PII detector in context injector -> block + Admin alert | Hard block |
| Every escalation must contain written reason | Form validation — submit blocked if reason empty | Enforced |
| Every AI action documented in Press DB | Automatic — always on | Always |

---

## 10. Tech Debt Assessment

**Mandatory allocation: 20% of every sprint for tech debt — non-negotiable.**

| Area | Debt | Risk | Mitigation |
|---|---|---|---|
| Per-version context templates | V14/V15/V16 prompts need update per Frappe release | High | Versioned template files + CI tests |
| Frappe-only linter | API surface changes — linter becomes outdated silently | High | Linter tests run against each Frappe version |
| LiteLLM dependency | Fast-moving library — breaking changes risk | High | Pin version — upgrade in dedicated sprint only |
| Provider rate cache | Cached rates go stale — cost estimates drift | Medium | Daily rate refresh job + staleness alert |
| Milestone snapshot storage | ~2MB/milestone/site — grows without cleanup | Medium | Hourly cleanup job from day 1 |
| Action log retention | press_ai_action_log unbounded growth | Medium | 90-day retention + cold storage archive |
| PII detector accuracy | Regex-based detection has false positives | Medium | Structured field detection not free-text regex |
| Session JSON in git | `.press-ai/sessions/` becomes git noise on large projects | Low | Option to gitignore sessions (trade-off vs audit) |

---

## 11. Resource Planning

### 11.1 Build team

| Role | Scope | Allocation |
|---|---|---|
| Senior Backend | AI gateway (LiteLLM), token budget engine, action log, milestone rollback, site scope guard, git pipeline, escalation chain, PII detector | 1 FTE |
| Frontend | AI chat panel, diff viewer, provider settings, milestone timeline, governance tabs in admin panel, policy acknowledgment flow | 1 FTE |
| DevOps / Platform | SSH tab, cleanup jobs, milestone snapshot scheduling, Press DB schema migration, anomaly detection jobs | 0.5 FTE |
| QA | Per-scenario test matrix (A/B/C), linter tests, staging guard, rollback verification, budget enforcement tests | 0.5 FTE |

### 11.2 Delivery timeline

| Milestone | Scope | Duration |
|---|---|---|
| MVP — Scenario A | AI panel + context + diff viewer + apply + single provider + basic linter | 6-8 weeks |
| v1.0 — Full | All 3 IDE scenarios + multi-provider + token budget + action log + milestone rollback + escalation + governance tabs + policy | 14-16 weeks |
| v1.1 | VS Code extension webview + SSH badge + token budget UI + action log retention settings | 4-6 weeks |
| v2.0 | Prompt Library for implementors + upgrade migration suggestions + test generation | TBD |

### 11.3 Impact — 20 developers

| Task | Current | With AI | Weekly saving per dev |
|---|---|---|---|
| Debug traceback (3x/week) | 6 hours | 1 hour | ~5 hours |
| Module scaffold | 2-3 days | 4-6 hours | ~14 hours per module |
| Add field + view | 1 hour | 10 min | ~50 min per task |
| Server script | 45 min | 8 min | ~37 min per script |

**Conservative total: 80-100 engineering hours freed per week across the 20-developer team.**

### 11.4 Impact — 10 implementors

| Phase | Capability | Dependency |
|---|---|---|
| v1 (now) | Works alongside developer. Dev reviews AI output before apply. | Developer review required |
| v2 (Prompt Library) | Handles: add field, form view tweaks, basic validation — independently. | Prompt Library + staging guard |
| v2 full | Handles ~60-70% of minor customization requests without escalation. | Prompt Library quality |

---

## 12. All Gaps — Resolution Summary

| GAP | Question | Decision |
|---|---|---|
| GAP-01 | Billing model | Per-site attribution via action log |
| GAP-02 | Auto-commit or manual? | Auto-commit with structured message + session metadata |
| GAP-03 | Multi-file diff UX? | Tabbed diff viewer — per-file approve/reject |
| GAP-04 | Token budget per user? | Admin-configurable cap enforced in gateway |
| GAP-05 | Session storage? | JSON in `.press-ai/sessions/` + Press DB metadata |
| GAP-06 | Per-version context? | Auto-detected from bench version — versioned templates |
| GAP-07 | Bench restart? | User approval always required — never auto |
| GAP-08 | Prompt Library? | Deferred to v2 |
| GAP-09 | Action log location? | Press DB — independent of site DB |
| GAP-10 | Rollback mechanism? | Milestone-based — 60-min snapshots |
| GAP-11 | Staging behavior? | Explicit confirm modal |
| GAP-12 | Cost rates? | Auto from provider API + manual override for shared subscriptions |
| GAP-13 | Mid-session pool exhaustion? | Current request completes — next request blocked |
| GAP-14 | Dangerous code in response? | Show response minus dangerous part + escalation message |
| GAP-15 | Escalation approval: real-time or async? | Real-time notification to TL with approve/reject |
| GAP-16 | Misuse alerts — who? | Admin (all teams) + TL (their team only) |

---

## 13. Success Metrics — 90 days post-launch

| Metric | Target |
|---|---|
| Debug cycle time (avg) | < 25 min (vs current ~2 hours) |
| % debug tasks resolved without leaving Press | > 65% |
| Provider switch time (company -> personal) | < 2 minutes |
| AI call error rate | < 2% with clear user feedback |
| Developer NPS for feature | > 7/10 after 30 days |
| Unintended staging / production operations | 0 — hard block holds |
| Escalation resolution time (TL response) | < 30 min during working hours |
| Policy acknowledgment rate | 100% — panel locked until signed |
| Tech debt sprint allocation | 20% every sprint — tracked in project board |

---

## 14. Sign-Off & Next Steps

All 16 gaps resolved. Implementation can begin.

### Week 1
- [ ] Security review: key storage AES-256 + context injector allowlist
- [ ] Press DB schema migration: `press_ai_action_log` + `press_ai_milestone` + `press_ai_session` tables
- [ ] LiteLLM PoC: validate routing with Z.AI + Anthropic simultaneously
- [ ] Linter rule set finalized and unit-tested against V14/V15/V16

### Week 2
- [ ] Frontend: hi-fi design for AI panel + diff viewer + milestone timeline + governance tabs
- [ ] Policy document finalized and published in Press (ref: section 9)
- [ ] Admin panel integration points mapped (ref: `docs/plans/2026-04-03-admin-panel.md`)

### Week 3
- [ ] MVP sprint kickoff — Scenario A only, single provider, basic linter

---

*Document Owner: Eslam — Accurate Systems / Optiflow Solutions*  
*Part of plan: `docs/plans/2026-04-03-admin-panel.md`*  
*Version: 0.3 Final | April 2026*
