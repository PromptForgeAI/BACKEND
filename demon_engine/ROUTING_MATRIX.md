
# PromptForgeAI Brain Engine Routing Matrix

This document describes the dynamic routing logic for the Brain Engine core, mapping (intent, mode, client) to pipelines with wildcards, pro-gating, and kill-switches.

## Routing Lookup Order

1. Exact match: (intent, mode, client)
2. Wildcard: (intent, mode, *)
3. Wildcard: (intent, *, client)
4. Global fallback: (chat, free, *)

If no mapping is found, fallback to (chat, free, *). If still not found, raise PipelineNotFound.

## Default Mappings

| Intent  | Mode | Client  | Pipeline                      | Pro Only |
|---------|------|---------|-------------------------------|----------|
| chat    | free | chrome  | Conversational.Basic          | No       |
| chat    | pro  | chrome  | Conversational.LangGraph      | Yes      |
| editor  | free | vscode  | CodeForge.Basic               | No       |
| editor  | pro  | vscode  | CodeForge.LangGraph           | Yes      |
| agent   | pro  | cursor  | Agent.DemonEngine             | Yes      |
| chat    | free | web     | Temple.Basic                  | No       |
| chat    | pro  | web     | Temple.KnowledgeAugmented     | Yes      |
| chat    | free | *       | Conversational.Basic          | No       |

## Example Routing

- (chat, free, chrome) → Conversational.Basic
- (editor, pro, vscode) → CodeForge.LangGraph
- (agent, free, cursor) → ProRequiredError (no free variant)
- (unknown, free, unknown) → fallback to (chat, free, *)

## Fallbacks

- If Pro fails, fallback to Free (if enabled), with fidelity_score and fallback=true in response.

## Error Mapping

- ProRequiredError → HTTP 402 (upsell)
- KillSwitchError → HTTP 503 ("Temporarily disabled for stability.")
- PipelineNotFound → HTTP 500 ("No pipeline matched; fallback failed.")
- Timeout/retries → HTTP 504

## Telemetry Events (if enabled)

- route_selected
- pro_required
- killswitch_hit
- fallback_used

## Backward Compatibility

- If intent/client missing, infer:
  - chrome → chat
  - vscode → editor
  - cursor → agent
  - web/unknown → chat
