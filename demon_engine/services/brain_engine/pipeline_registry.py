

# =============================
# demon_engine/services/brain_engine/pipeline_registry.py
# =============================
from __future__ import annotations
from typing import Dict, Tuple, Optional

__all__ = ["PipelineRegistry"]

Key = Tuple[str, str, str]  # (intent, mode, client)

class PipelineRegistry:
    """Lightweight mapping of (intent, mode, client) → pipeline name.
    Keeps legacy behavior while Demon Engine plans prompts.
    """

    def __init__(self, matrix: Optional[Dict[Key, str]] = None, engine_version: str = "demon-2.1"):
        # Provide a minimal default matrix with sensible fallbacks
        self._matrix: Dict[Key, str] = matrix or {
            # VS Code — Editor (Architect → Pro)
            ("editor", "pro", "vscode"): "CodeForge.Architect.v1",  # pro_only: true, timeout_ms: 20000, max_passes: 2, cost_weight: medium, fallback_to: "editor/free/vscode", flags: ["enable_explain", "enforce_contract"]
            # VS Code — Editor (Free fallback)
            ("editor", "free", "vscode"): "CodeForge.Editor.Basic.v1",  # pro_only: false, timeout_ms: 12000, max_passes: 1, cost_weight: low, flags: ["enforce_contract"]
            # Web — Chat (Oracle Ideas → Free)
            ("chat", "free", "web"): "Oracle.Ideas.Basic.v1",  # pro_only: false, timeout_ms: 12000, max_passes: 1, cost_weight: low, flags: ["enable_explain", "enforce_contract"]
            # Web — Chat (Oracle Ideas → Pro)
            ("chat", "pro", "web"): "Oracle.Ideas.Pro.v1",  # pro_only: true, timeout_ms: 20000, max_passes: 2, cost_weight: medium, flags: ["enable_explain", "enforce_contract"]
            # Cursor — Agent (Pro only)
            ("agent", "pro", "cursor"): "Agent.DemonEngine.v1",  # pro_only: true, timeout_ms: 25000, max_passes: 2, cost_weight: high, flags: ["enable_explain", "enforce_contract"]
            # Optional: Chrome chat
            ("chat", "free", "chrome"): "Conversational.Basic.v1",
            ("chat", "pro", "chrome"): "Conversational.LangGraph.v1",
            # Legacy and fallback entries
            ("prompt.upgrade", "free", "web"): "UpgradeLite",
            ("prompt.upgrade", "pro",  "web"): "UpgradePro",
            ("oracle.idea",    "free", "web"): "Oracle.Ideas.Basic",
            ("oracle.idea",    "pro",  "web"): "Oracle.Ideas.Pro",
            ("oracle.idea",    "free", "vscode"): "Oracle.Ideas.Basic",
            ("oracle.idea",    "pro",  "vscode"): "Oracle.Ideas.Pro",
            ("architect.plan", "free", "web"): "ArchLite",
            ("architect.plan", "pro",  "web"): "CodeForge.Architect",
            ("architect.plan", "free", "vscode"): "ArchLite",
            ("architect.plan", "pro",  "vscode"): "CodeForge.Architect",
            ("prompt.upgrade", "free", "*"):   "UpgradeLite",
            ("prompt.upgrade", "pro",  "*"):   "UpgradePro",
            ("*",              "free", "*"):   "DefaultFree",
            ("*",              "pro",  "*"):   "DefaultPro",
        }
        self._engine_version = engine_version
        self._killswitch: set[Key] = set()
        self._pro_only: set[Key] = set()

    # ---- admin ops ----
    def register(self, intent: str, mode: str, client: str, pipeline_name: str) -> None:
        self._matrix[(intent, mode, client)] = pipeline_name

    def set_killswitch(self, key: Key, value: bool = True) -> None:
        if value: self._killswitch.add(key)
        else: self._killswitch.discard(key)

    def is_killswitch(self, key: Key) -> bool:
        return key in self._killswitch

    def set_pro_only(self, key: Key, value: bool = True) -> None:
        if value: self._pro_only.add(key)
        else: self._pro_only.discard(key)

    def is_pro_only(self, key: Key) -> bool:
        return key in self._pro_only

    # ---- lookup ----
    def lookup(self, intent: str, mode: str, client: str) -> Tuple[str, Key]:
        """Return (pipeline_name, matched_key). Raises KeyError if nothing found."""
        # Exact
        key = (intent, mode, client)
        if key in self._matrix:
            return self._matrix[key], key
        # Wildcards by client
        key2 = (intent, mode, "*")
        if key2 in self._matrix:
            return self._matrix[key2], key2
        # Intent wildcard by mode
        key3 = ("*", mode, client)
        if key3 in self._matrix:
            return self._matrix[key3], key3
        # Global tier default
        key4 = ("*", mode, "*")
        if key4 in self._matrix:
            return self._matrix[key4], key4
        raise KeyError(f"No pipeline for {intent}/{mode}/{client}")

    def get_engine_version(self) -> str:
        return self._engine_version
