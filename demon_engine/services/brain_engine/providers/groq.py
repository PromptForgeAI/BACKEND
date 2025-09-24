import httpx, os, time, asyncio, random
from .base import ProviderBase, LLMResult

class GroqProvider(ProviderBase):
    URL = "https://api.groq.com/openai/v1/chat/completions"
    def __init__(self, api_key=None, timeout=60):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.timeout = timeout

    async def complete(self, messages, model, **kw) -> LLMResult:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": kw.get("max_tokens", 800),
            "temperature": kw.get("temperature", 0.2),
            "stream": kw.get("stream", False),
        }
        print("[GROQ DEBUG] Payload to Groq API:", payload)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(4):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as c:
                    r = await c.post(self.URL, headers=headers, json=payload)
                r.raise_for_status()
                data = r.json()
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return LLMResult(text=text, model=model,
                                 tokens_in=usage.get("prompt_tokens"),
                                 tokens_out=usage.get("completion_tokens"))
            except (httpx.TimeoutException, httpx.TransportError) as e:
                await asyncio.sleep(min(2**attempt, 8) + random.random()*0.2)
                continue
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 500, 502, 503, 504):
                    await asyncio.sleep(min(2**attempt, 8) + random.random()*0.2)
                    continue
                raise
        raise RuntimeError("Provider unavailable after retries")
