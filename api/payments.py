

from fastapi import APIRouter, Request, Depends, HTTPException
from dependencies import get_current_user
from utils.payment_utils import select_payment_provider
import os
import uuid
import json
import razorpay
from paddle_billing import Client as PaddleClient, Environment, Options

# --- Load billing config and validate Paddle price IDs at startup ---
import threading
_billing_config = None
_billing_config_lock = threading.Lock()
def get_billing_config():
    global _billing_config
    with _billing_config_lock:
        if _billing_config is None:
            with open("billing.config.json", "r") as f:
                _billing_config = json.load(f)
        return _billing_config

def get_paddle_price_id(tier: str) -> str:
    config = get_billing_config()
    tier_cfg = config["tiers"].get(tier)
    if not tier_cfg:
        raise RuntimeError(f"Tier '{tier}' not found in billing.config.json")
    price_id = tier_cfg.get("paddle_price_id") or os.getenv(f"PADDLE_PRICE_ID_{tier.upper()}")
    if not price_id:
        raise RuntimeError(f"Paddle price_id for tier '{tier}' not set in billing.config.json or env")
    return price_id

# Validate all required Paddle price IDs at startup
for _tier in ["pro", "team"]:
    try:
        get_paddle_price_id(_tier)
    except Exception as e:
        print(f"[FATAL] Paddle price_id missing for tier '{_tier}': {e}")
        raise

def debug_log(msg):
    if os.getenv("DEBUG_TRIGGER", "false").lower() == "true":
        print(f"[DEBUG payments.py] {msg}")

router = APIRouter(tags=["Payments"])




@router.post("/initiate-payment")
async def initiate_payment(request: Request, user: dict = Depends(get_current_user)):
    """
    Initiate payment: Select provider based on user country (Razorpay for India, Paddle for others).
    Returns the provider and a real payment link. Supports both Pro and Team plans.
    """
    debug_log("/initiate-payment called")
    provider = select_payment_provider(request, user)
    debug_log(f"User: {user}")
    try:
        # Accept tier from request body or query param (default to pro)
        body = await request.json() if request.method == "POST" else {}
        tier = body.get("tier") if isinstance(body, dict) else None
        if not tier:
            tier = request.query_params.get("tier", "pro").lower()
        debug_log(f"Requested tier: {tier}")


        # Load tier info from billing.config.json
        config = get_billing_config()
        tier_cfg = config["tiers"].get(tier)
        if not tier_cfg:
            debug_log(f"Tier '{tier}' not found in billing.config.json")
            raise HTTPException(status_code=400, detail=f"Invalid tier: {tier}")
        amount = tier_cfg.get("price_month_usd", 0) if provider == "paddle" else tier_cfg.get("price_month_inr", 0) or (49 if tier == "team" else 12)
        paddle_price_id = get_paddle_price_id(tier)
        currency = "INR" if provider == "razorpay" else "USD"
        description = f"PromptForge {tier.capitalize()} Subscription"
        order_id = str(uuid.uuid4())
        debug_log(f"Amount: {amount}, Currency: {currency}, Description: {description}, OrderID: {order_id}")


        if provider == "razorpay":
            key_id = os.getenv("RAZORPAY_KEY_ID")
            key_secret = os.getenv("RAZORPAY_KEY_SECRET")
            if not key_id or not key_secret:
                debug_log("Razorpay keys missing!")
                raise HTTPException(status_code=500, detail="Razorpay keys not configured")
            try:
                client = razorpay.Client(auth=(key_id, key_secret))
                order = client.order.create({
                    "amount": int(amount) * 100,
                    "currency": currency,
                    "receipt": order_id,
                    "payment_capture": 1,
                    "notes": {"user_id": user.get("uid"), "tier": tier}
                })
                debug_log(f"Razorpay order created: {order}")
                payment_link = f"https://checkout.razorpay.com/v1/checkout.js?order_id={order['id']}"
                # Return key_id for frontend widget initialization
                return {"provider": provider, "payment_link": payment_link, "order_id": order["id"], "tier": tier, "key_id": key_id}
            except Exception as e:
                debug_log(f"Razorpay error: {e}")
                # Do not leak raw error to client
                raise HTTPException(status_code=500, detail="Razorpay payment error. Please try again later.")


        elif provider == "paddle":
            api_key = os.getenv("PADDLE_API_SECRET_KEY")
            if not api_key:
                debug_log("PADDLE_API_SECRET_KEY not set in environment!")
                raise HTTPException(status_code=500, detail="Paddle API key not configured")
            try:
                migration_mode = os.getenv("MIGRATION_MODE", "sandbox").lower()
                if migration_mode == "sandbox":
                    paddle = PaddleClient(api_key, options=Options(Environment.SANDBOX))
                    debug_log("Paddle SDK set to SANDBOX mode")
                else:
                    paddle = PaddleClient(api_key, options=Options(Environment.LIVE))
                    debug_log("Paddle SDK set to LIVE mode")
                transaction = paddle.transactions.create({
                    "items": [{"price_id": paddle_price_id, "quantity": 1}],
                    "customer_email": user.get("email"),
                    "custom_data": {"user_id": user.get("uid"), "order_id": order_id, "tier": tier},
                    "success_url": os.getenv("PADDLE_SUCCESS_URL", "https://yourdomain.com/success"),
                    "cancel_url": os.getenv("PADDLE_CANCEL_URL", "https://yourdomain.com/cancel")
                })
                debug_log(f"Paddle transaction created: {transaction}")
                payment_link = getattr(getattr(transaction, 'checkout', None), 'url', None)
                transaction_id = getattr(transaction, 'id', None)
                # Warn if checkout URL is not Paddle's hosted checkout
                if payment_link and not payment_link.startswith("https://checkout.paddle.com/"):
                    debug_log(f"[WARN] Paddle checkout URL does not look like Paddle hosted checkout: {payment_link}")
                return {
                    "provider": provider,
                    "payment_link": payment_link,
                    "transaction_id": transaction_id,
                    "tier": tier,
                    "paddle_env": migration_mode
                }
            except Exception as e:
                debug_log(f"Paddle error: {e}")
                # Do not leak raw error to client
                raise HTTPException(status_code=500, detail="Paddle payment error. Please try again later.")

        else:
            debug_log(f"Unsupported payment provider: {provider}")
            raise HTTPException(status_code=400, detail="Unsupported payment provider")

    except Exception as e:
        debug_log(f"General error in initiate_payment: {e}")
        raise HTTPException(status_code=500, detail=f"initiate_payment error: {e}")
