import os

GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
GROQ_API_KEY  = (os.getenv("GROQ_API_KEY") or "").strip()
GROQ_MODEL    = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

class ProviderAuthError(Exception):
    def __init__(self, provider: str, detail: str = ""):
        self.provider = provider
        super().__init__(f"{provider} auth failed: {detail}")

def validate_groq():
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing. Set it in environment.")


# Razorpay and Paddle integration keys
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
PADDLE_VENDOR_ID = os.getenv("PADDLE_VENDOR_ID", "")
PADDLE_API_KEY = os.getenv("PADDLE_API_KEY", "")
