DEBUG = True  # Set True to enable debug prints in ideas.py
def debug_print(*args, **kwargs):
    if DEBUG:
        print("[IDEAS DEBUG]", *args, **kwargs)
"""
Ideas API Router - Exposes OracleService for idea generation
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Dict
from services.oracle_service import OracleService, IdeaInput
from api.models import APIResponse
from dependencies import get_oracle_service, require_user
from utils import camelize

router = APIRouter(tags=["Ideas"])


# Accepts categories as a list and complexity as a string, for frontend compatibility
class IdeaGenerationRequest(BaseModel):
    categories: list[str]
    complexity: str
    pain_points: str = ""
    target_audience: str = None
    industry_context: str = None


@router.post("/generate", response_model=APIResponse)
async def generate_ideas(
    request: Request,
    body: IdeaGenerationRequest,
    user: dict = Depends(require_user()),
    oracle_service: OracleService = Depends(get_oracle_service)
):
    """
    Generate innovative project ideas based on categories and complexity from the frontend.
    Enforces plan and credit limits.
    """
    try:
        debug_print("[START] generate_ideas called", f"user={user}", f"body={body}")
        # --- Plan/Credit Enforcement ---
        plan = (user.get("plan") or user.get("claims", {}).get("plan") or "free").lower()
        credits = int(user.get("credits", {}).get("balance", 0))
        ideas_cost = 2 if plan == "pro" else 5
        max_per_day = 100 if plan == "pro" else 10
        debug_print(f"plan={plan}", f"credits={credits}", f"ideas_cost={ideas_cost}", f"max_per_day={max_per_day}")
        # Count today's generations (real per-user per-day count)
        from datetime import datetime, timedelta
        from dependencies import db
        user_id = user["uid"]
        now = datetime.utcnow()
        start_of_day = datetime(now.year, now.month, now.day)
        today_count = await db.ideas.count_documents({"user_id": user_id, "created_at": {"$gte": start_of_day}})
        debug_print(f"today_count={today_count}")
        if today_count >= max_per_day:
            debug_print("Daily limit reached", f"today_count={today_count}", f"max_per_day={max_per_day}")
            raise HTTPException(status_code=429, detail=f"Daily idea generation limit reached for your plan ({max_per_day}/day). Upgrade to Pro for more.")
        if credits < ideas_cost:
            debug_print("Insufficient credits", f"credits={credits}", f"ideas_cost={ideas_cost}")
            raise HTTPException(status_code=402, detail=f"Insufficient credits. This action costs {ideas_cost} credit(s).")
        # --- Existing logic ---
        categories = body.categories or ["General"]
        category = categories[0] if categories else "General"
        pain_points = body.pain_points or f"Users in {', '.join(categories)} face challenges."
        complexity_level = body.complexity or "intermediate"
        input_data = IdeaInput(
            niche=category,
            pain_points=pain_points,
            complexity_level=complexity_level.lower(),
            category=category,
            target_audience=body.target_audience,
            industry_context=body.industry_context
        )
        debug_print("Calling oracle_service.generate_ideas", f"input_data={input_data}")
        result = await oracle_service.generate_ideas(input_data, user_id=str(user.get("_id", user.get("uid", "anon"))))
        debug_print("oracle_service.generate_ideas result", result)
        # Save generated ideas to the 'ideas' collection (user's vault)
        from datetime import datetime
        ideas_to_insert = []
        for idea in result.ideas:
            ideas_to_insert.append({
                "user_id": user_id,
                "idea": idea.dict(),
                "created_at": datetime.utcnow(),
                "source": "oracle"
            })
        if ideas_to_insert:
            debug_print(f"Inserting {len(ideas_to_insert)} ideas into ideas collection for user {user_id}")
            await db.ideas.insert_many(ideas_to_insert)
        # Debit credits only after successful idea generation and save
        debug_print(f"Debiting {ideas_cost} credits from user {user_id} (credits.balance)")
        await db.users.update_one({"_id": user_id}, {"$inc": {"credits.balance": -ideas_cost}})
        # Track usage for dashboard analytics
        from dependencies import track_usage
        await track_usage(
            user_id=user_id,
            source=request.headers.get("X-Client-Source", "web"),
            action="idea_generated",
            details={
                "categories": categories,
                "complexity": complexity_level,
                "num_ideas": len(result.ideas)
            },
            credits_spent=ideas_cost,
            db=db
        )
        response_data = result.dict()
        response_data["inspiration"] = f"Here are some {complexity_level.lower()} ideas for {', '.join(categories)}. Unleash your creativity!"
        debug_print("Returning APIResponse.success", response_data)
        return camelize(APIResponse(response_data))
    except HTTPException as e:
        # Pass through HTTPExceptions (like insufficient credits, daily limit)
        debug_print("HTTPException in generate_ideas:", e)
        raise
    except Exception as e:
        debug_print("Exception in generate_ideas:", e)
        # Only treat real errors as 500
        raise HTTPException(status_code=500, detail=f"OracleService error: {str(e)}")
