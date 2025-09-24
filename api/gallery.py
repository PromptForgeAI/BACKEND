# Prompt Gallery API (MongoDB-native)
from fastapi import APIRouter, Depends, HTTPException, Body
from dependencies import get_current_user, db
from bson import ObjectId
from datetime import datetime

router = APIRouter(tags=["Prompt Gallery"])

@router.post("/gallery/share")
async def share_prompt(payload: dict = Body(...), user: dict = Depends(get_current_user)):
    prompt_id = payload.get("prompt_id")
    from bson import ObjectId
    if not prompt_id:
        raise HTTPException(status_code=400, detail="Missing prompt_id")
    try:
        oid = ObjectId(prompt_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid prompt_id")
    prompt = await db.vault.find_one({"_id": oid, "uid": user["uid"]})
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    gallery_doc = {
        "uid": user["uid"],
        "prompt_id": prompt_id,
        "text": prompt["text"],
        "upgraded": prompt["upgraded"],
        "persona": prompt.get("persona"),
        "tags": prompt.get("tags", []),
        "shared_at": datetime.utcnow(),
        "votes": 0,
        "public": True
    }
    ins = await db.gallery.insert_one(gallery_doc)
    return {"status": "shared", "gallery_id": str(ins.inserted_id)}

@router.get("/gallery/list")
async def list_gallery(q: str = None, tag: str = None, skip: int = 0, limit: int = 20):
    query = {"public": True}
    if q:
        query["$or"] = [
            {"text": {"$regex": q, "$options": "i"}},
            {"upgraded": {"$regex": q, "$options": "i"}}
        ]
    if tag:
        query["tags"] = tag
    prompts = await db.gallery.find(query).sort("votes", -1).skip(skip).limit(limit).to_list(limit)
    # Sanitize ObjectId for frontend
    for p in prompts:
        if "_id" in p:
            p["id"] = str(p.pop("_id"))
        if "shared_at" in p and hasattr(p["shared_at"], "isoformat"):
            p["shared_at"] = p["shared_at"].isoformat()
    return {"gallery": prompts}

@router.post("/gallery/vote/{gallery_id}")
async def vote_gallery(gallery_id: str, user: dict = Depends(get_current_user)):
    from bson import ObjectId
    # Prevent double voting by same user (store in votes collection)
    try:
        oid = ObjectId(gallery_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid gallery_id")
    vote_key = {"gallery_id": gallery_id, "uid": user["uid"]}
    if await db.gallery_votes.find_one(vote_key):
        raise HTTPException(status_code=400, detail="Already voted")
    res = await db.gallery.update_one({"_id": oid}, {"$inc": {"votes": 1}})
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="Gallery item not found")
    await db.gallery_votes.insert_one({**vote_key, "voted_at": datetime.utcnow()})
    return {"status": "voted"}
