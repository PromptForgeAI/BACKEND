import os
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request
router = APIRouter()
logger = logging.getLogger(__name__)




PADDLE_WEBHOOK_SECRET = os.getenv("PADDLE_WEBHOOK_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

# Health endpoint removed - duplicate of main health endpoint at /health
# Use main health endpoint instead: GET /health or GET /api/v1/health

from dependencies import is_duplicate_event, mark_event_processed

async def process_successful_payment(payment_intent: Dict[str, Any]):
    """Adds credits to a user account after a successful Stripe payment."""
    logger.info("Processing successful payment...")
    from dependencies import db
    try:
        # Extract metadata (user_id, amount, etc.)
        metadata = payment_intent.get("metadata", {})
        user_id = metadata.get("user_id")
        if not user_id:
            logger.error("No user_id in Stripe payment metadata")
            return
        amount_received = payment_intent.get("amount_received", 0)
        currency = payment_intent.get("currency", "usd")
        # Define your credit conversion rate (e.g., 100 cents = 1 credit)
        credits_to_add = int(amount_received // 100)  # 1 credit per $1
        if credits_to_add <= 0:
            logger.warning(f"No credits to add for payment_intent: {payment_intent.get('id')}")
            return
        # Update user credits atomically
        res = await db["users"].update_one({"uid": user_id}, {"$inc": {"credits": credits_to_add}})
        if res.matched_count == 0:
            logger.error(f"User not found for Stripe payment: {user_id}")
            return
        # Log transaction
        tx_doc = {
            "user_id": user_id,
            "amount": amount_received / 100.0,
            "credits_added": credits_to_add,
            "currency": currency,
            "payment_intent_id": payment_intent.get("id"),
            "created_at": datetime.utcnow(),
            "type": "stripe_payment"
        }
        await db["transactions"].insert_one(tx_doc)
        logger.info(f"Added {credits_to_add} credits to user {user_id} for Stripe payment {payment_intent.get('id')}")
    except Exception as e:
        logger.error(f"Failed to process Stripe payment: {e}")

# ------------------------------ STRIPE: WEBHOOK (Commented Out) ------------------------------
# @router.post("/stripe", tags=["webhooks"])
# async def stripe_webhook(request: Request):
#     if not STRIPE_WEBHOOK_SECRET:
#         raise HTTPException(status_code=503, detail="Webhook system is not configured")
#
#     payload = await request.body()
#     sig_header = request.headers.get("stripe-signature")
#
#     try:
#         event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
#     except ValueError:
#         logger.error("Invalid payload in Stripe webhook")
#         raise HTTPException(status_code=400, detail="Invalid payload")
#     except stripe.error.SignatureVerificationError:
#         logger.error("Invalid signature in Stripe webhook")
#         raise HTTPException(status_code=400, detail="Invalid signature")
#
#     event_id = event["id"]
#     from dependencies import is_duplicate_event, mark_event_processed
#     if await is_duplicate_event(event_id):
#         logger.info(f"Duplicate Stripe event: {event_id}")
#         return APIResponse(data=None, message="Duplicate event", status_code=200)
#
#     await mark_event_processed(event_id)

# ------------------------------ PADDLE: WEBHOOK ------------------------------

# --- SECURE PADDLE WEBHOOK HANDLER ---
from utils.payment_utils import verify_signature
from dependencies import db, track_event
from demon_engine.services.brain_engine.analytics import log_event
import datetime
import razorpay

@router.post("/paddle", tags=["webhooks"])
async def paddle_webhook(request: Request):
    if not PADDLE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Paddle webhook secret not configured")
    # Signature verification
    is_valid = await verify_signature("paddle", request)
    if not is_valid:
        logger.error("Invalid Paddle webhook signature")
        return {"ok": False, "error": "Invalid signature"}, 401
    payload = await request.json()
    event_id = payload.get("event_id") or payload.get("id") or payload.get("alert_id")
    transaction_id = payload.get("transaction_id") or payload.get("order_id")
    user_id = None
    # Try to extract user_id from custom_data or passthrough
    custom_data = payload.get("custom_data") or payload.get("passthrough")
    if isinstance(custom_data, dict):
        user_id = custom_data.get("user_id")
    elif isinstance(custom_data, str):
        try:
            import json as _json
            user_id = _json.loads(custom_data).get("user_id")
        except Exception:
            pass
    # Idempotency: check if transaction already processed
    if not transaction_id:
        logger.error("No transaction_id in Paddle webhook")
        return {"ok": False, "error": "No transaction_id"}, 400
    exists = await db.transactions.find_one({"provider": "paddle", "transaction_id": transaction_id})
    if exists:
        logger.info(f"Duplicate Paddle transaction: {transaction_id}")
        return {"ok": True, "duplicate": True}
    # Success: update user subscription, credits, log transaction
    tier = payload.get("tier") or payload.get("plan_name") or "pro"
    credits_to_add = 500 if tier == "pro" else 2000 if tier == "team" else 0
    now = datetime.datetime.utcnow()
    if not user_id:
        logger.error(f"No user_id in Paddle webhook: {payload}")
        return {"ok": False, "error": "No user_id"}, 400
    # Update user subscription
    await db.users.update_one(
        {"uid": user_id},
        {"$set": {"subscription.tier": tier, "subscription.status": "active", "subscription.provider_customer_id": payload.get("customer_id"), "updated_at": now},
         "$inc": {"credits.balance": credits_to_add}},
        upsert=True
    )
    # Log transaction
    tx_doc = {
        "user_id": user_id,
        "provider": "paddle",
        "transaction_id": transaction_id,
        "amount": payload.get("amount", 0),
        "currency": payload.get("currency", "USD"),
        "tier": tier,
        "credits_added": credits_to_add,
        "created_at": now,
        "raw": payload
    }
    await db.transactions.insert_one(tx_doc)
    # Analytics event
    await track_event(user_id, "payment_success", {"provider": "paddle", "transaction_id": transaction_id, "tier": tier, "amount": payload.get("amount", 0)})
    log_event("payment_success", {"user_id": user_id, "provider": "paddle", "transaction_id": transaction_id, "tier": tier, "amount": payload.get("amount", 0)})
    logger.info(f"Paddle payment success for user {user_id}, transaction {transaction_id}")
    return {"ok": True, "user_id": user_id, "transaction_id": transaction_id}

# ------------------------------ RAZORPAY: WEBHOOK ------------------------------

# --- SECURE RAZORPAY WEBHOOK HANDLER ---
@router.post("/razorpay", tags=["webhooks"])
async def razorpay_webhook(request: Request):
    if not RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Razorpay webhook secret not configured")
    is_valid = await verify_signature("razorpay", request)
    if not is_valid:
        logger.error("Invalid Razorpay webhook signature")
        return {"ok": False, "error": "Invalid signature"}, 401
    payload = await request.json()
    event = payload.get("event")
    order_id = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("order_id") or payload.get("order_id")
    user_id = None
    notes = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("notes", {})
    if isinstance(notes, dict):
        user_id = notes.get("user_id")
    # Log all incoming events for audit/debug
    print(f"[DEBUG webhook] Received Razorpay event: {event}, order_id: {order_id}, user_id: {user_id}")
    logger.info(f"Razorpay webhook event: {event}, order_id: {order_id}, user_id: {user_id}")
    # Handle missing order_id
    if not order_id:
        logger.error("No order_id in Razorpay webhook")
        return {"ok": False, "error": "No order_id"}, 400
    # Robust idempotency: Only mark as processed for success events
    now = datetime.datetime.utcnow()
    success_events = {"payment.captured", "order.paid"}
    # Always log/store every event for audit
    tx_doc = {
        "user_id": user_id,
        "provider": "razorpay",
        "transaction_id": order_id,
        "amount": payload.get("payload", {}).get("payment", {}).get("entity", {}).get("amount", 0) / 100.0,
        "currency": payload.get("payload", {}).get("payment", {}).get("entity", {}).get("currency", "INR"),
        "tier": notes.get("tier") or "pro",
        "credits_added": 0,
        "created_at": now,
        "event": event,
        "raw": payload
    }
    # Check if already processed for success events
    if event in success_events:
        exists = await db.transactions.find_one({"provider": "razorpay", "transaction_id": order_id, "event": {"$in": list(success_events)}})
        if exists:
            print(f"[DEBUG webhook] Duplicate Razorpay success event for order: {order_id}")
            logger.info(f"Duplicate Razorpay success event for order: {order_id}")
            return {"ok": True, "duplicate": True}
        # Only update user and credits for success events
        tier = notes.get("tier") or "pro"
        credits_to_add = 500 if tier == "pro" else 2000 if tier == "team" else 0
        if not user_id:
            print(f"[DEBUG webhook] No user_id in Razorpay webhook: {payload}")
            logger.error(f"No user_id in Razorpay webhook: {payload}")
            return {"ok": False, "error": "No user_id"}, 400
        try:
            print(f"[DEBUG webhook] Attempting to update user {user_id} with tier {tier} and credits {credits_to_add}")
            # Extract payment entity for billing fields
            payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
            billing_update = {
                "plan": tier,
                "status": "active",
                "renewed_at": now,
                "provider": "razorpay",
                "customer_id": payment_entity.get("contact"),
            }
            subscription_update = {
                "tier": tier,
                "status": "active",
                "provider_customer_id": payment_entity.get("contact"),
                "updated_at": now,
            }
            update_fields = {
                "subscription": subscription_update,
                "billing": billing_update,
                "updated_at": now,
            }
            res = await db.users.update_one(
                {"uid": user_id},
                {"$set": update_fields, "$inc": {"credits.balance": credits_to_add}},
                upsert=True
            )
            print(f"[DEBUG webhook] DB update result: matched={res.matched_count}, upserted={res.upserted_id}")
            if res.matched_count == 0 and res.upserted_id is None:
                raise Exception("User not found or not updated")
            tx_doc["credits_added"] = credits_to_add
            await db.transactions.insert_one(tx_doc)
            print(f"[DEBUG webhook] Transaction inserted for user {user_id}, order {order_id}")
            await track_event(user_id, "payment_success", {"provider": "razorpay", "transaction_id": order_id, "tier": tier, "amount": tx_doc["amount"]})
            log_event("payment_success", {"user_id": user_id, "provider": "razorpay", "transaction_id": order_id, "tier": tier, "amount": tx_doc["amount"]})
            logger.info(f"Razorpay payment success for user {user_id}, order {order_id}")
            return {"ok": True, "user_id": user_id, "order_id": order_id}
        except Exception as e:
            # Refund logic
            print(f"[DEBUG webhook] Failed to update user after payment success, refunding: {e}")
            logger.error(f"Failed to update user after payment success, refunding: {e}")
            try:
                # Setup Razorpay client
                razorpay_key = os.getenv("RAZORPAY_KEY_ID")
                razorpay_secret = os.getenv("RAZORPAY_KEY_SECRET")
                client = razorpay.Client(auth=(razorpay_key, razorpay_secret))
                payment_id = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("id")
                amount_paise = int(payload.get("payload", {}).get("payment", {}).get("entity", {}).get("amount", 0))
                refund = client.payment.refund(payment_id, {"amount": amount_paise})
                print(f"[DEBUG webhook] Refund issued for payment {payment_id} (order {order_id}) due to error: {e}")
                logger.error(f"Refund issued for payment {payment_id} (order {order_id}) due to error: {e}")
                tx_doc["refund"] = refund
                tx_doc["refund_reason"] = str(e)
                await db.transactions.insert_one(tx_doc)
                return {"ok": False, "refund": True, "reason": str(e)}
            except Exception as refund_exc:
                print(f"[DEBUG webhook] Refund failed for payment {order_id}: {refund_exc}")
                logger.critical(f"Refund failed for payment {order_id}: {refund_exc}")
                tx_doc["refund_failed"] = str(refund_exc)
                await db.transactions.insert_one(tx_doc)
                return {"ok": False, "refund": False, "reason": str(e), "refund_error": str(refund_exc)}
    else:
        # For all other events, just log/store for audit, but do not update user or mark as processed
        print(f"[DEBUG webhook] Logging non-success Razorpay event: {event} for user {user_id}, order {order_id}")
        await db.transactions.insert_one(tx_doc)
        logger.info(f"Razorpay event logged: {event} for user {user_id}, order {order_id}")
        await track_event(user_id or "unknown", f"payment_{event}", {"provider": "razorpay", "transaction_id": order_id, "event": event})
        log_event(f"payment_{event}", {"user_id": user_id, "provider": "razorpay", "transaction_id": order_id, "event": event})
        return {"ok": True, "event": event, "user_id": user_id, "order_id": order_id}

