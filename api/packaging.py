
# api/packaging.py
import logging
import time
import hashlib
import json
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pymongo import ASCENDING, DESCENDING, UpdateOne, ReturnDocument

from api.models import PackageCreateRequest, PackageManagementRequest, APIResponse
from dependencies import (
    limiter, 
    get_current_user, 
    db, 
    track_event, 
    call_gemini_async, 
    safe_parse_json,
    cache_key,
    cache_get,
    cache_set,
    cache_delete
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Simple performance monitor context manager
@asynccontextmanager
async def performance_monitor(operation_name: str):
    """Simple performance monitoring context manager"""
    import time
    start_time = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start_time
        logger.info(f"Operation '{operation_name}' completed in {elapsed:.3f}s")




@router.post("/{prompt_id}/package")
@limiter.limit("3/minute")
async def package_prompt_for_marketplace(
    prompt_id: str,
    request_body: PackageCreateRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    async def suggest_dynamic_price(prompt_body, tags, base_price):
        """
        Suggest an optimal price based on recent marketplace sales, ratings, and competitor analysis.
        Returns (suggested_price, reasoning)
        """
        # 1. Find similar packages by tags/category
        tag_filter = {"tags": {"$in": tags or []}, "marketplace_ready": True, "status": "Packaged"}
        cursor = db["prompts"].find(tag_filter, {"price_suggestion_usd": 1, "total_sales": 1, "rating_average": 1}).sort("updated_at", -1).limit(20)
        prices = []
        sales = []
        ratings = []
        async for pkg in cursor:
            prices.append(pkg.get("price_suggestion_usd", 0.0))
            sales.append(pkg.get("total_sales", 0))
            ratings.append(pkg.get("rating_average", 0.0))
        # 2. Compute median price, top performer price, and average rating
        if prices:
            sorted_prices = sorted(prices)
            median_price = sorted_prices[len(prices)//2]
            top_price = sorted_prices[-1]
            avg_rating = sum(ratings)/len(ratings) if ratings else 0.0
            avg_sales = sum(sales)/len(sales) if sales else 0.0
            # 3. Heuristic: if avg_rating > 4.5 and avg_sales > 10, suggest top_price; else median; else base_price
            if avg_rating > 4.5 and avg_sales > 10:
                suggestion = top_price
                reason = f"Top similar packages are high performers (avg rating {avg_rating:.2f}, avg sales {avg_sales:.1f}). Suggesting top price ${top_price:.2f}."
            else:
                suggestion = median_price
                reason = f"Suggesting median price ${median_price:.2f} based on {len(prices)} similar packages."
        else:
            suggestion = base_price
            reason = "No similar packages found. Using base price."
        return round(suggestion, 2), reason
    user_id = user["uid"]
    config = {
        "basic_cost": 10,
        "premium_cost": 20,
        "max_daily_packages": 50,
        "required_status": "Architected",
    }
    cost = config["premium_cost"] if request_body.marketplace_ready else config["basic_cost"]
    today_key = datetime.now(timezone.utc).date().isoformat()
    now = datetime.now(timezone.utc)

    if not db:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    # 1) Partner + daily limit (ATOMIC)
    # - If user doesn't exist or not partner/approved -> fail
    # - If dailyPackages[today] >= max -> no match -> fail
    user_filter = {
        "_id": user_id,
        "$or": [{"is_partner": True}, {"isPartner": True}],
        "partnerStatus": {"$in": ["active", "approved"]},
        "$expr": {
            "$lt": [
                {"$ifNull": [f"$dailyPackages.{today_key}", 0]},
                config["max_daily_packages"],
            ]
        },
    }
    inc_map = {f"dailyPackages.{today_key}": 1}
    user_after = await db.users.find_one_and_update(
        user_filter,
        {"$inc": inc_map, "$set": {"lastPackageDate": now}},
        return_document=ReturnDocument.AFTER,
    )
    if not user_after:
        # find out why to return a meaningful error
        u = await db.users.find_one({"_id": user_id})
        if not u:
            raise HTTPException(status_code=404, detail="User profile not found")
        if not (u.get("is_partner") or u.get("isPartner")) or u.get("partnerStatus") not in ["active", "approved"]:
            raise HTTPException(status_code=403, detail="Marketplace packaging requires active Partner status")
        # daily limit exceeded
        raise HTTPException(status_code=429, detail=f"Daily packaging limit reached ({config['max_daily_packages']}/day)")

    # 2) Validate prompt + ensure latest version exists
    version_id = None
    prompt = await db.prompts.find_one({"_id": prompt_id, "user_id": user_id})
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found in your arsenal")

    version_id = prompt.get("latest_version_id") or prompt.get("latestVersionId")
    if not version_id:
        # revert daily inc if you want strict accounting (optional):
        # await db.users.update_one({"_id": user_id}, {"$inc": {f"dailyPackages.{today_key}": -1}})
        raise HTTPException(status_code=400, detail="Prompt must have content before packaging")

    version = await db.prompt_versions.find_one({"_id": version_id, "prompt_id": prompt_id})
    if not version:
        raise HTTPException(status_code=500, detail="Prompt version corrupted")

    prompt_body = version.get("content") or version.get("prompt_body") or ""
    if not prompt_body:
        raise HTTPException(status_code=500, detail="Prompt content empty")

    # 3) Credit check & atomic debit
    user_after_debit = await db.users.find_one_and_update(
        {"_id": user_id, "credits": {"$gte": cost}},
        {"$inc": {"credits": -cost, "total_purchased": 0}},  # total_purchased isn't credits; keep unchanged or adjust to your schema
        return_document=ReturnDocument.AFTER,
    )
    if not user_after_debit:
        # optional rollback of daily inc:
        # await db.users.update_one({"_id": user_id}, {"$inc": {f"dailyPackages.{today_key}": -1}})
        raise HTTPException(status_code=402, detail=f"Insufficient credits. Packaging costs {cost} credits.")
    new_credits = user_after_debit.get("credits", 0)


    # 4) Generate package via LLM (no cache)
    content_hash = hashlib.md5(
        f"{prompt_body}:{request_body.sales_title}:{request_body.price_usd}".encode()
    ).hexdigest()

    meta_prompt = f"""
You are \"The Merchant,\" an expert AI marketer and prompt marketplace specialist. 
Analyze the prompt and generate a compelling marketplace package.

PROMPT TO ANALYZE:
---
{prompt_body}
---

USER PREFERENCES:
- Custom Sales Title: {request_body.sales_title or 'Auto-generate'}
- Custom Sales Copy: {request_body.sales_copy or 'Auto-generate'}
- Custom Tags: {request_body.tags or 'Auto-generate'}
- Suggested Price: {request_body.price_usd or 'Auto-suggest'}

Return ONLY JSON with keys:
{{
  "sales_title": "...",
  "sales_copy": "...",
  "tags": ["k1","k2","k3","k4","k5"],
  "price_suggestion_usd": 4.99,
  "complexity_score": 7,
  "target_audience": "...",
  "use_cases": ["...","...","..."],
  "competitive_advantage": "..."
}}
""".strip()

    raw = await call_gemini_async(meta_prompt)
    package_data = safe_parse_json(raw)
    required = {
        "sales_title", "sales_copy", "tags",
        "price_suggestion_usd", "complexity_score",
        "target_audience", "use_cases", "competitive_advantage",
    }
    if not isinstance(package_data, dict) or not required.issubset(package_data.keys()):
        raise HTTPException(status_code=500, detail="AI returned invalid package format")

    # 4b) Dynamic pricing suggestion
    dynamic_price, price_reason = await suggest_dynamic_price(prompt_body, package_data.get("tags", []), package_data.get("price_suggestion_usd", 4.99))
    package_data["dynamic_price_suggestion_usd"] = dynamic_price
    package_data["dynamic_price_reasoning"] = price_reason

    # 5) Apply user overrides
    if request_body.sales_title: package_data["sales_title"] = request_body.sales_title
    if request_body.sales_copy:  package_data["sales_copy"]  = request_body.sales_copy
    if request_body.tags:        package_data["tags"]        = request_body.tags
    if request_body.price_usd is not None:
        package_data["price_suggestion_usd"] = request_body.price_usd

    # 6) Atomic prompt status transition (Architected -> Packaged) + set fields
    update_fields = {
        "status": "Packaged",
        "sales_title": package_data["sales_title"],
        "sales_copy": package_data["sales_copy"],
        "tags": package_data["tags"],
        "price_suggestion_usd": package_data["price_suggestion_usd"],
        "complexity_score": package_data.get("complexity_score", 5),
        "target_audience": package_data.get("target_audience", ""),
        "use_cases": package_data.get("use_cases", []),
        "competitive_advantage": package_data.get("competitive_advantage", ""),
        "marketplace_ready": bool(request_body.marketplace_ready),
        "packaged_at": now,
        "package_version": "2.1",
        "package_cost": cost,
        "updated_at": now,
    }
    result = await db.prompts.update_one(
        {"_id": prompt_id, "user_id": user_id, "status": config["required_status"]},
        {"$set": update_fields}
    )
    if result.matched_count == 0:
        # Someone else packaged it meanwhile or status changed
        raise HTTPException(status_code=409, detail="Prompt already packaged or not in 'Architected' state")

    # 7) Analytics (no cache)
    await track_event(
        user_id=user_id,
        event_type="prompt_packaged",
        event_data={
            "prompt_id": prompt_id,
            "package_cost": cost,
            "credits_remaining": new_credits,
            "daily_packages_count": int(user_after.get("dailyPackages", {}).get(today_key, 0)) + 1,
            "marketplace_ready": bool(request_body.marketplace_ready),
            "complexity_score": package_data.get("complexity_score", 5),
            "price_suggestion": package_data["price_suggestion_usd"],
            "package_version": "2.1",
            "feature": "marketplace_packaging",
            "content_hash": content_hash,
        },
        session_id=getattr(user, "session_id", None),
    )

    logger.info(f"Prompt {prompt_id} packaged. Credits left: {new_credits}")
    return APIResponse(
        data={
            "package_data": package_data,
            "credits_remaining": new_credits,
            "marketplace_ready": bool(request_body.marketplace_ready),
            "cost": cost,
            "dynamic_price_suggestion_usd": dynamic_price,
            "dynamic_price_reasoning": price_reason,
        },
        message="Prompt successfully packaged for marketplace distribution (with dynamic price suggestion)",
    )

@router.get("/debug")
async def debug_packaging():
    """Simple debug endpoint to test packaging module"""
    return {"status": "ok", "message": "Packaging module is working", "timestamp": datetime.now().isoformat()}

@router.get("/")
@limiter.limit("30/minute")
async def list_user_packages(
    request: Request,
    user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None),
    marketplace: Optional[bool] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    user_id = user["uid"]

    if not db:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    # Query filter
    q = {"user_id": user_id, "status": "Packaged"}
    if marketplace is not None:
        q["marketplace_ready"] = marketplace
    if status:
        q["package_status"] = status

    valid_sort_fields = [
        "created_at","updated_at","title","price_suggestion_usd",
        "total_sales","rating_average","packaged_at"
    ]
    if sort_by not in valid_sort_fields:
        sort_by = "packaged_at"
    direction = DESCENDING if sort_order == "desc" else ASCENDING

    # Totals via aggregation
    pipeline = [
        {"$match": q},
        {"$group": {
            "_id": None,
            "total_packages": {"$sum": 1},
            "total_revenue": {"$sum": {"$ifNull": ["$total_revenue", 0.0]}},
            "total_sales": {"$sum": {"$ifNull": ["$total_sales", 0]}},
            "published_packages": {"$sum": {"$cond": [{"$eq": ["$marketplace_ready", True]}, 1, 0]}},
            "rating_sum": {"$sum": {"$multiply": [{"$ifNull": ["$rating_average", 0.0]}, {"$ifNull": ["$rating_count", 0]}]}},
            "rating_count": {"$sum": {"$ifNull": ["$rating_count", 0]}},
        }},
    ]
    agg_doc = await (db["prompts"].aggregate(pipeline).to_list(1))
    stats = agg_doc[0] if agg_doc else {
        "total_packages": 0, "total_revenue": 0.0, "total_sales": 0,
        "published_packages": 0, "rating_sum": 0.0, "rating_count": 0
    }
    draft_count = stats["total_packages"] - stats["published_packages"]
    avg_rating = (stats["rating_sum"] / stats["rating_count"]) if stats["rating_count"] > 0 else 0.0

    total_packages = int(stats["total_packages"])
    total_pages = (total_packages + limit - 1) // limit
    has_next = page < total_pages
    has_previous = page > 1

    # Page data
    cursor = (db["prompts"]
              .find(q, {
                  "title": 1, "sales_title": 1, "sales_copy": 1, "tags": 1,
                  "price_suggestion_usd": 1, "complexity_score": 1,
                  "target_audience": 1, "use_cases": 1, "competitive_advantage": 1,
                  "marketplace_ready": 1, "package_status": 1, "package_version": 1,
                  "packaged_at": 1, "published_at": 1, "total_sales": 1,
                  "total_revenue": 1.0, "download_count": 1, "rating_average": 1.0,
                  "rating_count": 1, "created_at": 1, "updated_at": 1, "last_sale_at": 1
              })
              .sort(sort_by, direction)
              .skip((page - 1) * limit)
              .limit(limit))

    packages = []
    async for p in cursor:
        packages.append({
            "id": str(p.get("_id", "")),
            "title": p.get("title", "Untitled"),
            "sales_title": p.get("sales_title", ""),
            "sales_copy": p.get("sales_copy", ""),
            "tags": p.get("tags", []),
            "price_usd": p.get("price_suggestion_usd", 0.0),
            "complexity_score": p.get("complexity_score", 5),
            "target_audience": p.get("target_audience", ""),
            "use_cases": p.get("use_cases", []),
            "competitive_advantage": p.get("competitive_advantage", ""),
            "marketplace_ready": p.get("marketplace_ready", False),
            "package_status": p.get("package_status", "draft"),
            "package_version": p.get("package_version", "1.0"),
            "packaged_at": p.get("packaged_at"),
            "published_at": p.get("published_at"),
            "total_sales": p.get("total_sales", 0),
            "total_revenue": p.get("total_revenue", 0.0),
            "download_count": p.get("download_count", 0),
            "rating_average": p.get("rating_average", 0.0),
            "rating_count": p.get("rating_count", 0),
            "created_at": p.get("created_at"),
            "updated_at": p.get("updated_at"),
            "last_sale_at": p.get("last_sale_at"),
        })

    return {
        "status": "success",
        "message": f"Retrieved {len(packages)} packages",
        "data": {
            "packages": packages,
            "statistics": {
                "total_packages": total_packages,
                "published_packages": int(stats["published_packages"]),
                "draft_packages": draft_count,
                "total_revenue": round(float(stats["total_revenue"]), 2),
                "total_sales": int(stats["total_sales"]),
                "average_rating": round(float(avg_rating), 2),
                "conversion_rate": round((int(stats["published_packages"]) / max(1, total_packages)) * 100, 1),
            },
            "pagination": {
                "current_page": page,
                "total_pages": total_pages,
                "total_items": total_packages,
                "items_per_page": limit,
                "has_next": has_next,
                "has_previous": has_previous,
                "next_page": page + 1 if has_next else None,
                "previous_page": page - 1 if has_previous else None
            },
            "filtering": {
                "status_filter": status,
                "marketplace_filter": marketplace,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "available_sorts": valid_sort_fields
            }
        },
        "performance": {
            "query_time": "fast",
            "cache_hit": False,
            "packages_scanned": total_packages
        }
    }


@router.post("/manage-bulk")
@limiter.limit("10/minute")
async def manage_packages_bulk(
    request_body: PackageManagementRequest,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """
    Bulk package ops: publish, unpublish, update pricing, delete. (Mongo-only)
    """
    user_id = user['uid']
    logger.info(f"Bulk package management request from user: {user_id}, action: {request_body.action}")

    async with performance_monitor("manage_packages_bulk"):
        try:
            valid_actions = ["publish", "unpublish", "update_pricing", "delete"]
            if request_body.action not in valid_actions:
                raise HTTPException(status_code=400, detail=f"Invalid action. Must be one of: {valid_actions}")

            # Validate package ownership & status
            verified_ids = []
            for package_id in request_body.package_ids:
                q = {"user_id": user_id}
                try:
                    q["_id"] = ObjectId(package_id)
                except Exception:
                    q["id"] = package_id
                doc = await db["prompts"].find_one(q)
                if not doc:
                    raise HTTPException(status_code=404, detail=f"Package '{package_id}' not found")
                if doc.get('status') != 'Packaged':
                    raise HTTPException(status_code=400, detail=f"Prompt '{package_id}' is not a package")
                verified_ids.append((package_id, q))

            results = []

            if request_body.action == "publish":
                ops = []
                for package_id, q in verified_ids:
                    set_update = {
                        'marketplace_ready': True,
                        'package_status': 'published',
                        'published_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                    if getattr(request_body, "bulk_tags", None):
                        set_update['tags'] = request_body.bulk_tags
                    ops.append(UpdateOne(q, {"$set": set_update}))
                if ops:
                    await db["prompts"].bulk_write(ops, ordered=False)
                for package_id, _ in verified_ids:
                    results.append({'package_id': package_id, 'status': 'published', 'message': 'Successfully published to marketplace'})

            elif request_body.action == "unpublish":
                ops = []
                for package_id, q in verified_ids:
                    ops.append(UpdateOne(q, {"$set": {
                        'marketplace_ready': False,
                        'package_status': 'draft',
                        'unpublished_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }}))
                if ops:
                    await db["prompts"].bulk_write(ops, ordered=False)
                for package_id, _ in verified_ids:
                    results.append({'package_id': package_id, 'status': 'unpublished', 'message': 'Successfully removed from marketplace'})

            elif request_body.action == "update_pricing":
                if not getattr(request_body, "new_price", None) or request_body.new_price <= 0:
                    raise HTTPException(status_code=400, detail="Valid new_price is required for pricing updates")
                ops = []
                for package_id, q in verified_ids:
                    ops.append(UpdateOne(q, {"$set": {
                        'price_suggestion_usd': request_body.new_price,
                        'pricing_updated_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }}))
                if ops:
                    await db["prompts"].bulk_write(ops, ordered=False)
                for package_id, _ in verified_ids:
                    results.append({'package_id': package_id, 'status': 'price_updated', 'message': f'Price updated to ${request_body.new_price}', 'new_price': request_body.new_price})

            elif request_body.action == "delete":
                # "Delete package" => revert prompt to Architected + remove package fields
                ops = []
                for package_id, q in verified_ids:
                    ops.append(UpdateOne(q, {
                        "$set": {
                            'status': 'Architected',
                            'marketplace_ready': False,
                            'package_status': 'deleted',
                            'deleted_at': datetime.utcnow(),
                            'updated_at': datetime.utcnow()
                        },
                        "$unset": {
                            'sales_title': "",
                            'sales_copy': "",
                            'price_suggestion_usd': "",
                            'complexity_score': "",
                            'target_audience': "",
                            'use_cases': "",
                            'competitive_advantage': "",
                            'packaged_at': ""
                        }
                    }))
                if ops:
                    await db["prompts"].bulk_write(ops, ordered=False)
                for package_id, _ in verified_ids:
                    results.append({'package_id': package_id, 'status': 'deleted', 'message': 'Package deleted, prompt reverted to Architected status'})

            # Cache invalidation (best-effort)
            try:
                await cache_delete(f"user_packages:{user_id}:*")  # if your cache supports glob
            except Exception:
                pass
            try:
                await cache_delete("marketplace_listings:*")
            except Exception:
                pass

            # n8n workflow
            try:
                await n8n.trigger_webhook('packages-bulk-action', {
                    'user_id': user_id,
                    'action': request_body.action,
                    'package_ids': request_body.package_ids,
                    'results': results,
                    'timestamp': time.time()
                })
            except Exception as workflow_error:
                logger.error(f"n8n workflow trigger failed: {workflow_error}")

            # Analytics event (via n8n)
            try:
                await n8n.trigger_webhook('analytics-event', {
                    'event_type': 'packages_bulk_action',
                    'user_id': user_id,
                    'action': request_body.action,
                    'package_count': len(request_body.package_ids),
                    'success_count': len(results),
                    'timestamp': time.time()
                })
            except Exception as analytics_error:
                logger.error(f"Analytics event failed: {analytics_error}")

            logger.info(f"Bulk package action '{request_body.action}' completed for {len(results)} packages")

            return APIResponse(
                data={
                    "action": request_body.action,
                    "processed_count": len(results),
                    "results": results,
                    "timestamp": time.time()
                },
                message=f"Bulk {request_body.action} operation completed successfully"
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to execute bulk package management for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Bulk package management failed: {str(e)}")
@router.get("/analytics")
@limiter.limit("10/minute")
async def get_package_analytics(
    request: Request,
    user: dict = Depends(get_current_user),
    timeframe: str = Query("30d", description="Analytics timeframe (7d, 30d, 90d, 1y)"),
    package_id: Optional[str] = Query(None, description="Specific package analytics")
):
    """
    Package performance analytics and insights. (Mongo-only)
    """
    user_id = user['uid']
    logger.info(f"Package analytics requested by user: {user_id}, timeframe: {timeframe}")

    async with performance_monitor("package_analytics"):
        try:
            cache_key_name = cache_key("package_analytics", f"{user_id}:{timeframe}:{package_id}")
            cached_result = await cache_get(cache_key_name)
            if cached_result:
                logger.info(f"Package analytics cache hit for user: {user_id}")
                return json.loads(cached_result)

            timeframe_days = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}.get(timeframe, 30)
            cutoff_date = datetime.utcnow() - timedelta(days=timeframe_days)

            q = {"user_id": user_id, "status": "Packaged"}
            if package_id:
                # constrain to a single package id
                try:
                    q["_id"] = ObjectId(package_id)
                except Exception:
                    q["id"] = package_id

            # (Optionally) filter by updated_at >= cutoff_date to bound timeframe
            # If you keep per-sale logs elsewhere, integrate them here.
            # For now we just compute over packaged prompts.
            cursor = db["prompts"].find(q)

            packages = []
            total_revenue = 0.0
            total_sales = 0
            total_downloads = 0
            rating_sum = 0.0
            rating_count = 0

            async for p in cursor:
                pkg = {
                    'id': str(p.get('_id')),
                    'title': p.get('title', 'Untitled'),
                    'sales_title': p.get('sales_title', ''),
                    'price_usd': p.get('price_suggestion_usd', 0.0),
                    'total_sales': p.get('total_sales', 0),
                    'total_revenue': p.get('total_revenue', 0.0),
                    'download_count': p.get('download_count', 0),
                    'rating_average': p.get('rating_average', 0.0),
                    'rating_count': p.get('rating_count', 0),
                    'marketplace_ready': p.get('marketplace_ready', False),
                    'packaged_at': p.get('packaged_at'),
                    'published_at': p.get('published_at'),
                    'tags': p.get('tags', []),
                    'target_audience': p.get('target_audience', ''),
                    'complexity_score': p.get('complexity_score', 5)
                }
                packages.append(pkg)

                total_revenue += float(pkg['total_revenue'])
                total_sales += int(pkg['total_sales'])
                total_downloads += int(pkg['download_count'])
                if int(pkg['rating_count']) > 0:
                    rating_sum += float(pkg['rating_average']) * int(pkg['rating_count'])
                    rating_count += int(pkg['rating_count'])

            avg_rating = (rating_sum / rating_count) if rating_count > 0 else 0.0
            avg_price = (sum(p['price_usd'] for p in packages) / max(1, len(packages))) if packages else 0.0
            conversion_rate = (sum(1 for p in packages if p['marketplace_ready']) / max(1, len(packages))) * 100 if packages else 0.0

            top_by_revenue = sorted(packages, key=lambda x: x['total_revenue'], reverse=True)[:5]
            top_by_sales = sorted(packages, key=lambda x: x['total_sales'], reverse=True)[:5]
            top_by_rating = sorted([p for p in packages if p['rating_count'] > 0], key=lambda x: x['rating_average'], reverse=True)[:5]

            # Tag performance
            tag_stats = {}
            for pkg in packages:
                for tag in pkg['tags']:
                    if tag not in tag_stats:
                        tag_stats[tag] = {'count': 0, 'revenue': 0.0, 'sales': 0}
                    tag_stats[tag]['count'] += 1
                    tag_stats[tag]['revenue'] += float(pkg['total_revenue'])
                    tag_stats[tag]['sales'] += int(pkg['total_sales'])
            top_tags = sorted(tag_stats.items(), key=lambda x: x[1]['revenue'], reverse=True)[:10]

            analytics_data = {
                "overview": {
                    "total_packages": len(packages),
                    "published_packages": sum(1 for p in packages if p['marketplace_ready']),
                    "total_revenue": round(total_revenue, 2),
                    "total_sales": total_sales,
                    "total_downloads": total_downloads,
                    "average_rating": round(avg_rating, 2),
                    "average_price": round(avg_price, 2),
                    "conversion_rate": round(conversion_rate, 1),
                    "timeframe": timeframe
                },
                "top_performers": {
                    "by_revenue": top_by_revenue,
                    "by_sales": top_by_sales,
                    "by_rating": top_by_rating
                },
                "tag_performance": [
                    {
                        "tag": tag,
                        "package_count": stats['count'],
                        "total_revenue": round(stats['revenue'], 2),
                        "total_sales": stats['sales'],
                        "avg_revenue_per_package": round(stats['revenue'] / max(1, stats['count']), 2)
                    } for tag, stats in top_tags
                ],
                "insights": {
                    "best_price_range": f"${max(1, int(avg_price * 0.8))}-${int(avg_price * 1.2) if avg_price else 0}",
                    "top_tags": [tag for tag, _ in top_tags[:5]],
                    "revenue_per_package": round(total_revenue / max(1, len(packages)), 2),
                    "sales_per_package": round(total_sales / max(1, len(packages)), 2),
                    "optimization_suggestions": [
                        "Focus on high-performing tags",
                        "Consider pricing optimization",
                        "Improve package descriptions for better conversion"
                    ]
                },
                "trends": {
                    "weekly": [],
                    "monthly": []
                }
            }

            if package_id and packages:
                pkg = packages[0]
                analytics_data["package_details"] = {
                    "performance_score": min(100, (int(pkg['total_sales']) * 10) + (float(pkg['rating_average']) * 15)),
                    "market_position": "top_10%" if float(pkg['total_revenue']) > (avg_price * 5) else "average",
                    "optimization_score": min(100, len(pkg['tags']) * 10 + (50 if pkg['marketplace_ready'] else 0)),
                    "recommendations": [
                        "Add more relevant tags" if len(pkg['tags']) < 5 else "Optimize tag selection",
                        "Consider price adjustment" if int(pkg['total_sales']) < 5 else "Maintain current pricing",
                        "Improve package description" if float(pkg['rating_average']) < 4.0 else "Excellent user satisfaction"
                    ]
                }

            response_data = {
                "status": "success",
                "message": "Package analytics retrieved successfully",
                "data": analytics_data,
                "performance": {
                    "query_time": "fast",
                    "cache_hit": False,
                    "packages_analyzed": len(packages)
                }
            }

            await cache_set(cache_key_name, json.dumps(response_data, default=str), 600)
            return response_data

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get package analytics for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve package analytics")
