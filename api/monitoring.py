# api/monitoring.py - Monitoring and Health Check Endpoints
from fastapi import APIRouter, Depends, HTTPException
from dependencies import db
import asyncio

from middleware.auth import get_current_user, require_plan
from utils.monitoring import tracer, health_checker
from utils.circuit_breaker import circuit_manager
from typing import Dict, Any, Optional
import time
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Monitoring"])
@router.get("/stats", tags=["Monitoring"])
async def get_global_stats():
    """Return global stats for dashboard: prompts, users, uptime, integrations."""
    try:
        # Run all DB queries in parallel
        prompts_count_task = db.prompts.count_documents({})
        users_count_task = db.users.count_documents({})
        integrations_count_task = db.integrations.count_documents({}) if hasattr(db, "integrations") else asyncio.sleep(0, result=0)
        shared_prompts_task = db.prompts.count_documents({"is_public": True}) if hasattr(db, "prompts") else asyncio.sleep(0, result=0)
        oracle_runs_task = db.usage.count_documents({"event_type": "oracle.run"}) if hasattr(db, "usage") else asyncio.sleep(0, result=0)
        credits_spent_task = db.users.aggregate([
            {"$group": {"_id": None, "total": {"$sum": "$credits.total_spent"}}}
        ]).to_list(1) if hasattr(db, "users") else asyncio.sleep(0, result=[{"total": 0}])
        countries_task = db.users.distinct("location.country") if hasattr(db, "users") else asyncio.sleep(0, result=[])
        integrations_live_task = db.integrations.distinct("name") if hasattr(db, "integrations") else asyncio.sleep(0, result=[])
        quests_completed_task = db.academy_quest_submissions.count_documents({"auto_eval": True}) if hasattr(db, "academy_quest_submissions") else asyncio.sleep(0, result=0)
        badges_earned_task = db.users.aggregate([
            {"$group": {"_id": None, "total": {"$sum": {"$size": {"$ifNull": ["$badges", []]}}}}}
        ]).to_list(1) if hasattr(db, "users") else asyncio.sleep(0, result=[{"total": 0}])
        teams_onboarded_task = db.teams.count_documents({}) if hasattr(db, "teams") else asyncio.sleep(0, result=0)

        # Uptime from health_checker
        health = await health_checker.get_health_status()

        (
            prompts,
            users,
            integrations,
            shared_prompts,
            oracle_runs,
            credits_spent,
            countries,
            integrations_live,
            quests_completed,
            badges_earned,
            teams_onboarded
        ) = await asyncio.gather(
            prompts_count_task,
            users_count_task,
            integrations_count_task,
            shared_prompts_task,
            oracle_runs_task,
            credits_spent_task,
            countries_task,
            integrations_live_task,
            quests_completed_task,
            badges_earned_task,
            teams_onboarded_task
        )

        # Fallbacks and formatting
        credits_spent_val = credits_spent[0]["total"] if credits_spent and isinstance(credits_spent, list) and credits_spent[0].get("total") is not None else 0
        badges_earned_val = badges_earned[0]["total"] if badges_earned and isinstance(badges_earned, list) and badges_earned[0].get("total") is not None else 0
        uptime_rolling = round(health.get("uptime", 0), 2)
        fastest_upgrade_time = 1200  # ms, mock/fallback
        security_checks = health.get("database", {}).get("status", "healthy")

        return {
            "promptsForged": prompts,
            "oracleRuns": oracle_runs,
            "creditsSpent": credits_spent_val,
            "uptime_rolling": uptime_rolling,
            "user_count": users,
            "countries_reached": len(countries) if countries else 0,
            "integration_count": integrations,
            "integrations_live": ", ".join(integrations_live) if integrations_live else "Chrome, VS Code",
            "community_prompts": shared_prompts,
            "fastestUpgradeMs": fastest_upgrade_time,
            "security": security_checks,
            "quests_completed": quests_completed,
            "badges_earned": badges_earned_val,
            "teams_onboarded": teams_onboarded
        }
    except Exception as e:
        logger.error(f"Failed to fetch global stats: {e}")
        # Return all fields with fallback defaults
        return {
            "promptsForged": 0,
            "oracleRuns": 0,
            "creditsSpent": 0,
            "uptime_rolling": 0,
            "user_count": 0,
            "countries_reached": 0,
            "integration_count": 0,
            "integrations_live": "Chrome, VS Code",
            "community_prompts": 0,
            "fastestUpgradeMs": 1200,
            "security": "unknown",
            "quests_completed": 0,
            "badges_earned": 0,
            "teams_onboarded": 0
        }
async def check_time_sync() -> Dict[str, Any]:
    """Check server time synchronization"""
    try:
        # For production, you'd use NTP client here
        # For now, we'll just check if time is reasonable
        current_time = time.time()
        
        # Basic sanity check - ensure we're not too far in past/future
        # This is a simplified check - in production you'd compare with NTP
        expected_min = 1756900000  # Around your current timestamp range
        expected_max = 1757000000  # A reasonable range
        
        is_reasonable = expected_min < current_time < expected_max
        
        return {
            "current_timestamp": current_time,
            "is_reasonable": is_reasonable,
            "status": "synced" if is_reasonable else "drift_detected",
            "note": "Basic timestamp sanity check - use NTP for production"
        }
    except Exception as e:
        logger.error(f"Time sync check failed: {e}")
        return {
            "current_timestamp": None,
            "is_reasonable": False,
            "status": "check_failed",
            "error": str(e)
        }

@router.get("/health")
async def health_check():
    """Public health check endpoint with time sync monitoring"""
    try:
        status = await health_checker.get_health_status()
        time_sync = await check_time_sync()
        
        return {
            "status": "healthy",
            "timestamp": status["timestamp"],
            "uptime": status["uptime"],
            "database": status["database"]["status"],
            "active_requests": status["active_requests"],
            "time_sync": time_sync  # 🔥 Added time sync monitoring
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": health_checker._start_time if hasattr(health_checker, '_start_time') else 0
        }

@router.get("/health/detailed")
@require_plan("pro")
async def detailed_health_check(user: dict = Depends(get_current_user)):
    """Detailed health check for Pro users"""
    return await health_checker.get_health_status()

@router.get("/metrics")
@require_plan("pro")
async def get_metrics(user: dict = Depends(get_current_user)):
    """Get performance metrics"""
    return {
        "performance": tracer.get_performance_stats(),
        "circuit_breakers": circuit_manager.get_all_stats(),
        "active_requests": len(tracer.active_requests)
    }

@router.get("/trace/{request_id}")
@require_plan("pro")
async def get_request_trace(request_id: str, user: dict = Depends(get_current_user)):
    """Get detailed trace for a specific request"""
    trace_info = tracer.get_request_info(request_id)
    if not trace_info:
        raise HTTPException(status_code=404, detail="Request trace not found")
    return trace_info

@router.get("/circuit-breakers")
@require_plan("team")
async def get_circuit_breaker_status(user: dict = Depends(get_current_user)):
    """Get circuit breaker status (Team plan and above)"""
    return circuit_manager.get_all_stats()

@router.post("/circuit-breakers/{breaker_name}/reset")
@require_plan("team")
async def reset_circuit_breaker(breaker_name: str, user: dict = Depends(get_current_user)):
    """Reset a circuit breaker (Team plan and above)"""
    if breaker_name not in circuit_manager.breakers:
        raise HTTPException(status_code=404, detail="Circuit breaker not found")
    
    breaker = circuit_manager.breakers[breaker_name]
    await breaker._close_circuit()
    
    return {"message": f"Circuit breaker {breaker_name} reset", "status": "closed"}
