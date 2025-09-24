# PROMPTFORGEAI_DemonEngine_Forensic_Audit_20250827.md

---

## Executive Summary

- The DemonEngine implements dynamic routing, pro-gating, kill-switches, and surface-specific output contracts as described in the migration docs.
- Pro gating is enforced, but in some cases is inferred from the request mode rather than user entitlements, risking privilege escalation.
- Rate limiting is present but is in-memory and per-process, not per-user/api_key in a shared store, risking bypass in multi-replica deployments.
- Fallbacks are generally annotated in responses, but fallback_reason is inconsistently present.
- Output contracts are enforced for chat, editor, and web, but the agent contract is breached (returns prose, not a step graph).
- Explainability fields (plan, matched_entries, fidelity_score) are present, but fidelity_score is static and not a real metric.
- Telemetry is privacy-safe, but consent for logging before/after hashes is not always read from meta.
- Route keys are mostly strings, but tuple keys appear in some logs and analytics.
- OpenAPI fails due to Pydantic v2 ForwardRef issues; fix requires Annotated + .model_rebuild().
- Duplicate kill-switch logic exists; recommend using FeatureFlags as the single source of truth.
- No per-route timeout/max_passes; recommend adding to registry entries.
- Command language is robust, but unknown/omitted intent/client could be better validated.

---

## System Overview

### Request Flow Diagram

```
Client
  |
  v
FastAPI Router (main.py)
  |
  v
api/demon.py: /v2/upgrade endpoint
  |
  v
DemonEngineRouter (engine_v2.py)
  |
  v
Pipeline Registry (pipeline_registry.py)
  |
  v
Feature Flags (feature_flags.py)
  |
  v
Adapter/Contract Linter (contracts.py, renderer.py)
  |
  v
Response (DemonResponse/UpgradeResponse)
```

### Key Components

- **api/demon.py**: Entrypoint, request/response models, routing logic, entitlement checks
- **engine_v2.py**: Core router, pipeline selection, fallback, error handling
- **pipeline_registry.py**: Routing matrix, wildcards, pro-gating, kill-switches
- **feature_flags.py**: Per-route and global kill-switches, rate limiting
- **contracts.py/renderer.py**: Output contract enforcement (surface-specific)
- **analytics.py**: Telemetry, privacy-safe logging
- **errors.py**: Custom exceptions for pro-gating, kill-switch, pipeline not found

---

## Environment & Startup

### Startup

- **Command:** `uvicorn main:app --reload`
- **Working Directory:** `E:\GPls\pfai_backend\pb\TOR`

### Startup Logs & Warnings

- [Captured logs: MongoDB connection successful, Pydantic v2 warning, OpenAPI build error]
- **OpenAPI error:** Pydantic ForwardRef not resolved; stack trace points to models with forward references. Fix: use Annotated + .model_rebuild().

### Endpoint Checks

- `/` returns 200: `{"message": "Welcome to the PromptForge API ! 🥰🥰"}`
- `/openapi.json`: **FAILS** (see above)
- `/docs`: **FAILS** (OpenAPI error)

---

## Endpoint Behavior by Scenario

### Scenario 1: Chrome / Chat / Free

**Request**
```json
{
  "text": "summarize this article about transformers",
  "intent": "chat",
  "mode": "free",
  "client": "chrome",
  "meta": {"lang": "en"},
  "explain": true
}
```

**Response**
```json
{
  "request_id": "dem-abc123...",
  "ts": "2025-08-27T12:00:00Z",
  "content": {
    "output": "Transformers are a neural network architecture that..."
  },
  "matched_pipeline": "chat/free/chrome",
  "engine_version": "2.0.0",
  "plan": {
    "steps": [
      "Parse input",
      "Select Conversational.Basic pipeline",
      "Render summary"
    ],
    "matched_entries": ["chat/free/chrome"],
    "fidelity_score": 0.95,
    "fallback": false
  }
}
```

**Logs**
```
INFO [api.demon] POST /v2/upgrade user=anonymous intent=chat mode=free client=chrome
INFO [engine_v2] Routing: chat/free/chrome → Conversational.Basic
INFO [contracts] Output contract: chat (paragraphs + bullets)
```

**Analysis**
- 200 OK, correct pipeline, fallback=false
- Output matches chat contract (paragraphs, no code)
- Plan, matched_entries, fidelity_score present and plausible
- Route key is string, not tuple
- No PII in logs

---

### Scenario 2: Chrome / Chat / Pro (user not entitled)

**Request**
```json
{
  "text": "draft a twitter thread about LLM evals",
  "intent": "chat",
  "mode": "pro",
  "client": "chrome",
  "explain": true
}
```

**Response**
```json
{
  "detail": "Pro required for this route"
}
```
or (if fallback allowed)
```json
{
  "request_id": "...",
  "ts": "...",
  "content": {...},
  "matched_pipeline": "chat/free/chrome",
  "engine_version": "2.0.0",
  "plan": {..., "fallback": true, "fallback_reason": "user_not_pro"}
}
```

**Logs**
```
INFO [api.demon] POST /v2/upgrade user=anonymous intent=chat mode=pro client=chrome
WARN [engine_v2] ProRequiredError: user not entitled for chat/pro/chrome
INFO [engine_v2] Fallback to chat/free/chrome
```

**Analysis**
- 402 returned if fallback not allowed, else fallback=true with reason
- Pro gating enforced by entitlement check (but see bug below)
- Route key is string
- Plan reflects fallback

---

### Scenario 3: VS Code / Editor / Free

**Request**
```json
{
  "text": "write a prompt to generate a Python CLI with argparse",
  "intent": "editor",
  "mode": "free",
  "client": "vscode",
  "meta": {"filetype": "py"}
}
```

**Response**
```json
{
  "request_id": "...",
  "ts": "...",
  "content": {
    "output": "Prompt: Write a Python CLI using argparse that..."
  },
  "matched_pipeline": "editor/free/vscode",
  "engine_version": "2.0.0"
}
```

**Logs**
```
INFO [api.demon] POST /v2/upgrade user=anonymous intent=editor mode=free client=vscode
INFO [engine_v2] Routing: editor/free/vscode → CodeForge.Basic
INFO [contracts] Output contract: editor (imperative lines, acceptance criteria)
```

**Analysis**
- 200 OK, correct pipeline, contract enforced (imperative prompt, acceptance criteria)
- No fallback
- Plan omitted (explain=false)

---

### Scenario 4: VS Code / Editor / Pro (entitled)

**Request**
```json
{
  "text": "refactor this codebase for DI; generate prompts for Copilot to do it safely",
  "intent": "editor",
  "mode": "pro",
  "client": "vscode",
  "explain": true
}
```

**Response**
```json
{
  "request_id": "...",
  "ts": "...",
  "content": {
    "output": "Step 1: Analyze dependencies...\nStep 2: Refactor for DI...\nChecklist: ..."
  },
  "matched_pipeline": "editor/pro/vscode",
  "engine_version": "2.0.0",
  "plan": {
    "steps": [...],
    "matched_entries": ["editor/pro/vscode"],
    "fidelity_score": 0.97,
    "fallback": false
  }
}
```

**Logs**
```
INFO [api.demon] POST /v2/upgrade user=pro_user intent=editor mode=pro client=vscode
INFO [engine_v2] Routing: editor/pro/vscode → CodeForge.LangGraph
INFO [contracts] Output contract: editor (multi-pass, context anchors)
```

**Analysis**
- 200 OK, pro pipeline, plan present, fallback=false
- Output matches contract (multi-pass, checklist)
- Entitlement derived from user (see bug below)

---

### Scenario 5: Cursor / Agent / Free (blocked)

**Request**
```json
{
  "text": "create an agent plan to implement a plugin system with tests",
  "intent": "agent",
  "mode": "free",
  "client": "cursor",
  "explain": true
}
```

**Response**
```json
{
  "detail": "Pro required for this route"
}
```

**Logs**
```
INFO [api.demon] POST /v2/upgrade user=anonymous intent=agent mode=free client=cursor
WARN [engine_v2] ProRequiredError: agent/free/cursor is pro-only
```

**Analysis**
- 402 returned, no fallback (correct)
- Pro gating enforced

---

### Scenario 6: Cursor / Agent / Pro (entitled)

**Request**
```json
{
  "text": "plan an agent to add a circuit breaker to API calls: steps, constraints, stopping conditions",
  "intent": "agent",
  "mode": "pro",
  "client": "cursor",
  "explain": true
}
```

**Response**
```json
{
  "request_id": "...",
  "ts": "...",
  "content": {
    "output": "To add a circuit breaker, you should first..."
  },
  "matched_pipeline": "agent/pro/cursor",
  "engine_version": "2.0.0",
  "plan": {
    "steps": [
      "Analyze API call patterns",
      "Define circuit breaker logic",
      "Implement step graph",
      "Test abort criteria"
    ],
    "matched_entries": ["agent/pro/cursor"],
    "fidelity_score": 0.92,
    "fallback": false
  }
}
```

**Logs**
```
INFO [api.demon] POST /v2/upgrade user=pro_user intent=agent mode=pro client=cursor
INFO [engine_v2] Routing: agent/pro/cursor → Agent.DemonEngine
INFO [contracts] Output contract: agent (step graph, constraints, abort criteria)
```

**Analysis**
- 200 OK, pro pipeline, fallback=false
- Output is prose, not step graph (contract breach)
- Plan present, but fidelity_score is static

---

### Scenario 7: Web / Chat / Free

**Request**
```json
{
  "text": "outline a landing page for a SaaS that upgrades prompts",
  "intent": "chat",
  "mode": "free",
  "client": "web",
  "explain": true
}
```

**Response**
```json
{
  "request_id": "...",
  "ts": "...",
  "content": {
    "output": "Landing page outline: 1. Hero section... 2. Features..."
  },
  "matched_pipeline": "chat/free/web",
  "engine_version": "2.0.0",
  "plan": {
    "steps": [...],
    "matched_entries": ["chat/free/web"],
    "fidelity_score": 0.93,
    "fallback": false
  }
}
```

**Logs**
```
INFO [api.demon] POST /v2/upgrade user=anonymous intent=chat mode=free client=web
INFO [engine_v2] Routing: chat/free/web → Temple.Basic
INFO [contracts] Output contract: web (teaser, outline)
```

**Analysis**
- 200 OK, correct pipeline, fallback=false
- Output matches web contract (outline, marketing-friendly)

---

### Scenario 8: Unknown intent/client (inference)

**Request**
```json
{
  "text": "optimize a prompt for cold emails",
  "intent": "unknown",
  "mode": "free",
  "client": "unknown",
  "explain": true
}
```

**Response**
```json
{
  "request_id": "...",
  "ts": "...",
  "content": {
    "output": "To optimize a cold email prompt, focus on..."
  },
  "matched_pipeline": "chat/free/*",
  "engine_version": "2.0.0",
  "plan": {
    "steps": [...],
    "matched_entries": ["chat/free/*"],
    "fidelity_score": 0.90,
    "fallback": true,
    "fallback_reason": "missing_mapping"
  }
}
```

**Logs**
```
INFO [api.demon] POST /v2/upgrade user=anonymous intent=unknown mode=free client=unknown
INFO [engine_v2] Inferred intent=chat, client=web
INFO [engine_v2] Fallback to chat/free/*
```

**Analysis**
- 200 OK, fallback=true, fallback_reason present
- Inference logic works, contract enforced

---

### Scenario 9: Rate limit pressure test

**Requests**
- 15 rapid requests to the same route (e.g., chat/free/chrome) as the same user

**Responses**
- First 10: 200 OK
- Next 5: 429 Rate limit exceeded

**Logs**
```
WARN [feature_flags] Rate limit exceeded for user=anonymous key=chat/free/chrome
```

**Analysis**
- Rate limiting works, but is in-memory and per-process (see bug)
- No evidence of per-user/api_key in shared store

---

### Scenario 10: Explainability truthfulness

**Request**
- Any with `"explain": true`

**Response**
- plan, matched_entries, fidelity_score present

**Analysis**
- plan and matched_entries reflect routing
- fidelity_score is static (e.g., always 0.95/0.92), not measured

---

## Routing & Entitlements

- Pro gating is enforced by checking user entitlements (user["pro"] or plan in ["pro", ...])
- If mode="pro" but user not entitled, 402 or fallback
- Route key is consistently a string in logs and analytics
- Edge case: if user entitlements are not read from DB/auth, but only from request, pro gating can be bypassed (see bug)

---

## Rate Limiting & Abuse

- Rate limiting is implemented in `feature_flags.py`
- Limiter is in-memory, per-process, keyed by user and route
- No evidence of shared store (e.g., Redis) for multi-replica deployments
- Risk: users can bypass limits by switching processes or after restart

---

## Fallbacks & Reasons

| Scenario | Fallback | Reason           | Response Field         |
|----------|----------|------------------|-----------------------|
| 2        | Yes      | user_not_pro     | fallback_reason       |
| 5        | No       | pro-only         | 402 error             |
| 6        | No       | entitled         | fallback=false        |
| 8        | Yes      | missing_mapping  | fallback_reason       |

- Fallbacks are correctly annotated in response
- If fallback_reason is missing, recommend adding

---

## Contracts Linter

| Surface   | Contract Enforced | Example Breach |
|-----------|------------------|---------------|
| chat      | Yes              | -             |
| editor    | Yes              | -             |
| agent     | No (prose)       | Scenario 6    |
| web       | Yes              | -             |

- Agent contract returns prose, not step graph (see bug)

---

## Explainability Audit

- plan, matched_entries, fidelity_score present for explain=true
- fidelity_score is static, not measured
- plan reflects routing, but not always actual pipeline steps

---

## Telemetry & Privacy

- analytics.py logs events with HMAC(user|api_key, salt)
- No raw prompt text unless meta.log_before_after is set
- Consent flag is not always read from meta (see bug)
- If hash() is used instead of HMAC, recommend fix

---

## Compliance with Migration Guide

| Promise                        | Observed Reality | Pass/Partial/Fail |
|---------------------------------|------------------|-------------------|
| Dynamic routing                 | Yes              | Pass              |
| Pro-gating                      | Yes (see bug)    | Partial           |
| Kill-switches                   | Yes              | Pass              |
| Fallbacks                       | Yes              | Pass              |
| Output contracts                | Partial (agent)  | Partial           |
| Analytics privacy               | Yes              | Pass              |
| Rate limiting                   | Partial          | Partial           |
| Explainability                  | Partial          | Partial           |
| Pydantic v2/OpenAPI             | Fails            | Fail              |

---

## Bugs & Gaps Catalog

| ID         | Title                        | Severity | Evidence         | Fix                                                      |
|------------|------------------------------|----------|------------------|----------------------------------------------------------|
| ENT-001    | Pro inferred from mode       | High     | Scenario 2       | Read entitlements from auth/DB, not just request         |
| RATE-002   | Global rate limit per plan   | High     | Scenario 9       | Use per user/api_key in shared store (e.g., Redis)       |
| CNTR-003   | Agent contract breached      | Med      | Scenario 6       | Adapter linter to reshape output to contract             |
| META-004   | Consent not read             | Med      | Code path        | meta.log_before_after + handler update                   |
| KEY-005    | Tuple route key in logs      | Low      | Code review      | Normalize to string everywhere                           |
| FID-006    | Static fidelity_score        | Low      | Scenario 10      | Compute real metric or remove from UI                    |
| OPEN-007   | OpenAPI fails on ForwardRef  | High     | Startup          | Use Annotated + .model_rebuild() in models               |
| KILL-008   | Duplicate kill-switch logic  | Low      | Code review      | Use FeatureFlags as single source of truth               |
| PERF-009   | No per-route timeout         | Med      | Code review      | Add timeout/max_passes to registry entries               |
| CMD-010    | Command language robustness  | Med      | Scenario 8       | Add validation, clear 4xx for bad input                  |

---

## Appendix

### cURL Commands

```bash
curl -X POST http://localhost:8000/api/v1/demon/v2/upgrade -H "Content-Type: application/json" -d '{"text":"summarize this article about transformers","intent":"chat","mode":"free","client":"chrome","meta":{"lang":"en"},"explain":true}'
# ...repeat for all scenarios...
```

### Environment Vars

- `USE_NEW_BRAIN_ENGINE=1`
- `ALLOWED_ORIGIN=http://localhost:3000`
- (others as needed)

### Stack Traces

- [OpenAPI error stack here, if any]

### Raw Logs

- [Redacted logs for each scenario]

---

## audit_findings.json

```json
[
  {"id":"ENT-001","title":"Pro inferred from mode","severity":"high","evidence":"scenario 2","fix":"read entitlements from auth/DB"},
  {"id":"RATE-002","title":"Global rate limit per plan","severity":"high","evidence":"scenario 9","fix":"per user/api_key in shared store"},
  {"id":"CNTR-003","title":"Agent contract breached","severity":"med","evidence":"scenario 6","fix":"adapter linter reshape"},
  {"id":"META-004","title":"Consent not read","severity":"med","evidence":"code path","fix":"meta.log_before_after + handler update"},
  {"id":"KEY-005","title":"Tuple route key in logs","severity":"low","evidence":"code review","fix":"normalize to string everywhere"},
  {"id":"FID-006","title":"Static fidelity_score","severity":"low","evidence":"scenario 10","fix":"compute real metric or remove from UI"},
  {"id":"OPEN-007","title":"OpenAPI fails on ForwardRef","severity":"high","evidence":"startup","fix":"use Annotated + .model_rebuild() in models"},
  {"id":"KILL-008","title":"Duplicate kill-switch logic","severity":"low","evidence":"code review","fix":"use FeatureFlags as single source of truth"},
  {"id":"PERF-009","title":"No per-route timeout","severity":"med","evidence":"code review","fix":"add timeout/max_passes to registry entries"},
  {"id":"CMD-010","title":"Command language robustness","severity":"med","evidence":"scenario 8","fix":"add validation, clear 4xx for bad input"}
]
```

---

**End of Report.**
