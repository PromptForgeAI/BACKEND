

# =============================
# demon_engine/services/brain_engine/feature_flags.py
# =============================
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple, Deque, Optional

__all__ = ["FeatureFlags"]

Key = Tuple[str, str, str]  # (intent, mode, client)

@dataclass
class RateWindow:
    limit: int
    seconds: int

class FeatureFlags:
    """In-memory feature flags & rate-limits.
    Replace with Redis/DB-backed storage in production.
    """
    def __init__(self):
        self._global_pro_disabled: bool = False
        self._telemetry_enabled: bool = True
        self._killswitch: set[Key] = set()
        self._pro_only: set[Key] = set()
        # rate window per (user_id, key or wildcard)
        self._rate_limits: Dict[Tuple[str, Key], Deque[datetime]] = {}
        self._default_rate_free = RateWindow(limit=30, seconds=60)   # 30/min
        self._default_rate_pro = RateWindow(limit=120, seconds=60)   # 120/min

    # ---- telemetry ----
    def set_telemetry(self, enabled: bool) -> None:
        self._telemetry_enabled = bool(enabled)

    def is_telemetry_enabled(self) -> bool:
        return self._telemetry_enabled

    # ---- pro disable ----
    def set_global_pro_disabled(self, disabled: bool) -> None:
        self._global_pro_disabled = bool(disabled)

    def is_global_pro_disabled(self) -> bool:
        return self._global_pro_disabled

    # ---- killswitch ----
    def enable_killswitch(self, key: Key) -> None:
        self._killswitch.add(key)

    def disable_killswitch(self, key: Key) -> None:
        self._killswitch.discard(key)

    def is_killswitch(self, key: Key) -> bool:
        return key in self._killswitch or (key[0], "*", "*") in self._killswitch or ("*", "*", "*") in self._killswitch

    # ---- pro-only gating ----
    def set_pro_only(self, key: Key, value: bool = True) -> None:
        if value:
            self._pro_only.add(key)
        else:
            self._pro_only.discard(key)

    def is_pro_only(self, key: Key) -> bool:
        return key in self._pro_only

    # ---- rate limits ----
    def check_rate_limit(self, user_id: str, key: Key, mode: str) -> bool:
        """Return True if allowed; False if over limit.
        Sliding window per (user_id, key). Uses defaults per tier.
        """
        rw = self._default_rate_pro if mode == "pro" else self._default_rate_free
        now = datetime.utcnow()
        dq = self._rate_limits.setdefault((user_id, key), deque())
        # prune old
        cutoff = now - timedelta(seconds=rw.seconds)
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= rw.limit:
            return False
        dq.append(now)
        return True
