# --- Ensure matching indexes ---
await db.users.create_index([("_id",1)], unique=True)
await db.users.create_index([("email",1)], unique=True, sparse=True)
await db.prompts.create_index([("user_id",1), ("created_at",-1)])
await db.analytics_events.create_index([("timestamp",-1)])
# scripts/create_indexes.py
# Run:  MONGODB_URI="mongodb+srv://shivadeepakdev_db_user:IazHjfnuOfLEnw40@testpfai.uoiqsww.mongodb.net/?retryWrites=true&w=majority&appName=testpfai" MONGODB_DB="promptforge" python scripts/create_indexes.py
import asyncio
import os
from typing import List, Tuple

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, DESCENDING


MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://shivadeepakdev_db_user:IazHjfnuOfLEnw40@testpfai.uoiqsww.mongodb.net/?retryWrites=true&w=majority&appName=testpfai")  # TODO: Set explicit production DB URI in prod
MONGODB_DB = os.getenv("MONGODB_DB", "promptforge")

# Toggle TTL indexes if you want Mongo to auto-delete docs at expires_at
ENABLE_TTL = False  # set True to enable TTL indexes (be careful in non-prod)

# ---------- Index definitions ----------
# Each entry: (collection_name, [IndexModel(...), ...])

INDEXES: List[Tuple[str, List[IndexModel]]] = [

    # users
    ("users", [
        IndexModel([("_id", ASCENDING)], name="users__id_1"),
        IndexModel([("email", ASCENDING)], name="users_email_1", sparse=True),
        IndexModel([("is_partner", ASCENDING)], name="users_is_partner_1"),
        IndexModel([("partner_request_status", ASCENDING)], name="users_partner_request_status_1"),
        IndexModel([("created_at", DESCENDING)], name="users_created_at_-1"),
    ]),

    # prompts (global collection)
    ("prompts", [
        IndexModel([("user_id", ASCENDING), ("project_id", ASCENDING)], name="prompts_user_project_1_1"),
        IndexModel([("user_id", ASCENDING), ("project_id", ASCENDING), ("updated_at", DESCENDING)], name="prompts_user_project_updated_1_1_-1"),
        IndexModel([("user_id", ASCENDING), ("status", ASCENDING)], name="prompts_user_status_1_1"),
        IndexModel([("user_id", ASCENDING), ("updated_at", DESCENDING)], name="prompts_user_updated_1_-1"),
        IndexModel([("visibility", ASCENDING), ("deleted", ASCENDING), ("tags", ASCENDING)], name="prompts_visibility_deleted_tags_1_1_1"),
        IndexModel([("tags", ASCENDING)], name="prompts_tags_1"),
        IndexModel([("created_at", DESCENDING)], name="prompts_created_at_-1"),
    ]),

    # marketplace_listings
    ("marketplace_listings", [
        # Approved listings + category with different sorts
        IndexModel([("status", ASCENDING), ("category", ASCENDING), ("createdAt", DESCENDING)], name="mkt_status_category_createdAt_1_1_-1"),
        IndexModel([("status", ASCENDING), ("category", ASCENDING), ("analytics.purchaseCount", DESCENDING)], name="mkt_status_category_purchases_1_1_-1"),
        IndexModel([("status", ASCENDING), ("category", ASCENDING), ("price", ASCENDING)], name="mkt_status_category_price_1_1_1"),

        # Alternate field names used elsewhere
        IndexModel([("status", ASCENDING), ("category", ASCENDING), ("created_at", DESCENDING)], name="mkt_status_category_created_at_1_1_-1"),
        IndexModel([("status", ASCENDING), ("downloads", DESCENDING)], name="mkt_status_downloads_1_-1"),
        IndexModel([("status", ASCENDING), ("rating", DESCENDING)], name="mkt_status_rating_1_-1"),
        IndexModel([("status", ASCENDING), ("price", ASCENDING)], name="mkt_status_price_1_1"),

        # Lookups and lightweight search helpers
        IndexModel([("id", ASCENDING)], name="mkt_id_1", sparse=True),
        IndexModel([("title_lowercase", ASCENDING)], name="mkt_title_lowercase_1"),
        IndexModel([("tags", ASCENDING)], name="mkt_tags_1"),
    ]),

    # transactions (used for revenue & time windows)
    ("transactions", [
        IndexModel([("recipient_id", ASCENDING), ("created_at", DESCENDING)], name="tx_recipient_created_1_-1"),
        IndexModel([("buyer_id", ASCENDING), ("created_at", DESCENDING)], name="tx_buyer_created_1_-1"),
    ]),

    # prompt_purchases (if present)
    ("prompt_purchases", [
        IndexModel([("user_id", ASCENDING), ("listing_id", ASCENDING)], name="pp_user_listing_unique", unique=True),
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="pp_user_created_1_-1"),
    ]),

    # marketplace_purchases (if present)
    ("marketplace_purchases", [
        IndexModel([("buyer_id", ASCENDING), ("created_at", DESCENDING)], name="mp_buyer_created_1_-1"),
        IndexModel([("prompt_id", ASCENDING), ("buyer_id", ASCENDING)], name="mp_prompt_buyer_1_1"),
    ]),

    # notifications
    ("notifications", [
        IndexModel([("user_id", ASCENDING), ("read", ASCENDING), ("createdAt", DESCENDING)], name="notif_user_read_createdAt_1_1_-1"),
        IndexModel([("user_id", ASCENDING), ("createdAt", DESCENDING)], name="notif_user_createdAt_1_-1"),
    ]),

    # ideas
    ("ideas", [
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="ideas_user_created_1_-1"),
    ]),

    # analytics (per-request/endpoint logs)
    ("analytics", [
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="analytics_user_created_1_-1"),
        IndexModel([("endpoint", ASCENDING), ("created_at", DESCENDING)], name="analytics_endpoint_created_1_-1"),
    ]),

    # exports (completed export artifacts)
    ("exports", [
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="exports_user_created_1_-1"),
        # Optional TTL
        IndexModel([("expires_at", ASCENDING)], name="exports_expires_at_1", expireAfterSeconds=0) if ENABLE_TTL else None,
    ]),

    # export_jobs (queued/background export jobs)
    ("export_jobs", [
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="export_jobs_user_created_1_-1"),
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="export_jobs_status_created_1_-1"),
    ]),

    # analytics_jobs (long analytics jobs)
    ("analytics_jobs", [
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="aj_user_created_1_-1"),
        IndexModel([("job_id", ASCENDING)], name="aj_job_id_1", unique=True),
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="aj_status_created_1_-1"),
        IndexModel([("expires_at", ASCENDING)], name="aj_expires_at_1", expireAfterSeconds=0) if ENABLE_TTL else None,
    ]),

    # demo_bookings
    ("demo_bookings", [
        IndexModel([("preferred_date", ASCENDING), ("status", ASCENDING)], name="demo_preferred_date_status_1_1"),
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="demo_user_created_1_-1"),
    ]),

    # reviews (marketplace reviews)
    ("reviews", [
        IndexModel([("promptId", ASCENDING), ("userId", ASCENDING)], name="reviews_prompt_user_unique", unique=True),
        IndexModel([("promptId", ASCENDING), ("createdAt", DESCENDING)], name="reviews_prompt_createdAt_1_-1"),
        IndexModel([("promptId", ASCENDING), ("helpfulCount", DESCENDING)], name="reviews_prompt_helpful_1_-1"),
        IndexModel([("promptId", ASCENDING), ("rating", DESCENDING)], name="reviews_prompt_rating_1_-1"),
    ]),
]


async def ensure_indexes():
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[MONGODB_DB]

    created_total = 0
    # Ensure indexes for prompt_versions collection
    await db["prompt_versions"].create_index([("prompt_id", 1)])
    await db["prompt_versions"].create_index([("version_number", 1)])
    await db["prompt_versions"].create_index([("created_at", -1)])

    # Ensure indexes for projects collection
    await db["projects"].create_index([("owner_id", 1)])
    await db["projects"].create_index([("team_id", 1)])
    await db["projects"].create_index([("created_at", -1)])

    # Ensure indexes for teams collection
    await db["teams"].create_index([("owner_id", 1)])
    await db["teams"].create_index([("members.user_id", 1)])
    await db["teams"].create_index([("created_at", -1)])

    # Ensure indexes for analytics_events collection (standardized)
    await db["analytics_events"].create_index([("user_id", 1)])
    await db["analytics_events"].create_index([("event_type", 1)])
    await db["analytics_events"].create_index([("timestamp", -1)])

    # Normalize marketplace index field to created_at
    from pymongo import IndexModel, ASCENDING, DESCENDING
    await db["marketplace_listings"].create_indexes([
        IndexModel([("status", ASCENDING), ("category", ASCENDING), ("created_at", DESCENDING)], name="mkt_status_category_created_at_1_1_-1")
    ])
    for coll_name, models in INDEXES:
        # Some entries can be None (TTL toggles)
        models = [m for m in (models or []) if m is not None]
        if not models:
            continue

        coll = db[coll_name]
        try:
            result = await coll.create_indexes(models)
            created_total += len(result or [])
            print(f"[OK] {coll_name}: ensured {len(models)} index(es).")
        except Exception as e:
            print(f"[WARN] {coll_name}: index creation error: {e}")

    print(f"\nDone. Index batches executed. (TTL enabled: {ENABLE_TTL})")


if __name__ == "__main__":
    asyncio.run(ensure_indexes())
