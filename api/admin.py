from fastapi import APIRouter, Depends, HTTPException, Request
from dependencies import db, get_current_user
from auth import require_role
import logging

router = APIRouter(tags=["Admin"])
logger = logging.getLogger(__name__)

@router.get("/diagnostics")
async def diagnostics(request: Request, user: dict = Depends(require_role("admin"))):
    """
    Returns backend health: Mongo/Redis status, DB name, user_id, collection counts.
    Only accessible to users with the 'admin' role claim.
    """
    result = {}
    # MongoDB check
    try:
        await db.command("ping")
        mongo_status = "OK"
        db_name = db.name
    except Exception as e:
        mongo_status = f"FAIL: {e}"
        db_name = None
    result["mongo"] = {"status": mongo_status, "db": db_name}

    # Current user
    result["current_user_id"] = user.get("uid")

    # Collection counts (users, prompts, ideas)
    try:
        users_count = await db.users.count_documents({})
    except Exception as e:
        users_count = f"ERR: {e}"
    try:
        prompts_count = await db.prompts.count_documents({})
    except Exception as e:
        prompts_count = f"ERR: {e}"
    try:
        ideas_count = await db.ideas.count_documents({}) if hasattr(db, "ideas") else "N/A"
    except Exception as e:
        ideas_count = f"ERR: {e}"
    result["counts"] = {"users": users_count, "prompts": prompts_count, "ideas": ideas_count}

    return {"data": result, "message": "Diagnostics OK"}
