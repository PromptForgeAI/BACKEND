# Backend Audit

## Server & Build
- **Language/Runtime:** Python 3.11
- **Framework:** FastAPI
- **Start Command:** `uvicorn main:app` (see `main.py`)
- **Ports:** Default 8000 (configurable via `PORT` env var)
- **Env Vars (names only):**
  | Name                |
  |---------------------|
  | MONGO_URL           |
  | MONGO_DB            |
  | STRIPE_WEBHOOK_SECRET |
  | PORT                |
  | HOST                |
  | ALLOWED_ORIGIN      |
  | LOG_LEVEL           |
  | REDIS_URL (forbidden, see below) |
  | LLM_PROVIDER        |
  | LLM_API_KEY         |
  | LLM_MODEL           |
- **Middleware:**
  - CORS (configurable origin)
  - Rate limiting (slowapi)
  - Structured logging (Python logging)

## Routes
- **Grouped by Feature:**

| Method | Path | Description | Protected |
|--------|------|-------------|-----------|
| GET    | /health | Health check | No |
| GET    | /      | Welcome root | No |
| /api/v1/prompts/* | Prompts CRUD, test, analytics | Yes (Depends) |
| /api/v1/ai/* | AI features | Yes (Depends) |
| /api/v1/marketplace/* | Listings, purchase, review | Yes (Depends) |
| /api/v1/users/* | User profile, credits, settings | Yes (Depends) |
| /api/v1/packaging/* | Prompt packaging | Yes (Depends) |
| /api/v1/partnerships/* | Partner apps, dashboard | Yes (Depends) |
| /api/v1/analytics/* | Analytics dashboard, export | Yes (Depends) |
| /api/v1/projects/* | Project CRUD | Yes (Depends) |
| /api/v1/notifications/* | Notifications | Yes (Depends) |
| /api/v1/webhooks/stripe | Stripe webhook | No (verifies signature) |
| /api/v1/search/* | Search | Yes (Depends) |

- **Auth Enforcement:**
  - Most routes use FastAPI `Depends(get_current_user)` or similar.
  - Some routes (e.g., `/health`, `/webhooks/stripe`) are public.

## Auth (Firebase)
- **Token Verification:**
  - Placeholder for `verify_firebase_token` in `api/users.py` (lines 72-76).
  - Expects Bearer Firebase ID token from Authorization header.
  - Not fully implemented; must be completed for production.
- **Role/Claims:**
  - No explicit role/claims checks found; only user presence enforced.

## Data Layer (Mongo)
- **Client Init:**
  - `AsyncIOMotorClient` in `dependencies.py`.
  - DB name from `MONGO_DB` env var (default: `promptforge`).
- **Collections/Models:**
  - `users`, `prompts`, `prompt_versions`, `marketplace_listings`, `transactions`, `usage`, `webhook_events`, `exports`, `analytics_jobs`, etc.
- **Indexes:**
  - Ensured on startup for:
    - `users(uid)` unique
    - `transactions(user_id, created_at)`
    - `listings(seller_id, created_at)`
    - `usage(user_id, timestamp)`
    - `webhook_events(event_id)` unique
  - Some additional indexes may be present in code (e.g., via pymongo).
- **Common Queries:**
  - Filter by user_id, created_at, seller_id, etc.
  - No evidence of unindexed scans in main flows.

## Payments & Webhooks (Stripe)
- **Webhook Endpoint:**
  - `/api/v1/webhooks/stripe` (POST)
  - Verifies Stripe signature using `STRIPE_WEBHOOK_SECRET`.
  - Idempotency: event_id stored in `webhook_events` collection.
- **Credit/Entitlement Updates:**
  - Payment success triggers Mongo updates (not Firestore).
- **Transaction Records:**
  - `transactions` collection; schema includes user_id, created_at, amount, etc.

## Marketplace
- **Listings:**
  - CRUD via `marketplace_listings`.
  - Purchase flow: atomic Mongo session, credits debited/credited.
- **Moderation:**
  - No explicit moderation hooks found.
- **Payouts:**
  - Revenue tracked in `transactions`.
- **Notifications:**
  - No Redis pub/sub; some n8n hooks (see below).
- **External Automation:**
  - n8n workflow triggers present (disabled or best-effort, not critical path).

## Config & Security
- **CORS:**
  - Allowed origin from env var.
- **Rate Limiting:**
  - slowapi, default 100/minute.
- **Input Validation:**
  - Pydantic models for request bodies.
- **Request Size Limits:**
  - Not explicitly set.
- **Error Handling:**
  - FastAPI exception handlers, structured logs.
- **Health Checks:**
  - `/health` endpoint.

## Forbidden Tech Findings — MUST READ
- **Firestore:**
  - No usage found.
- **Redis/Queues/Workers:**
  - Redis is imported and used in `dependencies.py` (lines 33, 61, 142, 144, 145, etc.).
  - Functions: `cache_get`, `cache_set`, `cache_delete`, `cache_delete_pattern`.
  - `REDIS_URL` env var present.
  - No evidence of BullMQ, Agenda, SQS, Kafka, RabbitMQ, etc.
- **Jobs/Workers:**
  - Analytics job creation endpoint exists, but uses Mongo for persistence and n8n for workflow triggers (not a queue system).
- **Migration Note:**
  - All Redis-based cache logic must be removed for Mongo-only compliance.
  - Replace any cache_get/set with direct Mongo queries or in-memory cache if absolutely needed.

## Risks, Bugs, Tech Debt
- **Redis usage is present and must be removed for compliance.**
- **Firebase Auth is not fully implemented; token verification is a stub.**
- **n8n workflow triggers are present (best-effort, not critical path).**
- **No explicit request size limits.**
- **Some endpoints may lack granular role/claims checks.**
- **Moderation and notification logic is minimal.**

## Open Questions for Gateway/Frontend
- What is the final plan for Firebase Auth integration? (Who owns token verification?)
- Should all cache logic be removed, or is a Mongo-backed cache allowed?
- Is n8n automation allowed for non-critical flows?
- Are there any required admin/moderation endpoints not yet implemented?
- Should request size limits be enforced at the API gateway or here?
