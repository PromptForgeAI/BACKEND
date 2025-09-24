# PromptForgeAI Backend: Capabilities & Usage Guide

## Overview
PromptForgeAI is a production-grade, Pro-gated SaaS backend built with FastAPI and MongoDB. It provides a full suite of endpoints for prompt management, user analytics, marketplace, Pro plans, personas, gallery, notifications, and real-time integrations. The backend is designed for extensibility, security, and real-world SaaS operations.

---

## Core Capabilities

### 1. Prompt Vault
- **CRUD for Prompts**: Save, list (with search, persona, and tag filtering), and delete prompts per user.
- **MongoDB-native**: All operations use ObjectId validation and output sanitization.
- **Persona & Tag Support**: Prompts can be associated with personas and tags for organization and filtering.

### 2. Personas
- **Default & Custom Personas**: Returns a set of default personas and allows users to create their own.
- **Unique Enforcement**: Persona names are unique per user.

### 3. Prompt Gallery
- **Share Prompts Publicly**: Users can share prompts to a public gallery.
- **List & Search**: Gallery supports search and tag filtering, sorted by votes.
- **Voting**: Users can upvote prompts (one vote per user per prompt).

### 4. Pro Plans & Subscription
- **Plan Info**: Query current plan and expiry.
- **Upgrade**: Upgrade to Pro plans (pro_lite, pro_max, team) with duration and expiry.
- **Pro Gating**: Full pipeline upgrades and premium features are gated by Pro status.

### 5. Brain Engine (Prompt Upgrades)
- **Quick Upgrade**: Fast, low-latency prompt upgrade for all users.
- **Full Upgrade**: Deep, explainable pipeline for Pro users (with strict Pro enforcement).
- **Pipeline Logic**: Modular, extensible pipeline for prompt transformation (ML/rule-based TODOs remain).

### 6. Marketplace
- **List Prompts**: Users can list packaged prompts for sale.
- **Purchase**: Atomic purchase flow with credit transfer, commission, and prompt cloning.
- **Listings & Filters**: Search, filter, and paginate marketplace listings.
- **Reviews & Ratings**: Users can rate and review purchased prompts.
- **Analytics**: Download, view, and sales analytics for marketplace items.

### 7. Analytics
- **Dashboard**: Comprehensive analytics dashboard (prompt usage, sales, revenue, categories, trends).
- **Exports**: Export prompt and analytics data in CSV/JSON.
- **Background Jobs**: Create and track analytics jobs (export, report, aggregation).

### 8. Notifications
- **Mark Read**: Mark individual or all notifications as read.
- **User-Scoped**: All notification actions are scoped to the authenticated user.

### 9. Webhooks
- **Stripe Integration**: Handles Stripe payment webhooks, adds credits to user accounts, and logs transactions.
- **Duplicate Protection**: Prevents double-processing of webhook events.

### 10. Security & Best Practices
- **Authentication**: All endpoints require authentication (Firebase or similar).
- **MongoDB Safety**: All ObjectId usage is validated; outputs are sanitized for frontend.
- **Error Handling**: Robust error handling and logging throughout.
- **Rate Limiting**: Key endpoints are rate-limited to prevent abuse.

---

## Usage Guide

### Authentication
- All endpoints require a valid user session (token-based, e.g., Firebase).
- User context is injected via FastAPI dependencies.

### API Endpoints (Key Examples)
- `POST /vault/save` — Save a prompt to the user's vault.
- `GET /vault/list` — List/search prompts in the user's vault.
- `DELETE /vault/delete/{prompt_id}` — Delete a prompt from the vault.
- `GET /personas/list` — List default and user personas.
- `POST /personas/save` — Create a new persona.
- `POST /gallery/share` — Share a prompt to the public gallery.
- `GET /gallery/list` — List/search public gallery prompts.
- `POST /gallery/vote/{gallery_id}` — Upvote a gallery prompt.
- `GET /plans/info` — Get current plan and expiry.
- `POST /plans/upgrade` — Upgrade to a Pro plan.
- `GET /plans/check_pro` — Check if user is Pro.
- `POST /prompt/quick_upgrade` — Quick prompt upgrade (all users).
- `POST /prompt/upgrade` — Full pipeline upgrade (Pro only).
- `POST /list-prompt` — List a prompt in the marketplace.
- `GET /listings` — Search and filter marketplace listings.
- `POST /purchase` — Purchase a marketplace prompt.
- `POST /rate` — Rate/review a purchased prompt.
- `GET /dashboard` — Get analytics dashboard.
- `POST /exports/prompts` — Export prompt data.
- `POST /exports/analytics` — Export analytics data.
- `PUT /notifications/{notification_id}/read` — Mark a notification as read.
- `POST /notifications/mark-all-read` — Mark all notifications as read.
- `POST /stripe` — Stripe webhook endpoint for payments.

### Data Model
- **MongoDB Collections**: users, vault, personas, gallery, gallery_votes, prompts, prompt_versions, marketplace_listings, marketplace_purchases, analytics_jobs, notifications, transactions, webhook_events, exports.
- **ObjectId Usage**: All IDs are MongoDB ObjectIds, validated and serialized for frontend.

### Extensibility
- **Services Layer**: Analytics, brain engine, and other services are modular and can be extended.
- **TODOs**: ML/rule-based pipeline logic and LangGraph adapter are marked for future enhancement.

### Deployment
- **FastAPI**: Run with Uvicorn or Gunicorn for production.
- **MongoDB**: Requires a running MongoDB instance.
- **Environment**: Configure secrets (e.g., Stripe) via environment variables.

---

## Known Limitations & TODOs
- Some advanced ML/pipeline features are marked as TODO and not yet implemented.
- Some exception handling is broad for async safety; can be made more granular.
- Print statements in scripts (e.g., create_indexes.py) are for CLI feedback.

---

## Conclusion
PromptForgeAI backend is a robust, production-ready SaaS backend with full support for prompt management, Pro gating, marketplace, analytics, and extensibility. All endpoints are MongoDB-native, secure, and ready for integration with frontend, extension, or third-party services.

For further details, see the codebase or contact the maintainers.
