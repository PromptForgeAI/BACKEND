# =============================
# demon_engine/services/brain_engine/analytics.py
# =============================
from __future__ import annotations
import json, os, sys, time, threading
from datetime import datetime
from typing import Any, Dict, Optional

__all__ = ["log_event", "log_before_after", "AnalyticsSink"]

class AnalyticsSink:
    """Thread-safe JSONL sink (stdout or file). Non-blocking best-effort.
    Replace with your real backend (Kafka/Redis/ClickHouse) when ready.
    """
    def __init__(self, path: Optional[str] = None):
        self.path = path or os.environ.get("DEMON_ANALYTICS_PATH")
        self._lock = threading.Lock()
        self._fh = None
        if self.path:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self._fh = open(self.path, "a", encoding="utf-8")

    def write(self, record: Dict[str, Any]) -> None:
        record["ts"] = record.get("ts") or datetime.utcnow().isoformat() + "Z"
        line = json.dumps(record, ensure_ascii=False)
        try:
            if self._fh:
                with self._lock:
                    self._fh.write(line + "\n"); self._fh.flush()
            else:
                # stdout fallback
                sys.stdout.write(line + "\n"); sys.stdout.flush()
        except Exception:
            # Never raise from analytics
            pass

# Global sink
_sink = AnalyticsSink()

def log_event(name: str, data: Optional[Dict[str, Any]] = None) -> None:
    rec = {
        "type": "event",
        "name": name,
        "data": data or {},
    }
    _sink.write(rec)


def log_before_after(name: str, before: Any, after: Any, consent: bool = False, extra: Optional[Dict[str, Any]] = None) -> None:
    if not consent:
        return
    rec = {
        "type": "before_after",
        "name": name,
        "before": before,
        "after": after,
        "extra": extra or {},
    }
    _sink.write(rec)
