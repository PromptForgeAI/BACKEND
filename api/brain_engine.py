# FastAPI router for Brain Engine endpoints (MVP)
from fastapi import APIRouter, Request, Depends, HTTPException
from middleware.auth import get_current_user, require_pro_plan
from services.brain_engine.engine import BrainEngine
from api.models import APIResponse
from utils.rate_limiting import require_credits_and_rate_limit
import os

router = APIRouter(tags=["Brain Engine"])

# Lightweight debug_print helper for local tracing (uses module logger at DEBUG level)
import logging as _logging
_logger = _logging.getLogger("api.brain_engine")
def debug_print(msg, *args, **kwargs):
    try:
        # Provide a predictable debug wrapper that won't fail
        _logger.debug(msg, *args)
    except Exception:
        try:
            # best-effort fallback to print so debug doesn't hide errors
            print("[DEBUG api.brain_engine]", msg % args if args else msg)
        except Exception:
            pass

# Load compendium on startup (MVP: from file)
import traceback
from demon_engine.services.brain_engine.engine_v2 import DemonEngineRouter

COMPENDIUM_PATH = os.path.join(os.path.dirname(__file__), '../compendium.json')
brain_engine = BrainEngine(compendium_path=COMPENDIUM_PATH)


from fastapi import Body
from fastapi.responses import JSONResponse
from fastapi.openapi.models import Response as OpenAPIResponse

@router.post(
    "/quick_upgrade",
    response_model=APIResponse,
    summary="Quick Mode: Upgrade prompt (extension, low-latency)",
    responses={
        200: {
            "description": "Quick Mode upgrade result",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "upgraded": "<god-tier prompt>",
                            "plan": None,
                            "diffs": None,
                            "fidelity_score": None,
                            "matched_entries": None
                        },
                        "message": "Prompt upgraded via Brain Engine"
                    }
                }
            }
        }
    }
)
async def quick_upgrade(
    payload: dict = Body(...),
    request: Request = None,
    security_check: dict = Depends(require_credits_and_rate_limit("brain.quick_upgrade", 2, 1))
):
    """Quickly upgrade a prompt using the Brain Engine (Quick Mode, extension/low-latency)."""
    from config.providers import ProviderAuthError
    import logging, traceback
    import time
    logging.info("[quick_upgrade] Called with payload: %s", payload)
    text = payload.get("text")
    context = payload.get("context", {})
    options = payload.get("options", {})
    logging.info(f"[quick_upgrade] text: {text}")
    logging.info(f"[quick_upgrade] context: {context}")
    logging.info(f"[quick_upgrade] options: {options}")
    if not text:
        logging.warning("[quick_upgrade] Missing input text")
        raise HTTPException(status_code=400, detail="Missing input text")
    # --- Enforce authentication for all users ---
    user = security_check.get('user') if security_check and isinstance(security_check, dict) else None
    logging.info(f"[quick_upgrade] user: {user}")
    if not user or not user.get("uid"):
        logging.warning("[quick_upgrade] Authentication required: user missing or no uid")
        raise HTTPException(status_code=401, detail="Authentication required")
    mode = options.get("mode", "quick")
    logging.info(f"[quick_upgrade] mode: {mode}")
    signals = brain_engine.extract_signals(text, context)
    logging.info(f"[quick_upgrade] signals: {signals}")
    techniques = brain_engine.match_techniques(signals, mode=mode)
    logging.info(f"[quick_upgrade] techniques: {techniques}")
    pipeline = brain_engine.compose_pipeline(techniques, mode=mode)
    logging.info(f"[quick_upgrade] pipeline: {pipeline}")
    try:
        result = await brain_engine.run_pipeline(pipeline, text, context, mode=mode, user=user)
        logging.info(f"[quick_upgrade] pipeline result: {result}")
        # Log usage event (extension or web) and update stats/history
        try:
            db = request.app.state.db
            log_doc = {
                "user_id": user["uid"],
                "action": "prompt_upgrade",
                "mode": mode,
                "source": context.get("source", "unknown"),
                "url": context.get("url", ""),
                "timestamp": time.time(),
                "text": text,
                "upgraded": result.get("upgraded"),
            }
            logging.info(f"[quick_upgrade] Logging usage event: {log_doc}")
            await db.user_analytics.insert_one(log_doc)
            # Add to prompt_upgrades history
            await db.prompt_upgrades.insert_one({
                "user_id": user["uid"],
                "text": text,
                "upgraded": result.get("upgraded"),
                "mode": mode,
                "source": context.get("source", "unknown"),
                "timestamp": time.time(),
            })
            # Archive anonymized copy for AI training (no user info)
            archive_doc = {
                "text": text,
                "upgraded": result.get("upgraded"),
                "mode": mode,
                "source": context.get("source", "unknown"),
                "archived_at": time.time()
            }
            try:
                await db.archived_prompts.insert_one(archive_doc)
            except Exception as e:
                logging.warning(f"Failed to archive upgraded prompt: {e}")
            # Increment stats.prompts_upgraded
            await db.users.update_one({"uid": user["uid"]}, {"$inc": {"stats.prompts_upgraded": 1}})
            # Optionally update credits/subscription
            if "credits" in user and isinstance(user["credits"], dict):
                await db.users.update_one({"uid": user["uid"]}, {"$inc": {"credits.balance": -1}})
        except Exception as logerr:
            logging.warning(f"Failed to log usage event or update stats: {logerr}")
        return APIResponse(data=result, message="Prompt upgraded via Brain Engine")
    except ProviderAuthError as e:
        logging.error(f"[quick_upgrade] ProviderAuthError: {e}")
        raise HTTPException(
            status_code=502,
            detail={"code": "provider_auth_error", "provider": "groq", "message": str(e)}
        )
    except Exception as e:
        logging.error(f"[quick_upgrade] Exception: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="upgrade_failed")


@router.post(
    "/upgrade",
    response_model=APIResponse,
    summary="Full Mode: Upgrade prompt (deep pipeline, Pro)",
    responses={
        200: {
            "description": "Full Mode upgrade result",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "upgraded": "<god-tier prompt>",
                            "plan": {"nodes": [], "edges": []},
                            "diffs": "<unified diff>",
                            "fidelity_score": 0.9,
                            "matched_entries": [{"id": "few_shot_prompting", "score": 0.83}]
                        },
                        "message": "Prompt upgraded via Brain Engine (Full Mode)"
                    }
                }
            }
        }
    }
)
@require_pro_plan
async def full_upgrade(
    payload: dict = Body(...),
    request: Request = None,
    user: dict = Depends(get_current_user),
    security_check: dict = Depends(require_credits_and_rate_limit("brain.full_upgrade", 8, 1))
):
    """Upgrade a prompt using the Brain Engine (Full Mode, Pro, explainable pipeline)."""
    import time, traceback as _traceback
    text = payload.get("text")
    context = payload.get("context", {})
    options = payload.get("options", {})

    debug_print("full_upgrade called")
    debug_print("payload keys: %s", list(payload.keys()) if isinstance(payload, dict) else str(type(payload)))
    debug_print("received text length: %s", len(text) if text else 0)
    debug_print("context: %s", context)
    debug_print("options: %s", options)
    debug_print("user (partial): %s", {k: user.get(k) for k in ("uid","email") if user and k in user})

    if not text:
        debug_print("full_upgrade - missing input text, raising 400")
        raise HTTPException(status_code=400, detail="Missing input text")

    # Pro validation is now handled by @require_pro_plan decorator
    mode = options.get("mode", "full")
    debug_print("mode: %s", mode)

    try:
        t0 = time.time()
        debug_print("calling extract_signals")
        signals = brain_engine.extract_signals(text, context)
        debug_print("extract_signals result: %s", signals)
        t1 = time.time()

        debug_print("calling match_techniques")
        techniques = brain_engine.match_techniques(signals, mode=mode)
        debug_print("match_techniques result: %s", techniques)
        t2 = time.time()

        debug_print("calling compose_pipeline")
        pipeline = brain_engine.compose_pipeline(techniques, mode=mode)
        debug_print("compose_pipeline result: %s", pipeline)
        t3 = time.time()

        debug_print("running pipeline (this may call external providers)")
        result = await brain_engine.run_pipeline(pipeline, text, context, mode=mode, user=user)
        t4 = time.time()
        debug_print("pipeline finished; durations: extract=%.3fs match=%.3fs compose=%.3fs run=%.3fs", (t1-t0), (t2-t1), (t3-t2), (t4-t3))
        debug_print("pipeline result keys: %s", list(result.keys()) if isinstance(result, dict) else str(type(result)))
        # Log usage event (extension or web) and update stats/history
        import time as _time
        try:
            db = request.app.state.db
            debug_print("inserting usage log into user_analytics")
            await db.user_analytics.insert_one({
                "user_id": user["uid"],
                "action": "prompt_upgrade",
                "mode": mode,
                "source": context.get("source", "unknown"),
                "url": context.get("url", ""),
                "timestamp": _time.time(),
                "text": text,
                "upgraded": result.get("upgraded"),
            })
            debug_print("usage log inserted successfully")
            # Add to prompt_upgrades history
            await db.prompt_upgrades.insert_one({
                "user_id": user["uid"],
                "text": text,
                "upgraded": result.get("upgraded"),
                "mode": mode,
                "source": context.get("source", "unknown"),
                "timestamp": _time.time(),
            })
            # Archive anonymized copy for AI training (no user info)
            archive_doc = {
                "text": text,
                "upgraded": result.get("upgraded"),
                "mode": mode,
                "source": context.get("source", "unknown"),
                "archived_at": _time.time()
            }
            try:
                await db.archived_prompts.insert_one(archive_doc)
            except Exception as e:
                debug_print("Failed to archive upgraded prompt: %s", str(e))
            # Increment stats.prompts_upgraded
            await db.users.update_one({"uid": user["uid"]}, {"$inc": {"stats.prompts_upgraded": 1}})
            # Optionally update credits/subscription
            if "credits" in user and isinstance(user["credits"], dict):
                await db.users.update_one({"uid": user["uid"]}, {"$inc": {"credits.balance": -1}})
        except Exception as logerr:
            debug_print("Failed to log usage event or update stats: %s", str(logerr))
        debug_print("returning APIResponse to caller")
        return APIResponse(data=result, message="Prompt upgraded via Brain Engine (Full Mode)")
    except Exception as _e:
        # log full traceback for debugging
        tb = _traceback.format_exc()
        debug_print("full_upgrade EXCEPTION: %s", str(_e))
        debug_print("full_upgrade TRACEBACK: %s", tb)
        raise
