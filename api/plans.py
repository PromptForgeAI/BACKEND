# Pro Plan & Subscription API (MongoDB-native)
from fastapi import APIRouter, Depends, HTTPException, Body
from dependencies import get_current_user, db
from datetime import datetime

router = APIRouter(tags=["Plans"])

@router.get("/plans/info")
async def plan_info(user: dict = Depends(get_current_user)):
    uid = user["uid"]
    db_user = await db.users.find_one({"uid": uid})
    plan = (db_user or {}).get("plan", "free")
    expires = (db_user or {}).get("plan_expires")
    # Convert expires to ISO string if present
    if expires and hasattr(expires, "isoformat"):
        expires = expires.isoformat()
    return {"plan": plan, "expires": expires}

@router.post("/plans/upgrade")
async def upgrade_plan(payload: dict = Body(...), user: dict = Depends(get_current_user)):
    plan = payload.get("plan")
    duration = payload.get("duration", 30)  # days
    valid_plans = ["pro_lite", "pro_max", "team"]
    if plan not in valid_plans:
        raise HTTPException(status_code=400, detail="Invalid plan")
    try:
        duration = int(duration)
        if duration <= 0 or duration > 365:
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid duration")
    expires = datetime.utcnow() + __import__('datetime').timedelta(days=duration)
    await db.users.update_one({"uid": user["uid"]}, {"$set": {"plan": plan, "plan_expires": expires}}, upsert=True)
    return {"status": "upgraded", "plan": plan, "expires": expires.isoformat()}

@router.get("/plans/check_pro")
async def check_pro(user: dict = Depends(get_current_user)):
    db_user = await db.users.find_one({"uid": user["uid"]})
    plan = (db_user or {}).get("plan", "free")
    expires = (db_user or {}).get("plan_expires")
    is_pro = False
    valid_plans = ["pro_lite", "pro_max", "team"]
    if plan in valid_plans:
        # If expiry is set, check if still valid
        if expires:
            now = datetime.utcnow()
            if hasattr(expires, "timestamp"):
                # expires is datetime
                is_pro = expires > now
            else:
                # expires is string
                try:
                    from dateutil.parser import isoparse
                    is_pro = isoparse(expires) > now
                except Exception:
                    is_pro = True  # fallback: treat as valid
        else:
            is_pro = True
    return {"is_pro": is_pro, "plan": plan}
