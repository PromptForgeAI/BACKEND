# Debug log utility
import os
def debug_log(msg):
    if os.getenv("DEBUG_TRIGGER", "false").lower() == "true":
        print(msg)
# --- Payment Webhook Processing, Signature Verification, Credit Granting, and Entitlement Enforcement ---
import hashlib, hmac, json, datetime
from fastapi import HTTPException, Request, Depends
from dependencies import db

async def verify_signature(provider: str, request: Request) -> bool:
    debug_log(f"[verify_signature] Provider: {provider}")
    import os
    if provider == "razorpay":
        # Razorpay signature verification
        body = await request.body()
        signature = request.headers.get("X-Razorpay-Signature")
        secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
        if not signature or not secret:
            return False
        import hmac
        import hashlib
        expected = hmac.new(bytes(secret, 'utf-8'), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    elif provider == "paddle":
        # Paddle signature verification
        body = await request.json()
        signature = body.get("p_signature")
        if not signature:
            return False
    import paddle_sdk
    vendor_id = os.getenv("PADDLE_VENDOR_ID")
    api_key = os.getenv("PADDLE_API_KEY")
    paddle = paddle_sdk.Paddle(vendor_id=vendor_id, api_key=api_key)
    return paddle.verify_webhook(body)
    # Add other providers as needed
    return True

from utils.cache import invalidate_cache
async def process_payment_event(provider: str, event: dict):
    debug_log(f"[process_payment_event] Provider: {provider}, Event: {event}")
    """Process payment/subscription event and upsert user/org in MongoDB. Invalidate entitlements cache."""
    # Extract event_id for idempotency
    event_id = event.get("id") or event.get("event_id") or event.get("event")
    if not event_id:
        return False
    # Check idempotency
    exists = await db.billing_events.find_one({"event_id": event_id})
    if exists:
        return False
    await db.billing_events.insert_one({"event_id": event_id, "provider": provider, "raw": event, "created_at": datetime.datetime.utcnow()})
    # Map event to user/org and update subscription/credits
    subject_id = event.get("user_id") or event.get("customer_id") or event.get("org_id")
    if not subject_id:
        return False
    # Fetch user/org
    doc = await db.users.find_one({"_id": subject_id})
    is_org = False
    if not doc:
        doc = await db.orgs.find_one({"_id": subject_id})
        is_org = True if doc else False
    if not doc:
        return False
    # Determine plan and grant amount
    plan = event.get("plan") or (doc.get("subscription", {}) or {}).get("tier", "free")
    # Load config
    with open("billing.config.json", "r") as f:
        config = json.load(f)
    tier_cfg = config["tiers"].get(plan, config["tiers"]["free"])
    monthly_grant = tier_cfg.get("monthly_credits", 0)
    rollover = tier_cfg.get("rollover", False)
    # Event mapping
    event_type = event.get("type")
    now = datetime.datetime.utcnow()
    credits = doc.get("credits", {}) or {}
    balance = credits.get("balance", 0)
    used_this_cycle = credits.get("used_this_cycle", 0)
    update = {}
    if event_type in ("payment_succeeded", "invoice.paid", "subscription.paid", "subscription.created", "subscription.updated"):
        # Grant credits (rollover logic)
        if rollover:
            carry = min(balance, monthly_grant)
            new_balance = min(balance + monthly_grant + carry, 2 * monthly_grant)
        else:
            new_balance = max(balance, monthly_grant)
        credits.update({"balance": new_balance, "monthly_grant": monthly_grant, "last_grant_at": now})
        update = {"credits": credits, "subscription.tier": plan, "subscription.status": "active", "updated_at": now, "usage.month_count": 0}
    elif event_type == "subscription.canceled":
        update = {"subscription.status": "canceled", "updated_at": now}
    elif event_type in ("payment.failed", "past_due"):
        grace_days = 7
        update = {"subscription.status": "past_due", "subscription.grace_until": (now + datetime.timedelta(days=grace_days)), "updated_at": now}
    # Upsert
    if is_org:
        await db.orgs.update_one({"_id": subject_id}, {"$set": update}, upsert=True)
    else:
        await db.users.update_one({"_id": subject_id}, {"$set": update}, upsert=True)
    # Invalidate entitlements cache
    cache_key = f"entitlements:{subject_id}"
    invalidate_cache(cache_key)
    return True


from fastapi import Request
from dependencies import db
import datetime

def entitlement_guard(route_key: str, cost_table: dict, explain: bool = False):
    async def dependency(request: Request, user: dict = Depends(lambda: None)):
        # Load config
        with open("billing.config.json", "r") as f:
            config = json.load(f)
        sub = user.get("subscription", {}) or {}
        credits = user.get("credits", {}) or {}
        plan = sub.get("tier", "free")
        tier_cfg = config["tiers"].get(plan, config["tiers"]["free"])
        cost = cost_table.get(route_key, 0) + (cost_table.get("_explain_addon", 0) if explain else 0)
        subject_id = user.get("org_id") or user.get("uid") or user.get("_id")
        # Agent gating
        if route_key.startswith("agent.") and plan not in ("pro", "team", "enterprise"):
            raise HTTPException(status_code=402, detail={"error": "pro_required", "upgrade_url": "/pricing"})
        # Daily cap
        if tier_cfg.get("daily_cap") and credits.get("today_count", 0) >= tier_cfg["daily_cap"]:
            reset_at = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            raise HTTPException(status_code=402, detail={"error": "hit_daily_cap", "reset_at": reset_at})
        # Burst limit (stub: always allow, replace with Redis in prod)
        # TODO: Implement Redis burst limit here
        # Dunning: allow if past_due and grace_until > now, else demote to free
        if sub.get("status") == "past_due":
            grace_until = sub.get("grace_until")
            now = datetime.datetime.utcnow()
            if grace_until:
                if now < grace_until:
                    # Still in grace, allow
                    pass
                else:
                    # Grace expired: demote to free, keep balance
                    await db.users.update_one(
                        {"_id": subject_id},
                        {"$set": {"subscription.tier": "free", "subscription.status": "canceled", "updated_at": now}},
                        upsert=True
                    )
                    raise HTTPException(status_code=402, detail={"error": "billing_required", "upgrade_url": "/pricing"})
        # Atomic credit debit
        filter = {"_id": subject_id, "credits.balance": {"$gte": cost}}
        update = {
            "$inc": {
                "credits.balance": -cost,
                "credits.total_spent": cost,
                "usage.today_count": 1,
                "usage.month_count": 1
            },
            "$set": {"updated_at": datetime.datetime.utcnow()}
        }
        doc = await db.users.find_one_and_update(filter, update, return_document=True)
        if not doc:
            raise HTTPException(status_code=402, detail={"error": "insufficient_credits", "required": cost, "available": credits.get("balance", 0), "upgrade_url": "/pricing"})
        return True
    return dependency
import requests
from fastapi import Request

def get_country_from_ip(request: Request) -> str:
    """Detect country from IP address using a public geolocation API."""
    ip = request.client.host
    try:
        # Use a free geolocation API (can be swapped for a paid one in prod)
        resp = requests.get(f"https://ipapi.co/{ip}/country/", timeout=2)
        if resp.status_code == 200:
            return resp.text.strip()
    except Exception:
        pass
    return "US"  # Default fallback

# Payment provider selection logic
def select_payment_provider(request: Request, user_profile: dict = None) -> str:
    """Return 'razorpay' for India, 'paddle' for others. Optionally use user profile country if available."""
    country = None
    # Check for country in user_profile['country'] or user_profile['profile']['country']
    if user_profile:
        if user_profile.get("country"):
            country = user_profile["country"].upper()
        elif user_profile.get("profile") and user_profile["profile"].get("country"):
            country = user_profile["profile"]["country"].upper()
    if not country:
        country = get_country_from_ip(request)
    if country == "IN":
        return "razorpay"
    return "paddle"
