# BRAIN_ENGINE – File Inventory

Total files: **21**

---

## `BRAIN_ENGINE\api\brain_engine.py`
- Language: **python**, Lines: **81**, Tags: `—`
- Top comment/docstring:

> Enforce kill-switch/global pro disable/rate limits

- Functions:
  - `upgrade_v2` — Dynamic routing upgrade endpoint (intent × client × mode).
Backward compatible: infers intent/client if missing.
Returns surface-specific output contract and techniques.
If explain=true, returns plan, fidelity_score, matched_entries.
Logs analytics and (if consented) before/after hashes.

## `BRAIN_ENGINE\api\models.py`
- Language: **python**, Lines: **39**, Tags: `model`
- Classes:
  - `ModeEnum`
  - `ClientEnum`
  - `IntentEnum`
  - `UpgradeRequest`
  - `UpgradeResponse`

## `BRAIN_ENGINE\DEMONSAINT_SCROLL.md`
- Language: **other**, Lines: **14**, Tags: `—`
- Top comment/docstring:

> 🕯️ The DemonSaint Scroll of PromptForgeAI: The Legendary Brain Engine


## `BRAIN_ENGINE\kaiboy.py`
- Language: **python**, Lines: **131**, Tags: `—`
- Top comment/docstring:

> !/usr/bin/env python3

- Functions:
  - `read_first_comment_block`
  - `list_py_symbols`
  - `detect_lang`
  - `summarize_file`
  - `main`

## `BRAIN_ENGINE\MIGRATION_GUIDE.md`
- Language: **other**, Lines: **393**, Tags: `—`
- Top comment/docstring:

> PROMPTFORGEAI Backend: Migration Guide (Old → New Brain Engine)


## `BRAIN_ENGINE\PIPELINE_CONTRACTS.md`
- Language: **other**, Lines: **22**, Tags: `pipeline`
- Top comment/docstring:

> Pipeline Output Contracts by Surface


## `BRAIN_ENGINE\PLAN_BRAIN_ENGINE_INTEGRATION.md`
- Language: **other**, Lines: **49**, Tags: `—`
- Top comment/docstring:

> PLAN: PromptForgeAI Brain Engine Dynamic Routing Integration


## `BRAIN_ENGINE\QA_CHECKLIST.md`
- Language: **other**, Lines: **24**, Tags: `—`
- Top comment/docstring:

> Manual QA Checklist: Brain Engine


## `BRAIN_ENGINE\README.md`
- Language: **other**, Lines: **15**, Tags: `—`
- Top comment/docstring:

> PromptForgeAI Brain Engine (BRAIN_ENGINE/)


## `BRAIN_ENGINE\ROUTING_MATRIX.md`
- Language: **other**, Lines: **60**, Tags: `—`
- Top comment/docstring:

> PromptForgeAI Brain Engine Routing Matrix


## `BRAIN_ENGINE\SAFETY_FLAGS.md`
- Language: **other**, Lines: **21**, Tags: `feature-flags`
- Top comment/docstring:

> Safety Flags & Controls


## `BRAIN_ENGINE\services\brain_engine\adapters.py`
- Language: **python**, Lines: **16**, Tags: `adapter`
- Top comment/docstring:

> Adapters for each surface: apply technique packs and output contracts

- Functions:
  - `apply_surface_adapter`

## `BRAIN_ENGINE\services\brain_engine\analytics.py`
- Language: **python**, Lines: **14**, Tags: `—`
- Top comment/docstring:

> Analytics and feedback hooks for Brain Engine (privacy-safe)

- Functions:
  - `log_event`
  - `log_before_after`

## `BRAIN_ENGINE\services\brain_engine\engine.py`
- Language: **python**, Lines: **70**, Tags: `—`
- Top comment/docstring:

> Preprocess

- Classes:
  - `BrainEngineRouter`
- Functions:
  - `__init__`
  - `infer_intent`
  - `route`

## `BRAIN_ENGINE\services\brain_engine\errors.py`
- Language: **python**, Lines: **9**, Tags: `errors`
- Classes:
  - `ProRequiredError`
  - `KillSwitchError`
  - `PipelineNotFound`

## `BRAIN_ENGINE\services\brain_engine\feature_flags.py`
- Language: **python**, Lines: **67**, Tags: `feature-flags`
- Top comment/docstring:

> Feature Flags and Kill Switches for Brain Engine

- Classes:
  - `FeatureFlags`
- Functions:
  - `__init__`
  - `enable_killswitch`
  - `disable_killswitch`
  - `is_killswitch`
  - `set_telemetry`
  - `is_telemetry_enabled`
  - `set_global_pro_disabled`
  - `is_global_pro_disabled`
  - `check_rate_limit`

## `BRAIN_ENGINE\services\brain_engine\pipeline_registry.py`
- Language: **python**, Lines: **55**, Tags: `pipeline, registry`
- Top comment/docstring:

> Pipeline Registry: intent × mode × client dynamic routing for PromptForgeAI Brain Engine

- Classes:
  - `PipelineRegistry`
- Functions:
  - `__init__`
  - `set_killswitch`
  - `is_killswitch`
  - `is_pro_only`
  - `lookup`
  - `get_engine_version`

## `BRAIN_ENGINE\services\brain_engine\technique_packs.py`
- Language: **python**, Lines: **65**, Tags: `—`
- Top comment/docstring:

> Technique packs and output contracts for each surface (Chrome, VS Code, Cursor, Web)

- Functions:
  - `get_technique_pack`

## `BRAIN_ENGINE\tests\brain_engine\test_explainability.py`
- Language: **python**, Lines: **24**, Tags: `—`
- Functions:
  - `test_explain_fields`

## `BRAIN_ENGINE\tests\brain_engine\test_routing.py`
- Language: **python**, Lines: **43**, Tags: `—`
- Top comment/docstring:

> Enable kill switch for a key

- Functions:
  - `router`
  - `test_exact_hit`
  - `test_wildcard_fallback`
  - `test_pro_gating`
  - `test_killswitch`
  - `test_backward_compatibility`
  - `test_pipeline_not_found`

## `BRAIN_ENGINE\tests\brain_engine\test_surface_contracts.py`
- Language: **python**, Lines: **39**, Tags: `—`
- Functions:
  - `router`
  - `test_chrome_chat_contract`
  - `test_vscode_editor_contract`
  - `test_cursor_agent_contract`
  - `test_web_temple_contract`
