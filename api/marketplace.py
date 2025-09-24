
# ------------------------------ MARKETPLACE: LIST PROMPT (Mongo) ------------------------------
# api/marketplace.py
import json
import os
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from api.models import MarketplaceListingRequest, MarketplacePurchaseRequest, PromptRatingRequest, APIResponse
from bson import ObjectId
from pymongo import DESCENDING
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body
import logging
from dependencies import get_current_user, db
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from bson import ObjectId
from api.prompts import optimize_mongo_response

def rate_key_user_or_ip(request: Request, uid_or_none=None):
    """Generate rate limiting key based on user ID or IP address"""
    # Prefer UID if present, else client IP (X-Forwarded-For first hop)
    if uid_or_none:
        return str(uid_or_none)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

# Initialize rate limiter with safe key function
limiter = Limiter(key_func=lambda request: getattr(request.state, 'rate_key', rate_key_user_or_ip(request)))

# Debug functionality
DEBUG_TRIGGER = os.getenv("DEBUG_TRIGGER", "false").lower() == "true"

def debug_print(message: str):
    """Print debug messages only if DEBUG_TRIGGER is enabled"""
    if DEBUG_TRIGGER:
        print(f"[MARKETPLACE DEBUG] {message}")
router = APIRouter()
logger = logging.getLogger(__name__)

# --- Marketplace Public Search Endpoint ---
from fastapi import Query
@router.get("/search", tags=["marketplace"])
async def search_marketplace(
    q: str = Query(None, description="Search text"),
    tag: str = Query(None, description="Tag filter"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Search public marketplace prompts by text or tag.
    """
    query = {"is_active": True, "status": "active"}
    if q:
        query["title_lowercase"] = {"$regex": q.lower(), "$options": "i"}
    if tag:
        query["tags"] = tag
    cursor = db.marketplace_listings.find(query).sort("created_at", -1).skip(offset).limit(limit)
    listings = []
    async for doc in cursor:
        item = dict(doc)
        if item.get("_id"):
            item["id"] = str(item.pop("_id"))
        for f in ("created_at", "updated_at", "listed_at"):
            if item.get(f) and hasattr(item[f], "isoformat"):
                item[f] = item[f].isoformat()
        listings.append(item)
    return {"listings": listings, "limit": limit, "offset": offset, "total": len(listings)}
@router.post("/purchase", tags=["marketplace"])
async def purchase_marketplace_prompt(request: Request, purchase: MarketplacePurchaseRequest, user: dict = Depends(get_current_user)):
    """Purchase a marketplace prompt: deduct credits, mark ownership, return run output or job id. Idempotent."""
    user_id = user["uid"]
    listing_id = purchase.listing_id
    # Check if already purchased (idempotent)
    existing = await db["marketplace_purchases"].find_one({"buyer_id": user_id, "listing_id": listing_id})
    if existing:
        # Already purchased, return job id or output if available
        return APIResponse(data={"job_id": existing.get("job_id"), "output": existing.get("output"), "already_owned": True}, message="Already purchased.")

    # Get listing and price
    listing = await db["marketplace_listings"].find_one({"_id": ObjectId(listing_id)})
    if not listing:
        raise HTTPException(status_code=404, detail="Marketplace listing not found")
    price_credits = int(listing.get("price_credits", 0))
    prompt_id = listing.get("prompt_id")

    # Deduct credits atomically
    user_doc = await db["users"].find_one_and_update(
        {"_id": user_id, "credits": {"$gte": price_credits}},
        {"$inc": {"credits": -price_credits}},
        return_document=ReturnDocument.AFTER,
    )
    if not user_doc:
        raise HTTPException(status_code=402, detail=f"Insufficient credits. Purchase costs {price_credits} credit(s).")

    # Mark ownership
    purchase_doc = {
        "buyer_id": user_id,
        "listing_id": listing_id,
        "prompt_id": prompt_id,
        "price_credits": price_credits,
        "purchased_at": datetime.utcnow(),
        # Optionally, run output or job id
        "job_id": str(uuid.uuid4()),
        "output": None,  # Placeholder for run output
    }
    await db["marketplace_purchases"].insert_one(purchase_doc)

    # Optionally, trigger run and store output (stub)
    # output = run_prompt(prompt_id, user_id)  # Implement as needed
    # await db["marketplace_purchases"].update_one({"_id": purchase_doc["_id"]}, {"$set": {"output": output}})

    return APIResponse(data={"job_id": purchase_doc["job_id"], "output": purchase_doc["output"], "new_credits": user_doc["credits"]}, message="Purchase successful.")
# --- Marketplace: Ownership Check ---
# --- Marketplace: Admin Leaderboard Endpoint ---
@router.get("/admin/leaderboard", tags=["marketplace"])
async def get_marketplace_leaderboard(limit: int = Query(20, ge=1, le=100)):
    """Return top sellers leaderboard for admins."""
    pipeline = [
        {"$match": {"is_active": True, "status": "active"}},
        {"$group": {"_id": "$seller_id", "totalSales": {"$sum": "$analytics.purchaseCount"}}},
        {"$sort": {"totalSales": -1}},
        {"$limit": limit}
    ]
    leaderboard = await db["marketplace_listings"].aggregate(pipeline).to_list(length=limit)
    for entry in leaderboard:
        seller = await db["users"].find_one({"_id": entry["_id"]})
        entry["seller"] = {
            "id": entry["_id"],
            "name": seller.get("displayName", "") if seller else "",
            "avatar": seller.get("avatarUrl", "") if seller else "",
            "verified": seller.get("verifiedSeller", False) if seller else False
        }
    return APIResponse(data={"leaderboard": leaderboard, "count": len(leaderboard)}, message="Leaderboard fetched")

# --- Marketplace: Admin Promotions Analytics Endpoint ---
@router.get("/admin/promotions", tags=["marketplace"])
async def get_marketplace_promotions_analytics(limit: int = Query(50, ge=1, le=200)):
    """Return promotion analytics for admins (impressions, clicks, conversions)."""
    cursor = db["marketplace_promotions"].find({}).sort("created_at", -1).limit(limit)
    promotions = [optimize_mongo_response(doc) async for doc in cursor]
    return APIResponse(data={"promotions": promotions, "count": len(promotions)}, message="Promotions analytics fetched")
# --- Marketplace: Recommendations Endpoint ---
@router.get("/recommendations", tags=["marketplace"])
async def get_marketplace_recommendations(
    userId: str = Query(None),
    promptId: str = Query(None),
    type: str = Query("for-you", description="Recommendation type: for-you|similar|popular"),
    limit: int = Query(12, ge=1, le=50)
):
    """Return recommended prompts for carousels: for-you, similar, popular."""
    query = {"is_active": True, "status": "active"}
    if type == "for-you" and userId:
        purchased = await db["marketplace_purchases"].find({"buyer_id": userId}).to_list(length=100)
        tags = set()
        for p in purchased:
            listing = await db["marketplace_listings"].find_one({"_id": ObjectId(p["listing_id"])})
            tags.update(listing.get("tags", []))
        if tags:
            query["tags"] = {"$in": list(tags)}
    elif type == "similar" and promptId:
        prompt = await db["marketplace_listings"].find_one({"_id": ObjectId(promptId)})
        tags = prompt.get("tags", []) if prompt else []
        if tags:
            query["tags"] = {"$in": tags}
            query["_id"] = {"$ne": ObjectId(promptId)}
    elif type == "popular":
        pass  # Default sort by purchaseCount
    sort_spec = [("analytics.purchaseCount", -1)] if type == "popular" else [("created_at", -1)]
    cursor = db["marketplace_listings"].find(query).sort(sort_spec).limit(limit)
    items = []
    async for doc in cursor:
        items.append({
            "_id": str(doc.get("_id")),
            "title": doc.get("title"),
            "slug": doc.get("slug", ""),
            "shortDesc": doc.get("description", ""),
            "thumbnail": doc.get("thumbnailUrl", ""),
            "price": doc.get("price", doc.get("price_credits", 0)),
            "currency": doc.get("currency", "INR"),
            "rating": doc.get("reviews", {}).get("averageRating", 0),
            "reviewsCount": doc.get("reviews", {}).get("totalReviews", 0),
            "salesCount": doc.get("analytics", {}).get("purchaseCount", doc.get("sales_count", 0)),
            "tags": doc.get("tags", []),
            "seller": {
                "id": doc.get("seller_id"),
                "name": doc.get("seller", {}).get("displayName", ""),
                "avatar": doc.get("seller", {}).get("avatarUrl", ""),
                "verified": doc.get("seller", {}).get("verifiedSeller", False)
            },
            "badges": doc.get("badges", [])
        })
    return APIResponse(data={"items": items, "type": type, "count": len(items)}, message=f"Recommendations ({type}) fetched")
# --- Marketplace: Seller Public Profile Endpoint ---
@router.get("/seller/{seller_id}", tags=["marketplace"])
async def get_marketplace_seller_profile(seller_id: str, limit: int = Query(20, ge=1, le=100), page: int = Query(1, ge=1)):
    """Return seller info, prompts, stats, badges for public seller page."""
    seller_doc = await db["users"].find_one({"_id": seller_id})
    if not seller_doc:
        raise HTTPException(status_code=404, detail="Seller not found")
    prompts_cursor = db["marketplace_listings"].find({"seller_id": seller_id, "is_active": True}).sort("created_at", -1).skip((page-1)*limit).limit(limit)
    prompts = []
    total_sales = 0
    avg_rating = 0.0
    ratings = []
    async for doc in prompts_cursor:
        total_sales += doc.get("analytics", {}).get("purchaseCount", doc.get("sales_count", 0))
        ratings.append(doc.get("reviews", {}).get("averageRating", 0))
        prompts.append({
            "_id": str(doc.get("_id")),
            "title": doc.get("title"),
            "slug": doc.get("slug", ""),
            "shortDesc": doc.get("description", ""),
            "thumbnail": doc.get("thumbnailUrl", ""),
            "price": doc.get("price", doc.get("price_credits", 0)),
            "currency": doc.get("currency", "INR"),
            "rating": doc.get("reviews", {}).get("averageRating", 0),
            "reviewsCount": doc.get("reviews", {}).get("totalReviews", 0),
            "salesCount": doc.get("analytics", {}).get("purchaseCount", doc.get("sales_count", 0)),
            "tags": doc.get("tags", []),
            "badges": doc.get("badges", [])
        })
    if ratings:
        avg_rating = round(sum(ratings)/len(ratings), 2)
    seller_info = {
        "id": seller_id,
        "name": seller_doc.get("displayName", ""),
        "avatar": seller_doc.get("avatarUrl", ""),
        "bio": seller_doc.get("bio", ""),
        "verified": seller_doc.get("verifiedSeller", False),
        "totalSales": total_sales,
        "avgRating": avg_rating,
        "badges": seller_doc.get("badges", [])
    }
    return APIResponse(data={"seller": seller_info, "prompts": prompts, "page": page, "limit": limit, "count": len(prompts)}, message="Seller profile fetched")
# --- Marketplace: Tag Landing Endpoint ---
@router.get("/tag/{tag}", tags=["marketplace"])
async def get_marketplace_tag_landing(tag: str, limit: int = Query(20, ge=1, le=100), page: int = Query(1, ge=1)):
    """Return prompts for a tag, for SEO-rich landing pages."""
    query = {"is_active": True, "status": "active", "tags": tag}
    cursor = db["marketplace_listings"].find(query).sort("created_at", -1).skip((page-1)*limit).limit(limit)
    items = []
    async for doc in cursor:
        item = {
            "_id": str(doc.get("_id")),
            "title": doc.get("title"),
            "slug": doc.get("slug", ""),
            "shortDesc": doc.get("description", ""),
            "thumbnail": doc.get("thumbnailUrl", ""),
            "price": doc.get("price", doc.get("price_credits", 0)),
            "currency": doc.get("currency", "INR"),
            "rating": doc.get("reviews", {}).get("averageRating", 0),
            "reviewsCount": doc.get("reviews", {}).get("totalReviews", 0),
            "salesCount": doc.get("analytics", {}).get("purchaseCount", doc.get("sales_count", 0)),
            "tags": doc.get("tags", []),
            "seller": {
                "id": doc.get("seller_id"),
                "name": doc.get("seller", {}).get("displayName", ""),
                "avatar": doc.get("seller", {}).get("avatarUrl", ""),
                "verified": doc.get("seller", {}).get("verifiedSeller", False)
            },
            "badges": doc.get("badges", [])
        }
        items.append(item)
    return APIResponse(data={"items": items, "tag": tag, "page": page, "limit": limit, "count": len(items)}, message=f"Prompts for tag {tag} fetched")
# --- Marketplace: Curated Rows Endpoint ---
@router.get("/curated", tags=["marketplace"])
async def get_curated_marketplace_rows(
    type: str = Query(..., description="Curated row type: trending|top|editors|new|for-you"),
    user: dict = Depends(get_current_user),
    limit: int = Query(12, ge=1, le=50)
):
    """Return curated carousel rows for marketplace: trending, top sellers, editors picks, newly listed, for-you."""
    query = {"is_active": True, "status": "active"}
    sort_spec = [("created_at", -1)]
    if type == "trending":
        sort_spec = [("analytics.viewCount", -1)]
    elif type == "top":
        sort_spec = [("analytics.purchaseCount", -1)]
    elif type == "editors":
        query["badges"] = "EditorsPick"
    elif type == "new":
        sort_spec = [("created_at", -1)]
        query["created_at"] = {"$gte": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)}
    elif type == "for-you":
        # Simple personalized: match tags from user's purchases
        user_id = user.get("uid")
        purchased = await db["marketplace_purchases"].find({"buyer_id": user_id}).to_list(length=100)
        tags = set()
        for p in purchased:
            listing = await db["marketplace_listings"].find_one({"_id": ObjectId(p["listing_id"])})
            tags.update(listing.get("tags", []))
        if tags:
            query["tags"] = {"$in": list(tags)}
    cursor = db["marketplace_listings"].find(query).sort(sort_spec).limit(limit)
    items = []
    async for doc in cursor:
        item = {
            "_id": str(doc.get("_id")),
            "title": doc.get("title"),
            "slug": doc.get("slug", ""),
            "shortDesc": doc.get("description", ""),
            "thumbnail": doc.get("thumbnailUrl", ""),
            "price": doc.get("price", doc.get("price_credits", 0)),
            "currency": doc.get("currency", "INR"),
            "rating": doc.get("reviews", {}).get("averageRating", 0),
            "reviewsCount": doc.get("reviews", {}).get("totalReviews", 0),
            "salesCount": doc.get("analytics", {}).get("purchaseCount", doc.get("sales_count", 0)),
            "tags": doc.get("tags", []),
            "seller": {
                "id": doc.get("seller_id"),
                "name": doc.get("seller", {}).get("displayName", ""),
                "avatar": doc.get("seller", {}).get("avatarUrl", ""),
                "verified": doc.get("seller", {}).get("verifiedSeller", False)
            },
            "badges": doc.get("badges", [])
        }
        items.append(item)
    return APIResponse(data={"items": items, "type": type, "count": len(items)}, message=f"Curated {type} row fetched")

@router.get("/{prompt_id}/ownership", tags=["marketplace"])
async def get_marketplace_ownership(request: Request, prompt_id: str, user: dict = Depends(get_current_user)):
    """Quickly check if current user owns the marketplace item."""
    user_id = user.get("uid") or user.get("_id")
    # Check ownership by user_id and prompt_id
    listing = await db["marketplace_listings"].find_one({"_id": prompt_id, "user_id": user_id})
    owns = bool(listing)
    return APIResponse(data={"owns": owns, "prompt_id": prompt_id}, message="Ownership check complete")

# --- Marketplace: My Listings (must come before /{id} route) ---
@router.get("/my-listings", tags=["marketplace"])
async def get_my_marketplace_listings(user: dict = Depends(get_current_user)):
    """Fetch current user's active marketplace listings (Mongo)."""
    user_id = user["uid"]
    debug_print(f"Fetching marketplace listings for user: {user_id}")
    try:
        debug_print(f"Querying marketplace_listings collection for seller_id: {user_id}")
        cursor = (
            db.marketplace_listings.find({"seller_id": user_id, "is_active": True})
            .sort("created_at", DESCENDING)
        )
        listings = []
        debug_print(f"Processing cursor results...")
        async for doc in cursor:
            debug_print(f"Processing document: {doc.get('_id', 'unknown')}")
            item = dict(doc)
            item["id"] = str(item.pop("_id"))
            for f in ("created_at", "updated_at", "listed_at"):
                if f in item and hasattr(item[f], "isoformat"):
                    item[f] = item[f].isoformat()
            listings.append(item)
        debug_print(f"Found {len(listings)} listings for user {user_id}")
        return APIResponse(data={"listings": listings}, message="Your active marketplace listings retrieved successfully")
    except Exception as e:
        debug_print(f"Exception in get_my_marketplace_listings: {e}")
        logger.error(f"Error fetching user's marketplace listings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch your listings")

# --- Marketplace: Public Prompt Details ---
@router.get("/{id}", tags=["marketplace"])
async def get_public_prompt_details(id: str, request: Request):
    """
    Fetch public prompt details by ID (listing or prompt ID).
    """
    from bson import ObjectId
    from dependencies import db as default_db
    db = request.app.state.db if hasattr(request.app.state, "db") else default_db
    # Try as listing ID first
    try:
        oid = ObjectId(id)
    except Exception:
        oid = id
    listing = await db["marketplace_listings"].find_one({"_id": oid})
    if not listing:
        # Try as prompt_id
        listing = await db["marketplace_listings"].find_one({"prompt_id": id})
    if not listing:
        raise HTTPException(status_code=404, detail="Marketplace prompt not found")
    # Normalize output
    result = {
        "id": str(listing.get("_id", id)),
        "title": listing.get("title", "Untitled"),
        "description": listing.get("description", ""),
        "tags": listing.get("tags", []),
        "price_credits": listing.get("price_credits"),
        "category": listing.get("category"),
        "sales_count": listing.get("sales_count", 0),
        "created_at": listing.get("created_at").isoformat() if listing.get("created_at") and hasattr(listing.get("created_at"), "isoformat") else listing.get("created_at"),
        "updated_at": listing.get("updated_at").isoformat() if listing.get("updated_at") and hasattr(listing.get("updated_at"), "isoformat") else listing.get("updated_at"),
        "seller_id": listing.get("seller_id"),
        "marketplace_ready": listing.get("status") == "active",
        "package_version": listing.get("package_version"),
        "complexity_score": listing.get("complexity_score"),
        "target_audience": listing.get("target_audience"),
        "use_cases": listing.get("use_cases", []),
        "sales_copy": listing.get("sales_copy", ""),
    }
    return {"prompt": result}
# --- Import required dependencies ---

@router.post("/list-prompt", tags=["marketplace"])
async def list_prompt_in_marketplace(request: MarketplaceListingRequest, user: dict = Depends(get_current_user)):
    """List a packaged prompt in the marketplace."""
    user_id = user["uid"]
    from bson import ObjectId
    logger.info(f"Marketplace listing requested for prompt {request.prompt_id} by user {user_id}")
    try:
        if db is None:
            raise HTTPException(status_code=503, detail="Database connection unavailable")
        try:
            prompt_oid = ObjectId(request.prompt_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid prompt_id")
        prompt = await db.prompts.find_one({"_id": prompt_oid, "user_id": user_id})
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found in your arsenal")
        if prompt.get("status") != "Packaged":
            raise HTTPException(status_code=400, detail="Only packaged prompts can be listed in marketplace")
        if prompt.get("marketplace_listing_id"):
            raise HTTPException(status_code=409, detail="Prompt is already listed in marketplace")
        listing_doc = {
            "prompt_id": request.prompt_id,
            "seller_id": user_id,
            "price_credits": int(request.price_credits),
            "description": request.description,
            "tags": request.tags or [],
            "prompt_title": prompt.get("title", "Untitled"),
            "status": "active",
            "sales_count": 0,
            "is_active": True,
            "is_public": True,
            "package_version": prompt.get("package_version", prompt.get("packageVersion", "2.0")),
            "complexity_score": prompt.get("complexity_score", prompt.get("complexityScore", 5)),
            "target_audience": prompt.get("target_audience", prompt.get("targetAudience", "")),
            "use_cases": prompt.get("use_cases", prompt.get("useCases", [])) or [],
            "sales_copy": prompt.get("sales_copy", prompt.get("salesCopy", "")),
            "title_lowercase": (prompt.get("title", "") or "").lower(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "listed_at": datetime.utcnow(),
        }
        ins = await db.marketplace_listings.insert_one(listing_doc)
        listing_id = str(ins.inserted_id)
        await db.prompts.update_one(
            {"_id": prompt_oid},
            {
                "$set": {
                    "marketplace_listing_id": listing_id,
                    "marketplace_status": "active",
                    "listed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        await track_event(
            user_id=user_id,
            event_type="marketplace_listing_created",
            event_data={
                "prompt_id": request.prompt_id,
                "listing_id": listing_id,
                "price_credits": int(request.price_credits),
                "package_version": listing_doc["package_version"],
                "complexity_score": listing_doc["complexity_score"],
                "feature": "marketplace",
            },
            session_id=getattr(user, "session_id", None),
        )
        logger.info(f"Prompt {request.prompt_id} listed in marketplace by user {user_id}")
        return APIResponse(
            data={"listing_id": listing_id, "prompt_id": request.prompt_id, "price_credits": int(request.price_credits), "status": "active"},
            message="Prompt listed in marketplace successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing prompt in marketplace: {e}")
        raise HTTPException(status_code=500, detail="Failed to list prompt in marketplace")
# ------------------------------ MARKETPLACE: LISTINGS QUERY (Mongo) ------------------------------
@router.get("/listings", tags=["marketplace"])
async def get_marketplace_listings(
    request: Request,
    category: Optional[str] = Query(None),
    sort_by: str = Query("recent", pattern="^(recent|popular|price)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user)
):
    """Get marketplace listings with filters (Mongo-only)."""
    q: Dict[str, Any] = {"is_active": True, "status": "active"}
    if category:
        q["category"] = category

    # Accept sort_by=recent as alias for newest
    if sort_by in ["recent", "newest"]:
        sort_spec = [("created_at", -1)]
    elif sort_by == "popular":
        sort_spec = [("analytics.purchaseCount", -1)]
    elif sort_by == "price":
        sort_spec = [("price", 1)]
    else:
        sort_spec = [("created_at", -1)]

    total_results = await db["marketplace_listings"].count_documents(q)
    cursor = (
        db["marketplace_listings"]
        .find(q)
        .sort(sort_spec)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )

    listings = []
    async for d in cursor:
        listings.append({
            "_id": str(d.get("_id")),
            "title": d.get("title"),
            "slug": d.get("slug", ""),
            "shortDesc": d.get("description", ""),
            "thumbnail": d.get("thumbnailUrl", ""),
            "price": d.get("price", d.get("price_credits", 0)),
            "currency": d.get("currency", "INR"),
            "rating": d.get("reviews", {}).get("averageRating", 0),
            "reviewsCount": d.get("reviews", {}).get("totalReviews", 0),
            "salesCount": d.get("analytics", {}).get("purchaseCount", d.get("sales_count", 0)),
            "tags": d.get("tags", []),
            "seller": {
                "id": d.get("seller_id"),
                "name": d.get("seller", {}).get("displayName", ""),
                "avatar": d.get("seller", {}).get("avatarUrl", ""),
                "verified": d.get("seller", {}).get("verifiedSeller", False)
            },
            "badges": d.get("badges", [])
        })

    total_pages = (total_results + per_page - 1) // per_page
    return APIResponse(
        data={
            "listings": listings,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_results": total_results,
                "total_pages": total_pages
            },
            "filters": {"category": category, "sort_by": sort_by}
        },
        message="Marketplace listings retrieved successfully"
    )
#=== END CHUNK
# ------------------------------ MARKETPLACE: PURCHASE (Mongo-native) ------------------------------

# --------------------------------------------------------------------------------------
# v4 Marketplace Listings (Mongo-native, cached)

@router.get("/preview/{prompt_id}", tags=["marketplace"])
@limiter.limit("30/minute")
async def preview_marketplace_item(
    request: Request,
    prompt_id: str,
    user: dict = Depends(get_current_user)
):
    try:
        listing = await db["marketplace_listings"].find_one({"_id": ObjectId(prompt_id)}) \
                  or await db["marketplace_listings"].find_one({"id": prompt_id})
        if not listing:
            raise HTTPException(status_code=404, detail="Marketplace item not found")
        preview = {
            "id": str(listing.get("_id", prompt_id)),
            "title": listing.get("title"),
            "category": listing.get("category"),
            "tags": listing.get("tags", []),
            "description": listing.get("description"),
            "price": listing.get("price"),
            "rating": listing.get("reviews", {}).get("averageRating", 0),
            "rating_count": listing.get("reviews", {}).get("totalReviews", 0),
            "view_count": listing.get("analytics", {}).get("viewCount", 0),
            "download_count": listing.get("analytics", {}).get("purchaseCount", 0),
            "created_at": listing.get("createdAt"),
            "creator": {
                "id": listing.get("sellerId"),
                "displayName": listing.get("seller", {}).get("displayName"),
                "total_prompts": listing.get("seller", {}).get("totalSales", 0),
                "is_partner": listing.get("seller", {}).get("verifiedSeller", False),
            },
            "marketplace_ready": listing.get("status") == "approved",
        }
        return APIResponse(data=preview, message="Preview retrieved successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Marketplace preview failed: {e}")
        raise HTTPException(status_code=500, detail="Preview failed")



@router.post("/rate", tags=["marketplace"])
@limiter.limit("10/hour")
async def rate_marketplace_prompt(
    request: Request,
    rating_request: PromptRatingRequest,
    user: dict = Depends(get_current_user)
):
    """Rate and review a marketplace prompt (Mongo-only, idempotent per user/prompt)."""
    user_id = user["uid"]
    logger.info(f"Rating prompt {rating_request.prompt_id} by user: {user_id}")
    try:
        purchased = await db["marketplace_purchases"].find_one({
            "buyer_id": user_id,
            "prompt_id": rating_request.prompt_id
        })
        if not purchased:
            raise HTTPException(status_code=403, detail="You can only rate prompts you have purchased")
        review_query = {"user_id": user_id, "prompt_id": rating_request.prompt_id}
        review_doc = {
            **review_query,
            "rating": rating_request.rating,
            "review_title": rating_request.review_title,
            "review_content": rating_request.review_content,
            "pros": rating_request.pros or [],
            "cons": rating_request.cons or [],
            "would_recommend": bool(rating_request.would_recommend) if rating_request.would_recommend is not None else None,
            "verified_purchase": True,
            "updated_at": datetime.utcnow(),
        }
        existing = await db["prompt_ratings"].find_one(review_query)
        if existing:
            await db["prompt_ratings"].update_one(review_query, {"$set": review_doc})
            action = "updated"
            rating_id = str(existing.get("_id"))
        else:
            review_doc["_id"] = str(uuid.uuid4())
            review_doc["created_at"] = datetime.utcnow()
            await db["prompt_ratings"].insert_one(review_doc)
            action = "created"
            rating_id = str(review_doc["_id"])
        # Recompute listing aggregates
        listing = await db["marketplace_listings"].find_one({"promptId": rating_request.prompt_id})
        if listing:
            pipe = [
                {"$match": {"prompt_id": rating_request.prompt_id}},
                {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "cnt": {"$sum": 1}}},
            ]
            agg = await db["prompt_ratings"].aggregate(pipe).to_list(length=1)
            avg = round(agg[0]["avg"], 2) if agg else 0.0
            cnt = agg[0]["cnt"] if agg else 0
            await db["marketplace_listings"].update_one(
                {"_id": listing["_id"]},
                {"$set": {"reviews.averageRating": avg, "reviews.totalReviews": cnt}}
            )
        return APIResponse(
            data={
                "rating_id": rating_id,
                "rating": rating_request.rating,
                "review_title": rating_request.review_title,
                "action": action,
                "prompt_id": rating_request.prompt_id
            },
            message=f"Rating {action} successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rate prompt {rating_request.prompt_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit rating")
# --- Marketplace: List Reviews ---
@router.get("/{prompt_id}/reviews", tags=["marketplace"])
async def list_marketplace_reviews(
    request: Request,
    prompt_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100)
):
    skip = (page - 1) * per_page
    cursor = db["prompt_ratings"].find({"prompt_id": prompt_id}).skip(skip).limit(per_page)
    reviews = [optimize_mongo_response(doc) async for doc in cursor]
    return {"reviews": reviews, "page": page, "per_page": per_page}
# --- Marketplace: Analytics (stub) ---
@router.get("/{prompt_id}/analytics", tags=["marketplace"])
async def get_marketplace_prompt_analytics(
    request: Request,
    prompt_id: str
):
    analytics = await db["marketplace_analytics"].find_one({"prompt_id": prompt_id})
    return {"analytics": optimize_mongo_response(analytics) if analytics else {}}
