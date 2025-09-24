

# ------------------------------ ANALYTICS DASHBOARD (Mongo) ------------------------------
# api/analytics.py
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body
import logging
from api.models import ExportRequest, AnalyticsJobRequest ,APIResponse

from dependencies import (
    limiter,
    get_current_user,
    track_event,
    db
)

from fastapi import Request
router = APIRouter()
logger = logging.getLogger(__name__)

# --- Analytics Events Endpoint (for VS Code Extension) ---
@router.get("/events")
async def get_analytics_events(request: Request):
    """VS Code extension analytics events GET endpoint"""
    logger.info(f"Analytics GET request from {request.client.host}")
    return {
        "status": "ok",
        "events": [],
        "message": "Analytics endpoint active"
    }
@router.get("/v1/analytics/aggregator-health")
async def get_aggregator_health():
    """
    Returns aggregator health: last successful aggregation timestamp, job status, and staleness indicator.
    """
    from datetime import timezone
    # Find last completed analytics aggregation job
    job = await db["analytics_jobs"].find_one({"job_type": "aggregation", "status": "completed"}, sort=[("completed_at", -1)])
    last_aggregated_at = job.get("completed_at") if job else None
    now = datetime.now(timezone.utc)
    staleness_seconds = None
    staleness = "unknown"
    if last_aggregated_at:
        staleness_seconds = (now - last_aggregated_at).total_seconds()
        if staleness_seconds < 3600:
            staleness = "green"
        elif staleness_seconds < 6*3600:
            staleness = "orange"
        else:
            staleness = "red"
    return {
        "last_aggregated_at": last_aggregated_at.isoformat() if last_aggregated_at else None,
        "job_status": job.get("status") if job else None,
        "staleness_seconds": staleness_seconds,
        "staleness": staleness
    }
@router.post("/events")
async def log_analytics_events(
    events_data: dict = Body(...),
    user: dict = Depends(get_current_user)
):
    """
    Receive and log analytics events from VS Code extension and other clients.
    """
    user_id = user["uid"]
    events = events_data.get("events", [])
    session_id = events_data.get("session_id")
    
    now = datetime.now(timezone.utc)
    
    # Process each event
    processed_events = []
    for event in events:
        event_doc = {
            "user_id": user_id,
            "session_id": session_id,
            "event_type": event.get("type"),
            "event_data": event.get("data", {}),
            "timestamp": event.get("timestamp", now.isoformat()),
            "created_at": now
        }
        processed_events.append(event_doc)
    
    # Bulk insert events if any
    if processed_events:
        await db["analytics_events"].insert_many(processed_events)
        logger.info(f"Logged {len(processed_events)} analytics events for user {user_id}")
    
    return {
        "status": "success", 
        "message": f"Processed {len(processed_events)} analytics events",
        "events_processed": len(processed_events)
    }


# --- Analytics Performance Endpoint ---
@router.post("/performance")
async def log_performance_metrics(
    metrics: dict = Body(...),
    user: dict = Depends(get_current_user)
):
    """
    Receive and log web/app vitals from the frontend (CLS, FCP, LCP, etc.).
    """
    user_id = user["uid"]
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "metrics": metrics,
        "created_at": now
    }
    await db["web_vitals"].insert_one(doc)
    return {"status": "success", "message": "Performance metrics logged"}



@router.get("/dashboard")
async def get_analytics_dashboard(
    range: str = Query("30d"),
    user: dict = Depends(get_current_user),
    request: Request = None
):
    """
    Get a comprehensive analytics dashboard.
    Pro users get full analytics, free users get limited/basic stats.
    """
    user_id = user["uid"]
    plan = (user.get("plan") or user.get("claims", {}).get("plan") or "free").lower()
    logger.info(f"Analytics dashboard request for user: {user_id} with range: {range} (plan: {plan})")


    try:
        # Always return real usage stats for all users
        days_map = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
        days = days_map.get(range, 30)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        prompts_count = await db.prompts.count_documents({"user_id": user_id})

        # Marketplace stats
        purchases_cursor = db.marketplace_purchases.find({"seller_id": user_id, "created_at": {"$gte": start_date}})
        listings_sold = 0
        revenue_earned = 0
        async for p in purchases_cursor:
            listings_sold += 1
            revenue_earned += int(p.get("seller_earnings", 0))

        # Popular categories
        cat_counts: Dict[str, int] = defaultdict(int)
        async for p in db.prompts.find({"user_id": user_id}, projection={"category": 1}):
            cat_counts[p.get("category", "Uncategorized")] += 1
        popular_categories = [{"category": k, "count": v} for k, v in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:5]]

        analytics_data = {
            "overview": {
                "total_prompts": prompts_count,
                "listings_sold_in_period": listings_sold,
                "revenue_earned_in_period": revenue_earned,
            },
            "usage_stats": {
                "popular_categories": popular_categories,
            },
            "period": {"days": days},
            "data_source": "mongo_fallback"
        }

        return APIResponse(data=analytics_data, message="Analytics data retrieved successfully")

    except Exception as e:
        logger.error(f"Error fetching analytics for UID: {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch analytics data")
    """
    Comprehensive analytics (Mongo-native).
    Sources:
      - db.prompts (user_id)
      - db.users (credits)
      - db.user_analytics (events)
      - db.marketplace_purchases (seller_id/buyer_id)
      - db.marketplace_listings (seller_id for ratings/downloads)
    """
    user_id = user["uid"]

    try:
        days_map = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
        days = days_map.get(range, 30)
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        # Prompts count
        prompts_count = await db.prompts.count_documents({"user_id": user_id})

        # Credits
        user_doc = await db.users.find_one({"_id": user_id}, projection={"credits": 1})
        total_credits = int((user_doc or {}).get("credits", 0))

        # Analytics events (if your track_event stores here)
        analytics_cursor = db.user_analytics.find(
            {"userId": user_id, "timestamp": {"$gte": start_date}}
        )
        analytics_docs = []
        async for ev in analytics_cursor:
            analytics_docs.append(ev)

        # Generation events (loosely defined)
        total_generations = sum(1 for ev in analytics_docs if ev.get("eventType") in {"prompt_analyzed", "prompt_remixed", "ideas_generated", "prompt_test_driven"})
        successes = total_generations  # adjust if you log failures separately
        success_rate = (successes / total_generations * 100.0) if total_generations else 0.0

        # Marketplace stats as seller
        purchases_cursor = db.marketplace_purchases.find(
            {"seller_id": user_id, "created_at": {"$gte": start_date}}
        )
        listings_sold = 0
        revenue_earned = 0
        async for p in purchases_cursor:
            listings_sold += 1
            revenue_earned += int(p.get("seller_earnings", 0))

        # Listings for rating/downloads
        lst_cursor = db.marketplace_listings.find({"seller_id": user_id})
        total_downloads = 0
        rating_sum = 0.0
        rating_count = 0
        async for l in lst_cursor:
            total_downloads += int(l.get("downloads", 0))
            if "rating" in l:
                rating_sum += float(l.get("rating", 0.0))
                rating_count += 1
        average_rating = (rating_sum / rating_count) if rating_count else 0.0

        # Daily generations
        daily_counts = defaultdict(int)
        for ev in analytics_docs:
            ts = ev.get("timestamp")
            if ts and hasattr(ts, "date"):
                daily_counts[ts.date().isoformat()] += 1
        daily_generations = [
            {
                "date": (start_date + timedelta(days=i)).date().isoformat(),
                "count": daily_counts.get((start_date + timedelta(days=i)).date().isoformat(), 0),
            }
            for i in range(days)
        ]

        # Popular categories
        cat_counts: Dict[str, int] = {}
        async for p in db.prompts.find({"user_id": user_id}, projection={"category": 1}):
            cat = p.get("category", "Uncategorized")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        popular_categories = [
            {"category": k, "count": v} for k, v in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        # Top performing prompts (by events count)
        usage_counts: Dict[str, int] = defaultdict(int)
        for ev in analytics_docs:
            pid = (ev.get("eventData") or {}).get("prompt_id") or ev.get("prompt_id")
            if pid:
                usage_counts[pid] += 1

        top_prompt_ids = sorted(usage_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        top_prompts = []
        for pid, cnt in top_prompt_ids:
            pr = await db.prompts.find_one({"_id": pid}, projection={"title": 1})
            top_prompts.append(
                {
                    "prompt_id": pid,
                    "title": (pr or {}).get("title", "Untitled"),
                    "generations": cnt,
                    "rating": (pr or {}).get("rating", 0),
                }
            )

        # Time series
        credits_over_time = [
            {"date": (start_date + timedelta(days=i)).isoformat(), "credits": total_credits} for i in range(days)
        ]
        generation_trends = [
            {
                "date": (start_date + timedelta(days=i)).isoformat(),
                "generations": daily_counts.get((start_date + timedelta(days=i)).date().isoformat(), 0),
            }
            for i in range(days)
        ]

        analytics_data = {
            "overview": {
                "total_prompts": int(prompts_count),
                "total_credits": total_credits,
                "total_generations": int(total_generations),
                "success_rate": success_rate,
            },
            "usage_stats": {
                "daily_generations": daily_generations,
                "popular_categories": popular_categories,
                "prompt_performance": top_prompts,
            },
            "marketplace_stats": {
                "listings_sold": int(listings_sold),
                "revenue_earned": int(revenue_earned),
                "average_rating": float(average_rating),
                "total_downloads": int(total_downloads),
            },
            "time_series": {
                "credits_over_time": credits_over_time,
                "generation_trends": generation_trends,
            },
            "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "days": days},
        }

        return APIResponse(data=analytics_data, message="Analytics data retrieved successfully")

    except Exception as e:
        logger.error(f"Error fetching analytics for UID: {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {e}")



@router.post("/exports/prompts")
@limiter.limit("5/minute")
async def export_prompts_data(
    export_request: ExportRequest,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """
    Export user's prompt data in CSV/JSON/XLSX (XLSX returned as CSV for now).
    Mongo-only queries against db['prompts'].
    """
    user_id = user['uid']
    logger.info(f"Prompts export request from user: {user_id}, format: {export_request.format}")

    async with performance_monitor("prompts_export"):
        try:
            # --- 1) Validate request ---
            valid_formats = ["csv", "json", "xlsx"]
            if export_request.format not in valid_formats:
                raise HTTPException(status_code=400, detail=f"Invalid format. Supported: {valid_formats}")

            valid_types = ["prompts", "analytics", "usage", "performance"]
            if export_request.export_type not in valid_types:
                raise HTTPException(status_code=400, detail=f"Invalid export type. Supported: {valid_types}")

            # --- 2) Date range ---
            if export_request.date_range == "custom":
                start_date = _parse_date_if_str(export_request.start_date)
                end_date = _parse_date_if_str(export_request.end_date)
                if not start_date or not end_date:
                    raise HTTPException(status_code=400, detail="Custom date range requires valid start_date and end_date")
            else:
                end_date = datetime.now(timezone.utc)
                if export_request.date_range == "7d":
                    start_date = end_date - timedelta(days=7)
                elif export_request.date_range == "90d":
                    start_date = end_date - timedelta(days=90)
                elif export_request.date_range == "1y":
                    start_date = end_date - timedelta(days=365)
                else:
                    start_date = end_date - timedelta(days=30)

            # --- 3) Build Mongo query (user + filters) ---
            q = {"user_id": user_id}
            q["created_at"] = {}
            if start_date:
                q["created_at"]["$gte"] = start_date
            if end_date:
                q["created_at"]["$lte"] = end_date
            if not q["created_at"]:
                del q["created_at"]

            if export_request.filters:
                cat = export_request.filters.get("category")
                if cat:
                    q["category"] = cat
                is_pub = export_request.filters.get("is_published")
                if is_pub is not None:
                    q["is_published"] = bool(is_pub)
                has_rev = export_request.filters.get("has_revenue")
                if has_rev:
                    q["total_revenue"] = {"$gt": 0}

            # Sorting + limit
            sort_by = export_request.sort_by or "created_at"
            direction = _sort_direction(export_request.sort_order)
            cur = db["prompts"].find(q).sort(sort_by, direction)
            if export_request.limit:
                cur = cur.limit(int(export_request.limit))

            # --- 4) Collect & shape data ---
            export_data = []
            total_revenue = 0.0
            total_views = 0

            async for p in cur:
                prompt_revenue = float(p.get('total_revenue', 0.0) or 0.0)
                prompt_views = int(p.get('view_count', 0) or 0)
                total_revenue += prompt_revenue
                total_views += prompt_views

                rec = {
                    'id': str(p.get('_id', '')),
                    'title': p.get('title', 'Untitled'),
                    'category': p.get('category', 'Uncategorized'),
                    'created_at': p.get('created_at'),
                    'updated_at': p.get('updated_at'),
                    'is_published': p.get('is_published', False),
                    'view_count': prompt_views,
                    'download_count': p.get('download_count', 0),
                    'total_revenue': prompt_revenue,
                    'rating_average': p.get('average_rating', 0.0),
                    'rating_count': p.get('rating_count', 0),
                    'tags': p.get('tags', []),
                    'character_count': len(p.get('prompt', '') or ''),
                    'marketplace_ready': p.get('marketplace_ready', False)
                }

                if export_request.include_columns:
                    rec = {k: v for k, v in rec.items() if k in export_request.include_columns}
                elif export_request.exclude_columns:
                    rec = {k: v for k, v in rec.items() if k not in export_request.exclude_columns}

                # Ensure datetimes are serializable later
                if isinstance(rec.get('created_at'), datetime):
                    rec['created_at'] = rec['created_at'].isoformat()
                if isinstance(rec.get('updated_at'), datetime):
                    rec['updated_at'] = rec['updated_at'].isoformat()

                export_data.append(rec)

            # --- 5) Generate export content ---
            export_id = str(uuid.uuid4())

            if export_request.format == "json":
                payload = {
                    "export_metadata": {
                        "export_id": export_id,
                        "export_type": export_request.export_type,
                        "user_id": user_id,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                        "total_records": len(export_data),
                        "summary": {
                            "total_revenue": total_revenue,
                            "total_views": total_views,
                            "avg_revenue_per_prompt": (total_revenue / len(export_data)) if export_data else 0
                        }
                    },
                    "data": export_data
                }
                export_content = json.dumps(payload, indent=2, default=str)
                content_type = "application/json"
                filename = f"prompts_export_{export_id}.json"

            else:
                # CSV (also used for XLSX fallback)
                output = io.StringIO()
                headers = list(export_data[0].keys()) if export_data else ["id"]
                writer = csv.DictWriter(output, fieldnames=headers)
                writer.writeheader()
                for row in export_data:
                    writer.writerow(row)
                export_content = output.getvalue()
                content_type = "text/csv"
                filename = f"prompts_export_{export_id}.csv"

            # Optionally: persist the file content to a storage (S3/minio/gridfs). Here we only record metadata row.
            export_record = {
                'export_id': export_id,
                'user_id': user_id,
                'export_type': export_request.export_type,
                'format': export_request.format,
                'record_count': len(export_data),
                'file_size': len(export_content),
                'created_at': datetime.now(timezone.utc),
                'expires_at': datetime.now(timezone.utc) + timedelta(days=7),
                'download_count': 0,
                'status': 'completed'
            }
            await db["exports"].insert_one(export_record)

            logger.info(f"Prompts export completed for user {user_id}: {len(export_data)} records, {len(export_content)} bytes")

            return APIResponse(
                data={
                    "export_id": export_id,
                    "filename": filename,
                    "content_type": content_type,
                    "file_size": len(export_content),
                    "record_count": len(export_data),
                    "download_url": f"/api/v4/exports/{export_id}/download",
                    "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                    "summary": {
                        "total_revenue": total_revenue,
                        "total_views": total_views,
                        "date_range": f"{start_date.date()} to {end_date.date()}"
                    }
                },
                message="Prompts export completed successfully"
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Prompts export failed for user {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Export processing failed")

@router.post("/exports/analytics")
@limiter.limit("3/minute")
async def export_analytics_data(
    export_request: ExportRequest,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """
    Export comprehensive analytics data (Mongo-only). Pro users only.
    """
    user_id = user['uid']
    plan = (user.get("plan") or user.get("claims", {}).get("plan") or "free").lower()
    logger.info(f"Analytics export request from user: {user_id} (plan: {plan})")

    if plan != "pro":
        raise HTTPException(status_code=403, detail="Analytics export is available to Pro users only. Upgrade to Pro to access this feature.")

    async with performance_monitor("analytics_export"):
        try:
            # --- 1) Date range ---
            if export_request.date_range == "custom":
                start_date = _parse_date_if_str(export_request.start_date)
                end_date = _parse_date_if_str(export_request.end_date)
                if not start_date or not end_date:
                    raise HTTPException(status_code=400, detail="Custom date range requires start_date and end_date")
            else:
                end_date = datetime.now(timezone.utc)
                if export_request.date_range == "7d":
                    start_date = end_date - timedelta(days=7)
                elif export_request.date_range == "90d":
                    start_date = end_date - timedelta(days=90)
                elif export_request.date_range == "1y":
                    start_date = end_date - timedelta(days=365)
                else:
                    start_date = end_date - timedelta(days=30)

            # --- 2) Collect analytics data ---
            user_doc = await db["users"].find_one({"_id": user_id})  # optional
            _ = user_doc or {}

            # Prompts within timeframe
            prompts_q = {"user_id": user_id, "created_at": {"$gte": start_date, "$lte": end_date}}
            prompts_cursor = db["prompts"].find(prompts_q)

            prompts_analytics = []
            category_performance = {}
            daily_metrics = {}

            async for p in prompts_cursor:
                created_date = p.get('created_at')
                if not created_date or not isinstance(created_date, datetime):
                    continue

                category = p.get('category', 'Uncategorized')
                revenue = float(p.get('total_revenue', 0.0) or 0.0)
                views = int(p.get('view_count', 0) or 0)
                downloads = int(p.get('download_count', 0) or 0)

                prompts_analytics.append({
                    'prompt_id': str(p.get('_id')),
                    'title': p.get('title', 'Untitled'),
                    'category': category,
                    'created_at': created_date.isoformat(),
                    'views': views,
                    'downloads': downloads,
                    'revenue': revenue,
                    'rating': float(p.get('average_rating', 0.0) or 0.0),
                    'conversion_rate': (downloads / views * 100) if views > 0 else 0.0
                })

                if category not in category_performance:
                    category_performance[category] = {
                        'prompts': 0, 'total_views': 0, 'total_downloads': 0, 'total_revenue': 0.0
                    }
                category_performance[category]['prompts'] += 1
                category_performance[category]['total_views'] += views
                category_performance[category]['total_downloads'] += downloads
                category_performance[category]['total_revenue'] += revenue

                date_key = created_date.date().isoformat()
                if date_key not in daily_metrics:
                    daily_metrics[date_key] = {'prompts_created': 0, 'total_views': 0, 'total_revenue': 0.0}
                daily_metrics[date_key]['prompts_created'] += 1
                daily_metrics[date_key]['total_views'] += views
                daily_metrics[date_key]['total_revenue'] += revenue

            # Revenue transactions
            tx_q = {"recipient_id": user_id, "created_at": {"$gte": start_date, "$lte": end_date}}
            transactions_cursor = db["transactions"].find(tx_q)
            revenue_analytics = []
            async for t in transactions_cursor:
                revenue_analytics.append({
                    'transaction_id': str(t.get('_id')),
                    'amount': float(t.get('amount', 0.0) or 0.0),
                    'created_at': t.get('created_at').isoformat() if isinstance(t.get('created_at'), datetime) else t.get('created_at'),
                    'prompt_id': t.get('prompt_id'),
                    'buyer_id': t.get('buyer_id'),
                    'commission_rate': float(t.get('commission_rate', 0.0) or 0.0)
                })

            # --- 3) Summary ---
            overview = {
                'total_prompts': len(prompts_analytics),
                'total_views': sum(p['views'] for p in prompts_analytics),
                'total_downloads': sum(p['downloads'] for p in prompts_analytics),
                'total_revenue': sum(p['revenue'] for p in prompts_analytics),
                'avg_rating': (sum(p['rating'] for p in prompts_analytics) / len(prompts_analytics)) if prompts_analytics else 0.0,
                'conversion_rate': (sum(p['conversion_rate'] for p in prompts_analytics) / len(prompts_analytics)) if prompts_analytics else 0.0
            }

            analytics_summary = {
                'overview': overview,
                'category_performance': category_performance,
                'daily_metrics': daily_metrics,
                'top_performers': sorted(prompts_analytics, key=lambda x: x['revenue'], reverse=True)[:10],
                'revenue_transactions': revenue_analytics
            }

            # --- 4) Format export ---
            export_id = str(uuid.uuid4())
            export_payload = {
                "export_metadata": {
                    "export_id": export_id,
                    "export_type": "analytics",
                    "user_id": user_id,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()}
                },
                "analytics_summary": analytics_summary,
                "detailed_data": {"prompts": prompts_analytics, "transactions": revenue_analytics}
            }

            if export_request.format == "json":
                export_content = json.dumps(export_payload, indent=2, default=str)
                content_type = "application/json"
                filename = f"analytics_export_{export_id}.json"
            else:
                # Simple CSV with overview metrics (extend as needed)
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=['metric', 'value'])
                writer.writeheader()
                for k, v in overview.items():
                    writer.writerow({'metric': k, 'value': v})
                export_content = output.getvalue()
                content_type = "text/csv"
                filename = f"analytics_export_{export_id}.csv"

            # Persist export record (content should be stored in your file store / GridFS; here we keep metadata only)
            await db["exports"].insert_one({
                'export_id': export_id,
                'user_id': user_id,
                'export_type': 'analytics',
                'format': export_request.format,
                'record_count': len(prompts_analytics) + len(revenue_analytics),
                'file_size': len(export_content),
                'created_at': datetime.now(timezone.utc),
                'expires_at': datetime.now(timezone.utc) + timedelta(days=7),
                'status': 'completed'
            })

            logger.info(f"Analytics export completed for user {user_id}")

            return APIResponse(
                data={
                    "export_id": export_id,
                    "filename": filename,
                    "content_type": content_type,
                    "file_size": len(export_content),
                    "record_count": len(prompts_analytics) + len(revenue_analytics),
                    "download_url": f"/api/v4/exports/{export_id}/download",
                    "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                    "analytics_preview": overview
                },
                message="Analytics export completed successfully"
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Analytics export failed for user {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Analytics export processing failed")


@router.post("/jobs/analytics")
@limiter.limit("3/minute")
async def create_analytics_job(
    job_request: AnalyticsJobRequest,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """
    Create background analytics processing job (Mongo-only). Pro users only.
    """
    user_id = user['uid']
    plan = (user.get("plan") or user.get("claims", {}).get("plan") or "free").lower()
    logger.info(f"Analytics job request from user: {user_id}, type: {job_request.job_type} (plan: {plan})")

    if plan != "pro":
        raise HTTPException(status_code=403, detail="Analytics jobs are available to Pro users only. Upgrade to Pro to access this feature.")

    async with performance_monitor("analytics_job_creation"):
        try:
            valid_job_types = ["export", "report", "analysis", "aggregation"]
            if job_request.job_type not in valid_job_types:
                raise HTTPException(status_code=400, detail=f"Invalid job type. Supported: {valid_job_types}")

            job_id = str(uuid.uuid4())
            # Simple human estimate text (for UI; not used for scheduling)
            estimated_duration = "2-5 minutes" if job_request.job_type == "export" else \
                                 "10-15 minutes" if job_request.job_type == "analysis" else \
                                 "15-30 minutes" if job_request.job_type == "aggregation" else \
                                 "5-10 minutes"

            job_data = {
                'job_id': job_id,
                'user_id': user_id,
                'job_type': job_request.job_type,
                'job_name': job_request.job_name or f"{job_request.job_type}_job",
                'parameters': job_request.parameters,
                'priority': job_request.priority,
                'status': 'queued',
                'progress': 0,
                'created_at': datetime.now(timezone.utc),
                'started_at': None,
                'completed_at': None,
                'estimated_duration': estimated_duration,
                'notification_email': job_request.notification_email,
                'retention_days': job_request.retention_days,
                'expires_at': datetime.now(timezone.utc) + timedelta(days=job_request.retention_days),
                'result_data': None,
                'error_message': None
            }

            await db["analytics_jobs"].insert_one(job_data)

            # Queue via n8n (non-blocking)
            try:
                await n8n.trigger_webhook('analytics-job-created', {
                    'job_id': job_id,
                    'user_id': user_id,
                    'job_type': job_request.job_type,
                    'priority': job_request.priority,
                    'parameters': job_request.parameters,
                    'timestamp': time.time()
                })
                logger.info(f"Analytics job {job_id} queued for processing")
            except Exception as webhook_error:
                logger.error(f"Failed to queue analytics job: {webhook_error}")
                await db["analytics_jobs"].update_one(
                    {"job_id": job_id},
                    {"$set": {
                        'status': 'failed',
                        'error_message': 'Failed to queue job for processing',
                        'completed_at': datetime.now(timezone.utc)
                    }}
                )
                raise HTTPException(status_code=500, detail="Failed to queue job for processing")

            return APIResponse(
                data={
                    "job_id": job_id,
                    "status": "queued",
                    "estimated_duration": estimated_duration,
                    "priority": job_request.priority,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "status_url": f"/api/jobs/analytics/{job_id}/status",
                    "result_url": f"/api/jobs/analytics/{job_id}/result",
                    "expires_at": (datetime.now(timezone.utc) + timedelta(days=job_request.retention_days)).isoformat()
                },
                message="Analytics job created and queued successfully"
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Analytics job creation failed for user {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Job creation failed")


@router.get("/jobs/analytics/{job_id}/status")
@limiter.limit("20/minute")
async def get_analytics_job_status(
    request: Request,
    job_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get status of analytics background job (Mongo-only).
    """
    user_id = user['uid']
    try:
        job_data = await db["analytics_jobs"].find_one({"job_id": job_id})
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        if job_data.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        return APIResponse(
            data={
                "job_id": job_id,
                "status": job_data.get('status', 'unknown'),
                "progress": job_data.get('progress', 0),
                "created_at": job_data.get('created_at'),
                "started_at": job_data.get('started_at'),
                "completed_at": job_data.get('completed_at'),
                "estimated_duration": job_data.get('estimated_duration'),
                "error_message": job_data.get('error_message'),
                "result_available": job_data.get('status') == 'completed' and job_data.get('result_data') is not None
            },
            message="Job status retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job status")