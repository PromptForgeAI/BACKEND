# PromptForge Academy API

## Endpoints

### GET /api/academy/curriculum
- Returns curriculum structure (modules, lessons)
- Reads from public/curriculum.json or fallback to content/curriculum.json

### GET /api/academy/lesson/{lesson_id}
- Returns lesson metadata and compiled HTML
- Reads from content/academy/{lesson_id}.json

### POST /api/academy/labs/run
- Proxies to /api/v1/prompt/prompt/quick_upgrade
- Auth: Forwards Authorization header if present
- Guest: Requires X-SANDBOX: true header, rate-limited to 5/hr per IP (in-memory, TODO: Redis)
- Input: Validates max 20k chars, basic sanitization
- Logs analytics event (TODO)

### POST /api/academy/progress
- Stores progress in academy_progress collection
- Fields: userId, lessonId, completedParts, xp, timestamp

### POST /api/academy/quest/submit
- Stores submission in academy_submissions
- Auto-evaluates JSON schema tasks

### GET /api/academy/leaderboard
- Aggregates top XP from academy_progress

### POST /api/academy/validate (admin-only)
- Validates MDX files in content/academy
- Requires X-ADMIN-TOKEN header (env var)
- TODO: Secure with real auth

## Rate Limits
- /labs/run: 5/hr per IP for guests (in-memory, TODO: Redis)
- Documented as temporary; production should use Redis or external store

## Security
- Admin endpoints require X-ADMIN-TOKEN (env var)
- TODO: Secure with real authentication

## CORS
- Ensure CORS allows NEXT_PUBLIC_API_BASE origin

## Content Ingestion
- Use scripts/ingest_mdx.py to parse MDX and generate lesson/curriculum JSON

## Testing
- Pytest unit and integration tests required for all endpoints
- Integration test should mock upstream quick_upgrade and verify /labs/run response shape

---
