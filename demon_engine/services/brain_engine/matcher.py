
# ==========================
# services/brain_engine/matcher.py
# ==========================
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from demon_engine.services.brain_engine.compendium import Compendium, Technique
from demon_engine.services.brain_engine.pfcl import PFCLCommand, PFCLParser

@dataclass
class MatchResult:
    id: str
    score: float
    why: Dict[str, Any] = field(default_factory=dict)

class TechniqueMatcher:
    def __init__(self, compendium: Compendium):
        self.comp = compendium
        sc = (self.comp.data.get("scoring") or {})
        self.sigw = sc.get("signals", {})
        self.sel = sc.get("selection", {"max_techniques": 6, "prefer_complements": True})

    def select(self, text: str, cmds: List[PFCLCommand], surface: str, tier: str, budget: float | None = None) -> Dict[str, Any]:
        budget_max = self.comp.budget(tier) if budget is None else budget
        signals = self._signals(text)
        pfcl_names = [c.name for c in cmds]
        scored: Dict[str, MatchResult] = {}

        # score by PFCL + rules + compatibility
        for tid, tech in self.comp.techniques.items():
            s = 0.0; why = {"hits": []}
            # PFCL alias
            pfcl_boost = float(self.sigw.get("pfcl_alias", 2.0))
            mapped = set()
            for cmd in pfcl_names:
                mapped |= set(self.comp.pfcl_map.get(cmd, []))
            if tid in mapped:
                s += pfcl_boost; why["hits"].append({"pfcl": True})
            # Technique aliases direct
            for a in (tech.get("aliases") or []):
                if a in pfcl_names:
                    s += pfcl_boost; why["hits"].append({"alias": a})
            # keyword rules
            kw_w = float(self.sigw.get("keyword_hit", 1.0))
            for rule in (tech.get("matcher_rules") or {}).get("signals", []):
                t = rule.get("type")
                if t == "keyword":
                    hits = [k for k in rule.get("any", []) if k.lower() in signals["keywords"]]
                    if hits: s += kw_w; why["hits"].append({"keywords": hits})
                elif t == "pfcl":
                    inter = list(set(rule.get("any", [])) & set(pfcl_names))
                    if inter: s += pfcl_boost; why["hits"].append({"pfcl_rule": inter})
                elif t == "ambiguity":
                    thr = float(rule.get("gte", 0.6))
                    amb_w = float((self.sigw.get("ambiguity_boost") or {}).get("weight", 0.8))
                    if signals["ambiguity"] >= thr: s += amb_w; why["hits"].append({"ambiguity": signals["ambiguity"]})
            # compatibility bonuses
            if surface in (tech.get("surfaces") or [surface]): s += float(self.sigw.get("surface_match", 0.2))
            if tier in (tech.get("tiers") or [tier]): s += float(self.sigw.get("tier_match", 0.2))
            # length penalty
            lp = self.sigw.get("length_penalty", {})
            if signals["len"] < int(lp.get("min_chars", 50)): s += float(lp.get("penalty", -0.4))
            if s != 0: scored[tid] = MatchResult(id=tid, score=s, why=why)

        # choose under budget with conflicts + complements
        ordered = sorted(scored.values(), key=lambda r: r.score, reverse=True)
        chosen: List[str] = []; used = 0.0
        maxn = int(self.sel.get("max_techniques", 6))
        for r in ordered:
            if len(chosen) >= maxn: break
            t = self.comp.techniques[r.id]
            if not self._compat(t, surface, tier): continue
            if self._conflicts(t, chosen): continue
            if used + float((t.get("cost_estimate") or {}).get("tokens", 1.0)) > budget_max: continue
            chosen.append(t.id); used += float((t.get("cost_estimate") or {}).get("tokens", 1.0))
        # complement pass
        if self.sel.get("prefer_complements", True) and chosen:
            base = set(chosen)
            for cid in list(chosen):
                for tid in (self.comp.techniques[cid].get("complements") or []):
                    if tid in base or tid not in self.comp.techniques: continue
                    t = self.comp.techniques[tid]
                    if not self._compat(t, surface, tier): continue
                    if self._conflicts(t, chosen): continue
                    est = float((t.get("cost_estimate") or {}).get("tokens", 1.0))
                    if used + est > budget_max: continue
                    chosen.append(tid); used += est; base.add(tid)
                    if len(chosen) >= maxn: break

        # warnings for unknown PFCL
        warnings = [f"ignored command: {c}" for c in pfcl_names if c not in self.comp.pfcl_map]

        chosen_expanded = [{
            "id": tid,
            "score": scored.get(tid).score if tid in scored else 0.0,
            "fragments": self.comp.techniques[tid].get("template_fragments") or {},
            "phase": self.comp.techniques[tid].get("phase") or []
        } for tid in chosen]

        return {
            "chosen": chosen_expanded,
            "budget": {"max": budget_max, "used": round(used, 3)},
            "warnings": warnings,
            "telemetry": {"signals": signals, "scores": {k: v.score for k, v in scored.items()}},
        }

    def _signals(self, text: str):
        tl = text.lower();
        kw = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]{2,}", tl))
        vagues = {"maybe","somehow","something","stuff","thing","probably","kinda","sort","unsure"}
        q = tl.count("?"); v = sum(1 for w in vagues if w in tl)
        L = len(text.strip())
        amb = 0.0 if L <= 1 else min(1.0, (q * 0.25 + v * 0.15 + (1 if L < 80 else 0) * 0.2))
        return {"keywords": kw, "ambiguity": amb, "len": L}

    def _compat(self, t: Technique, surface: str, tier: str) -> bool:
        s_ok = not t.get("surfaces") or surface in t.get("surfaces")
        t_ok = not t.get("tiers") or tier in t.get("tiers")
        return s_ok and t_ok

    def _conflicts(self, t: Technique, chosen: List[str]) -> bool:
        conf = set(t.get("conflicts_with") or [])
        return any(c in conf for c in chosen)

