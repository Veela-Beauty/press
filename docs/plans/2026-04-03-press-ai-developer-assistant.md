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

### Architecture decision (2026-04-05): Sanad AI + Press hybrid

**Key insight:** Sanad Business Intelligence AI (`sanad_bi_ai 0.2.0`) is already installed on the staging site (`accubuild-stg-qimma.sandbox.mvpstorm.com`). It already provides:

| Feature | Sanad AI module | Status |
|---|---|---|
| AI chat widget (global, every page) | `public/js/chat_core/` — 17 JS files | **Already working** |
| Multi-provider (Anthropic, OpenAI, Groq, OpenRouter, Local) | `ai_integration/utils/providers.py` | **Already working** |
| SSE streaming responses | `ai_integration/utils/chat_processing/_stream.py` | **Already working** |
| 27 tool categories (CRUD, files, system, research, etc.) | `ai_integration/tools/` — auto-discovered | **Already working** |
| Token billing + usage tracking | `ai_billing/` — 7 DocTypes | **Already working** |
| Rate limiting + security | `ai_security/` — 7 DocTypes | **Already working** |
| Conversation history | `AI Conversation` + `AI Conversation Message` | **Already working** |
| Agent system (instructions, skills, triggers) | `ai_core/doctype/ai_agent/` | **Already working** |
| Knowledge base (RAG) | `ai_core/utils/knowledge/` — FTS5, Qdrant | **Already working** |
| MCP gateway + OAuth | `ai_integration/mcp_server/` | **Already working** |
| Action logging | `AI Agent Action Log` DocType | **Already working** |
| Prompt templates | `AI Prompt Template` DocType | **Already working** |

**What this means:** We do NOT rebuild chat, streaming, providers, billing, tools, or knowledge in Press. Instead:

- **Sanad AI (on the site)** = the AI engine — chat, tools, providers, billing, knowledge
- **Press (on press-ctrl)** = the governance layer — scope guard, escalation, rollback, policy

**What we ADD to Sanad AI** (3 new tools, not a new app):

| New tool | File | Purpose |
|---|---|---|
| Code diff viewer | `tools/code_diff.py` | Generate unified diffs, show in chat |
| Git commit | `tools/git_commit.py` | Commit AI changes with structured `[Press AI]` messages |
| Destructive linter | `tools/destructive_linter.py` | Scan AI output for DROP/DELETE/rm-rf, block Cat 1 |

**What stays in Press** (governance only):

| Feature | Why it must be in Press |
|---|---|
| Site scope guard | Press knows which site is dev/staging/prod |
| Escalation chain | TL/Admin approval across teams — Press DB |
| Rollback orchestration | Press controls the agent, sends rollback commands |
| Policy gate | Acknowledgment stored in Press user record |
| Governance dashboard | Admin panel tabs — budget, alerts, escalations |

**Savings:** ~12 weeks of development avoided. We use 46,000 lines of existing code instead of rebuilding.

```
┌─────────────────────────────────────────────────────┐
│ Press (press-ctrl) — GOVERNANCE                     │
│   Site scope guard · Escalation · Rollback          │
│   Policy gate · Admin dashboard                     │
└──────────────────┬──────────────────────────────────┘
                   │ agent API
┌──────────────────▼──────────────────────────────────┐
│ Dev/Staging Site (container) — AI ENGINE             │
│   Sanad AI (already installed)                      │
│     Chat widget · 5 providers · SSE streaming       │
│     27 tools + 3 new (diff, git, linter)           │
│     Token billing · Rate limiting · Knowledge       │
└─────────────────────────────────────────────────────┘
```

### Five core principles

| Principle | What it means |
|---|---|
| Zero context switch | Sanad AI chat widget lives on every page — reads logs, apps, DocType schema automatically |
| Multi-provider | Sanad AI already supports 5 providers — users configure in AI Settings |
| Safe by default | Press enforces: dev = open · staging = explicit confirm · production = hard block |
| Full traceability | Sanad AI logs actions + conversations; Press logs governance decisions |
| Governed | Press manages budgets, escalation, rollback — Sanad AI enforces rate limits + security |

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

### 5.3 Rollback architecture — MariaDB System Versioning (hybrid)

**Research conclusion (2026-04-05):** No external library needed. MariaDB 10.3+ has built-in System-Versioned Tables that track every INSERT/UPDATE/DELETE at the SQL layer. Combined with Frappe's built-in `Version` DocType and git revert for files, this gives 100% rollback coverage with zero external dependencies.

**Alternatives evaluated and rejected:**

| Library | Stars | Why rejected |
|---|---|---|
| SQLAlchemy-Continuum | 641 | Wrong ORM — Frappe doesn't use SQLAlchemy |
| django-reversion | 3,154 | Wrong framework — Frappe doesn't use Django |
| django-simple-history | 2,447 | Wrong framework |
| Debezium CDC | 10K+ | Requires Kafka infra — massive overkill for dev/staging |
| Stellar | 3,900 | Full-DB restore only, no per-document rollback |
| postgresql-audit | — | PostgreSQL only, we use MariaDB |

#### Three-layer rollback strategy

| Layer | Technology | What it captures | Rollback method |
|---|---|---|---|
| **1. DB — System Versioning** | MariaDB `ADD SYSTEM VERSIONING` | ALL SQL: ORM, raw SQL, bulk ops, `db_set` | `FOR SYSTEM_TIME AS OF TIMESTAMP` query → compensating SQL |
| **2. App — Frappe Version** | `track_changes = 1` per DocType | Frappe ORM saves (field-level diff) | Walk `changed` list, apply `old_value` — used for UI timeline display |
| **3. Files — Git** | AI commits tagged with `[Press AI]` prefix | File patches (Python, JSON, hooks) | `git revert --no-edit <commit_hash>` |

#### How MariaDB System Versioning works

```sql
-- One-time setup per table (run via agent on target site)
ALTER TABLE `tabPayment Entry` ADD SYSTEM VERSIONING;

-- MariaDB now automatically tracks all changes with invisible
-- ROW_START / ROW_END timestamp columns

-- Query state at any past point:
SELECT * FROM `tabPayment Entry`
FOR SYSTEM_TIME AS OF TIMESTAMP '2026-04-05 10:00:00'
WHERE name = 'PE-00042';

-- Full history of a single row:
SELECT *, ROW_START, ROW_END FROM `tabPayment Entry`
FOR SYSTEM_TIME ALL
WHERE name = 'PE-00042';
```

#### Implementation: `press/press/ai/rollback.py` (~80 lines)

```python
@frappe.whitelist()
def enable_versioning(site_name, doctypes):
    """Enable system versioning on target tables via agent."""
    for dt in doctypes:
        table = f"tab{dt}"
        agent.execute_on_site(site_name, f"""
            import frappe
            frappe.db.sql('ALTER TABLE `{table}` ADD SYSTEM VERSIONING')
            frappe.db.commit()
        """)

@frappe.whitelist()
def rollback_to_timestamp(site_name, timestamp, doctypes):
    """Rollback all versioned tables to a point in time."""
    for dt in doctypes:
        table = f"tab{dt}"
        agent.execute_on_site(site_name, f"""
            import frappe
            old_rows = frappe.db.sql(
                'SELECT * FROM `{table}` FOR SYSTEM_TIME AS OF TIMESTAMP %s',
                timestamp, as_dict=True
            )
            current = set(r.name for r in frappe.db.get_all('{dt}'))
            old_names = set(r['name'] for r in old_rows)

            # Delete rows added after timestamp
            for name in current - old_names:
                frappe.delete_doc('{dt}', name, force=True)

            # Restore changed/deleted rows from history
            for row in old_rows:
                if row['name'] in current:
                    doc = frappe.get_doc('{dt}', row['name'])
                    doc.update(row)
                    doc.save(ignore_permissions=True)
                else:
                    doc = frappe.get_doc(row)
                    doc.insert(ignore_permissions=True)

            frappe.db.commit()
        """)

@frappe.whitelist()
def rollback_git_commit(bench_name, app_name, commit_hash):
    """Revert a specific AI commit."""
    agent.execute_in_container(bench_name, f"""
        cd /home/frappe/frappe-bench/apps/{app_name}
        git revert --no-edit {commit_hash}
    """)
```

#### Gateway flow (before/after every AI DB command)

```
AI Gateway (gateway.py):
  1. Record current timestamp → Press AI Action Log
  2. Execute command on site via agent
  3. Log result + commit hash (if file change)

User clicks "Rollback" in UI:
  1. Press reads the action's timestamp from Action Log
  2. Calls rollback_to_timestamp() for DB changes
  3. Calls rollback_git_commit() for file changes
  4. Updates action status → "rolled_back"
  5. Toast: "Rolled back to ms_20260405_1042"
```

#### Rollback feasibility per action type

| Action type | Rollback method | Layer | Feasibility |
|---|---|---|---|
| Demo data insert | System versioning → delete added rows | DB | Full |
| `frappe.db.set_value` / `set_config` | System versioning → restore old values | DB | Full |
| Raw SQL (any) | System versioning → compensating SQL | DB | Full |
| Bulk operations | System versioning → compensating SQL | DB | Full |
| File patch | `git revert --no-edit <hash>` | Git | Full |
| bench migrate | Restore site backup taken before migrate | Backup | Partial |
| module install | `bench uninstall-app` — manual verification | Manual | Manual only |
| `frappe.rename_doc` | System versioning + reverse rename | DB | Partial — links may break |

#### Press DB schema for rollback tracking

```
Press AI Action Log (DocType on press-ctrl)
├── session_id        VARCHAR(32)   -- groups actions in same chat session
├── action_type       ENUM          -- demo_data | config | file_patch | raw_sql | migrate
├── site_name         VARCHAR(255)  -- target site
├── bench_name        VARCHAR(255)  -- target bench
├── branch            VARCHAR(255)  -- git branch at time of action
├── command           TEXT          -- human-readable description
├── payload_json      JSON          -- what was sent to execute
├── rollback_timestamp DATETIME     -- MariaDB SYSTEM_TIME reference point
├── commit_hash       VARCHAR(40)   -- git commit hash (for file patches)
├── versioned_doctypes JSON         -- which tables had versioning enabled
├── status            ENUM          -- pending | executed | rolled_back | expired
├── executed_at       DATETIME
├── executed_by       VARCHAR(255)  -- user email + AI session ID
├── milestone_id      INT FK        -- parent milestone
├── expires_at        DATETIME      -- executed_at + 60 minutes
└── rolled_back_at    DATETIME      -- when rollback was performed

Press AI Milestone (DocType on press-ctrl)
├── milestone_id      VARCHAR(32)   -- ms_YYYYMMDD_HHMM
├── site_name         VARCHAR(255)
├── created_at        DATETIME
├── expires_at        DATETIME      -- created_at + 60 min
├── action_count      INT           -- number of actions in this milestone
├── status            ENUM          -- active | expired | rolled_back
└── rolled_back_at    DATETIME
```

#### Milestone lifecycle

```
┌─────────┐    60 min     ┌─────────┐    cleanup    ┌──────────┐
│  Active  │ ──────────→  │ Expired │ ──────────→   │ Cleaned  │
└─────────┘               └─────────┘               └──────────┘
     │
     │ user clicks "Rollback"
     ▼
┌──────────────┐
│ Rolled Back  │  (permanent audit record)
└──────────────┘
```

#### Scheduler cleanup job (runs hourly on press-ctrl)

```python
def cleanup_expired_milestones():
    expired = frappe.get_all("Press AI Milestone",
        filters={"status": "active", "expires_at": ["<", now()]})
    for ms in expired:
        frappe.db.set_value("Press AI Milestone", ms.name, "status", "expired")
        # Optionally: disable system versioning on tables to free storage
    frappe.db.commit()
```

#### Known limitations of MariaDB System Versioning

- History is **lost in `mysqldump`** — only current rows exported (known MariaDB limitation)
- `ALTER TABLE ... DROP SYSTEM VERSIONING` deletes all history permanently
- Cannot version tables with `FULLTEXT` indexes (rare in Frappe)
- History grows table size — cleanup via `DELETE HISTORY FROM table BEFORE SYSTEM_TIME '...'`
- ROW_START/ROW_END columns are invisible — do not interfere with Frappe ORM

#### Storage estimate

- ~2MB per milestone per site (unchanged from original plan)
- MariaDB history rows stored in same table — auto-cleaned by `DELETE HISTORY` command
- Press AI Action Log: 90-day retention + cold storage archive

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
| MariaDB versioning storage | System-versioned tables grow unbounded if not cleaned | Medium | `DELETE HISTORY BEFORE` in scheduler + monitor table sizes |
| MariaDB versioning + mysqldump | History lost in dumps — rollback data not in backups | Low | Acceptable — rollback window is only 60 min, not backup scope |

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

All 16 gaps resolved. Implementation started 2026-04-04.

### Week 1 — DONE (2026-04-04)
- [x] Security review: key storage AES-256-GCM + context injector allowlist — `key_storage.py` (155 lines, 20 tests)
- [x] Press DB schema: 3 DocTypes created on server — `db_setup.py` (166 lines)
- [x] Custom Fields: `ai_api_key`, `ai_provider`, `ai_policy_acknowledged` on User; `ai_company_key`, `ai_rules` on Team
- [x] Provider: OpenRouter integration via urllib — `provider.py` (175 lines, 8 real API tests)
- [x] Linter: 3-category scanner, 2-pass (fenced + prose), 12 patterns — `linter.py` (301 lines, 44 tests)
- [x] Context injector: sanitized prompt builder — `context_injector.py` (147 lines, 19 tests)
- [x] Site scope guard: dev/staging/prod + branch enforcement — `site_scope_guard.py` (116 lines, 21 tests)
- [x] Token budget: per-user cap + project pool + optimistic reservation — `token_budget.py` (180 lines, 12 tests)
- [x] Gateway: orchestrator (scope -> budget -> provider -> lint) — `gateway.py` (148 lines, 8 tests)
- [x] API wrapper: `press/api/ai_chat.py` for Frappe URL routing — allow_guest with auth check

### Week 2 — DONE (2026-04-04)
- [x] AI chat panel: collapsible right panel with quick prompts, budget bar — `AiChatPanel.vue` (310 lines)
- [x] Diff viewer: tabbed per-file approve/reject — `AiDiffViewer.vue` (214 lines)
- [x] Governance tabs: AI Governance + Escalations + Usage & Cost — 3 components (341 lines)
- [x] Policy gate: acknowledgment flow before AI use — `AiPolicyGate.vue` (102 lines)
- [x] Per-team AI Rules: token cap + prod access overrides — `AiTeamRules.vue` (118 lines)
- [x] Admin Panel: 6-tab navigation wired (Teams, Servers, AI Governance, Escalations, Usage & Cost, Policy)
- [x] Prototype: standalone HTML with DOMPurify + highlight.js + marked.js — `ai_chat_panel_prototype.html`

### Week 3 — DONE (2026-04-04)
- [x] MVP wiring: AI panel integrated into SiteDevTab (floating button + panel)
- [x] Backend API: `chat()`, `apply_patch()`, `acknowledge_policy()`, `update_team_ai_rules()`, `get_ai_config()`
- [x] E2E backend tests: 6/6 pass on live server (simple prompt, Frappe code, debug, prod block, branch block, budget)
- [x] Playwright UAT: AI button appears on Dev Tab, panel opens, tabs render in Admin Panel

### Code Reviews Applied
- [x] Linter: 3 HIGH bypass fixes (prose scan, backtick quoting, trailing space) + 5 new patterns
- [x] Test review: DROP DATABASE, site_config path variable, bulk delete list, bench migrate generic
- [x] Backend security: 4 MUST FIX (shell injection, permission checks on apply_patch/chat/team_rules)
- [x] Frontend: XSS fix (DOMPurify), prop mutation fix, accessibility (aria-labels), applying reset

### Stats (as of 2026-04-05)
- **19 commits** pushed to `cloudflare-dns` branch
- **173 tests** in Press (132 Week 1-3 + 41 governance)
- **156 tests** in Sanad AI (ai_dev module, TDD)
- **Press governance**: 4 Python modules + 4 test files (after deleting 15 duplicate files, -2,585 lines)
- **Sanad AI ai_dev**: 6 tools + 2 utils + 1 page + 10 test files + 2 tool categories
- **Architecture shift**: Sanad AI = engine (tools, providers, billing), Press = governance only
- **5 code reviews** completed (2 backend, 2 frontend, 1 ai_dev)
- **14 security/quality fixes** applied (8 earlier + 5 HIGH + 1 architecture)

### Remaining for production readiness

#### Architecture shift (2026-04-05): Sanad AI is already installed — use it
- [x] Fresh OpenRouter API key — saved to Infisical `/press/ai/OPENROUTER_API_KEY`
- [x] Streaming responses — **already done** (Sanad AI `_stream.py` has SSE)
- [x] Multi-provider — **already done** (Sanad AI supports 5 providers)
- [x] Token billing — **already done** (Sanad AI `ai_billing/` module, 7 DocTypes)
- [x] Chat widget — **already done** (Sanad AI global widget, 17 JS files)
- [x] Conversation history — **already done** (Sanad AI `AI Conversation` DocType)

#### Sanad AI — ai_dev module (DONE, 2026-04-05)
- [x] `ai_dev/tools/destructive_linter.py` — 3-category scanner (Cat 1 hard block, Cat 2 approval, Cat 3 warning)
- [x] `ai_dev/tools/code_diff.py` — generate unified diffs from AI patches
- [x] `ai_dev/tools/git_commit.py` — commit AI changes with `[Press AI]` structured messages
- [x] `ai_dev/tools/post_patch_verify.py` — post-apply verification checks
- [x] `ai_dev/tools/rollback.py` — MariaDB System Versioning rollback
- [x] `ai_dev/tools/playwright_verify.py` — browser-based verification (Playwright engine)
- [x] `ai_dev/utils/linter_pipeline.py` — multi-pass scan orchestrator
- [x] `ai_dev/utils/rollback_api.py` — whitelisted rollback endpoints
- [x] `ai_dev/utils/rollback.py` — System Versioning SQL wrapper
- [x] `ai_dev/utils/playwright_verify.py` — Playwright engine (71-step benchmark 96% pass)
- [x] `ai_dev/page/ai_dev_playground/` — AI Dev Playground page
- [x] `ai_integration/tools/dev_tools.py` — tool category wired to auto-discovery
- [x] `ai_integration/tools/verify_tools.py` — tool category wired to auto-discovery
- [x] 156 unit tests (TDD, all passing)
- [x] Code review: 9 issues found and fixed (5 HIGH)

#### Press — governance layer (DONE, 2026-04-05)
- [x] `press/press/ai/site_scope_guard.py` — dev/staging/prod enforcement
- [x] `press/press/ai/escalation.py` — 3-category escalation chain
- [x] `press/press/ai/policy.py` — policy acknowledgment gate + per-team AI rules
- [x] `press/press/ai/rollback_trigger.py` — trigger rollback on target site via agent API
- [x] 41 unit tests (TDD, all passing)
- [x] Deleted 15 duplicate files (-2,585 lines) — now handled by Sanad AI
- [x] E2E test: 10/10 passed across full pipeline

#### Future
- [ ] VS Code extension webview (v1.1)
- [ ] Prompt Library for implementors (v2)

---

*Document Owner: Eslam — Accurate Systems / Optiflow Solutions*  
*Part of plan: `docs/plans/2026-04-03-admin-panel.md`*  
*Version: 0.7 — Phase 1-3 complete: 156 ai_dev tests + 41 governance tests + architecture shift | 5 April 2026*
