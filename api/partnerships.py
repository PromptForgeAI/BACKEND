import logging
from fastapi import APIRouter, Depends, HTTPException, Request
router = APIRouter()
logger = logging.getLogger(__name__)
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dependencies import limiter ,get_current_user
from pymongo import DESCENDING
from api.models import PartnerRevenueRequest ,PartnershipApplicationRequest ,PartnerDashboardRequest



async def process_payout_request(user_id: str, user_data: dict, req: PartnerRevenueRequest):
    amount = float(req.payout_amount or 0.0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid payout amount")
    pending = float(user_data.get("pendingPayoutAmount", 0.0))
    if amount > pending:
        raise HTTPException(status_code=400, detail="Amount exceeds pending payout")
    payout_id = str(uuid.uuid4())
    now = datetime.utcnow()

    await db.payout_requests.insert_one(
        {"_id": payout_id, "user_id": user_id, "amount": amount, "status": "requested", "created_at": now}
    )
    await db.users.update_one({"_id": user_id}, {"$inc": {"pendingPayoutAmount": -amount}})

    await track_event(
        user_id=user_id,
        event_type="payout_requested",
        event_data={"amount": amount, "payout_id": payout_id},
        session_id=None,
    )
    return APIResponse(data={"payout_id": payout_id, "status": "requested"}, message="Payout request submitted")


async def update_payout_method(user_id: str, req: PartnerRevenueRequest):
    if not req.payment_method:
        raise HTTPException(status_code=400, detail="payment_method required")
    await db.payout_methods.update_one(
        {"user_id": user_id}, {"$set": {"method": req.payment_method, "updated_at": datetime.utcnow()}}, upsert=True
    )
    await track_event(
        user_id=user_id, event_type="payout_method_updated", event_data={"provider": req.payment_method.get("provider")}, session_id=None
    )
    return APIResponse(data={"updated": True}, message="Payout method updated")


async def get_revenue_summary(user_id: str, req: PartnerRevenueRequest):
    end = datetime.utcnow()
    start = end - timedelta(days=30)
    if req.statement_period == "last_month":
        # simple example bounds
        end = datetime.utcnow().replace(day=1)
        start = (end - timedelta(days=1)).replace(day=1)
    tx_cursor = db.transactions.find({"seller_id": user_id, "status": "completed", "created_at": {"$gte": start, "$lte": end}})
    total = 0.0
    count = 0
    async for t in tx_cursor:
        total += float(t.get("amount", 0.0))
        count += 1
    return APIResponse(data={"total_revenue": total, "transactions": count, "start": start.isoformat(), "end": end.isoformat()}, message="Revenue summary")


async def generate_tax_report(user_id: str, req: PartnerRevenueRequest):
    # Placeholder: generate a simple JSON tax summary document record
    report_id = str(uuid.uuid4())
    now = datetime.utcnow()
    await db.tax_reports.insert_one({"_id": report_id, "user_id": user_id, "generated_at": now, "format": "json"})
    return APIResponse(data={"report_id": report_id, "format": "json"}, message="Tax report generated")
#=== END CHUNK

@router.post("/request")
@limiter.limit("1/day")
async def request_partnership_enhanced(
    application: PartnershipApplicationRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Enhanced partnership application — Mongo-native."""
    user_id = user["uid"]
    logger.info(f"Enhanced partnership application from user: {user_id}")

    async with performance_monitor("partnership_application"):
        try:
            if not db:
                raise HTTPException(status_code=503, detail="Database connection unavailable")

            # 1) Verify user
            user_data = await db.users.find_one({"_id": user_id})
            if not user_data:
                raise HTTPException(status_code=404, detail="User profile not found")

            # 2) Basic scoring (heuristic)
            score = 0
            if application.business_type in {"startup", "enterprise"}:
                score += 20
            score += min(max(application.expected_monthly_volume // 100, 0), 50)
            if application.website_url:
                score += 10
            if application.portfolio_urls:
                score += 10
            score += 10 if "api" in (application.use_case or "").lower() else 0
            application_score = min(score, 100)

            auto_approve = application_score >= 60
            final_status = "approved" if auto_approve else "under_review"

            application_id = str(uuid.uuid4())
            now = datetime.utcnow()

            # 3) Persist application
            await db.partnership_applications.insert_one(
                {
                    "_id": application_id,
                    "user_id": user_id,
                    "payload": application.dict(),
                    "score": application_score,
                    "status": final_status,
                    "auto_approved": auto_approve,
                    "created_at": now,
                    "updated_at": now,
                }
            )

            # 4) Update user flags if approved
            if auto_approve:
                await db.users.update_one(
                    {"_id": user_id},
                    {
                        "$set": {
                            "is_partner": True,
                            "partner_tier": user_data.get("partner_tier", "standard"),
                            "partner_since": now,
                            "partner_commission_rate": user_data.get("partner_commission_rate", 0.70),
                        }
                    },
                )

            # 5) Usage + analytics
            current_month = now.strftime("%Y-%m")
            await db.usage.update_one(
                {"user_id": user_id, "month": current_month},
                {"$inc": {"partnerApplications": 1}, "$set": {"lastActivity": now}},
                upsert=True,
            )

            await track_event(
                user_id=user_id,
                event_type="partnership_application_submitted",
                event_data={
                    "application_id": application_id,
                    "company_name": application.company_name,
                    "business_type": application.business_type,
                    "expected_monthly_volume": application.expected_monthly_volume,
                    "application_score": application_score,
                    "auto_approved": auto_approve,
                    "final_status": final_status,
                    "feature": "partnership_application",
                },
                session_id=getattr(user, "session_id", None),
            )

            # 6) n8n notifications (best-effort) -- integration disabled

            logger.info(f"Partnership application submitted. ID: {application_id}, Status: {final_status}")
            response_message = (
                "Partnership application approved! Welcome to the PromptForge Partner Program."
                if auto_approve
                else "Partnership application submitted successfully. You'll hear back within 2-3 business days."
            )

            return APIResponse(
                data={
                    "application_id": application_id,
                    "status": final_status,
                    "application_score": application_score,
                    "auto_approved": auto_approve,
                    "review_timeline": "immediate" if auto_approve else "2-3 business days",
                    "is_partner": auto_approve,
                    "partner_tier": user_data.get("partner_tier", "standard") if auto_approve else None,
                    "commission_rate": user_data.get("partner_commission_rate", 0.70) if auto_approve else None,
                },
                message=response_message,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Partnership application failed for user {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Partnership application processing failed")

# ------------------------------ Partner Revenue Management ------------------------------
@router.post("/revenue")
@limiter.limit("5/minute")
async def manage_partner_revenue(
    request: Request,
    revenue_request: PartnerRevenueRequest,
    user: dict = Depends(get_current_user),
):
    """Partner revenue management — payout requests, payout method, summary, tax report."""
    user_id = user["uid"]
    logger.info(f"Partner revenue request from user: {user_id}, action: {revenue_request.action}")

    # normalize action names (legacy vs new)
    action_map = {
        "payout_request": "request_payout",
        "get_statement": "get_revenue_summary",
    }
    action = action_map.get(revenue_request.action, revenue_request.action)

    async with performance_monitor("partner_revenue_management"):
        try:
            if not db:
                raise HTTPException(status_code=503, detail="Database connection unavailable")

            user_data = await db.users.find_one({"_id": user_id})
            if not user_data:
                raise HTTPException(status_code=404, detail="User profile not found")
            is_partner = user_data.get("is_partner") or user_data.get("isPartner", False)
            if not is_partner:
                raise HTTPException(status_code=403, detail="Partner access required")

            if action == "request_payout":
                return await process_payout_request(user_id, user_data, revenue_request)
            elif action == "update_payout_method":
                return await update_payout_method(user_id, revenue_request)
            elif action == "get_revenue_summary":
                return await get_revenue_summary(user_id, revenue_request)
            elif action == "download_tax_report":
                return await generate_tax_report(user_id, revenue_request)
            else:
                raise HTTPException(status_code=400, detail="Unknown action")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Partner revenue management failed for user {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Revenue management operation failed")

# ------------------------------ Partner Dashboard ------------------------------
@router.get("/dashboard")
@limiter.limit("10/minute")
async def get_partner_dashboard(
    request: Request,
    dashboard_request: PartnerDashboardRequest,
    user: dict = Depends(get_current_user),
):
    """Partner dashboard analytics — Mongo-native."""
    user_id = user["uid"]
    logger.info(f"Partner dashboard request from user: {user_id}")

    async with performance_monitor("partner_dashboard"):
        try:
            if not db:
                raise HTTPException(status_code=503, detail="Database connection unavailable")

            user_data = await db.users.find_one({"_id": user_id})
            if not user_data:
                raise HTTPException(status_code=404, detail="User profile not found")

            is_partner = user_data.get("is_partner") or user_data.get("isPartner", False)
            if not is_partner:
                raise HTTPException(status_code=403, detail="Partner access required")

            # Date range
            if dashboard_request.timeframe == "custom":
                start_date = dashboard_request.start_date or (datetime.utcnow() - timedelta(days=30))
                end_date = dashboard_request.end_date or datetime.utcnow()
            else:
                end_date = datetime.utcnow()
                tf = (dashboard_request.timeframe or "30d").lower()
                days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}.get(tf, 30)
                start_date = end_date - timedelta(days=days)

            # What to include (fallbacks, since model fields are different)
            include = {
                "prompts": True,
                "revenue": True,
                "top_prompts": True,
                "activity": True,
            }
            if dashboard_request.include_analytics is False:
                include["prompts"] = False
                include["top_prompts"] = False
            if dashboard_request.include_revenue is False:
                include["revenue"] = False

            # Prompts analytics
            prompts_analytics = None
            if include["prompts"]:
                prompts_cursor = db.prompts.find({"user_id": user_id})
                total_prompts = 0
                active_prompts = 0
                total_views = 0
                total_downloads = 0
                total_revenue = 0.0
                prompt_categories: Dict[str, Dict[str, Any]] = {}

                async for p in prompts_cursor:
                    total_prompts += 1
                    if p.get("is_public") and p.get("status") == "active":
                        active_prompts += 1
                    stats = p.get("stats", {})
                    total_views += int(stats.get("views", 0))
                    total_downloads += int(stats.get("uses", 0))
                    total_revenue += float(stats.get("revenue", 0.0))
                    cat = p.get("category", "Uncategorized")
                    d = prompt_categories.setdefault(cat, {"count": 0, "revenue": 0.0, "downloads": 0})
                    d["count"] += 1
                    d["revenue"] += float(stats.get("revenue", 0.0))
                    d["downloads"] += int(stats.get("uses", 0))

                prompts_analytics = {
                    "total_prompts": total_prompts,
                    "active_prompts": active_prompts,
                    "total_views": total_views,
                    "total_downloads": total_downloads,
                    "total_revenue": total_revenue,
                    "category_breakdown": prompt_categories,
                }

            # Revenue analytics
            revenue_analytics = None
            if include["revenue"]:
                tx_cursor = db.transactions.find(
                    {
                        "seller_id": user_id,
                        "status": "completed",
                        "created_at": {"$gte": start_date, "$lte": end_date},
                    }
                ).sort("created_at", DESCENDING)

                daily: Dict[str, float] = {}
                total_period_revenue = 0.0
                total_transactions = 0
                commission_earned = 0.0

                async for tx in tx_cursor:
                    dt = tx.get("created_at") or datetime.utcnow()
                    ds = dt.date().isoformat()
                    amt = float(tx.get("amount", 0.0))
                    com = float(tx.get("commission_amount", 0.0))
                    total_period_revenue += amt
                    commission_earned += com
                    total_transactions += 1
                    daily[ds] = daily.get(ds, 0.0) + amt

                days_in_period = (end_date.date() - start_date.date()).days + 1
                avg_daily_revenue = total_period_revenue / days_in_period if days_in_period > 0 else 0.0

                revenue_analytics = {
                    "total_revenue": total_period_revenue,
                    "commission_earned": commission_earned,
                    "total_transactions": total_transactions,
                    "avg_daily_revenue": avg_daily_revenue,
                    "daily_revenue_chart": daily,
                }

            # Top prompts
            top_prompts_analytics = None
            if include["top_prompts"]:
                top_cursor = db.prompts.find({"user_id": user_id}).sort("stats.revenue", DESCENDING).limit(10)
                top_list = []
                async for p in top_cursor:
                    stats = p.get("stats", {})
                    top_list.append(
                        {
                            "id": p.get("_id"),
                            "title": p.get("title", "Untitled"),
                            "category": p.get("category", "Uncategorized"),
                            "total_revenue": float(stats.get("revenue", 0.0)),
                            "download_count": int(stats.get("uses", 0)),
                            "view_count": int(stats.get("views", 0)),
                            "likes_count": int(stats.get("likes", 0)),
                            "rating": float(stats.get("averageRating", 0.0)) if "averageRating" in stats else 0.0,
                            "created_at": p.get("created_at"),
                        }
                    )
                top_prompts_analytics = top_list

            # Recent activity (transactions)
            activity_analytics = None
            if include["activity"]:
                act_cursor = db.transactions.find({"seller_id": user_id}).sort("created_at", DESCENDING).limit(20)
                activity_feed = []
                async for tx in act_cursor:
                    activity_feed.append(
                        {
                            "type": "purchase",
                            "prompt_title": tx.get("prompt_title", "Unknown Prompt"),
                            "amount": float(tx.get("amount", 0.0)),
                            "buyer_id": tx.get("buyer_id"),
                            "timestamp": tx.get("created_at"),
                        }
                    )
                activity_analytics = activity_feed[:10]

            partner_info = {
                "partner_since": user_data.get("partner_since") or user_data.get("partnerSince"),
                "partner_tier": user_data.get("partner_tier") or user_data.get("partnerTier", "standard"),
                "commission_rate": user_data.get("partner_commission_rate") or user_data.get("partnerCommissionRate", 0.70),
                "total_lifetime_revenue": user_data.get("stats", {}).get("totalLifetimeRevenue", 0.0),
                "payout_method": user_data.get("payoutMethod", "pending"),
                "next_payout_date": user_data.get("nextPayoutDate"),
                "pending_payout_amount": user_data.get("pendingPayoutAmount", 0.0),
                "partnership_status": user_data.get("partnershipData", {}).get("status", "active"),
            }

            await track_event(
                user_id=user_id,
                event_type="partner_dashboard_accessed",
                event_data={
                    "date_range": dashboard_request.timeframe,
                    "metrics_requested": [k for k, v in include.items() if v],
                    "partner_tier": partner_info["partner_tier"],
                    "feature": "partner_dashboard",
                },
                session_id=getattr(user, "session_id", None),
            )

            return APIResponse(
                data={
                    "partner_info": partner_info,
                    "date_range": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "period": dashboard_request.timeframe,
                    },
                    "prompts_analytics": prompts_analytics,
                    "revenue_analytics": revenue_analytics,
                    "top_prompts": top_prompts_analytics,
                    "recent_activity": activity_analytics,
                    "generated_at": datetime.utcnow().isoformat(),
                },
                message="Partner dashboard data retrieved successfully",
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Partner dashboard failed for user {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Dashboard data retrieval failed")

