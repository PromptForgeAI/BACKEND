

# ==========================
# services/brain_engine/contracts.py
# ==========================
import json
from typing import Any, Dict, List

class ContractError(Exception):
    pass

class Contracts:
    def __init__(self):
        pass

    def enforce(self, surface: str, mode: str, raw_text: str) -> Dict[str, Any]:
        """Minimal contract enforcement.
        - If output claims JSON, attempt json.loads; ensure object with common keys.
        - Otherwise, wrap in sections for web, or lines for vscode.
        Replace later with full JSON Schema once jsonschema is added.
        """
        if surface in ("vscode",):
            return {"edits": [], "text": raw_text}
        # web/chrome default contract
        try:
            obj = json.loads(raw_text)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        return {"sections": [{"title": "Response", "body": raw_text.strip()}]}

