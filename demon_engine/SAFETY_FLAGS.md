# Safety Flags & Controls

## Kill-switches
- Per (intent, mode, client) key
- Globally disable Pro pipelines (maintenance mode)

## Rate Limits
- Per-plan (free/pro) and per-client (chrome/vscode/cursor/web)
- Burst control: throttle excessive requests

## Fallback Policy
- If Pro fails, fallback to Free (configurable)
- Attach fidelity_score and fallback=true in response

## Error Codes
- 402: Pro required
- 429: Rate limit exceeded
- 503: Kill-switch/maintenance
- 500: No pipeline matched
- 504: Timeout
