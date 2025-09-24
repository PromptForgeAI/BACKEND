from utils.cache import get_cache, set_cache, invalidate_cache
from utils.camelize import camelize
import json
import os
import logging
import hashlib
from fastapi import APIRouter, Request, HTTPException, Depends, Body, Response
from dependencies import get_current_user
from utils.payment_utils import verify_signature, process_payment_event, debug_log

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "billing.config.json")
router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    body = await request.json()
    debug_log(f"[Webhook] Stripe event received: {body}")
    if not await verify_signature("stripe", request):
        debug_log("[Webhook] Stripe signature verification failed.")
        raise HTTPException(status_code=400, detail="Invalid signature")
    debug_log("[Webhook] Stripe signature verified.")
    await process_payment_event("stripe", body)
    debug_log("[Webhook] Stripe event processed.")
    return {"ok": True}


@router.post("/webhooks/paddle")
async def paddle_webhook(request: Request):
    body = await request.json()
    debug_log(f"[Webhook] Paddle event received: {body}")
    if not await verify_signature("paddle", request):
        debug_log("[Webhook] Paddle signature verification failed.")
        raise HTTPException(status_code=400, detail="Invalid signature")
    debug_log("[Webhook] Paddle signature verified.")
    await process_payment_event("paddle", body)
    debug_log("[Webhook] Paddle event processed.")
    return {"ok": True}


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    body = await request.json()
    debug_log(f"[Webhook] Razorpay event received: {body}")
    if not await verify_signature("razorpay", request):
        debug_log("[Webhook] Razorpay signature verification failed.")
        raise HTTPException(status_code=400, detail="Invalid signature")
    debug_log("[Webhook] Razorpay signature verified.")
    await process_payment_event("razorpay", body)
    debug_log("[Webhook] Razorpay event processed.")
    return {"ok": True}


@router.post("/webhooks/paypal")
async def paypal_webhook(request: Request):
    body = await request.json()
    debug_log(f"[Webhook] Paypal event received: {body}")
    if not await verify_signature("paypal", request):
        debug_log("[Webhook] Paypal signature verification failed.")
        raise HTTPException(status_code=400, detail="Invalid signature")
    debug_log("[Webhook] Paypal signature verified.")
    await process_payment_event("paypal", body)
    debug_log("[Webhook] Paypal event processed.")
    return {"ok": True}
# --- Cancel Subscription Endpoint ---
@router.post("/cancel")
async def cancel_subscription(user: dict = Depends(get_current_user)):
    """Cancel subscription at period end. Returns status and renews_at (mock)."""
    # Detect provider (mock: use user.subscription.provider or country)
    sub = user.get("subscription", {}) or {}
    provider = sub.get("provider")
    if not provider:
        country = (user.get("profile", {}) or {}).get("country", "IN")
        provider = "razorpay" if country.upper() == "IN" else "paddle"
    # TODO: Integrate with provider API to schedule cancellation
    renews_at = sub.get("renews_at", "2099-12-31T00:00:00Z")
    return {
        "status": "scheduled_cancellation",
        "provider": provider,
        "renews_at": renews_at
    }

# --- Customer Portal Endpoint ---
@router.get("/portal")
async def get_billing_portal(user: dict = Depends(get_current_user)):
    """Returns a URL to the provider's customer portal (mock)."""
    sub = user.get("subscription", {}) or {}
    provider = sub.get("provider")
    if not provider:
        country = (user.get("profile", {}) or {}).get("country", "IN")
        provider = "razorpay" if country.upper() == "IN" else "paddle"
    # Mock URLs
    if provider == "razorpay":
        url = f"https://razorpay.com/portal?user={user['uid']}"
    elif provider == "paddle":
        url = f"https://paddle.com/portal?user={user['uid']}"
    else:
        url = f"https://paypal.com/portal?user={user['uid']}"
    return {"url": url, "provider": provider}
# --- Subscription Purchase Endpoint ---
@router.post("/subscribe", status_code=201)
async def subscribe_plan(
    body: dict = Body(...),
    user: dict = Depends(get_current_user)
):

    """Initiate a subscription purchase. Selects Razorpay (IN), Paddle (non-IN), PayPal as backup. Creates pending_checkout doc. Returns checkout_url and provider."""
    from dependencies import db
    import os
    import razorpay
    import paddle_sdk
    import uuid
    tier = body.get("tier")
    cycle = body.get("cycle", "monthly")
    org_id = body.get("org_id")
    if tier not in ("pro", "team"):
        return {"error": "invalid_tier", "available": ["pro", "team"]}
    country = (user.get("profile", {}) or {}).get("billing_country") or (user.get("profile", {}) or {}).get("country", "IN")
    provider = "razorpay" if country and country.upper() == "IN" else "paddle"
    checkout_url = None
    session_id = None
    order_id = None
    if provider == "razorpay":
        key_id = os.getenv("RAZORPAY_KEY_ID")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET")
        client = razorpay.Client(auth=(key_id, key_secret))
        amount = 10000 if tier == "pro" else 25000  # Example: INR in paise
        data = {
            "amount": amount,
            "currency": "INR",
            "receipt": str(uuid.uuid4()),
            "payment_capture": 1,
            "notes": {"user_id": user["uid"], "tier": tier, "cycle": cycle}
        }
        order = client.order.create(data)
        order_id = order["id"]
        session_id = order_id
        checkout_url = f"https://checkout.razorpay.com/v1/checkout.js?order_id={order_id}"  # Frontend should use Razorpay widget
    elif provider == "paddle":
        vendor_id = os.getenv("PADDLE_VENDOR_ID")
        api_key = os.getenv("PADDLE_API_KEY")
        paddle = paddle_sdk.Paddle(vendor_id=vendor_id, api_key=api_key)
        product_id = 12345 if tier == "pro" else 67890  # Example product IDs
        resp = paddle.generate_pay_link(product_id=product_id, quantity=1, custom_message="Subscription", customer_email=user.get("email"))
        checkout_url = resp["url"]
        session_id = resp["checkout_id"]
    await db.pending_checkout.insert_one({
        "user_id": user["uid"],
        "org_id": org_id,
        "provider": provider,
        "session_id": session_id,
        "order_id": order_id,
        "type": "subscription",
        "tier": tier,
        "cycle": cycle,
        "created_at": __import__('datetime').datetime.utcnow()
    })
    return {"checkout_url": checkout_url, "provider": provider}
# --- Credit Purchase Endpoint ---
from fastapi import Body


@router.post("/credits/purchase", status_code=201)
async def purchase_credits(
    body: dict = Body(...),
    user: dict = Depends(get_current_user)
):
    """Initiate a credit pack purchase. Selects Razorpay (IN), Paddle (non-IN), PayPal as backup. Creates pending_checkout doc. Returns checkout_url and provider."""
    from dependencies import db
    import os
    import razorpay
    import paddle_sdk
    import uuid
    pack = body.get("pack")
    packs = {
        "small": {"price": 5, "credits": 200},
        "medium": {"price": 12, "credits": 500},
        "large": {"price": 25, "credits": 1200}
    }
    if pack not in packs:
        return {"error": "invalid_pack", "available": list(packs.keys())}
    country = (user.get("profile", {}) or {}).get("billing_country") or (user.get("profile", {}) or {}).get("country", "IN")
    provider = "razorpay" if country and country.upper() == "IN" else "paddle"
    checkout_url = None
    session_id = None
    order_id = None
    if provider == "razorpay":
        key_id = os.getenv("RAZORPAY_KEY_ID")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET")
        client = razorpay.Client(auth=(key_id, key_secret))
        amount = int(packs[pack]["price"] * 100)  # INR in paise
        data = {
            "amount": amount,
            "currency": "INR",
            "receipt": str(uuid.uuid4()),
            "payment_capture": 1,
            "notes": {"user_id": user["uid"], "pack": pack}
        }
        order = client.order.create(data)
        order_id = order["id"]
        session_id = order_id
        checkout_url = f"https://checkout.razorpay.com/v1/checkout.js?order_id={order_id}"  # Frontend should use Razorpay widget
    elif provider == "paddle":
        vendor_id = os.getenv("PADDLE_VENDOR_ID")
        api_key = os.getenv("PADDLE_API_KEY")
        paddle = paddle_sdk.Paddle(vendor_id=vendor_id, api_key=api_key)
        product_id = 11111 if pack == "small" else 22222 if pack == "medium" else 33333
        resp = paddle.generate_pay_link(product_id=product_id, quantity=1, custom_message="Credit Pack", customer_email=user.get("email"))
        checkout_url = resp["url"]
        session_id = resp["checkout_id"]
    await db.pending_checkout.insert_one({
        "user_id": user["uid"],
        "provider": provider,
        "session_id": session_id,
        "order_id": order_id,
        "type": "credits",
        "pack": pack,
        "created_at": __import__('datetime').datetime.utcnow()
    })
    return {"checkout_url": checkout_url, "provider": provider}
# --- Credit Balance Endpoint ---
@router.get("/credits/balance")
async def get_credits_balance(user: dict = Depends(get_current_user)):
    """Returns user's credit balance, monthly grant, and total available."""
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    sub = user.get("subscription", {}) or {}
    credits = user.get("credits", {}) or {}
    plan = sub.get("tier", "free")
    tier_cfg = config["tiers"].get(plan, config["tiers"]["free"])
    balance = credits.get("balance", 0)
    monthly_grant = tier_cfg.get("monthly_credits", 0)
    total_available = balance  # If you want to add other sources, update here
    return {
        "balance": balance,
        "subscription_credits": monthly_grant,
        "total_available": total_available
    }

from fastapi import APIRouter, Response, Depends, HTTPException, Request
import json
import os
from dependencies import get_current_user

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "billing.config.json")


@router.get("/tiers")
def get_billing_tiers(request: Request):
    with open(CONFIG_PATH, "rb") as f:
        raw = f.read()
        etag = hashlib.md5(raw).hexdigest()
        config = json.loads(raw)
    # ETag support
    if_none_match = request.headers.get("if-none-match")
    if if_none_match == etag:
        return Response(status_code=304)
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=300"
    }
    tiers = []
    for k, v in config["tiers"].items():
        tier = {"id": k}
        tier.update({key: v[key] for key in v})
        tiers.append(tier)
    camel = camelize({"tiers": tiers})
    return Response(
        content=json.dumps(camel),
        media_type="application/json",
        headers=headers,
        status_code=200
    )


# --- Entitlements Endpoint ---
@router.get("/me/entitlements")
async def get_me_entitlements(user: dict = Depends(get_current_user)):
    """Returns the current user's plan, credits, caps, burst, and allowed routes. Cached for 60s, invalidated on webhook."""
    subject_id = user.get("org_id") or user.get("uid") or user.get("_id")
    cache_key = f"entitlements:{subject_id}"
    cached = get_cache(cache_key)
    if cached:
        return camelize(cached)
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    sub = user.get("subscription", {}) or {}
    credits = user.get("credits", {}) or {}
    plan = sub.get("tier", "free")
    tier_cfg = config["tiers"].get(plan, config["tiers"]["free"])
    # Compute routes_allowed
    routes_allowed = tier_cfg.get("routes", [])
    # Compose response
    resp = {
        "plan": plan,
        "balance": credits.get("balance", 0),
        "monthly_credits": tier_cfg.get("monthly_credits", 0),
        "starter_grant_used": credits.get("starter_grant_used", False),
        "daily_cap": tier_cfg.get("daily_cap"),
        "burst": tier_cfg.get("burst"),
        "routes_allowed": routes_allowed,
        "subject": {"type": "org" if user.get("org_id") else "user", "id": subject_id}
    }
    set_cache(cache_key, resp, ttl=60)
    return camelize(resp)
