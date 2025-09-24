# api/search.py
import asyncio
import logging
import re
from typing import List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query , HTTPException
from dependencies import db, get_current_user
from api.models import APIResponse
import logging
router = APIRouter()
logger = logging.getLogger(__name__)



@router.get("/users", tags=["search"])
async def search_users(
    query: str = Query(..., min_length=1, description="Search term for user email or name"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Search users by email or name (case-insensitive, paginated)."""
    try:
        mongo_query = {
            "$or": [
                {"email": {"$regex": query, "$options": "i"}},
                {"name": {"$regex": query, "$options": "i"}}
            ]
        }
        users_cursor = db.users.find(mongo_query).skip(offset).limit(limit)
        users = []
        async for user in users_cursor:
            user["id"] = str(user.pop("_id"))
            user.pop("password", None)
            user.pop("api_key", None)
            users.append(user)
        return APIResponse(data={"users": users}, message="Users search successful")
    except Exception as e:
        logger.error(f"Error searching users: {e}")
        raise HTTPException(status_code=500, detail="Failed to search users")
logger = logging.getLogger(__name__)

# --- Pydantic Models for Search Results ---
class SearchResultItem(BaseModel):
    id: str
    title: str
    description: str
    type: str
    url: str

class SearchResponse(BaseModel):
    prompts: List[SearchResultItem] = []
    listings: List[SearchResultItem] = []
    users: List[SearchResultItem] = []

# --- The Global Search Endpoint ---
@router.get("/")
async def global_search(
    q: str = Query(..., min_length=3, description="The search query."),
    user: dict = Depends(get_current_user)
):
    """
    Performs a global search across public prompts/listings and user profiles.
    """
    logger.info(f"Global search performed for query: '{q}' by user: {user['uid']}")
    
    # Use regex for a case-insensitive 'contains' search
    search_regex = re.compile(q, re.IGNORECASE)

    # Define the search tasks to run in parallel
    prompts_task = db.prompts.find(
        {"user_id": user['uid'], "title": search_regex},
        limit=10
    ).to_list(length=10)

    listings_task = db.marketplace_listings.find(
        {"is_active": True, "prompt_title": search_regex},
        limit=10
    ).to_list(length=10)
    
    # Run searches in parallel for maximum speed
    results = await asyncio.gather(prompts_task, listings_task)
    
    user_prompts, marketplace_listings = results

    # Format the results into a clean response
    response_data = SearchResponse(
        prompts=[
            SearchResultItem(
                id=str(p["_id"]),
                title=p.get("title", "Untitled"),
                description=p.get("content", "")[:100],
                type="prompt",
                url=f"/prompts/{p['_id']}"
            ) for p in user_prompts
        ],
        listings=[
            SearchResultItem(
                id=str(l["_id"]),
                title=l.get("prompt_title", "Untitled Listing"),
                description=l.get("description", "")[:100],
                type="listing",
                url=f"/marketplace/{l['_id']}"
            ) for l in marketplace_listings
        ]
    )

    return APIResponse(data=response_data.dict(), message="Search completed successfully.")
