# PLAN: PromptForgeAI Brain Engine Dynamic Routing Integration

## Vision

Replace hardcoded pipeline routing with a registry-driven, intent × client × mode matrix. Support wildcards, pro-gating, kill-switches, and graceful fallbacks. Enable explainable, testable, and extensible pipeline selection for all clients.

## Scope
- All new code in BRAIN_ENGINE/ (for migration later)
- Registry, feature flags, errors, models, and docs
- Tests for routing, pro-gating, kill-switch, fallbacks

## Key Components
- `pipeline_registry.py`: Routing matrix, lookup logic, wildcards
- `feature_flags.py`: Kill-switches, telemetry toggles
- `errors.py`: Custom exceptions for routing
- `models.py`: Enums and request/response schemas
- `engine.py`: Routing integration (to be implemented)
- `ROUTING_MATRIX.md`: Human-readable routing table and rules

## Routing Rules
- Lookup: exact → intent+mode+* → intent+*+client → chat/free/*
- Pro-only: 402/403 if not entitled
- Kill-switch: 503 if enabled
- No mapping: fallback to chat/free/*
- Attach matched_pipeline and engine_version in response

## Default Mappings
See `ROUTING_MATRIX.md` for full table and examples.

## Preprocessing
- Infer intent if missing (see table)
- Normalize meta and pass through

## Error Mapping
- ProRequiredError → HTTP 402 (upsell)
- KillSwitchError → HTTP 503
- PipelineNotFound → HTTP 500
- Timeout/retries → HTTP 504

## Telemetry
- If enabled, log only event names (never raw input/output)

## Tests
- Exact-hit, wildcard, pro-gating, kill-switch, fallback, backward compatibility

## Delivery
- PR: `feat(engine): dynamic intent+client routing via pipeline registry`
- All code/docs in BRAIN_ENGINE/ for review and migration
