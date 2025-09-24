
from fastapi import APIRouter, Depends, HTTPException, Body
from dependencies import get_current_user, db

router = APIRouter(tags=["Prompt Vault"])

# TODO: Merge into /api/v1/prompts/arsenal - same functionality different namespace
# --- Arsenal Alias Endpoint ---
@router.get("/arsenal")
async def get_arsenal(user: dict = Depends(get_current_user)):
    """
    DEPRECATED: Use /api/v1/prompts/arsenal instead.
    TODO: Merge into main prompts API - consolidate with /api/v1/prompts/arsenal
    Alias for /vault/list: returns all prompts in the user's arsenal/vault.
    """
    query = {"uid": user["uid"]}
    prompts = await db.vault.find(query).sort("created_at", -1).to_list(100)
    for p in prompts:
        if "_id" in p:
            p["id"] = str(p.pop("_id"))
        if "created_at" in p and hasattr(p["created_at"], "isoformat"):
            p["created_at"] = p["created_at"].isoformat()
    return {"prompts": prompts}
# TODO: Merge into main prompts listing functionality
# --- Prompt Search Endpoint ---
from fastapi import Query
@router.get("/search")
async def search_prompts(
    q: str = Query(None, description="Search text"),
    persona: str = Query(None, description="Persona filter"),
    tag: str = Query(None, description="Tag filter"),
    user: dict = Depends(get_current_user)
):
    """
    DEPRECATED: Use global search /api/v1/search with vault filter instead.
    TODO: Merge into global search functionality with vault filter parameter
    Search prompts in the user's vault by text, persona, or tag.
    """
    query = {"uid": user["uid"]}
    if q:
        query["$or"] = [
            {"text": {"$regex": q, "$options": "i"}},
            {"upgraded": {"$regex": q, "$options": "i"}}
        ]
    if persona:
        query["persona"] = persona
    if tag:
        query["tags"] = tag
    prompts = await db.vault.find(query).sort("created_at", -1).to_list(100)
    for p in prompts:
        if "_id" in p:
            p["id"] = str(p.pop("_id"))
        if "created_at" in p and hasattr(p["created_at"], "isoformat"):
            p["created_at"] = p["created_at"].isoformat()
    return {"prompts": prompts}
# TODO: Merge into main prompts test-drive functionality
# --- Prompt Test Drive Endpoint ---
from fastapi import Request
@router.post("/{prompt_id}/test-drive")
async def test_drive_prompt(prompt_id: str, request: Request, user: dict = Depends(get_current_user)):
    """
    DEPRECATED: Use /api/v1/prompts/test-drive-by-id instead.
    TODO: Merge into main prompts test-drive endpoint - same functionality different namespace
    Test-drive a prompt by ID. (Stub: returns prompt content and mock result)
    """
    from bson import ObjectId
    try:
        oid = ObjectId(prompt_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid prompt_id")
    prompt = await db.vault.find_one({"_id": oid, "uid": user["uid"]})
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    # Simulate test-drive (replace with real LLM call if needed)
    test_result = {
        "input": prompt.get("text"),
        "output": f"[Test-drive result for prompt: {prompt.get('upgraded', prompt.get('text'))}]",
        "status": "success"
    }
    return {"prompt_id": prompt_id, "test_drive": test_result}

# TODO: Merge into standard prompt creation functionality
# Prompt Vault API (MVP)
@router.post("/save")
async def save_prompt(payload: dict = Body(...), user: dict = Depends(get_current_user)):
    text = payload.get("text")
    upgraded = payload.get("upgraded")
    persona = payload.get("persona")
    tags = payload.get("tags", [])
    if not text or not upgraded:
        raise HTTPException(status_code=400, detail="Missing prompt text or upgraded version")
    if not isinstance(tags, list):
        tags = [tags] if tags else []
    now = __import__('datetime').datetime.utcnow()
    # Save to user's vault (with user info)
    doc = {
        "uid": user["uid"],
        "text": text,
        "upgraded": upgraded,
        "persona": persona,
        "tags": tags,
        "created_at": now
    }
    ins = await db.vault.insert_one(doc)

    # Archive anonymized copy for AI training (no user info)
    archive_doc = {
        "text": text,
        "upgraded": upgraded,
        "tags": tags,
        "persona": persona,
        "archived_at": now
    }
    try:
        await db.archived_prompts.insert_one(archive_doc)
    except Exception as e:
        import logging
        logging.warning(f"Failed to archive prompt for AI training: {e}")

    # Patch: increment stats.prompts_created and add to saved_prompts
    try:
        await db.users.update_one({"uid": user["uid"]}, {"$inc": {"stats.prompts_created": 1}})
        await db.users.update_one({"uid": user["uid"]}, {"$push": {"saved_prompts": str(ins.inserted_id)}})
    except Exception as logerr:
        import logging
        logging.warning(f"Failed to update user stats or saved_prompts: {logerr}")

    return {"status": "success", "prompt_id": str(ins.inserted_id)}

@router.get("/list")
async def list_prompts(q: str = None, persona: str = None, tag: str = None, user: dict = Depends(get_current_user)):
    """
    DEPRECATED: Use main prompts listing functionality instead.
    TODO: Merge into main prompts API - likely overlaps with main prompts listing functionality
    """
    query = {"uid": user["uid"]}
    if q:
        query["$or"] = [
            {"text": {"$regex": q, "$options": "i"}},
            {"upgraded": {"$regex": q, "$options": "i"}}
        ]
    if persona:
        query["persona"] = persona
    if tag:
        query["tags"] = tag
    prompts = await db.vault.find(query).sort("created_at", -1).to_list(100)
    # Sanitize ObjectId for frontend
    for p in prompts:
        if "_id" in p:
            p["id"] = str(p.pop("_id"))
        if "created_at" in p and hasattr(p["created_at"], "isoformat"):
            p["created_at"] = p["created_at"].isoformat()
    return {"prompts": prompts}


# TODO: Merge into main prompts versioning functionality
# --- Prompt Versioning Endpoint ---
@router.get("/{prompt_id}/versions")
async def get_prompt_versions(prompt_id: str, user: dict = Depends(get_current_user)):
    """
    DEPRECATED: Use /api/v1/prompts/{prompt_id}/versions instead.
    TODO: Merge into main prompts versioning - likely duplicates main prompts versioning functionality
    Return all versions of a prompt. (Stub: returns current only unless versioning is implemented)
    """
    from bson import ObjectId
    try:
        oid = ObjectId(prompt_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid prompt_id")
    prompt = await db.vault.find_one({"_id": oid, "uid": user["uid"]})
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    # If you implement versioning, fetch all versions here. For now, return current as only version.
    version = {
        "id": str(prompt["_id"]),
        "text": prompt.get("text"),
        "upgraded": prompt.get("upgraded"),
        "persona": prompt.get("persona"),
        "tags": prompt.get("tags", []),
        "created_at": prompt["created_at"].isoformat() if hasattr(prompt["created_at"], "isoformat") else prompt["created_at"],
        "version": 1
    }
    return {"versions": [version]}

# TODO: Merge into standard prompt deletion functionality (non-RESTful path pattern)
@router.delete("/delete/{prompt_id}")
async def delete_prompt(prompt_id: str, user: dict = Depends(get_current_user)):
    """
    DEPRECATED: Use standard DELETE /api/v1/prompts/{prompt_id} instead.
    TODO: Merge into main prompt deletion endpoint with vault context if needed
    Non-RESTful path pattern and likely duplicates main prompt deletion
    """
    from bson import ObjectId
    try:
        oid = ObjectId(prompt_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid prompt_id")
    res = await db.vault.delete_one({"_id": oid, "uid": user["uid"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"status": "deleted"}
