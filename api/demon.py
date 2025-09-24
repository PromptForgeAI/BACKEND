# ==========================
# demon_engine/api/demon.py
# ==========================
from __future__ import annotations

from typing import Any, Dict, Optional, Literal
from uuid import uuid4
from datetime import datetime

from fastapi import APIRouter, HTTPException, Body, Response, status, Depends, Request
from pydantic import BaseModel, Field, ConfigDict

from demon_engine.services.brain_engine.engine_v2 import DemonEngineRouter
from demon_engine.services.brain_engine.errors import (
    ProRequiredError,
    KillSwitchError,
    PipelineNotFound,
)
from demon_engine.services.brain_engine.analytics import log_event

from typing import Annotated
from middleware.auth import get_current_user, auth_manager
from api.models import UpgradeRequest, UpgradeResponse
from utils.atomic_credits import require_credits, ROUTE_COSTS

router = APIRouter(tags=["Demon Engine"])

# ---- Dependency singletons (can be DI-injected later) ----
# Initialize the Demon Engine with compendium.json
engine = DemonEngineRouter()  # compendium_path defaults to "compendium.json"

# ---- Schemas ----

Mode = Literal["free", "pro"]
Client = Literal["web", "chrome", "vscode", "cursor", "agent"]

class DemonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # reject unknown fields
    text: str = Field(min_length=1, max_length=40_000)
    mode: Mode = "free"
    client: Client = "web"
    intent: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    explain: bool = False
    stream: bool = False  # reserved for future SSE/streaming upgrades

class DemonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str
    content: Dict[str, Any]
    matched_pipeline: str
    engine_version: str
    plan: Optional[Dict[str, Any]] = None
    final_prompt: Optional[str] = None
    ts: str

# ---- Endpoint ----

@router.post(
    "/route",
    response_model=DemonResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
async def route(
    req: DemonRequest = Body(...), 
    response: Response = None,
    user: dict = Depends(get_current_user),
    credit_check: dict = Depends(require_credits("demon.route", ROUTE_COSTS["demon.route"], ROUTE_COSTS["_explain_addon"]))
):
    """
    Demon Engine unified entrypoint.
    Parses PFCL, selects techniques from compendium.json, renders fragments,
    enforces contracts, and returns surface-shaped content.
    """
    request_id = f"dem-{uuid4().hex[:12]}"
    ts = datetime.utcnow().isoformat() + "Z"

    # Basic size guard on meta (defense-in-depth)
    if req.meta is not None and len(str(req.meta)) > 60_000:
        raise HTTPException(status_code=413, detail="meta too large")

    # Telemetry: received
    try:
        log_event(
            "demon.request.received",
            {
                "request_id": request_id,
                "mode": req.mode,
                "client": req.client,
                "intent": req.intent,
                "explain": req.explain,
                "stream": req.stream,
                "len_text": len(req.text or ""),
            },
        )
    except Exception:
        # analytics must never break the request
        pass

    try:
        result = await engine.route(
            text=req.text,
            mode=req.mode,
            client=req.client,
            intent=req.intent,
            meta=req.meta,
            user_is_pro=(req.mode == "pro"),
        )

    except ProRequiredError as e:
        raise HTTPException(status_code=402, detail=str(e))  # payment required-ish
    except KillSwitchError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except PipelineNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        # Last-resort shield
        raise HTTPException(status_code=500, detail="internal_error: " + str(e))

    payload: Dict[str, Any] = {
        "request_id": request_id,
        "ts": ts,
        "content": result["content"],
        "matched_pipeline": result["matched_pipeline"],
        "engine_version": result["engine_version"],
    }
    if req.explain:
        payload["plan"] = result.get("plan")
        payload["final_prompt"] = result.get("final_prompt")

    # Response headers for tracing
    if response is not None:
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Engine-Version"] = result.get("engine_version", "unknown")

    # Telemetry: sent
    try:
        log_event(
            "demon.response.sent",
            {
                "request_id": request_id,
                "mode": req.mode,
                "client": req.client,
                "ok": True,
                "size_content": len(str(payload.get("content", ""))),
            },
        )
    except Exception:
        pass

    return payload

@router.post("/v2/upgrade", response_model=UpgradeResponse)
async def upgrade_v2(
    request: Annotated[UpgradeRequest, Body(...)],
    fastapi_request: Request,
    user: dict = Depends(get_current_user),
    credit_check: dict = Depends(require_credits("demon.upgrade_v2", ROUTE_COSTS["demon.upgrade_v2"], ROUTE_COSTS["_explain_addon"]))
):
    """
    Dynamic routing upgrade endpoint (intent × client × mode).
    Backward compatible: infers intent/client if missing.
    Returns surface-specific output contract and techniques.
    If explain=true, returns plan, fidelity_score, matched_entries.
    Logs analytics and (if consented) before/after hashes.
    """
    import time
    # Determine pro status from real user info - Use unified auth manager
    user_is_pro = auth_manager.is_pro_user(user)
    
    t0 = time.time()
    retries = 0
    # Enforce kill-switch/global pro disable/rate limits
    features = engine.features
    key = (request.intent.value if hasattr(request.intent, 'value') else request.intent or 'unknown',
           request.mode.value if hasattr(request.mode, 'value') else request.mode or 'free',
           request.client.value if hasattr(request.client, 'value') else request.client or 'unknown')
    if features.is_killswitch(key):
        log_event('killswitch_hit', f"{key}", 0, 0)
        raise HTTPException(status_code=503, detail="Temporarily disabled for stability.")
    if features.is_global_pro_disabled() and (request.mode == 'pro' or (hasattr(request.mode, 'value') and request.mode.value == 'pro')):
        log_event('pro_required', f"{key}", 0, 0)
        raise HTTPException(status_code=402, detail="Pro is globally disabled.")
    plan_str = request.mode.value if hasattr(request.mode, 'value') else request.mode or 'free'
    client_str = request.client.value if hasattr(request.client, 'value') else request.client or 'unknown'
    user_id = user.get("uid") or user.get("_id") or "anonymous"
    if not features.check_rate_limit(user_id, key, plan_str):
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
    try:
        route_info = await engine.route(
            intent=request.intent.value if hasattr(request.intent, 'value') else request.intent,
            mode=request.mode.value if hasattr(request.mode, 'value') else request.mode,
            client=request.client.value if hasattr(request.client, 'value') else request.client,
            user_is_pro=user_is_pro,
            text=request.text,
            meta=request.meta or {},
            allow_fallback=True
        )
    except ProRequiredError as e:
        log_event('pro_required', f"{key}", 0, 0)
        raise HTTPException(status_code=402, detail="Pro required: " + str(e))
    except KillSwitchError as e:
        log_event('killswitch_hit', f"{key}", 0, 0)
        raise HTTPException(status_code=503, detail="Temporarily disabled for stability: " + str(e))
    except PipelineNotFound as e:
        log_event('fallback_used', f"{key}", 0, 0)
        raise HTTPException(status_code=500, detail="No pipeline matched; fallback failed: " + str(e))
    latency = time.time() - t0
    log_event('route_selected', route_info["matched_key"], latency, retries, route_info.get('fidelity_score'))
    # Simulate plan, fidelity, matched_entries for explain
    plan = None
    fidelity_score = route_info.get('fidelity_score')
    matched_entries = None
    if request.explain:
        plan = [f"Apply {t}" for t in route_info.get("techniques", [])]
        matched_entries = route_info.get("techniques", [])
    # Log before/after if user consents (meta['log_before_after'])
    consent = (request.meta or {}).get('log_before_after', False)
    log_before_after(request.text, route_info["simulated_output"], consent)
    # --- Log upgrade and update stats/credits ---
    try:
        # Prefer the request's app.state.db (when running under the FastAPI app that sets it).
        db = getattr(getattr(fastapi_request, "app", None), "state", None)
        db = getattr(db, "db", None) if db is not None else None
        # Fallback to the global dependency export if app.state.db isn't available
        if db is None:
            from dependencies import db as default_db
            db = default_db

        # Safe writes (best-effort telemetry / archival)
        await db.prompt_upgrades.insert_one({
            "user_id": user.get("uid"),
            "text": request.text,
            "upgraded": route_info.get("simulated_output"),
            "mode": request.mode.value if hasattr(request.mode, 'value') else request.mode,
            "source": request.client.value if hasattr(request.client, 'value') else request.client,
            "timestamp": time.time(),
        })

        # Archive anonymized copy for AI training (no user info)
        archive_doc = {
            "text": request.text,
            "upgraded": route_info.get("simulated_output"),
            "mode": request.mode.value if hasattr(request.mode, 'value') else request.mode,
            "source": request.client.value if hasattr(request.client, 'value') else request.client,
            "archived_at": time.time()
        }
        try:
            await db.archived_prompts.insert_one(archive_doc)
        except Exception as e:
            import logging
            logging.warning(f"Failed to archive upgraded prompt: {e}")

        await db.users.update_one({"uid": user.get("uid")}, {"$inc": {"stats.prompts_upgraded": 1}})
        if "credits" in user and isinstance(user["credits"], dict):
            await db.users.update_one({"uid": user.get("uid")}, {"$inc": {"credits.balance": -1}})
    except Exception as logerr:
        import logging
        logging.warning(f"Failed to log demon upgrade or update stats: {logerr}")
    return UpgradeResponse(
        upgraded=route_info["simulated_output"],
        matched_pipeline=route_info["matched_pipeline"],
        engine_version=route_info["engine_version"],
        plan=plan,
        diffs=None,
        fidelity_score=fidelity_score,
        matched_entries=matched_entries,
        message=f"Output contract: {route_info.get('output_contract')}" + (" (fallback used)" if route_info.get('fallback') else "")
    )
