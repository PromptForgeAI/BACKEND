import json
from pathlib import Path


from typing import Any, Dict, List, Optional

class BrainEngine:
    """
    Compendium-driven Brain Engine for PromptForgeAI.
    Supports Quick (minimal, low-latency) and Full (multi-stage, explainable) pipelines.
    """
    def __init__(self, compendium_path: Optional[str] = None, mongo=None):
        self.compendium: Optional[dict] = None
        self.mongo = mongo
        if compendium_path:
            self.load_compendium(compendium_path)

    def load_compendium(self, path: str):
        with open(path, 'r', encoding='utf-8') as f:
            self.compendium = json.load(f)

    def extract_signals(self, text: str, context: Optional[dict] = None) -> dict:
        """
        Deterministically extract signals from input for technique selection.
        TODO: Replace with rule-based or ML-enhanced extraction.
        """
        signals = {}
        if "json" in text.lower():
            signals["needs_json"] = True
        if context and context.get("persona"):
            signals["persona"] = context["persona"]
        # TODO: Add more sophisticated extraction (reasoning_depth, domain, style, etc.)
        return signals

    def match_techniques(self, signals: dict, mode: str = "quick") -> List[dict]:
        """
        Select techniques from compendium based on signals and mode.
        Quick Mode: foundational + structuring only.
        Full Mode: all relevant techniques.
        """
        if not self.compendium:
            return []
        # Compendium is a list of techniques, not a dict with "techniques" key
        techniques = self.compendium if isinstance(self.compendium, list) else self.compendium.get("techniques", [])
        if mode == "quick":
            return [t for t in techniques if t["category"] in ["foundational", "output_structuring"]]
        # Full mode: match all relevant techniques (TODO: smarter matching)
        return techniques

    def compose_pipeline(self, techniques: List[dict], mode: str = "full") -> dict:
        """
        Compose a LangGraph-style pipeline (nodes/edges) from techniques.
        """
        nodes = []
        edges = []
        prev_id = None
        for i, t in enumerate(techniques):
            node_id = f"n{i+1}"
            nodes.append({"id": node_id, "kind": t["id"]})
            if prev_id:
                edges.append({"from": prev_id, "to": node_id})
            prev_id = node_id
        return {"nodes": nodes, "edges": edges}

    async def run_pipeline(self, pipeline: dict, input_text: str, context: Optional[dict] = None, mode: str = "quick", user: Optional[dict] = None) -> dict:
        """
        Execute the pipeline. In Quick Mode, use a single LLM call for rewrite. In Full Mode, use a multi-stage pipeline:
        1. Rewrite (LLM)
        2. Critique (LLM self-critique)
        3. Expand (LLM expansion)
        4. Personalize (if user is Pro)
        """
        import httpx
        from config.providers import GROQ_BASE_URL, GROQ_API_KEY, GROQ_MODEL, ProviderAuthError
        async def call_llm(prompt, system=None, temperature=0.7, max_tokens=512, model=None):
            model = model or GROQ_MODEL
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system or ""},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{GROQ_BASE_URL}/chat/completions", headers=headers, json=payload)
            if resp.status_code == 401:
                raise ProviderAuthError("groq", "401 Unauthorized")
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"GROQ request failed: {e.response.status_code} {e.response.text[:300]}") from e
            data = resp.json()
            return data["choices"][0]["message"]["content"]

        # --- Quick Mode: single LLM rewrite ---
        try:
            if mode == "quick":
                system = (
                    "You are a world-class prompt engineer. Rewrite the user's prompt to be clearer, more effective, and more likely to get a great answer. "
                    "Output only the improved prompt, with no explanations, meta-comments, or advice. Do not add any commentary or suggestions—just return the upgraded prompt itself."
                )
                upgraded = await call_llm(input_text, system=system, temperature=0.5, max_tokens=400)
                return {
                    "upgraded": upgraded.strip(),
                    "plan": None,
                    "diffs": None,
                    "fidelity_score": None,
                    "matched_entries": None
                }
            # --- Full Mode: multi-stage pipeline ---
            # 1. Rewrite
            system_rewrite = "You are a legendary prompt engineer. Rewrite the user's prompt to be maximally detailed, creative, and effective."
            rewritten = await call_llm(input_text, system=system_rewrite, temperature=0.7, max_tokens=800)
            # 2. Critique
            system_critique = "You are a prompt critic. Analyze the following prompt and suggest improvements, missing details, or weaknesses."
            critique = await call_llm(f"Prompt:\n{rewritten}\n\nCritique:", system=system_critique, temperature=0.3, max_tokens=300)
            # 3. Expand
            system_expand = "You are a prompt enhancer. Expand the following prompt to include all missing details, best practices, and advanced techniques."
            expanded = await call_llm(f"Prompt:\n{rewritten}\n\nCritique:\n{critique}\n\nExpanded Prompt:", system=system_expand, temperature=0.8, max_tokens=1200)
            # 4. Personalize (if user is Pro)
            personalized = expanded
            if user and (user.get("claims", {}).get("pro") or user.get("claims", {}).get("plan") == "pro"):
                system_personal = "You are a prompt engineer with access to the user's profile. Personalize the prompt for their goals, style, and context."
                profile = f"User: {user.get('email','')} | UID: {user.get('uid','')}"
                personalized = await call_llm(f"Prompt:\n{expanded}\n\nUser Profile:\n{profile}\n\nPersonalized Prompt:", system=system_personal, temperature=0.7, max_tokens=1200)
            import difflib
            diffs = '\n'.join(difflib.unified_diff(input_text.splitlines(), personalized.splitlines(), fromfile='original', tofile='upgraded', lineterm=''))
            return {
                "upgraded": personalized.strip(),
                "plan": pipeline,
                "diffs": diffs,
                "fidelity_score": 0.99,
                "matched_entries": [n for n in pipeline["nodes"]]
            }
        except ProviderAuthError as e:
            # Bubble up for API to catch and return 502
            raise
        except Exception as e:
            # Bubble up for API to catch and return 500
            raise

        # --- Full Mode: multi-stage pipeline ---
        # 1. Rewrite
        system_rewrite = "You are a legendary prompt engineer. Rewrite the user's prompt to be maximally detailed, creative, and effective."
        rewritten = await call_llm(input_text, system=system_rewrite, temperature=0.7, max_tokens=800)
        # 2. Critique
        system_critique = "You are a prompt critic. Analyze the following prompt and suggest improvements, missing details, or weaknesses."
        critique = await call_llm(f"Prompt:\n{rewritten}\n\nCritique:", system=system_critique, temperature=0.3, max_tokens=300)
        # 3. Expand
        system_expand = "You are a prompt enhancer. Expand the following prompt to include all missing details, best practices, and advanced techniques."
        expanded = await call_llm(f"Prompt:\n{rewritten}\n\nCritique:\n{critique}\n\nExpanded Prompt:", system=system_expand, temperature=0.8, max_tokens=1200)
        # 4. Personalize (if user is Pro)
        personalized = expanded
        if user and (user.get("claims", {}).get("pro") or user.get("claims", {}).get("plan") == "pro"):
            system_personal = "You are a prompt engineer with access to the user's profile. Personalize the prompt for their goals, style, and context."
            profile = f"User: {user.get('email','')} | UID: {user.get('uid','')}"
            personalized = await call_llm(f"Prompt:\n{expanded}\n\nUser Profile:\n{profile}\n\nPersonalized Prompt:", system=system_personal, temperature=0.7, max_tokens=1200)
        # --- Diffs and plan ---
        import difflib
        diffs = '\n'.join(difflib.unified_diff(input_text.splitlines(), personalized.splitlines(), fromfile='original', tofile='upgraded', lineterm=''))
        return {
            "upgraded": personalized.strip(),
            "plan": pipeline,
            "diffs": diffs,
            "fidelity_score": 0.99,
            "matched_entries": [n for n in pipeline["nodes"]]
        }
