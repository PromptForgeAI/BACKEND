import os

# Toggle this to True for verbose debug output
DEBUG_BRAIN_ENGINE = os.getenv("DEBUG_BRAIN_ENGINE", "0") in ("1", "true", "True")

# ==========================
# services/brain_engine/engine_v2.py
# ==========================

from demon_engine.services.brain_engine.llm_client import LLMClient
from typing import Any, Dict, Optional, Tuple
from .feature_flags import FeatureFlags
from .errors import ProRequiredError, KillSwitchError, PipelineNotFound
from .pipeline_registry import PipelineRegistry
from demon_engine.services.brain_engine.pfcl import PFCLParser
from demon_engine.services.brain_engine.compendium import Compendium
from .matcher import TechniqueMatcher
from .renderer import FragmentRenderer
from .contracts import Contracts


class DemonEngineRouter:
    def __init__(self,
                 registry: Optional[PipelineRegistry] = None,
                 features: Optional[FeatureFlags] = None,
                 compendium_path: str = "compendium.json"):
        self.registry = registry or PipelineRegistry()
        self.features = features or FeatureFlags()
        self.comp = Compendium.from_path(compendium_path)
        self.parser = PFCLParser()
        self.matcher = TechniqueMatcher(self.comp)
        self.renderer = FragmentRenderer(fragments_root="fragments")
        self.contracts = Contracts()
        # LLM client abstraction
        self.llm = LLMClient()

    def infer_intent(self, client: str) -> str:
        return "chat" if client not in ("vscode", "cursor") else ("editor" if client=="vscode" else "agent")

    async def route(self,
              text: str,
              mode: str = "free",
              client: str = "web",
              intent: Optional[str] = None,
              meta: Optional[Dict[str, Any]] = None,
              user_is_pro: bool = False,
              allow_fallback: bool = True) -> Dict[str, Any]:
        if DEBUG_BRAIN_ENGINE:
            print("[BRAIN_ENGINE] route() called with:", {
                "text": text,
                "mode": mode,
                "client": client,
                "intent": intent,
                "meta": meta,
                "user_is_pro": user_is_pro,
                "allow_fallback": allow_fallback
            })
        intent = intent or self.infer_intent(client)
        key = (intent, mode, client)
        if DEBUG_BRAIN_ENGINE:
            print(f"[BRAIN_ENGINE] intent: {intent}, key: {key}")
        # pro gate / global flags / kill switch
        if DEBUG_BRAIN_ENGINE:
            print(f"[BRAIN_ENGINE] Checking global pro disable: {self.features.is_global_pro_disabled()} and mode: {mode}")
        if self.features.is_global_pro_disabled() and mode == "pro":
            if allow_fallback:
                mode = "free"; key = (intent, mode, client)
            else:
                raise ProRequiredError("Pro is globally disabled")
        if DEBUG_BRAIN_ENGINE:
            print(f"[BRAIN_ENGINE] Checking killswitch for key: {key} => {self.features.is_killswitch(key)}")
        if self.features.is_killswitch(key):
            raise KillSwitchError(f"Pipeline {key} disabled")
        # registry lookup (legacy compatibility)
        try:
            if DEBUG_BRAIN_ENGINE:
                print(f"[BRAIN_ENGINE] Looking up pipeline for: {intent}, {mode}, {client}")
            pipeline_name, matched_key = self.registry.lookup(intent, mode, client)
        except KeyError:
            if allow_fallback:
                if DEBUG_BRAIN_ENGINE:
                    print("[BRAIN_ENGINE] Fallback to chat/free/* pipeline")
                pipeline_name, matched_key = self.registry.lookup("chat", "free", "*")
            else:
                print(f"[BRAIN_ENGINE] PipelineNotFound: {intent}/{mode}/{client}")
                raise PipelineNotFound(f"No pipeline for {intent}/{mode}/{client}")

        # --- NEW: Route to adapters for special pipelines ---
        if pipeline_name in ("CodeForge.Architect", "ArchPro"):
            from demon_engine.services.brain_engine.adapters import run_architect_pro_pipeline
            # input_data: build from text/meta as needed
            input_data = {"description": text}
            user = meta.get("user", {}) if meta else {}
            meta_args = meta or {}
            return await run_architect_pro_pipeline(input_data, user, meta_args)
        elif pipeline_name in ("Oracle.Ideas.Pro", "Oracle.Ideas.Basic", "IdeaGenPro", "IdeaGenFree"):
            from demon_engine.services.brain_engine.adapters import run_oracle_pro_pipeline
            input_data = {"niche": text}
            user = meta.get("user", {}) if meta else {}
            meta_args = meta or {}
            return await run_oracle_pro_pipeline(input_data, user, meta_args)

        # --- Legacy path ---
        cmds, remainder = self.parser.parse(text)
        if DEBUG_BRAIN_ENGINE:
            print(f"[BRAIN_ENGINE] PFCL parse: cmds={cmds}, remainder={remainder}")
        plan = self.matcher.select(remainder, cmds, surface=client, tier=mode)
        if DEBUG_BRAIN_ENGINE:
            print(f"[BRAIN_ENGINE] Technique plan: {plan}")
        rendered = self.renderer.render(plan, {
            "prompt_text": remainder,
            "json_schema": (meta or {}).get("json_schema"),
            "examples": (meta or {}).get("examples"),
            "persona": (meta or {}).get("persona"),
            "objective": (meta or {}).get("objective"),
            "constraints": (meta or {}).get("constraints"),
            "n": (meta or {}).get("n"),
            "axes": (meta or {}).get("axes"),
            "tools": (meta or {}).get("tools"),
            "contexts": (meta or {}).get("contexts"),
        })
        if DEBUG_BRAIN_ENGINE:
            print(f"[BRAIN_ENGINE] Rendered fragments: {rendered}")
        # naive final prompt assembly: system + developer + user
        final_prompt = "\n\n".join([rendered.get("system", ""), rendered.get("developer", ""), rendered.get("user", "")]).strip()
        if DEBUG_BRAIN_ENGINE:
            print(f"[BRAIN_ENGINE] Final prompt: {final_prompt}")
        messages = []
        if rendered.get("system", ""): messages.append({"role": "system", "content": rendered["system"]})
        if rendered.get("user", ""): messages.append({"role": "user", "content": rendered["user"]})
        if DEBUG_BRAIN_ENGINE:
            print(f"[BRAIN_ENGINE] Messages to LLM: {messages}")
        if not messages:
            print("[BRAIN_ENGINE] ERROR: No messages to send to LLM. Check prompt assembly logic.")
            raise ValueError("No messages to send to LLM. Check prompt assembly logic.")
        llm_res = await self.llm.complete(messages=messages, tier=mode, meta={"intent": intent, "client": client})
        if DEBUG_BRAIN_ENGINE:
            print(f"[BRAIN_ENGINE] LLM result: {llm_res.text}")
        shaped = self.contracts.enforce(client, mode, llm_res.text)
        if DEBUG_BRAIN_ENGINE:
            print(f"[BRAIN_ENGINE] Shaped/enforced output: {shaped}")
        return {
            "matched_pipeline": pipeline_name,
            "matched_key": matched_key,
            "engine_version": self.registry.get_engine_version(),
            "plan": plan,
            "final_prompt": final_prompt,
            "content": shaped,
            "fallback": (mode=="free" and client=="web" and intent=="chat")
        }

