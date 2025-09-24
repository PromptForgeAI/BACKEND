from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum

class ModeEnum(str, Enum):
    free = "free"
    pro = "pro"

class ClientEnum(str, Enum):
    chrome = "chrome"
    vscode = "vscode"
    cursor = "cursor"
    web = "web"
    unknown = "unknown"

class IntentEnum(str, Enum):
    chat = "chat"
    editor = "editor"
    agent = "agent"
    unknown = "unknown"

class UpgradeRequest(BaseModel):
    text: str
    mode: ModeEnum = ModeEnum.free
    client: ClientEnum = ClientEnum.unknown
    intent: IntentEnum = IntentEnum.unknown
    meta: Optional[Dict[str, Any]] = None
    explain: Optional[bool] = False

class UpgradeResponse(BaseModel):
    upgraded: str
    matched_pipeline: str
    engine_version: str
    plan: Optional[List[str]] = None  # Bullet list of steps
    diffs: Optional[str] = None
    fidelity_score: Optional[float] = None
    matched_entries: Optional[List[str]] = None
    message: Optional[str] = None
