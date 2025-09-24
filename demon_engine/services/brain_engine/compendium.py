
# ==========================
# services/brain_engine/compendium.py
# ==========================
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

@dataclass
class Technique:
    id: str
    raw: Dict[str, Any]
    def get(self, k: str, d=None): return self.raw.get(k, d)

class Compendium:
    def __init__(self, data: Union[Dict[str, Any], List[Dict[str, Any]]]):
        # Handle both dictionary format (brain.json) and array format (compendium.json)
        if isinstance(data, list):
            # Convert array format to dictionary format
            self.data = {
                "techniques": data,
                "defaults": {
                    "budget_tokens": {"free": 1.0, "pro": 2.0},
                    "surfaces": ["web", "chrome", "vscode", "cursor", "agent"],
                    "tiers": ["free", "pro"]
                },
                "pfcl": {"commands": {}}
            }
        else:
            self.data = data
            
        self.techniques: Dict[str, Technique] = {t["id"]: Technique(t["id"], t) for t in self.data.get("techniques", [])}
        self.defaults = self.data.get("defaults", {})
        # PFCL map
        self.pfcl_map: Dict[str, List[str]] = {}
        for cmd, spec in (self.data.get("pfcl", {}).get("commands", {})).items():
            self.pfcl_map[cmd] = list(spec.get("maps_to") or [])
        for t in self.techniques.values():
            for a in (t.get("aliases") or []):
                self.pfcl_map.setdefault(a, []).append(t.id)

    @classmethod
    def from_path(cls, path: str | Path) -> "Compendium":
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(data)

    def budget(self, tier: str) -> float:
        bt = (self.defaults.get("budget_tokens") or {})
        return float(bt.get(tier, bt.get("free", 1.0)))

