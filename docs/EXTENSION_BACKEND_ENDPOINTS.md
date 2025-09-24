# 🔧 BACKEND ENDPOINTS - EXTENSION SUPPORT

## Required New API Endpoints for Extension

### 1. Enhanced Usage Analytics
```python
@router.post("/users/usage/analytics")
async def get_usage_analytics(
    period: str = "7d",
    current_user: dict = Depends(get_current_user)
):
    """Get detailed usage analytics for dashboard"""
    return {
        "daily_upgrades": [...],
        "credit_usage": [...], 
        "top_domains": [...],
        "success_rate": 0.95,
        "avg_improvement_score": 8.2
    }

@router.post("/users/usage/bulk-track")
async def bulk_track_usage(
    events: List[UsageEvent],
    current_user: dict = Depends(get_current_user)
):
    """Bulk track multiple events (for offline sync)"""
    pass
```

### 2. Real-time Limits & Quotas
```python
@router.get("/users/limits/current")
async def get_current_limits(current_user: dict = Depends(get_current_user)):
    """Get real-time usage limits and remaining quotas"""
    return {
        "plan": "pro",
        "daily_limit": 500,
        "daily_used": 47,
        "daily_remaining": 453,
        "monthly_limit": 15000,
        "monthly_used": 1247,
        "resets_at": "2025-09-02T00:00:00Z"
    }

@router.post("/users/limits/check")
async def check_usage_limit(
    action: str,
    credits_required: int = 1,
    current_user: dict = Depends(get_current_user)
):
    """Check if user can perform action without exceeding limits"""
    return {
        "allowed": True,
        "remaining_credits": 453,
        "upgrade_required": False
    }
```

### 3. Feature Flags & Configuration
```python
@router.get("/users/features")
async def get_feature_flags(current_user: dict = Depends(get_current_user)):
    """Get user-specific feature flags and extension config"""
    return {
        "realtime_upgrades": True,
        "analytics_dashboard": True, 
        "offline_mode": True,
        "max_prompt_length": 10000,
        "supported_techniques": ["chain_of_thought", "step_back", ...],
        "ui_theme": "dark"
    }
```

### 4. Error Reporting & Diagnostics
```python
@router.post("/system/errors/report")
async def report_error(
    error_data: ErrorReport,
    current_user: dict = Depends(get_current_user)
):
    """Report extension errors for debugging"""
    # Log to monitoring system
    # Alert on critical errors
    pass

@router.get("/system/health/extension")
async def extension_health_check():
    """Extension-specific health check with detailed status"""
    return {
        "status": "healthy",
        "services": {
            "demon_engine": "operational",
            "brain_engine": "operational", 
            "auth_service": "operational",
            "usage_tracking": "operational"
        },
        "maintenance_window": None,
        "notices": []
    }
```
