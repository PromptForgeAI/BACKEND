# PromptForgeAI Extension — Product & Engineering Plan

## Vision & Value Proposition
PromptForgeAI Extension instantly upgrades any prompt on the web into a god-tier, engineered prompt using the Brain Engine (compendium-driven, explainable, and always improving). It’s the fastest way to get world-class results in ChatGPT, Gemini, Claude, Notion, Gmail, and more — with a single shortcut.

- **Speed:** One shortcut → perfect prompt.
- **Quality:** Brain Engine ensures consistent, explainable upgrades.
- **Scale:** Works across sites, teams, and workflows (Pro policies).
- **Moat:** Same core as platform; results match your web app.

## Dual-Mode Execution: Quick vs Full Pipelines

**Quick Mode (Free):**
- Minimal techniques (foundational, structuring)
- Ultra-low latency (<300ms)
- No plan/fidelity returned (just the upgraded prompt)
- Used for instant upgrades, default for extension

**Full Mode (Pro):**
- Full compendium access (all categories, advanced techniques)
- Multi-step LangGraph pipeline (reasoning, verification, self-correction)
- Returns plan, diffs, fidelity score, and matched techniques
- Enterprise-ready: explainability, compliance, org policies
- Used for power users, enterprises, and analytics

**Free vs Pro = Quick vs Full is the upsell driver.**

---
| Feature                | Free         | Pro                |
|------------------------|--------------|--------------------|
| Quick Mode Upgrade     | ✅           | ✅                 |
| Inline Toolbar         | ✅           | ✅                 |
| Diff View              | ✅           | ✅                 |
| Auto-Approve           | ✅           | ✅                 |
| Auto-Save (local)      | ✅           | ✅                 |
| Local History (10)     | ✅           | Extended (100)     |
| Style Presets (basic)  | ✅           | Advanced           |
| Full Mode Pipeline     | ❌           | ✅                 |
| Plan+Diff+Fidelity     | ❌           | ✅                 |
| Cloud Library Sync     | ❌           | ✅                 |
| Multi-variant (A/B)    | ❌           | ✅                 |
| Org Policy/Workspace   | ❌           | ✅                 |
| Priority Queue         | ❌           | ✅                 |
| License-based Limits   | ❌           | ✅                 |

## LangGraph Pipeline Flow (ASCII Diagram)

```
 [Raw Input]
     |
     v
 [Signal Extraction] --+---> [Quick Mode?] --yes--> [Foundational Techniques] --+-->
     |                 |                                            |
     |                 +--no--> [Full Pipeline: Multi-Stage LangGraph] --+     |
     v                                                           |     |
 [Technique Selection] <-----------------------------------------+     |
     |
     v
 [Pipeline Composer (LangGraph)]
     |
     v
 [Execution Engine]
     |
     v
 [Self-Correct/Refine/Verify]
     |
     v
 [Enhanced Prompt + Plan + Fidelity Score]
```

**JSON Schema Example:**
```
{
  "nodes": [
    { "id": "n1", "kind": "signal_extract" },
    { "id": "n2", "kind": "match_techniques", "matched": ["few_shot_prompting", "role_playing_persona"] },
    { "id": "n3", "kind": "compose_pipeline" },
    { "id": "n4", "kind": "execute" },
    { "id": "n5", "kind": "refine" }
  ],
  "edges": [
    { "from": "n1", "to": "n2" },
    { "from": "n2", "to": "n3" },
    { "from": "n3", "to": "n4" },
    { "from": "n4", "to": "n5" }
  ]
}
```

---
- **Install Extension** → Welcome page (30-sec explainer)
- **Options Page:**
  - Set API Base (default: https://app.promptforgeai.tech or http://localhost:7000)
  - Ensure /api/v1 prefix; show detected routes status
  - Sign in (if Pro): OAuth or token paste
  - Pick default shortcut; toggles for Auto-Approve/Auto-Save
- **Guided Tour:**
  - Press shortcut in textbox → see diff & approve

## Signal Extraction Schema (Deterministic)

Every input is converted to a set of signals, which drive deterministic technique selection and pipeline composition.

**Example:**
```
{
  "needs_json": true,
  "persona": "teacher",
  "reasoning_depth": "multi_step",
  "domain": "finance",
  "style": ["concise", "professional"]
}
```

---
- **Manifest v3**
- **Content script:** Detects inputs, shows inline toolbar, reads selection
- **Background service worker:** Handles network calls, auth/session, rate limiting, license checks
- **Options page:** API base, auth, privacy toggles, shortcuts & behavior
- **Offscreen document:** (if needed) for screenshot/clipboard utilities
- **Permissions:** activeTab, scripting, storage, contextMenus, commands, host permissions (minimal)
- **Keyboard Shortcuts:** Ctrl/Cmd+Alt+U (Upgrade), Ctrl/Cmd+Enter (Approve), configurable

## Backend API Map (all /api/v1)
- **POST /api/v1/prompt/quick_upgrade**
  - Input: `{ text, context: { source:'extension', pageTitle, selection?, url }, options?: { fidelityMin?, stylePreset? } }`
  - Output: `{ upgraded, plan?, diffs?, fidelity_score?, matched_entries? }`
- **POST /api/v1/prompt/upgrade** (full mode)
- **POST /api/v1/library/prompts** (if exists) — save before/after when Auto-Save is on
- **GET /api/v1/users/me** — confirm auth/license (if Pro)
- **All requests:** prefix /api/v1. If backend routes differ, adapt in one place and document mapping here.

## Privacy, Security, and Compliance
- Opt-in telemetry only (upgradeRequested/Completed, ms, success/fail; no raw text)
- Do not store raw prompts unless Auto-Save is ON
- Minimize host permissions; request specific hosts when user enables “site support”
- Hardened messaging between content ↔ background; validate message origin
- Rate limit requests; exponential backoff; handle 401/429 gracefully
- CSP-friendly; no remote code; code-signed builds

## Monetization & Licensing — Why Pro is a No-Brainer

- **Quick Mode (Free):** Fast, basic upgrades, local history, basic presets.
- **Full Mode (Pro):**
  - Enterprise-ready pipelines (explainability, fidelity scoring, compliance)
  - Org policies & admin controls
  - Priority access, multi-variant (A/B) generation
  - Cloud library, advanced presets, extended history
  - Productivity multiplier: more upgrades, faster, smarter
- **Payment:** via existing web app; extension reads license token from backend /api/v1/users/me

**Pro = productivity, compliance, and explainability for teams and power users.**

---
- **Free:** Quick Mode, basic presets, local history
- **Pro:** Full Mode, variants, cloud saves, org policy, priority
- **Payment:** via existing web app; extension reads license token from backend /api/v1/users/me

## Marketing & Virality Hooks

- **Viral Hook:** “Press U to Upgrade” — memeable, demo-friendly, shareable.
- **Influencer Partnerships:** YouTubers/TikTokers demoing raw vs upgraded prompts.
- **Referral Links:** Built into saved history (“Upgraded with PromptForgeAI”).
- **Shareability:** One-click copy/share of upgraded prompts and diffs.
- **Early Access:** Toggle for orgs, beta invites.

## Store Listing Assets & Launch Checklist
- Icons (16–128px), promo tile, screenshots (upgrade flow), 30-sec video
- Privacy Policy (plain English, opt-in telemetry)
- Pricing page link (Pro features list)
- Support email & changelog
- Early-access toggles for orgs

## Telemetry, Metrics, KPIs
- **UAP:** Upgrades Approved % (approved / requested)
- **TTU:** Time to Upgrade (ms, P50/P95)
- **Replacements per session**
- **Errors per 1000 upgrades**
- **Pro conversion:** trial→paid
- **Sites coverage:** top domains used

## Testing Strategy & Release Plan
- **Unit:** content detection, selector edge cases, message bus, API client
- **E2E:** Puppeteer/Playwright scripts (ChatGPT/Notion demo → type → shortcut → approve → assert replacement)
- **Lint:** web-ext lint, MV3 validation
- **Beta channel:** (unlisted store) for staged rollout

## Rollout
- **v0.1:** Quick Mode only, Upgrade + Approve, Chrome Dev
- **v0.2:** Diff, Auto-Approve, Auto-Save, context menu
- **v0.3:** Pro features (Full Mode, variants, cloud library), store listing
- **v0.4:** Firefox build, org policies, analytics dashboards

## Edge Cases
- Huge inputs → chunk or reject with friendly message
- Non-English text → pass lang hint in metadata.lang
- Contenteditable vs custom editors (Quill/CodeMirror) → specialized replace routines
- Shadow DOM fields → fallback selectors
- Sites blocking injections → opt-in host permissions

## Contracts (API)
### Request
```
{
  "text": "<raw>",
  "context": {
    "source": "extension",
    "url": "<current_url>",
    "pageTitle": "<title>",
    "selection": "<optional>",
    "metadata": {}
  },
  "options": {
    "mode": "quick",
    "fidelityMin": 0.80,
    "stylePreset": "concise"
  }
}
```
### Response
```
{
  "upgraded": "<god-tier prompt>",
  "plan": { "nodes": [], "edges": [] },
  "diffs": "<unified diff>",
  "fidelity_score": 0.9,
  "matched_entries": [{ "id": "few_shot_prompting", "score": 0.83 }]
}
```

## Definition of Done
- PLAN.md complete and approved
- MV3 scaffold compiles; dev build runs
- Shortcut upgrade works on at least ChatGPT & Notion
- All network calls use /api/v1
- Options page functional; toggles persisted
- Basic E2E passes; lint clean
