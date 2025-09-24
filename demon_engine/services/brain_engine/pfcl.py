
# PR: Demon Engine Integration Patch — PFCL • Matcher • Renderer • API
# -------------------------------------------------------------------
# This patch introduces:
# 1) PFCL parser (slash-command DSL)
# 2) Compendium loader for brain.json v2.1
# 3) Technique matcher that selects techniques under budget
# 4) Lightweight fragment renderer (Jinja2 if available; fallback to string.Template)
# 5) Contract enforcement helper (minimal JSON schema checks with fallback)
# 6) Engine wiring to replace static technique_packs with compendium-driven plan
# 7) FastAPI endpoint /demon/route
# 8) Unit-test stubs
#
# Drop the following files into your repo under the noted paths.
# Adjust imports if your package root differs.

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

@dataclass
class PFCLCommand:
    name: str
    args: Dict[str, Any] = field(default_factory=dict)

class PFCLParser:
    _cmd_re = re.compile(r"/(\w+)(?=\s|$)")
    _tok_re = re.compile(
        r"\s+"                                 # whitespace
        r"|(?P<arraykey>\w+\[\w+\])\s*=\s*(?P<aval>\S+)"  # weight[context]=1.2
        r"|(?P<key>\w+)\s*=\s*(?P<val>\S+)"                # key=value
        r"|(?P<flag>\w+)"                                   # bare flag -> True
    )

    def parse(self, text: str) -> Tuple[List[PFCLCommand], str]:
        commands: List[PFCLCommand] = []
        consumed: List[Tuple[int, int]] = []
        for m in self._cmd_re.finditer(text):
            name = f"/{m.group(1)}"
            args: Dict[str, Any] = {}
            pos = m.end()
            nxt = self._cmd_re.search(text, pos)
            end = nxt.start() if nxt else len(text)
            seg = text[pos:end]
            for t in self._tok_re.finditer(seg):
                if t.group(0).strip() == "":
                    continue
                if t.group("arraykey"):
                    k = t.group("arraykey")
                    outer, inner = k.split("["); inner = inner.rstrip("]")
                    args.setdefault(outer, {})
                    args[outer][inner] = self._coerce(t.group("aval"))
                elif t.group("key"):
                    args[t.group("key")] = self._coerce(t.group("val"))
                elif t.group("flag"):
                    args[t.group("flag")] = True
            commands.append(PFCLCommand(name=name, args=args))
            consumed.append((m.start(), end))
        # remove consumed ranges
        remainder = self._strip(text, consumed)
        return commands, remainder.strip()

    def _coerce(self, s: str):
        if s.lower() in ("true", "false"): return s.lower() == "true"
        if re.fullmatch(r"[+-]?\d+", s):
            try: return int(s)
            except: pass
        if re.fullmatch(r"[+-]?(?:\d*\.\d+|\d+\.\d*)(?:[eE][+-]?\d+)?", s):
            try: return float(s)
            except: pass
        if (len(s) >= 2) and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
            return s[1:-1]
        return s

    def _strip(self, text: str, spans: List[Tuple[int, int]]):
        if not spans: return text
        spans = sorted(spans)
        out = []; cur = 0
        for s, e in spans:
            out.append(text[cur:s]); cur = e
        out.append(text[cur:])
        return "".join(out)

