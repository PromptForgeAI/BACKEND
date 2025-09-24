import os
import json
import time
import asyncio
from fastapi import APIRouter, Request, HTTPException, Depends, Body, status
from fastapi.responses import JSONResponse
from dependencies import db
from typing import Any, Dict
import httpx
from starlette.background import BackgroundTasks
from fastapi.security import HTTPBearer
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from collections import defaultdict

ACADEMY_CONTENT_PATH = os.getenv("ACADEMY_CONTENT_PATH", "content/academy")
CURRICULUM_JSON = os.path.join("public", "curriculum.json")
FALLBACK_CURRICULUM_JSON = os.path.join("content", "curriculum.json")
NEXT_PUBLIC_API_BASE = os.getenv("NEXT_PUBLIC_API_BASE", "http://localhost:3000")

router = APIRouter(prefix="/api/academy", tags=["Academy"])

# --- GET /api/academy/curriculum ---
@router.get("/curriculum")
async def get_curriculum():
    """Return the academy curriculum structure from public/curriculum.json or fallback."""
    try:
        if os.path.exists(CURRICULUM_JSON):
            with open(CURRICULUM_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        elif os.path.exists(FALLBACK_CURRICULUM_JSON):
            with open(FALLBACK_CURRICULUM_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            raise FileNotFoundError("No curriculum.json found")
    except Exception as e:
        return {
            "modules": [
                {"id": "intro", "title": "Introduction", "lessons": ["lesson-1", "lesson-2"]},
                {"id": "advanced", "title": "Advanced", "lessons": ["lesson-3"]}
            ],
            "_note": f"Mocked curriculum, error: {e}"
        }

# --- GET /api/academy/lesson/{lesson_id} ---
@router.get("/lesson/{lesson_id}")
async def get_lesson(lesson_id: str):
    """Return lesson content by ID (JSON frontmatter + compiled HTML)."""
    lesson_json = os.path.join(ACADEMY_CONTENT_PATH, f"{lesson_id}.json")
    if os.path.exists(lesson_json):
        with open(lesson_json, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        raise HTTPException(status_code=404, detail="Lesson not found")

# --- POST /api/academy/labs/run ---
_guest_lab_runs = defaultdict(list)  # ip: [timestamps]
_GUEST_LAB_LIMIT = 5  # per hour

@router.post("/labs/run")
async def run_lab(request: Request, payload: Dict[str, Any] = Body(...)):
    """Proxy to /api/v1/prompt/prompt/quick_upgrade. Auth required or guest (rate-limited)."""
    auth = request.headers.get("authorization")
    sandbox = request.headers.get("x-sandbox", "false").lower() == "true"
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    # Guest rate limit
    if not auth and sandbox:
        _guest_lab_runs[ip] = [t for t in _guest_lab_runs[ip] if now-t < 3600]
        if len(_guest_lab_runs[ip]) >= _GUEST_LAB_LIMIT:
            return JSONResponse(status_code=HTTP_429_TOO_MANY_REQUESTS, content={"error": "Guest lab run limit reached. Please sign in."})
        _guest_lab_runs[ip].append(now)
    # Input validation
    if not isinstance(payload, dict) or "input" not in payload:
        raise HTTPException(status_code=400, detail="Missing or invalid input")
    if len(str(payload["input"])) > 20000:
        raise HTTPException(status_code=413, detail="Input too long (max 20k chars)")
    # TODO: sanitize input
    # Proxy to internal endpoint
    try:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            headers = {"Authorization": auth} if auth else {}
            resp = await client.post("/api/v1/prompt/prompt/quick_upgrade", json=payload, headers=headers)
            if resp.status_code != 200:
                return JSONResponse(status_code=resp.status_code, content=resp.json())
            data = resp.json()
            # TODO: log analytics event via analytics client
            return {
                "output": data.get("output") or data.get("result") or data,
                "metrics": data.get("metrics", {}),
                "tokens_used": data.get("metrics", {}).get("tokens_used")
            }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Lab run proxy failed: {e}")

# --- POST /api/academy/progress ---
@router.post("/progress")
async def post_progress(request: Request, payload: Dict[str, Any] = Body(...)):
    """Record user progress in academy_progress collection."""
    auth = request.headers.get("authorization")
    user_id = "guest"
    if auth and auth.lower().startswith("bearer "):
        user_id = auth[-12:]  # stub: last 12 chars of token
    doc = {
        "userId": user_id,
        "lessonId": payload.get("lessonId"),
        "completedParts": payload.get("completedParts", []),
        "xp": payload.get("xp", 0),
        "timestamp": int(time.time())
    }
    await db.academy_progress.insert_one(doc)
    return {"status": "ok", "message": "Progress recorded"}

# --- POST /api/academy/quest/submit ---
@router.post("/quest/submit")
async def submit_quest(request: Request, payload: Dict[str, Any] = Body(...)):
    """Store quest submission and run auto-evaluator if structured."""
    auth = request.headers.get("authorization")
    user_id = "guest"
    if auth and auth.lower().startswith("bearer "):
        user_id = auth[-12:]  # stub
    doc = {
        "userId": user_id,
        "quest": payload.get("quest"),
        "answer": payload.get("answer"),
        "timestamp": int(time.time())
    }
    # Auto-eval for JSON schema tasks
    result = None
    if isinstance(payload.get("answer"), dict) and "expected" in payload["answer"]:
        result = payload["answer"]["expected"] == payload["answer"].get("actual")
        doc["auto_eval"] = result
    await db.academy_submissions.insert_one(doc)
    return {"status": "ok", "message": "Quest submitted", "auto_eval": result}

# --- GET /api/academy/leaderboard ---
@router.get("/leaderboard")
async def get_leaderboard():
    """Aggregate top xp from academy_progress."""
    pipeline = [
        {"$group": {"_id": "$userId", "xp": {"$sum": "$xp"}}},
        {"$sort": {"xp": -1}},
        {"$limit": 10}
    ]
    leaders = await db.academy_progress.aggregate(pipeline).to_list(10)
    return {"leaders": [{"user": l["_id"], "score": l["xp"]} for l in leaders]}

# --- POST /api/academy/validate (admin-only) ---
@router.post("/validate")
async def validate_mdx(request: Request):
    """Validate MDX files in content/academy. Admin-only (env token)."""
    admin_token = os.getenv("ACADEMY_ADMIN_TOKEN", "changeme")
    req_token = request.headers.get("x-admin-token")
    if req_token != admin_token:
        raise HTTPException(status_code=403, detail="Forbidden")
    # TODO: implement real MDX validation
    errors = []
    for fname in os.listdir(ACADEMY_CONTENT_PATH):
        if fname.endswith(".mdx"):
            # Simple token check: must contain 'export const frontmatter'
            with open(os.path.join(ACADEMY_CONTENT_PATH, fname), "r", encoding="utf-8") as f:
                content = f.read()
                if "export const frontmatter" not in content:
                    errors.append({"file": fname, "error": "Missing frontmatter export"})
    return {"errors": errors, "status": "ok"}

# --- CORS config ---
# TODO: Ensure CORS allows NEXT_PUBLIC_API_BASE origin in main.py

# --- Rate limit docs ---
# TODO: Document rate limits and security in api/docs/academy.md
