from typing import Any, Optional

class LLMResult:
    def __init__(self, text: str, model: str, tokens_in: Optional[int]=None, tokens_out: Optional[int]=None):
        self.text = text
        self.model = model
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out

class ProviderBase:
    async def complete(self, messages, model, **kw) -> LLMResult:
        raise NotImplementedError()
