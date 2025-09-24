
# api/prompts.py - Prompt Routes
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from pymongo import DESCENDING, ReturnDocument

# Imports from our main application
from dependencies import (
    track_event,
    call_gemini_async,
    db,
    get_current_user,
    limiter,
)
from api.models import SavePromptRequest, TestDriveByIdRequest, UpdatePromptRequest , APIResponse

# --- Router & Logger ---
router = APIRouter(tags=["Prompts"])
logger = logging.getLogger(__name__)

def optimize_mongo_response(doc: dict) -> dict:
    # Normalize MongoDB document for API output
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    for k in ("created_at", "updated_at", "listed_at"):
        v = doc.get(k)
        if v and hasattr(v, "isoformat"):
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            doc[k] = v.isoformat()
    return doc
@router.post("/upgrade/cost_estimate", response_model=APIResponse)
async def upgrade_cost_estimate(payload: dict = Body(...), request: Request = None):
    """Return approximate token/call cost for prompt upgrade."""
    text = payload.get("text", "")
    length = len(text)
    # Example cost logic: 1 token per 4 chars, 1 call per request
    token_estimate = max(1, length // 4)
    call_estimate = 1
    return APIResponse(
        data={
            "token_estimate": token_estimate,
            "call_estimate": call_estimate,
            "details": {
                "input_length": length,
                "formula": "1 token per 4 chars, 1 call per request"
            }
        },
        message="Approximate cost estimate for prompt upgrade."
    )
import csv
from fastapi.responses import StreamingResponse

@router.get("/revenue/export")
async def export_revenue(range: str = Query("30d"), user: dict = Depends(get_current_user)):
    """Export revenue data as CSV for selected time range."""
    import datetime
    today = datetime.date.today()
    if range == "7d":
        start_date = today - datetime.timedelta(days=7)
    elif range == "30d":
        start_date = today - datetime.timedelta(days=30)
    elif range == "90d":
        start_date = today - datetime.timedelta(days=90)
    else:
        start_date = today - datetime.timedelta(days=30)
    sales = await db.sales.find({"createdAt": {"$gte": start_date.isoformat()}, "buyerAnonymizedId": {"$exists": True}}).to_list(length=1000)
    def generate():
        writer = csv.writer(open('/dev/null', 'w', newline=''))
        yield ','.join(["promptId", "price", "currency", "createdAt", "buyerAnonymizedId", "rating"])+"\n"
        for s in sales:
            yield ','.join([
                str(s.get("promptId", "")),
                str(s.get("price", "")),
                str(s.get("currency", "")),
                str(s.get("createdAt", "")),
                str(s.get("buyerAnonymizedId", "")),
                str(s.get("rating", ""))
            ])+"\n"
    return StreamingResponse(generate(), media_type="text/csv")
@router.get("/analytics/prompts/{prompt_id}")
async def get_prompt_analytics(prompt_id: str, range: str = Query("7d"), user: dict = Depends(get_current_user)):
    """Return aggregated daily metrics for a prompt (for charts/sparklines)."""
    # Parse range
    import datetime
    today = datetime.date.today()
    if range == "7d":
        start_date = today - datetime.timedelta(days=7)
    elif range == "30d":
        start_date = today - datetime.timedelta(days=30)
    elif range == "90d":
        start_date = today - datetime.timedelta(days=90)
    else:
        start_date = today - datetime.timedelta(days=7)
    analytics = await db.analytics_daily.find({"promptId": prompt_id, "date": {"$gte": start_date.isoformat()}}).sort("date", 1).to_list(length=100)
    views = [{"date": a["date"], "count": a.get("views", 0)} for a in analytics]
    sales = [{"date": a["date"], "count": a.get("buys", 0), "revenue": a.get("revenue", 0)} for a in analytics]
    return APIResponse(data={"views": views, "sales": sales}, message="Prompt analytics fetched")


@router.patch("/{prompt_id}")
async def patch_prompt(prompt_id: str, patch: dict = Body(...), user: dict = Depends(get_current_user)):
    """Allow partial updates to prompt fields via PATCH /prompts/{id}."""
    user_id = user["uid"]
    prompt = await db.prompts.find_one({"_id": prompt_id, "user_id": user_id})
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    allowed_fields = {"title", "shortDesc", "content", "price", "tags", "thumbnailUrl", "status"}
    update_fields = {k: v for k, v in patch.items() if k in allowed_fields}
    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields to update.")
    update_fields["updated_at"] = datetime.utcnow().replace(tzinfo=timezone.utc)
    await db.prompts.update_one({"_id": prompt_id}, {"$set": update_fields})
    updated = await db.prompts.find_one({"_id": prompt_id})
    return APIResponse(data={
        "_id": str(updated.get("_id")),
        "title": updated.get("title"),
        "status": updated.get("status"),
        "updated_at": updated.get("updated_at")
    }, message="Prompt updated successfully")
@router.post("/{prompt_id}/duplicate")
async def duplicate_prompt(prompt_id: str, user: dict = Depends(get_current_user)):
    """Duplicate a prompt as a draft and return the new prompt object."""
    user_id = user["uid"]
    prompt = await db.prompts.find_one({"_id": prompt_id, "user_id": user_id})
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    new_id = str(uuid.uuid4())
    now_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
    draft = dict(prompt)
    draft["_id"] = new_id
    draft["status"] = "draft"
    draft["created_at"] = now_dt
    draft["updated_at"] = now_dt
    draft["publishedAt"] = None
    draft["title"] = f"{prompt.get('title', 'Prompt')} (Copy)"
    await db.prompts.insert_one(draft)
    return APIResponse(data={
        "_id": new_id,
        "title": draft.get("title"),
        "status": draft.get("status"),
        "created_at": draft.get("created_at"),
        "updated_at": draft.get("updated_at")
    }, message="Prompt duplicated as draft")
@router.post("/{prompt_id}/publish")
async def publish_prompt(prompt_id: str, user: dict = Depends(get_current_user)):
    """Publish a prompt, validate price, update status, and return updated prompt."""
    user_id = user["uid"]
    prompt = await db.prompts.find_one({"_id": prompt_id, "user_id": user_id})
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    price = prompt.get("price", 0)
    if price <= 0:
        raise HTTPException(status_code=400, detail="Price must be greater than 0 to publish.")
    now_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
    update = {
        "$set": {
            "status": "published",
            "publishedAt": now_dt,
            "updated_at": now_dt
        }
    }
    await db.prompts.update_one({"_id": prompt_id}, update)
    updated = await db.prompts.find_one({"_id": prompt_id})
    return APIResponse(data={
        "_id": str(updated.get("_id")),
        "title": updated.get("title"),
        "price": updated.get("price", 0),
        "status": updated.get("status"),
        "publishedAt": updated.get("publishedAt"),
        "updated_at": updated.get("updated_at")
    }, message="Prompt published successfully")

@router.get("/arsenal")
async def get_user_arsenal(
    user: dict = Depends(get_current_user),
    ownerId: str = Query(None, description="Owner ID (user_id) filter"),
    status: str = Query(None, description="Filter prompts by status"),
    tags: str = Query(None, description="Comma-separated tags filter"),
    sort: str = Query("newest", description="Sort by: newest|popular|price|rating"),
    q: str = Query(None, description="Search term for prompt titles or content"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Fetch a paginated, filterable list of prompts for dashboard cards."""
    user_id = ownerId or user["uid"]
    query: Dict[str, Any] = {"user_id": user_id}
    if status:
        query["status"] = status
    if tags:
        query["tags"] = {"$in": [t.strip() for t in tags.split(",") if t.strip()]}
    if q:
        query["$or"] = [
            {"title": {"$regex": re.escape(q), "$options": "i"}},
            {"content": {"$regex": re.escape(q), "$options": "i"}},
            {"tags": {"$regex": re.escape(q), "$options": "i"}}
        ]
    sort_spec = [("created_at", -1)]
    if sort == "popular":
        sort_spec = [("analytics.view_count", -1)]
    elif sort == "price":
        sort_spec = [("price", 1)]
    elif sort == "rating":
        sort_spec = [("performance.rating", -1)]
    skip = (page - 1) * limit
    total_count = await db.prompts.count_documents(query)
    cursor = db.prompts.find(query).sort(sort_spec).skip(skip).limit(limit)
    items = []
    async for doc in cursor:
        card = {
            "_id": str(doc.get("_id")),
            "title": doc.get("title"),
            "shortDesc": doc.get("description", ""),
            "price": doc.get("price", 0),
            "thumbnailUrl": doc.get("thumbnailUrl", ""),
            "tags": doc.get("tags", []),
            "status": doc.get("status", "draft"),
            "stats": {
                "viewsLast7": doc.get("analytics", {}).get("view_count", 0),
                "salesLast7": doc.get("analytics", {}).get("sales_last_7", 0),
                "totalSales": doc.get("analytics", {}).get("total_sales", 0),
                "rating": doc.get("performance", {}).get("rating", 0)
            }
        }
        items.append(card)
    result_data = {
        "items": items,
        "page": page,
        "limit": limit,
        "total": total_count
    }
    logger.info(f"Fetched {len(items)} prompts for UID: {user_id} (total: {total_count})")
    return APIResponse(data=result_data, message="Arsenal fetched successfully")

@router.post("/")
async def create_new_prompt(request: SavePromptRequest, user: dict = Depends(get_current_user)):
    """Creates a new prompt and its first version."""
    user_id = user["uid"]
    logger.info(f"Creating new prompt for UID: {user_id}, Title: {request.title}")

    try:
        prompt_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        now_dt = datetime.utcnow().replace(tzinfo=timezone.utc)

        prompt_doc = {
            "_id": prompt_id,
            "user_id": user_id,
            "title": request.title,
            "description": "",
            "content": request.body,
            "role": request.role,
            "category": "general",
            "tags": [],
            "difficulty": "beginner",
            "type": "text",
            "status": "active",
            "visibility": "private",
            "is_template": False,
            "is_featured": False,
            "version": 1,
            "latest_version_id": version_id,
            "performance": {"rating": 0,"effectiveness": 0,"test_count": 0, "success_rate": 0,"avg_response_time": 0,},
            "analytics": {"view_count": 0,"use_count": 0,"share_count": 0, "like_count": 0,"download_count": 0,"comment_count": 0,},
            "collaboration": {"is_collaborative": False,"allowed_users": [],"permissions": {},"active_editors": [],},
            "created_at": now_dt,
            "updated_at": now_dt,
            "created_by": user_id,
            "last_modified_by": user_id,
        }

        version_doc = {
            "_id": version_id,
            "prompt_id": prompt_id,
            "user_id": user_id,
            "version_number": 1,
            "content": request.body,
            "role": request.role,
            "type": "text",
            "changes": "Initial version",
            "created_at": now_dt,
            "created_by": user_id,
        }

        await db.prompts.insert_one(prompt_doc)
        await db.prompt_versions.insert_one(version_doc)

    # No cache delete (Mongo-only, no cache layer)
        
        logger.info(f"Prompt created successfully: ID {prompt_id} for UID: {user_id}")
        return APIResponse(
            data={"prompt_id": prompt_id, "version_number": 1, "status": "active", "visibility": "private",},
            message="Prompt forged and saved to MongoDB!",
        )
    except Exception as e:
        logger.error(f"Mongo error creating prompt for UID: {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create prompt")

@router.post("/test-drive-by-id")
@limiter.limit("5/minute")
async def test_drive_prompt_by_id(
    request_body: TestDriveByIdRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Test a prompt by its ID with user inputs; debit credits atomically in Mongo."""
    user_id = user["uid"]
    cost = 1
    logger.info(f"Test driving prompt by ID: {request_body.prompt_id} for UID: {user_id}")

    try:
            if db is None:
                raise HTTPException(status_code=503, detail="Database connection unavailable")

            # Try to find prompt in user's arsenal first
            prompt = await db.prompts.find_one({"_id": request_body.prompt_id, "user_id": user_id})
            if not prompt:
                # Not in arsenal, check marketplace
                marketplace_prompt = await db.marketplace_listings.find_one({"_id": request_body.prompt_id})
                if not marketplace_prompt:
                    # Try by prompt_id field (sometimes _id is ObjectId, sometimes string)
                    marketplace_prompt = await db.marketplace_listings.find_one({"prompt_id": request_body.prompt_id})
                if not marketplace_prompt:
                    raise HTTPException(status_code=404, detail="Prompt not found in arsenal or marketplace.")

                # Check if premium (price_credits > 0 or some premium flag)
                is_premium = bool(marketplace_prompt.get("price_credits", 0) > 0)
                # Check ownership in marketplace_purchases
                owns = await db.marketplace_purchases.find_one({"buyer_id": user_id, "prompt_id": request_body.prompt_id})
                if is_premium and not owns:
                    return APIResponse(data={"requires_purchase": True}, message="Prompt requires purchase before test-drive.")

                # If not premium or owned, allow test-drive
                # Use prompt_id from marketplace listing
                prompt_id_for_version = marketplace_prompt.get("prompt_id", request_body.prompt_id)
                latest_version_id = marketplace_prompt.get("latest_version_id")
                if not latest_version_id:
                    # Try to get latest version from prompt collection
                    prompt_doc = await db.prompts.find_one({"_id": prompt_id_for_version})
                    latest_version_id = prompt_doc.get("latest_version_id") if prompt_doc else None
                if not latest_version_id:
                    raise HTTPException(status_code=500, detail="Prompt has no valid version data.")
                version = await db.prompt_versions.find_one({"_id": latest_version_id, "prompt_id": prompt_id_for_version})
                if not version:
                    raise HTTPException(status_code=500, detail="Prompt version data is corrupted.")
                prompt_body = version.get("content") or ""
                if not prompt_body:
                    raise HTTPException(status_code=500, detail="Prompt body is empty.")
            else:
                # User owns the prompt
                latest_version_id = prompt.get("latest_version_id")
                if not latest_version_id:
                    raise HTTPException(status_code=500, detail="Prompt has no valid version data.")
                version = await db.prompt_versions.find_one({"_id": latest_version_id, "prompt_id": request_body.prompt_id})
                if not version:
                    raise HTTPException(status_code=500, detail="Prompt version data is corrupted.")
                prompt_body = version.get("content") or ""
                if not prompt_body:
                    raise HTTPException(status_code=500, detail="Prompt body is empty.")

            final_prompt = str(prompt_body)
            for key, value in (request_body.inputs or {}).items():
                placeholders = [f"[INPUT: {key}]", f"{{INPUT: {key}}}", f"[{key}]", f"{{{key}}}"]
                for ph in placeholders:
                    final_prompt = final_prompt.replace(ph, str(value))

            # --- Brain Engine Integration ---
            from services.brain_engine.engine import BrainEngine
            import os
            COMPENDIUM_PATH = os.path.join(os.path.dirname(__file__), '../compendium.json')
            brain_engine = BrainEngine(compendium_path=COMPENDIUM_PATH)
            mode = getattr(request_body, 'mode', 'quick')
            context = {"source": "test_drive", "user_id": user_id, "prompt_id": request_body.prompt_id}
            signals = brain_engine.extract_signals(final_prompt, context)
            techniques = brain_engine.match_techniques(signals, mode=mode)
            pipeline = brain_engine.compose_pipeline(techniques, mode=mode)
            result = await brain_engine.run_pipeline(pipeline, final_prompt, context, mode=mode)

            # Debit credits
            res = await db.users.find_one_and_update(
                {"_id": user_id, "credits": {"$gte": cost}},
                {"$inc": {"credits": -cost}},
                return_document=ReturnDocument.AFTER,
            )
            if not res:
                raise HTTPException(status_code=402, detail=f"Insufficient credits. Test driving costs {cost} credit(s).")
            new_credits = res.get("credits", 0)

            # Update monthly usage
            current_month = datetime.utcnow().strftime("%Y-%m")
            await db.usage.update_one(
                {"user_id": user_id, "month": current_month},
                {"$inc": {"promptsTestDriven": 1, "creditsSpent": cost}},
                upsert=True,
            )

            await track_event(user_id=user_id, event_type="prompt_test_driven", event_data={"prompt_id": request_body.prompt_id,"credits_spent": cost, "mode": mode})

            logger.info(f"Test drive successful for prompt {request_body.prompt_id}, UID: {user_id}")
            return APIResponse(
                data={
                    "preview": result.get("upgraded"),
                    "plan": result.get("plan"),
                    "diffs": result.get("diffs"),
                    "fidelity_score": result.get("fidelity_score"),
                    "matched_entries": result.get("matched_entries"),
                    "new_credits": new_credits,
                    "prompt_title": prompt.get("title", "Untitled")
                },
                message="Prompt test drive completed successfully",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error test driving prompt {request_body.prompt_id} for UID: {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test drive prompt: {e}")

@router.get("/public")
async def get_public_prompts(
    search: str = Query(None, description="Search term for prompt titles"),
    limit: int = Query(10, ge=1, le=100, description="Number of prompts to return"),
    offset: int = Query(0, ge=0, description="Number of prompts to skip"),
):
        """Paginated list of public prompts for sell-prompts dashboard, with stats and badges."""
        logger.info(f"Fetching public prompts, Search: {search}, Limit: {limit}, Offset: {offset}")
        try:
            if db is None:
                raise HTTPException(status_code=503, detail="Database connection unavailable")

            # Try cache first (if cache functions are available)
            cache_key_name = f"public_prompts:{search or 'all'}:{limit}:{offset}"
            try:
                cached = await cache_get(cache_key_name)
                if cached:
                    cached_data = json.loads(cached) if isinstance(cached, str) else cached
                    if isinstance(cached_data, dict) and "items" in cached_data:
                        logger.info(f"Cache hit for public prompts: {cache_key_name}")
                        return APIResponse(data=cached_data, message="Public prompts fetched from cache")
            except Exception as ce:
                logger.error(f"Cache optimization failed: {ce}")
                pass

            query: Dict[str, Any] = {"is_active": True, "is_public": True}
            if search:
                query["title_lowercase"] = {"$regex": re.escape(search.lower()), "$options": "i"}

            total_count = await db.marketplace_listings.count_documents(query)
            cursor = db.marketplace_listings.find(query).sort("created_at", DESCENDING).skip(offset).limit(limit)
            items = []
            async for doc in cursor:
                prompt = optimize_mongo_response(doc)
                prompt_id = prompt.get("id")
                # --- Stats aggregation ---
                stats = {
                    "viewsLast7": [0]*7,
                    "salesLast7": [0]*7,
                    "totalSales": 0,
                    "rating": 0.0
                }
                # Get analytics for last 7 days
                analytics = await db.analytics_daily.find({"promptId": prompt_id}).sort("date", -1).limit(7).to_list(length=7)
                analytics = list(reversed(analytics))
                stats["viewsLast7"] = [a.get("views", 0) for a in analytics]
                stats["salesLast7"] = [a.get("buys", 0) for a in analytics]
                stats["totalSales"] = sum(a.get("buys", 0) for a in analytics)
                stats["rating"] = prompt.get("performance", {}).get("rating", 0.0)
                # --- Badges logic ---
                badges = []
                if stats["totalSales"] > 20:
                    badges.append("TopSeller")
                if sum(stats["viewsLast7"]) > 50:
                    badges.append("Trending")
                # --- Build item ---
                item = {
                    "_id": prompt_id,
                    "title": prompt.get("title", ""),
                    "shortDesc": prompt.get("shortDesc", ""),
                    "price": prompt.get("price", 0),
                    "thumbnailUrl": prompt.get("thumbnailUrl", ""),
                    "tags": prompt.get("tags", []),
                    "status": prompt.get("status", "Published"),
                    "stats": stats,
                    "badges": badges
                }
                items.append(item)

            page_num = (offset // limit) + 1
            result_data = {
                "items": items,
                "page": page_num,
                "limit": limit,
                "total": total_count
            }
            # Cache the result (if cache is available)
            try:
                await cache_set(cache_key_name, json.dumps(result_data), ttl=300)
            except Exception as ce:
                logger.error(f"Cache optimization failed: {ce}")
                pass
            logger.info(f"Fetched {len(items)} public prompts for sell-prompts (total: {total_count})")
            return APIResponse(data=result_data, message="Public prompts fetched successfully")
        except Exception as e:
            logger.error(f"Error fetching public prompts: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch public prompts: {e}")

@router.get("/{prompt_id}")
async def get_prompt_details(prompt_id: str, user: dict = Depends(get_current_user), includeStats: bool = Query(False)):
    """Fetch prompt details, stats, versions, buyer list for dashboard."""
    user_id = user["uid"]
    logger.info(f"Fetching prompt details for ID: {prompt_id}, UID: {user_id}, includeStats={includeStats}")
    try:
        prompt = await db.prompts.find_one({"_id": prompt_id, "user_id": user_id})
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        latest_version_id = prompt.get("latest_version_id")
        version = None
        if latest_version_id:
            version = await db.prompt_versions.find_one({"_id": latest_version_id, "prompt_id": prompt_id})
        data = {
            "_id": str(prompt.get("_id")),
            "title": prompt.get("title"),
            "shortDesc": prompt.get("description", ""),
            "content": prompt.get("content", ""),
            "price": prompt.get("price", 0),
            "tags": prompt.get("tags", []),
            "status": prompt.get("status", "draft"),
            "thumbnailUrl": prompt.get("thumbnailUrl", ""),
            "versions": [],
            "stats": {},
            "latest_version": optimize_mongo_response(version) if version else None,
        }
        # Add versions
        versions = await db.prompt_versions.find({"prompt_id": prompt_id}).sort("created_at", DESCENDING).to_list(length=20)
        data["versions"] = [{
            "versionId": str(v.get("_id")),
            "editedAt": v.get("created_at"),
            "editorId": v.get("created_by")
        } for v in versions]
        if includeStats:
            # Aggregate stats from analytics_daily
            stats = {"views": [], "sales": [], "totalViews": 0, "totalSales": 0, "avgRating": 0}
            analytics = await db.analytics_daily.find({"promptId": prompt_id}).sort("date", 1).to_list(length=90)
            for a in analytics:
                stats["views"].append({"date": a["date"], "count": a.get("views", 0)})
                stats["sales"].append({"date": a["date"], "count": a.get("buys", 0), "revenue": a.get("revenue", 0)})
                stats["totalViews"] += a.get("views", 0)
                stats["totalSales"] += a.get("buys", 0)
            stats["avgRating"] = prompt.get("performance", {}).get("rating", 0)
            data["stats"] = stats
            # Buyer list (anonymized)
            buyers = await db.sales.find({"promptId": prompt_id}).to_list(length=50)
            data["buyers"] = [{"buyer": s.get("buyerAnonymizedId", "anon"), "price": s.get("price", 0), "createdAt": s.get("createdAt") } for s in buyers]
        return APIResponse(data=data, message="Prompt details fetched")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching prompt details {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch prompt details")

@router.delete("/{prompt_id}")
async def delete_prompt(prompt_id: str, user: dict = Depends(get_current_user)):
    """Delete prompt and all its versions."""
    user_id = user["uid"]
    logger.info(f"Deleting prompt {prompt_id} for UID: {user_id}")
    try:
        prompt = await db.prompts.find_one({"_id": prompt_id, "user_id": user_id})
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        # Soft-delete: set status=archived, require confirmation
        await db.prompts.update_one({"_id": prompt_id}, {"$set": {"status": "archived", "archivedAt": datetime.utcnow().replace(tzinfo=timezone.utc)}})
        await track_event(user_id=user_id, event_type="prompt_archived", event_data={"prompt_id": prompt_id})
        return APIResponse(data={"prompt_id": prompt_id}, message="Prompt archived (soft-delete)")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error archiving prompt {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to archive prompt")

@router.put("/{prompt_id}")
async def update_prompt(prompt_id: str, request: UpdatePromptRequest, user: dict = Depends(get_current_user)):
    """Create a new version and update prompt metadata."""
    user_id = user["uid"]
    logger.info(f"Updating prompt {prompt_id} for UID: {user_id}")
    try:
        prompt = await db.prompts.find_one({"_id": prompt_id, "user_id": user_id})
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")

        now_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
        next_version = int(prompt.get("version", 1)) + 1
        version_id = str(uuid.uuid4())

        version_doc = {
            "_id": version_id,
            "prompt_id": prompt_id,
            "user_id": user_id,
            "version_number": next_version,
            "content": request.body,
            "llm_role": request.role or prompt.get("role", "As defined in prompt"),
            "type": "text",
            "status": "active",
            "changelog": "User update",
            "metadata": {},
            "created_at": now_dt,
        }
        await db.prompt_versions.insert_one(version_doc)

        await db.prompts.update_one(
            {"_id": prompt_id},
            {"$set": {"title": request.title, "content": request.body, "updated_at": now_dt, "latest_version_id": version_id,"last_modified_by": user_id,},
             "$inc": {"version": 1, "version_count": 1},},
        )
        
    # No cache delete (Mongo-only, no cache layer)
        
        await track_event(user_id=user_id, event_type="prompt_updated", event_data={"prompt_id": prompt_id, "version_number": next_version})

        return APIResponse(
            data={"prompt_id": prompt_id, "version_number": next_version, "latest_version_id": version_id},
            message="Prompt updated",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating prompt {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update prompt")

@router.get("/{prompt_id}/versions")
async def get_prompt_versions(
    prompt_id: str,
    user: dict = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=100, description="Number of versions to return"),
    offset: int = Query(0, ge=0, description="Number of versions to skip"),
):
    """Fetch a prompt's version history."""
    user_id = user["uid"]
    try:
        prompt = await db.prompts.find_one({"_id": prompt_id, "user_id": user_id})
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        versions = await db.prompt_versions.find(
            {"prompt_id": prompt_id, "user_id": user_id}
        ).sort("created_at", DESCENDING).skip(offset).limit(limit).to_list(length=limit)
        
        versions = [optimize_mongo_response(v) for v in versions]

        return APIResponse(data=versions, message="Prompt versions fetched successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching prompt versions for {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch prompt versions: {e}")

@router.post("/bulk-action")
async def bulk_prompt_action(request: Request, user: dict = Depends(get_current_user)):
    """Perform bulk actions on multiple prompts."""
    user_id = user["uid"]
    try:
        body = await request.json()
        prompt_ids: List[str] = body.get("prompt_ids", []) or []
        action: str = body.get("action", "")
        action_data: Dict[str, Any] = body.get("action_data", {}) or {}
        if not prompt_ids or not action:
            raise HTTPException(status_code=400, detail="prompt_ids and action are required")
        if len(prompt_ids) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 prompts per bulk action")

        # Define supported actions
        SUPPORTED_BULK_ACTIONS = ["delete", "star", "unstar", "categorize", "tag", "untag", "make_public", "make_private"]
        
        if action not in SUPPORTED_BULK_ACTIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported action '{action}'. Supported actions: {', '.join(SUPPORTED_BULK_ACTIONS)}"
            )

        ids_set = list({str(pid) for pid in prompt_ids})
        processed_count = 0
        
        if action == "delete":
            await db.prompt_versions.delete_many({"prompt_id": {"$in": ids_set}, "user_id": user_id})
            res = await db.prompts.delete_many({"_id": {"$in": ids_set}, "user_id": user_id})
            processed_count = res.deleted_count
            
        elif action in ("star", "unstar"):
            val = (action == "star")
            res = await db.prompts.update_many(
                {"_id": {"$in": ids_set}, "user_id": user_id},
                {"$set": {"starred": val, "updated_at": datetime.utcnow()}},
            )
            processed_count = res.modified_count
            
        elif action == "categorize":
            new_category = action_data.get("category")
            if not new_category:
                raise HTTPException(status_code=400, detail="Missing category for categorize action")
            res = await db.prompts.update_many(
                {"_id": {"$in": ids_set}, "user_id": user_id},
                {"$set": {"category": new_category, "updated_at": datetime.utcnow()}},
            )
            processed_count = res.modified_count
            
        elif action in ("tag", "untag"):
            tags = action_data.get("tags", [])
            if not tags:
                raise HTTPException(status_code=400, detail=f"Missing tags for {action} action")
            
            if action == "tag":
                # Add tags (use $addToSet to avoid duplicates)
                res = await db.prompts.update_many(
                    {"_id": {"$in": ids_set}, "user_id": user_id},
                    {"$addToSet": {"tags": {"$each": tags}}, "$set": {"updated_at": datetime.utcnow()}},
                )
            else:  # untag
                # Remove tags
                res = await db.prompts.update_many(
                    {"_id": {"$in": ids_set}, "user_id": user_id},
                    {"$pull": {"tags": {"$in": tags}}, "$set": {"updated_at": datetime.utcnow()}},
                )
            processed_count = res.modified_count
            
        elif action in ("make_public", "make_private"):
            visibility = "public" if action == "make_public" else "private"
            res = await db.prompts.update_many(
                {"_id": {"$in": ids_set}, "user_id": user_id},
                {"$set": {"visibility": visibility, "updated_at": datetime.utcnow()}},
            )
            processed_count = res.modified_count
            # Emit purchase event for each prompt made public (simulate purchase)
            if action == "make_public":
                for pid in ids_set:
                    await track_event(user_id=user_id, event_type="purchase", event_data={"prompt_id": pid})
            
    # No cache delete (Mongo-only, no cache layer)

        return APIResponse(
            data={
                "processed_count": int(processed_count),
                "action": action,
                "prompt_ids": ids_set,
                "action_data": action_data
            },
            message=f"Bulk action '{action}' completed on {int(processed_count)} prompts",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error performing bulk action for UID: {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Bulk action failed: {e}")
