# PromptForge.ai Architecture & Migration Log

## Purpose
This file documents all crucial project changes, architectural decisions, and the reasoning behind them. It serves as a reference for future migrations, onboarding, and innovation tracking.

---

### [2025-08-21] Transitioning from Firestore to Postgres (Forever Architecture)

**Why:**
- Firestore lacks true async support, making it awkward for modern FastAPI apps.
- Async hacks (e.g., wrapping sync Firestore calls) are not sustainable for a production SaaS.
- Postgres offers:
  - Native async support (with async ORM like SQLAlchemy 2.0 or Prisma)
  - Strong schema and constraints for marketplace data
  - Robust transactions
  - Advanced queries and analytics
  - JSONB columns for flexible fields (tags, useCases, etc.)
  - Ecosystem support (pgvector for AI, Timescale for time-series)

**What:**
- Documenting all major changes and decisions in this file.
- Refactoring backend code to remove Firestore-specific async hacks.
- Planning a new Postgres schema for marketplace entities (users, prompts, prompt_versions, purchases, listings).
- Standardizing field naming (prefer snake_case for DB, camelCase for API if needed).
- Ensuring all transactional logic is robust and async-friendly.

**Next Steps:**
1. Draft a Postgres schema for core marketplace entities.
2. Refactor Firestore-dependent code to be DB-agnostic or Postgres-ready.
3. Log every major migration, refactor, and architectural decision here.

---

**This file is the single source of truth for all major backend migrations and architectural changes.**


---

## [2025-08-21] PromptForgeAI Brain Engine & Compendium Integration

**Reference Artifact:**
- `promptforge_compendium_v1_legend.pdf` (attached in repo)
- Legendary JSON compendium (all techniques, pipelines, categories, rules)

**How the Brain Engine Works:**

1. **Compendium as the Brain**
   - The compendium JSON is the central knowledge base: all techniques, pipelines, categories, and rules.
   - It is stored in MongoDB (`compendium` collection, key: `grand_unified`).

2. **Request Flow**
   - User input is analyzed for signals (needs_json, is_ambiguous, is_numeric, needs_facts, long_doc, persona_requested, creative, etc.).
   - The system ranks techniques from the compendium that best fit the detected signals.
   - A pipeline is selected (from compendium or synthesized from top techniques).
   - The pipeline is executed stage-by-stage, each stage running one or more techniques, passing context forward.
   - Optional evaluation/refinement (self-consistency, self-refine, verification).
   - All runs, signals, plans, and outputs are logged for provenance and analytics.

3. **Pipeline Example**
```json
{
  "id": "pipeline_alchemist",
  "name": "The Alchemist™ Knowledge Synthesizer",
  "objective": "Evidence-backed answers from multiple sources.",
  "stages": [
    { "name": "Retrieve & Rank", "techniques_used": ["retrieval_augmented_generation"], "inputs": ["user_input"], "outputs": ["retrieved_docs"] },
    { "name": "Self-Heal Retrieval", "techniques_used": ["self_healing_rag"], "inputs": ["retrieved_docs"], "outputs": ["clean_docs"] },
    { "name": "Evidence Graph Build", "techniques_used": ["evidence_graph_synthesis"], "inputs": ["clean_docs"], "outputs": ["evidence_graph"] },
    { "name": "Graph Reasoning", "techniques_used": ["graph_of_thoughts","chain_of_thought"], "inputs": ["evidence_graph"], "outputs": ["final_output"] }
  ],
  "metrics": ["citation_coverage","contradiction_rate","answer_factuality"],
  "artifacts": ["evidence_graph","citation_list"]
}
```

4. **Pipeline Execution Skeleton**
```python
ctx = {"user_input": payload["input"], "gen_params": payload.get("gen_params", {})}
async def run_pipeline(pipeline, adapter, evaluator=None):
    logs = []
    for stage in pipeline["stages"]:
        stage_inputs = {k: ctx.get(k) for k in stage.get("inputs", [])}
        for tid in stage.get("techniques_used", []):
            res = await adapter.run(tid, {**ctx, **stage_inputs})
            out_key = (stage.get("outputs") or ["working_ctx"])[-1]
            ctx[out_key] = res["output"]
            logs.append({"stage": stage["name"], "technique": tid, "preview": res["output"][:160]})
    if evaluator and payload.get("refine"):
        ctx["final_output"] = await evaluator.self_refine(adapter.llm_call, ctx.get("final_output", ctx.get("working_ctx","")))
    return {"final": ctx.get("final_output", ctx.get("working_ctx","")), "trace": logs}
```

5. **Decision Logic**
   - Signal extraction tags the input.
   - Rules engine matches signals to techniques (using compendium weights).
   - Planner picks the best pipeline or synthesizes one.
   - Executor runs each stage, passing context forward.
   - Evaluator (optional) polishes the output.
   - Ledger logs everything for traceability and future improvement.

**Reference:**
- All backend logic, pipeline selection, and prompt strategy must reference the compendium JSON and this architecture log for consistency and future-proofing.

---
