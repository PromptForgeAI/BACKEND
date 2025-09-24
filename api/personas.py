# Prompt Personas API
from fastapi import APIRouter, Depends, HTTPException, Body
from dependencies import get_current_user, db

router = APIRouter(tags=["Personas"])

@router.get("/personas/list")
async def list_personas(user: dict = Depends(get_current_user)):
    # Default personas + user-created
    default = [
        {"id": "ceo", "name": "The CEO", "desc": "Direct, strategic, high-level."},
        {"id": "copywriter", "name": "The Copywriter", "desc": "Persuasive, creative, marketing-focused."},
        {"id": "hacker", "name": "The Hacker", "desc": "Technical, precise, problem-solving."},
        {"id": "philosopher", "name": "The Philosopher", "desc": "Thoughtful, deep, analytical."}
    ]
    user_personas = await db.personas.find({"uid": user["uid"]}).to_list(20)
    # Sanitize ObjectId for frontend
    for p in user_personas:
        if "_id" in p:
            p["id"] = str(p.pop("_id"))
    return {"personas": default + user_personas}

@router.post("/personas/save")
async def save_persona(payload: dict = Body(...), user: dict = Depends(get_current_user)):
    name = payload.get("name")
    desc = payload.get("desc")
    if not name:
        raise HTTPException(status_code=400, detail="Missing persona name")
    # Enforce unique persona name per user
    existing = await db.personas.find_one({"uid": user["uid"], "name": name})
    if existing:
        raise HTTPException(status_code=409, detail="Persona name already exists")
    doc = {"uid": user["uid"], "name": name, "desc": desc}
    ins = await db.personas.insert_one(doc)
    return {"status": "success", "persona_id": str(ins.inserted_id)}
