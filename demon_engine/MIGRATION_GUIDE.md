# PROMPTFORGEAI Backend: Migration Guide (Old → New Brain Engine)

---

## Table of Contents
1. **Overview**
2. **Why Migrate?**
3. **Directory Structure: Old vs New**
4. **API Entrypoints: What Changes?**
5. **Engine Core: Old vs New**
6. **Routing & Pipeline Logic**
7. **Feature Flags, Kill-Switches, and Pro-Gating**
8. **Analytics & Explainability**
9. **Models & Contracts**
10. **Testing & QA**
11. **Migration Steps (Checklist)**
12. **Rollback & Dual-Path Operation**
13. **FAQ & Troubleshooting**
14. **Appendix: Code Snippets & Examples**

---

## 1. Overview

This document provides a comprehensive, step-by-step guide to migrating the PromptForgeAI backend from the legacy brain engine to the new, production-grade core in `BRAIN_ENGINE/`. It covers every architectural, code, and operational change, ensuring zero downtime and full backward compatibility during rollout.

---

## 2. Why Migrate?

- **Dynamic Routing:** Intent × mode × client matrix, wildcards, and fallback logic.
- **Surface-Specific Pipelines:** Adapters for extension, web, API, etc.
- **Feature Flags & Kill-Switches:** Per-key, per-surface, and global controls.
- **Pro-Gating & Rate Limiting:** Enforce business logic at the routing layer.
- **Explainability:** Query flag for pipeline introspection.
- **Analytics:** Privacy-safe, event-driven logging.
- **Testability & Docs:** Full test suite, ironclad documentation, and QA matrix.

---

## 3. Directory Structure: Old vs New

**Old:**
```
api/brain_engine.py
services/brain_engine/engine.py
services/brain_engine/langgraph_adapter.py
services/brain_engine/compendium_loader.py
api/models.py
```

**New:**
```
BRAIN_ENGINE/
  api/brain_engine.py
  api/models.py
  services/brain_engine/
    engine.py
    pipeline_registry.py
    feature_flags.py
    errors.py
    adapters.py
    technique_packs.py
    analytics.py
  tests/brain_engine/
  DEMONSAINT_SCROLL.md
  ROUTING_MATRIX.md
  PIPELINE_CONTRACTS.md
  SAFETY_FLAGS.md
  QA_CHECKLIST.md
  README.md
```

---

## 4. API Entrypoints: What Changes?

- **Old:** Endpoints `/prompt/quick_upgrade` and `/prompt/upgrade` call the legacy `BrainEngine`.
- **New:** Endpoints are preserved, but now call the new router/engine in `BRAIN_ENGINE/`.
- **Migration:**
  - Add a feature flag/env var (e.g., `USE_NEW_BRAIN_ENGINE`) to toggle between old and new.
  - Update imports and instantiation to use the new engine.
  - Ensure request/response models remain unchanged for clients.

---

## 5. Engine Core: Old vs New

| Aspect                | Old Engine                                 | New Engine (BRAIN_ENGINE/)                |
|-----------------------|--------------------------------------------|-------------------------------------------|
| Routing               | Hardcoded, minimal                         | Registry-driven, dynamic, fallback logic  |
| Pipeline Differentiation | Quick/Full only                        | Surface-specific, intent-aware, adapters  |
| Feature Flags         | None                                       | Per-key, per-surface, global, pro-gating  |
| Analytics             | Minimal, ad-hoc                            | Privacy-safe, event-driven, extensible    |
| Explainability        | None                                       | Built-in, query flag, pipeline introspect |
| Error Handling        | Basic exceptions                           | Custom errors, safe fallback, logging     |
| Testability           | Minimal                                    | Full pytest suite, contracts, QA matrix   |
| Documentation         | Sparse                                     | Ironclad, book-like, up-to-date          |

---

## 6. Routing & Pipeline Logic

- **Old:**
  - `BrainEngine` selects techniques based on simple signals and mode.
  - Pipelines are composed ad-hoc, with little surface differentiation.
- **New:**
  - `pipeline_registry.py` defines a routing matrix (intent × mode × client), with wildcards and fallbacks.
  - `adapters.py` and `technique_packs.py` provide surface-specific logic.
  - Pro-gating, kill-switches, and feature flags are enforced at the routing layer.

---

## 7. Feature Flags, Kill-Switches, and Pro-Gating

- **Old:** No feature flag or kill-switch support.
- **New:**
  - `feature_flags.py` provides per-key, per-surface, and global kill-switches.
  - Pro-gating and rate limiting are enforced before pipeline execution.
  - Flags can be toggled at runtime for safe rollout and rollback.

---

## 8. Analytics & Explainability

- **Old:** Minimal analytics, no explainability.
- **New:**
  - `analytics.py` logs all key events in a privacy-safe manner.
  - The `explain` query flag returns pipeline structure, routing decisions, and feature flag status for any request.

---

## 9. Models & Contracts

- **Old:** All Pydantic models in `api/models.py`.
- **New:**
  - Models are preserved for backward compatibility.
  - New engine imports and uses the same models, or shared models are moved to a common location if needed.
  - Output contracts for each surface are documented in `PIPELINE_CONTRACTS.md`.

---

## 10. Testing & QA

- **Old:** Minimal or ad-hoc tests.
- **New:**
  - Full pytest suite in `tests/brain_engine/` covers routing, contracts, explainability, and safety.
  - Manual QA checklist in `QA_CHECKLIST.md`.
  - All new features are test-driven and documented.

---

## 11. Migration Steps (Checklist)

1. **Preparation:**
   - Review all new code and docs in `BRAIN_ENGINE/`.
   - Ensure all tests pass (`pytest BRAIN_ENGINE/tests/brain_engine/`).
2. **API Entrypoint Refactor:**
   - Add a feature flag/env var (e.g., `USE_NEW_BRAIN_ENGINE`).
   - Update `api/brain_engine.py` to import and instantiate the new engine when the flag is set.
   - Ensure all endpoints pass through request data, user, and context as before.
3. **Model Sync:**
   - Import models from `api/models.py` in the new engine, or move to a shared location if needed.
4. **Analytics & Flags:**
   - Wire up analytics and feature flag checks in the API layer if not already handled in the new engine.
   - Expose the `explain` flag in the API if needed.
5. **Testing:**
   - Add tests to ensure both old and new engines produce equivalent results for the same inputs.
   - Run the full test suite and manual QA checklist.
6. **Rollout:**
   - Deploy with the feature flag off (old engine active).
   - Enable the flag for internal users and monitor logs/analytics.
   - Gradually roll out to all users.
7. **Cleanup:**
   - Once stable, remove the old engine and feature flag.
   - Archive or delete deprecated files per safety protocol.

---

## 12. Rollback & Dual-Path Operation

- **Dual-path logic** in the API entrypoint allows instant rollback by toggling the feature flag.
- **No downtime or breaking changes** for clients.
- **All new features are available when the flag is enabled.**

---

## 13. FAQ & Troubleshooting

- **Q: What if a client sees a different output?**
  - A: Use the `explain` flag to debug routing and pipeline decisions.
- **Q: How do I disable a feature or pipeline?**
  - A: Use the kill-switches in `feature_flags.py`.
- **Q: How do I add a new surface or intent?**
  - A: Update `pipeline_registry.py` and add a new adapter in `adapters.py`.
- **Q: How do I test analytics?**
  - A: Check logs and use the test suite in `tests/brain_engine/`.

---

## 14. Appendix: Code Snippets & Examples

### **A. API Entrypoint Dual-Path Example**
```python
import os
USE_NEW_BRAIN_ENGINE = os.getenv("USE_NEW_BRAIN_ENGINE", "0") == "1"

if USE_NEW_BRAIN_ENGINE:
    from BRAIN_ENGINE.services.brain_engine.engine import BrainEngineRouter
    brain_engine = BrainEngineRouter(...)
else:
    from services.brain_engine.engine import BrainEngine
    brain_engine = BrainEngine(...)

# ...existing FastAPI endpoints...
# In each endpoint, call brain_engine.upgrade(...) or route as appropriate
```

### **B. Feature Flag Usage**
```python
from BRAIN_ENGINE.services.brain_engine.feature_flags import is_feature_enabled
if not is_feature_enabled("prompt_upgrade", user):
    raise HTTPException(status_code=403, detail="Feature disabled")
```

### **C. Analytics Event Logging**
```python
from BRAIN_ENGINE.services.brain_engine.analytics import log_event
await log_event(user_id=user["uid"], action="prompt_upgrade", ...)
```

### **D. Explainability Flag**
```python
# Add ?explain=true to any API call to get pipeline/routing details
```

---

## Final Notes
- **All new code, docs, and tests are in `BRAIN_ENGINE/` and ready for production.**
- **Migration is zero-downtime, fully reversible, and client-safe.**
- **For questions, see DEMONSAINT_SCROLL.md or contact the core team.**

---
🔥 Upgrades I’m Adding To Your Migration Plan (so it’s foolproof)
1) Go/No-Go Readiness Checklist (must be ✅ before canary)

 Feature flag wired: USE_NEW_BRAIN_ENGINE=1 toggles new core; 0 reverts instantly.

 Routing matrix: All keys present (intent×mode×client), with wildcards and fallback entries.

 Pro-gating: agent/*/cursor returns 402/403 when not entitled.

 Kill-switches: Per-key + Global Pro disable flags flip without redeploy.

 Contracts locked: Output shape differs per surface (chat/editor/agent/web) and is documented in PIPELINE_CONTRACTS.md.

 Explainability: ?explain=true returns plan, matched entries, fidelity score.

 Privacy: Anonymous before/after capture is opt-in, redaction path passes test vectors.

 Rate limits: Free vs Pro caps configured; burst control per client.

 Backcompat: Legacy calls (no intent/client) route to web/chat/free.

 Tests green: Routing, fallbacks, pro-gating, kill-switch, contract snapshots.

 Runbooks written: Canary, rollback, incident, comms (below).

2) Canary Rollout Plan (production, zero drama)

Phase A (10%) – 2–4 hours
Watch: p50/p95 latency, 5xx rate, 402 spikes, fallback_used, kill-switch hits, accept-rate, edit-delta.

Phase B (50%) – 4–8 hours
Same metrics + business: conversion to Pro, churn of free.

Phase C (100%) – after two stable windows
Freeze old engine for 48h; keep flag for instant rollback.

Hard thresholds (SLOs):

Free: p95 ≤ 1.5s, error ≤ 0.5%

Pro: p95 ≤ 2.5s, error ≤ 1%

Fallback rate ≤ 3% (otherwise investigate)

3) Observability Pack (must-have dashboards)

Routing Overview

Requests by intent/mode/client

Success vs 4xx vs 5xx

402 counts (Pro required) by key

Fallbacks used

Latency

p50/p95 per key

Timeout/Retry counts

Quality Signals

Accept-rate (implicit)

Edit-delta trend (if captured)

Fidelity score distribution (explain mode samples)

Safety

Killswitch activations (by key)

Rate-limit blocks

Redaction drop rate

4) Operational Runbooks (copy into your repo)
A) Rollback

Set USE_NEW_BRAIN_ENGINE=0.

Disable all new-engine feature flags.

Verify canary endpoint returns old engine headers/markers.

Post incident note with timestamps + metrics deltas.

B) Pro Degradation

Flip Global Pro Disable → enable Pro→Free fallback (config).

Post banner to clients: “Pro engine degraded, temporarily using free pipeline.”

Track conversion dip; revert flag when stable.

C) Key Outage (single surface)

Flip kill-switch for intent/mode/client key.

Confirm 503 for that key only; others unaffected.

Open issue with notes & sample request.

5) Client Integration Checklist (Web / Chrome / VS Code / Cursor)

 All clients add client & (if available) intent in payload.

 Chrome defaults to intent=chat.

 VS Code defaults to intent=editor.

 Cursor defaults to intent=agent (Pro-only).

 Paddle/Razorpay entitlements included in auth middleware.

 Upsell path on 402/403: open pricing URL; don’t lose user input.

 Settings expose apiBase, plan, telemetry toggle (off by default).

6) Contract Snapshots (enforce output “shape”)

Create snapshot tests that validate structure, not wording:

chat: 1–2 paragraphs + optional bullet plan.

editor: imperative lines, acceptance criteria bullets, optional test hints.

agent: numbered step graph, constraints, stop conditions.

web: readable outline; marketing-friendly formatting.

If shape violated → mark contract breach and surface corrective message.

7) Performance & Load Targets

Warm caches/models before canary.

Synthetic load: 100 RPS short bursts on chat/free/*, 20 RPS on editor/pro/vscode.

Budget: Pro multi-pass ≤ 1.8× Free latency.

Memory headroom ≥ 30% under Phase B traffic.

8) Data & Compliance Notes (protect DemonSaint’s throne)

Reda
