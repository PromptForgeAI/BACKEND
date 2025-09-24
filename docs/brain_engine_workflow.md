# The Brain Engine of PromptForgeAI: An Ancient Scroll

## Table of Contents
1. Introduction
2. The Philosophy of the Brain Engine
3. High-Level Architecture
4. The Upgrade Workflow: Step by Step
5. Free vs Pro: The Duality of Power
6. Core Components and Their Roles
7. Complexity, Edge Cases, and Safeguards
8. Extensibility and Future Visions
9. Glossary of Terms
10. Appendix: Code Pointers

---

## 1. Introduction

The Brain Engine is the heart of PromptForgeAI, the ancient mechanism that transmutes raw prompts into refined, powerful instructions. It is the unifying force behind the website, Chrome extension, and VS Code extension, ensuring all users—novice or pro—receive the best possible upgrades for their text.

## 2. The Philosophy of the Brain Engine

- **Unification:** One backend, many clients. All prompt upgrades flow through the same sacred API.
- **Entitlement:** The engine respects the user's status—Free or Pro—guiding them to the appropriate path.
- **Extensibility:** Designed to evolve, the engine can absorb new models, pipelines, and logic as the AI arts advance.

## 3. High-Level Architecture

- **API Layer:** Receives requests at `/v1/upgrade`.
- **Router:** Decides which pipeline (Free or Pro) to invoke based on user plan.
- **Pipeline(s):** Chains of logic, models, and tools that process the prompt.
- **Postprocessor:** Cleans and finalizes the output.
- **Response:** Returns the upgraded text or an error/upsell if needed.

## 4. The Upgrade Workflow: Step by Step

1. **Invocation:**
   - Client sends a POST to `/v1/upgrade` with `{ input, mode, client }`.
2. **Authentication & Entitlement:**
   - Validates API key/token and checks user plan.
3. **Preprocessing:**
   - Normalizes input, strips dangerous content, applies safety checks.
4. **Pipeline Selection:**
   - `mode: free` → Basic LLM pipeline (e.g., GPT-3.5, single-step).
   - `mode: pro` → Legendary LangGraph pipeline (multi-step, multi-model, tool use, advanced reasoning).
5. **Processing:**
   - Applies prompt rewriting, context enrichment, templates, and (for Pro) multi-stage reasoning.
   - May call out to external APIs, internal knowledge, or toolchains.
6. **Postprocessing:**
   - Cleans up output, ensures format, applies final safety/quality checks.
7. **Response:**
   - Returns `{ output }` on success.
   - Returns 402/403 if Pro is required but not entitled.
   - Returns 4xx/5xx for errors, with clear messages.

## 5. Free vs Pro: The Duality of Power

- **Free Path:**
  - Fast, single-model, basic prompt upgrades.
  - Good for everyday use, but limited in depth and creativity.
- **Pro Path:**
  - Unlocks the "legendary" LangGraph pipeline.
  - Multi-step reasoning, tool use, advanced context, and higher quality.
  - May chain multiple LLMs, use retrieval, or apply custom logic.

## 6. Core Components and Their Roles

- **api/brain_engine.py:** Entrypoint for all upgrade requests.
- **services/brain_engine/engine.py:** Core logic for pipeline orchestration.
- **langgraph_adapter.py:** Connects to the advanced LangGraph pipeline for Pro users.
- **compendium_loader.py:** Loads prompt templates, context, and knowledge.
- **models.py:** Defines data structures for requests and responses.

## 7. Complexity, Edge Cases, and Safeguards

- **Input Validation:** Ensures no prompt injection, malicious content, or unsupported formats.
- **Timeouts & Retries:** Protects against slow or failing model calls.
- **Fallbacks:** If Pro pipeline fails, may fallback to Free or return a clear error.
- **Logging & Monitoring:** Tracks usage, errors, and performance (never logs raw prompt content by default).
- **Rate Limiting:** Prevents abuse and ensures fair usage.

## 8. Extensibility and Future Visions

- **New Pipelines:** Easily add new models, chains, or tools.
- **Custom Modes:** Support for more granular user plans or experimental features.
- **Plugin System:** (Planned) Allow third-party or user-defined prompt upgrades.
- **Analytics:** (Opt-in) For improving quality and reliability.

## 9. Glossary of Terms

- **Prompt:** The raw text input from the user.
- **Upgrade:** The process of enhancing, rewriting, or optimizing a prompt.
- **Pipeline:** A sequence of models, tools, and logic applied to a prompt.
- **LangGraph:** The advanced, multi-step pipeline for Pro users.
- **Entitlement:** The user's plan or access level (Free/Pro).

## 10. Appendix: Code Pointers

- `api/brain_engine.py` — API entrypoint
- `services/brain_engine/engine.py` — Core engine logic
- `services/brain_engine/langgraph_adapter.py` — Pro pipeline
- `services/brain_engine/compendium_loader.py` — Templates/context
- `api/models.py` — Data models
- `PLAN_BRAIN_ENGINE_INTEGRATION.md` — Architectural notes

---

*This scroll is but a snapshot of the living Brain Engine. Study it, improve it, and let the next chapter be written in code.*
