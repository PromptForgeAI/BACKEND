

# =============================
# demon_engine/services/brain_engine/errors.py
# =============================
from __future__ import annotations

__all__ = [
    "DemonEngineError",
    "ProRequiredError",
    "KillSwitchError",
    "PipelineNotFound",
    "RateLimitExceeded",
    "InvalidRequest",
]

class DemonEngineError(Exception):
    """Base class for Demon Engine domain errors."""

class ProRequiredError(DemonEngineError):
    pass

class KillSwitchError(DemonEngineError):
    pass

class PipelineNotFound(DemonEngineError):
    pass

class RateLimitExceeded(DemonEngineError):
    pass

class InvalidRequest(DemonEngineError):
    pass
