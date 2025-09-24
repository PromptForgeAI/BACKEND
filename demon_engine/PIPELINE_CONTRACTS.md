# Pipeline Output Contracts by Surface

This document describes the output shape and contract for each surface (client/intent/mode) in the Brain Engine.

## Chrome / Chat (Conversational)
- **Free:** 1–2 paragraphs, optional bullet plan, softened tone, no code unless asked
- **Pro:** Dialogue format, persona alignment, clarify-then-answer, paragraphs + bullets

## VS Code / Editor (CodeForge)
- **Free:** Concise, imperative prompt lines for Copilot/agent, acceptance criteria, security/perf hints
- **Pro:** Multi-pass refinement (spec → impl prompt → review checklist), context anchors

## Cursor / Agent (DemonEngine)
- **Pro-only:** Agent plan (list steps & constraints, not prose), objective expansion, step graph, tool placeholders, abort criteria

## Web / Temple
- **Free:** Teaser (polite, short), marketing-friendly
- **Pro:** Structured outline, examples, marketing-friendly

## Fallbacks
- If Pro fails, fallback to Free contract (with fidelity_score, fallback=true)
