## Endpoint Reference & Full Audit Plan

This document collects discovery results and implements the audit plan for the three endpoints requested (the `quick_upgrade` endpoint must NOT be modified).

### Files referencing endpoints

1) POST `/api/v1/prompt/upgrade` (Full Mode)
- `api/brain_engine.py`  — canonical handler (do NOT modify `/prompt/quick_upgrade` code)
- `extensions/pfai/workbench.js` — client chooses `/prompt/upgrade` for full mode
- docs & audits: `swaggeruiendpoints.md`, `ENDPOINT_CLEANUP_ANALYSIS.md`, `API_ENDPOINT_COMPREHENSIVE_DOCUMENTATION.md`, `API_ENDPOINT_ANALYSIS_REPORT.json`, etc.

2) POST `/api/v1/demon/route`
- `api/demon.py` — unified route handler
- `demon_engine/services/brain_engine/pfcl.py` — PFCL parsing / technique selection references
- docs & audits: `swaggeruiendpoints.md`, `SECURITY_IMPLEMENTATION_PLAN.md`, `ENDPOINT_CLEANUP_ANALYSIS.md`

3) POST `/api/v1/demon/v2/upgrade`
- `api/demon.py` — `upgrade_v2` handler
- client references: `pfa-vscode-extension/src/commands/upgradeDeep.ts` (calls `/demon/v2/upgrade`)
- docs & audits: `PROMPTFORGEAI_DemonEngine_Forensic_Audit_20250827.md`, `ENDPOINT_CLEANUP_ANALYSIS.md`

---

## Deep endpoint descriptions and runtime flow (to be added to repo docs)

### 1) `/api/v1/prompt/upgrade` (Full Mode — PRO)
- Purpose: run the explainable Brain Engine full pipeline to upgrade prompts. Returns upgraded prompt, plan, diffs, fidelity score, and matched entries.
- Auth & billing: enforced by `@require_pro_plan` and `require_credits_and_rate_limit("brain.full_upgrade", 8, 1)` dependency in `api/brain_engine.py`.
- Important: This endpoint is heavy and may call external provider(s). Do NOT block or modify the verified `quick_upgrade` path; add async job queue behind a feature flag if needed.

Flow notes and hardening checklist:
- Validate `text` exists and is within allowed length.
- Ensure `explain` option is boolean and limited in size; if `explain=true` return a capped plan or a paginated explain object.
- Ensure atomic decrement of credits via `require_credits_and_rate_limit` (optimistic lock or DB transaction).
- Mask prompts in logs; only log analytics if `analytics_consent` true for user.

### 2) `/api/v1/demon/route` (Demon Engine router)
- Purpose: unified routing endpoint that parses PFCL/prompt, selects techniques (compendium.json), renders fragments, enforces contracts, and returns a compact surface-shaped `content`.

Flow notes and hardening checklist:
- Validate `meta` size and `text` length (already present in code).
- Ensure `explain` is boolean; if true, return `plan` and `final_prompt` but cap the size.
- Telemetry must be opt-in for raw prompt logs. `log_event()` calls are used — ensure they respect consent flags.

### 3) `/api/v1/demon/v2/upgrade` (Dynamic upgrade V2)
- Purpose: Next-gen upgrade with intent/client inference, optional analytics, safe fallbacks, rate-limiting, and kill-switch.

Flow notes and hardening checklist:
- Apply kill-switch checks (already present in code via `features.is_killswitch`).
- Enforce strong rate-limiting per-user and per-key (verify `features.check_rate_limit` implementation).
- Analytics: require explicit consent (`meta.log_before_after` or `meta.analytics_consent`) before storing or transmitting before/after prompt hashes. Do not persist raw prompts unless consented.
- Implement safe fallback and avoid infinite loops in routing (use `allow_fallback=True` and clear retry limits).

---

## Centralization: `src/shared/api.js`

I created `src/shared/api.js` containing canonical functions:
- `canonicalizeApiBase(raw)`
- `getStoredApiBase()`
- `apiFetch(path, opts)` — logs request/response, masks PII
- `normalizeUserPayload(raw)`

Extension and client code should import and use this instead of local `apiFetch` duplicates (I will patch extension files to import it in the next iteration).

---

## Tests & Smoke checks

Smoke tests must run against a reachable dev server. Required env vars:
- `PFAI_API_BASE` (e.g. `http://localhost:8080/api/v1`)
- `PFAI_SERVICE_TOKEN` (bearer token for test user)

If missing, fail with machine-readable block:
```
{
	"status":"failed",
	"reason":"MISSING_ENV",
	"missing": ["PFAI_API_BASE","PFAI_SERVICE_TOKEN"],
	"instructions":"Set those env vars locally and re-run"
}
```

Smoke test commands (curl) — replace $API and $TOKEN:

- Quick upgrade (should remain unchanged):
```
curl -X POST "$API/prompt/quick_upgrade" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"text":"short prompt"}'
```

- Demon route:
```
curl -X POST "$API/demon/route" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"text":"summarize this", "mode":"free", "client":"chrome"}'
```

- Demon v2 without consent (analytics not logged):
```
curl -X POST "$API/demon/v2/upgrade" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"text":"test", "mode":"free", "client":"chrome", "meta": {"log_before_after": false } }'
```

- Demon v2 with consent (analytics logged):
```
curl -X POST "$API/demon/v2/upgrade" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"text":"test", "mode":"free", "client":"chrome", "meta": {"log_before_after": true } }'
```

Expected minimal response shapes:
- `/prompt/upgrade` (200): `{ "data": { "upgraded": "...", "plan": {...}, "fidelity_score": 0.9 }, "message": "Prompt upgraded via Brain Engine (Full Mode)" }`
- `/demon/route` (200): `{ "request_id": "dem-...", "content": {...}, "matched_pipeline": "...", "engine_version": "..." }`
- `/demon/v2/upgrade` (200): `{ "upgraded": "...", "matched_pipeline": "...", "engine_version": "..." }`

---

## Client patch plan (extension + VSCode)

- Replace local `apiFetch` with `src/shared/api.js` in:
	- `extensions/pfai/src/background.js`
	- `extensions/pfai/src/workbench.js`
	- `extensions/pfai/src/intelligence.js`
	- `pfa-vscode-extension/src/commands/upgradeDeep.ts` (use canonical API client)

- Ensure network errors surface to UI with friendly messages and a retry button.

---

## CSP/CORS / Manifest

- Add explicit `host_permissions` and `content_security_policy.connect-src` entries for dev (`http://localhost:8080`) and prod API hosts found in config. Do not add wildcards. This will be added to `extensions/pfai/manifest.json` behind a feature flag if present.

---

## Logging & Privacy changes

- All server logs that may contain user content must respect `analytics_consent` and mask PII.
- Analytics store must only contain consented hashes or anonymized telemetry.

---

## Rate limits & abuse

- Verify `features.check_rate_limit` and `require_credits` implement token-bucket/redis logic. If missing, add Redis-backed limiter behind feature flag.

---

## PR & commits to create (planned)

1. `chore(api): centralize apiFetch + canonicalize apiBase` — adds `src/shared/api.js`, updates imports in extension & VSCode clients.
2. `fix(quick): ensure quick_upgrade is low-latency + add tests` — verify `quick_upgrade` does not perform heavy sync tasks; add smoke tests that assert quick path remains fast.
3. `feat(demon): harden /demon/route and /demon/v2/upgrade (consent, rate-limit, privacy)` — server-side hardening and privacy checks (behind feature flags if risky).
4. `test(integration): add smoke-checks for quick/route/v2` — add node-based smoke test runner.
5. `chore(manifest): add host_permissions + connect-src for API hosts` — update extension manifest with explicit hosts.

---

## Failure handling

If any required env or service is missing, fail with the machine-readable block above and stop — do NOT proceed with test runs or commit changes that depend on missing secrets.

---

## What I will do next (automated):
1. Patch extension and client to import and use `src/shared/api.js` (without changing quick_upgrade behavior).
2. Add smoke test scripts under `tests/smoke/` that use `PFAI_API_BASE` and `PFAI_SERVICE_TOKEN` from env.
3. Run the smoke tests locally; if missing env, return machine-readable failure block.

I will now proceed with step 1 (client imports) and step 2 (smoke test scaffolding). If any required env is missing I will stop and return the failure block.

