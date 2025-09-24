# Manual QA Checklist: Brain Engine

## Surfaces
- [ ] Chrome Free: Conversational.Basic
- [ ] Chrome Pro: Conversational.LangGraph
- [ ] VS Code Free: CodeForge.Basic
- [ ] VS Code Pro: CodeForge.LangGraph
- [ ] Cursor (Pro-only): Agent.DemonEngine
- [ ] Web Free: Temple.Basic
- [ ] Web Pro: Temple.KnowledgeAugmented

## Safety & Fallbacks
- [ ] Kill-switch flip disables pipeline
- [ ] Global Pro disable triggers fallback/402
- [ ] Pro pipeline failure falls back to Free (fidelity_score, fallback=true)
- [ ] Rate limit triggers 429
- [ ] 402 upsell for Pro-only
- [ ] 503 for kill-switch
- [ ] 504 for timeout

## Edge Cases
- [ ] Old requests (no intent/client) route as web/chat/free
- [ ] Telemetry/analytics events fire (if enabled)
