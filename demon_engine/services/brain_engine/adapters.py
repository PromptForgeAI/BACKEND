def _reshape_web_contract(result):
    # Enforce web contract: outline sections present
    sections = getattr(result, "sections", [])
    if not sections:
        # Try to split raw text into sections
        raw = getattr(result, "raw", "") or getattr(result, "text", "")
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        # Group by empty line as section break
        grouped = []
        current = []
        for l in lines:
            if not l:
                if current:
                    grouped.append(current)
                    current = []
            else:
                current.append(l)
        if current:
            grouped.append(current)
        sections = [{"title": f"Section {i+1}", "body": "\n".join(group)} for i, group in enumerate(grouped)]
    return sections
def _reshape_agent_contract(result):
    # Enforce agent contract: numbered steps, constraints, stop conditions. Reshape prose if needed.
    steps = getattr(result, "steps", [])
    constraints = getattr(result, "constraints", [])
    stop_conditions = getattr(result, "stop_conditions", [])
    # If steps are not a list of numbered steps, try to split prose
    if not steps or not all(isinstance(s, str) and s.strip().startswith(("1.", "2.", "3.")) for s in steps):
        raw = getattr(result, "raw", "") or getattr(result, "text", "")
        # Split into lines and number if needed
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        steps = [f"{i+1}. {l}" for i, l in enumerate(lines) if l]
    return steps, constraints, stop_conditions

"""
DemonEngine Pipeline Adapters
- Adapter functions to wrap legacy services (ArchitectService, OracleService) for use as DemonEngine pipelines.
- Enforces output contracts, telemetry, explainability, and fallback logic.
"""

from demon_engine.services.brain_engine.analytics import log_event, log_before_after


# --- Pipeline Node: CodeForge.Architect.v1 (editor/pro/vscode) ---
import asyncio
from demon_engine.services.brain_engine.errors import ProRequiredError

def _is_verb(line):
    verbs = ["Refactor", "Implement", "Add", "Remove", "Update", "Create", "Write", "Test", "Fix", "Configure", "Set", "Build", "Design", "Document", "Deploy", "Integrate", "Optimize", "Generate", "Review", "Analyze", "Plan"]
    return any(line.strip().startswith(v) for v in verbs)

def _extract_imperative_lines(steps):
    return [s for s in steps if _is_verb(s)]

def _extract_acceptance_criteria(criteria):
    return [c for c in criteria if c.strip().startswith("-") or c.strip().startswith("•")]

def _reshape_editor_contract(result):
    # Try to reshape using steps/criteria/risks fields
    steps = getattr(result, "steps", [])
    criteria = getattr(result, "criteria", [])
    risks = getattr(result, "risks", [])
    imperative_lines = _extract_imperative_lines(steps)
    acceptance_criteria = _extract_acceptance_criteria(criteria) or _extract_acceptance_criteria(risks)
    return imperative_lines, acceptance_criteria

async def run_architect_pro_pipeline(input_data, user, meta=None, timeout_ms=20000, pro_only=True, fallback_to=None, user_is_pro=False):
    """
    Pipeline node for CodeForge.Architect.v1 (editor/pro/vscode)
    Calls ArchitectService.architect(input_text, meta) with timeout and fallback logic.
    """
    from services.architect_service import ArchitectService, ArchitectInput
    from demon_engine.services.brain_engine.feature_flags import FeatureFlags
    import time
    service = ArchitectService(llm_instance=None)  # Inject real LLM in production
    fallback = False
    fallback_reason = None
    plan = None
    result = None
    route_key = "editor/pro/vscode"
    user_id = user.get("uid", "anon")
    client = meta.get("client", "vscode") if meta else "vscode"
    flags = FeatureFlags()
    # --- Pro gating ---
    if pro_only and not user_is_pro:
        log_event("pipeline_error", {"pipeline": "CodeForge.Architect.v1", "user": user_id, "error": "Pro required"})
        raise ProRequiredError("Pro required for this pipeline.")
    # --- Kill-switch ---
    if flags.is_killswitch(("editor", "pro", client)):
        log_event("pipeline_error", {"pipeline": "CodeForge.Architect.v1", "user": user_id, "error": "killswitch"})
        return {"output": None, "plan": None, "fallback": True, "fallback_reason": "killswitch"}
    # --- Rate limiting ---
    rl_key = f"CodeForge.Architect.v1/{client}/{user_id}"
    if not flags.check_rate_limit(user_id, ("editor", "pro", client), "pro"):
        log_event("pipeline_error", {"pipeline": "CodeForge.Architect.v1", "user": user_id, "error": "rate_limit_exceeded"})
        return {"output": None, "plan": None, "fallback": True, "fallback_reason": "rate_limit_exceeded"}
    # --- Telemetry toggle ---
    telemetry_enabled = flags.is_telemetry_enabled()
    t0 = time.time()
    try:
        coro = service.architect(ArchitectInput(**input_data), user_id=user_id)
        result = await asyncio.wait_for(coro, timeout=timeout_ms/1000)
        plan = result.steps if hasattr(result, "steps") else None
        # --- Editor contract enforcement ---
        contract_breach = False
        imperative_lines, acceptance_criteria = _reshape_editor_contract(result)
        if len(imperative_lines) < 3 or len(acceptance_criteria) < 3:
            imperative_lines, acceptance_criteria = _reshape_editor_contract(result)
            if len(imperative_lines) < 3 or len(acceptance_criteria) < 3:
                contract_breach = True
        latency = time.time() - t0
        fidelity_score = 0.95 if not contract_breach else 0.7  # TODO: make dynamic
        explain = input_data.get("explain") or (meta and meta.get("explain"))
        response = {
            "upgraded": f"Prompt:\n- " + "\n- ".join(imperative_lines) + "\n\nAcceptance criteria:\n- " + "\n- ".join(acceptance_criteria),
            "matched_pipeline": "CodeForge.Architect.v1",
            "engine_version": "2.0.0",
            "plan": plan or [],
            "diffs": None,
            "fidelity_score": fidelity_score,
            "matched_entries": [route_key],
            "message": "Output contract: editor",
            "fallback": contract_breach,
            "fallback_reason": "contract_breach" if contract_breach else None
        }
        if explain:
            response["explain"] = {
                "plan": plan or [],
                "matched_entries": [route_key],
                "fallback": contract_breach,
                "fallback_reason": "contract_breach" if contract_breach else None
            }
        if telemetry_enabled:
            log_event("route_selected", {
                "route_key": route_key,
                "latency": latency,
                "retries": 0,
                "fidelity_score": fidelity_score,
                "extra": {
                    "fallback": contract_breach,
                    "fallback_reason": "contract_breach" if contract_breach else None,
                    "matched_pipeline": "CodeForge.Architect.v1"
                }
            })
        if meta and meta.get("log_before_after"):
            log_before_after(before=input_data, after=response, consent=True, user_id=user_id)
        return response
# --- Pipeline Node: Agent.DemonEngine.v1 (agent/pro/cursor) ---
async def run_agent_pro_pipeline(input_data, user, meta=None, timeout_ms=25000, pro_only=True, fallback_to=None, user_is_pro=False):
    """
    Pipeline node for Agent.DemonEngine.v1 (agent/pro/cursor)
    Calls AgentService.agent(input_text, meta) with timeout and fallback logic.
    Enforces agent contract: numbered steps, constraints, stop conditions.
    """
    from services.architect_service import ArchitectService, ArchitectInput  # Placeholder for AgentService
    from demon_engine.services.brain_engine.feature_flags import FeatureFlags
    import time
    service = ArchitectService(llm_instance=None)  # Replace with AgentService in production
    fallback = False
    fallback_reason = None
    plan = None
    result = None
    route_key = "agent/pro/cursor"
    user_id = user.get("uid", "anon")
    client = meta.get("client", "cursor") if meta else "cursor"
    flags = FeatureFlags()
    # --- Pro gating ---
    if pro_only and not user_is_pro:
        log_event("pipeline_error", {"pipeline": "Agent.DemonEngine.v1", "user": user_id, "error": "Pro required"})
        raise ProRequiredError("Pro required for this pipeline.")
    # --- Kill-switch ---
    if flags.is_killswitch(("agent", "pro", client)):
        log_event("pipeline_error", {"pipeline": "Agent.DemonEngine.v1", "user": user_id, "error": "killswitch"})
        return {"output": None, "plan": None, "fallback": True, "fallback_reason": "killswitch"}
    # --- Rate limiting ---
    rl_key = f"Agent.DemonEngine.v1/{client}/{user_id}"
    if not flags.check_rate_limit(user_id, ("agent", "pro", client), "pro"):
        log_event("pipeline_error", {"pipeline": "Agent.DemonEngine.v1", "user": user_id, "error": "rate_limit_exceeded"})
        return {"output": None, "plan": None, "fallback": True, "fallback_reason": "rate_limit_exceeded"}
    # --- Telemetry toggle ---
    telemetry_enabled = flags.is_telemetry_enabled()
    t0 = time.time()
    try:
        # TODO: Replace with AgentService.agent call
        coro = service.architect(ArchitectInput(**input_data), user_id=user_id)
        result = await asyncio.wait_for(coro, timeout=timeout_ms/1000)
        plan, constraints, stop_conditions = _reshape_agent_contract(result)
        contract_breach = False
        if not plan or len(plan) < 3:
            contract_breach = True
        latency = time.time() - t0
        fidelity_score = 0.95 if not contract_breach else 0.7
        explain = input_data.get("explain") or (meta and meta.get("explain"))
        response = {
            "upgraded": "\n".join(plan),
            "matched_pipeline": "Agent.DemonEngine.v1",
            "engine_version": "2.0.0",
            "plan": plan or [],
            "diffs": None,
            "fidelity_score": fidelity_score,
            "matched_entries": [route_key],
            "message": "Output contract: agent",
            "constraints": constraints,
            "stop_conditions": stop_conditions,
            "fallback": contract_breach,
            "fallback_reason": "contract_breach" if contract_breach else None
        }
        if explain:
            response["explain"] = {
                "plan": plan or [],
                "matched_entries": [route_key],
                "fallback": contract_breach,
                "fallback_reason": "contract_breach" if contract_breach else None
            }
        if telemetry_enabled:
            log_event("route_selected", {
                "route_key": route_key,
                "latency": latency,
                "retries": 0,
                "fidelity_score": fidelity_score,
                "extra": {
                    "fallback": contract_breach,
                    "fallback_reason": "contract_breach" if contract_breach else None,
                    "matched_pipeline": "Agent.DemonEngine.v1"
                }
            })
        if meta and meta.get("log_before_after"):
            log_before_after(before=input_data, after=response, consent=True, user_id=user_id)
        return response
    except ProRequiredError:
        if telemetry_enabled:
            log_event("pipeline_error", {"pipeline": "Agent.DemonEngine.v1", "user": user_id, "error": "Pro required"})
        raise
    except Exception as e:
        if telemetry_enabled:
            log_event("pipeline_error", {"pipeline": "Agent.DemonEngine.v1", "user": user_id, "error": str(e)})
        if fallback_to:
            # TODO: Actually resolve and call fallback pipeline node
            return {"output": None, "plan": None, "fallback": True, "fallback_reason": "pipeline_error"}
        return {"output": None, "plan": None, "fallback": True, "fallback_reason": str(e)}
    except ProRequiredError:
        if telemetry_enabled:
            log_event("pipeline_error", {"pipeline": "CodeForge.Architect.v1", "user": user_id, "error": "Pro required"})
        raise
    except Exception as e:
        if telemetry_enabled:
            log_event("pipeline_error", {"pipeline": "CodeForge.Architect.v1", "user": user_id, "error": str(e)})
        if fallback_to:
            # TODO: Actually resolve and call fallback pipeline node
            return {"output": None, "plan": None, "fallback": True, "fallback_reason": "pipeline_error"}
        return {"output": None, "plan": None, "fallback": True, "fallback_reason": str(e)}

# --- Pipeline Node: Oracle.Ideas.Basic/Pro.v1 (chat/free/web, chat/pro/web) ---
async def run_oracle_pipeline(input_data, user, meta=None, timeout_ms=12000, pro_mode=False):
    """
    Pipeline node for Oracle.Ideas.Basic.v1 and Oracle.Ideas.Pro.v1
    Calls OracleService.generate_ideas(input_text, meta). For Pro, adds rerank/dedupe pass.
    """
    from services.oracle_service import OracleService, IdeaInput
    import time
    service = OracleService(llm_instance=None)  # Inject real LLM in production
    fallback = False
    fallback_reason = None
    result = None
    try:
        start = time.time()
        coro = service.generate_ideas(IdeaInput(**input_data), user_id=user.get("uid", "anon"))
        result = await asyncio.wait_for(coro, timeout=timeout_ms/1000)
        ideas = result.ideas if hasattr(result, "ideas") else []
        # For Pro: rerank/dedupe
        if pro_mode and ideas:
            # TODO: Implement rerank/dedupe (cosine/LLM ranker)
            pass
        # Groq fallback detection (example: result.groq_fallback == True)
        if hasattr(result, "groq_fallback") and result.groq_fallback:
            fallback = True
            fallback_reason = "quota_exceeded"
        log_event("pipeline_run", {"pipeline": "Oracle.Ideas.Pro.v1" if pro_mode else "Oracle.Ideas.Basic.v1", "user": user.get("uid"), "fallback": fallback, "reason": fallback_reason})
        if meta and meta.get("log_before_after"):
            log_before_after("oracle_pro", before=input_data, after=result, consent=True)
        return {"output": result.dict(), "plan": [idea.title for idea in ideas], "fallback": fallback, "fallback_reason": fallback_reason}
    except Exception as e:
        log_event("pipeline_error", {"pipeline": "Oracle.Ideas.Pro.v1" if pro_mode else "Oracle.Ideas.Basic.v1", "user": user.get("uid"), "error": str(e)})
        return {"output": None, "plan": None, "fallback": True, "fallback_reason": str(e)}

# Example: Oracle Pro Pipeline Adapter
async def run_oracle_pro_pipeline(input_data, user, meta=None):
    """
    Adapter for chat/pro/web → Oracle.Ideas.Pro (Pro pipeline)
    - Calls OracleService.generate_ideas
    - Enforces Web/Chat contract (outline + bullets)
    - Logs telemetry and explainability
    """
        from services.oracle_service import OracleService, OracleInput
        from demon_engine.services.brain_engine.feature_flags import FeatureFlags
        import time
        service = OracleService(llm_instance=None)
        fallback = False
        fallback_reason = None
        result = None
        route_key = "oracle/pro/vscode"
        user_id = user.get("uid", "anon")
        client = meta.get("client", "vscode") if meta else "vscode"
        flags = FeatureFlags()
        # --- Pro gating ---
        if pro_only and not user_is_pro:
            log_event("pipeline_error", {"pipeline": "CodeForge.Oracle.v1", "user": user_id, "error": "Pro required"})
            raise ProRequiredError("Pro required for this pipeline.")
        # --- Kill-switch ---
        if flags.is_killswitch(("oracle", "pro", client)):
            log_event("pipeline_error", {"pipeline": "CodeForge.Oracle.v1", "user": user_id, "error": "killswitch"})
            return {"output": None, "fallback": True, "fallback_reason": "killswitch"}
        # --- Rate limiting ---
        rl_key = f"CodeForge.Oracle.v1/{client}/{user_id}"
        if not flags.check_rate_limit(user_id, ("oracle", "pro", client), "pro"):
            log_event("pipeline_error", {"pipeline": "CodeForge.Oracle.v1", "user": user_id, "error": "rate_limit_exceeded"})
            return {"output": None, "fallback": True, "fallback_reason": "rate_limit_exceeded"}
        # --- Telemetry toggle ---
        telemetry_enabled = flags.is_telemetry_enabled()
        t0 = time.time()
        try:
            coro = service.oracle(OracleInput(**input_data), user_id=user_id)
            result = await asyncio.wait_for(coro, timeout=timeout_ms/1000)
            sections = _reshape_web_contract(result)
            contract_breach = False
            if not sections or len(sections) < 1:
                contract_breach = True
            latency = time.time() - t0
            fidelity_score = 0.95 if not contract_breach else 0.7
            explain = input_data.get("explain") or (meta and meta.get("explain"))
            response = {
                "upgraded": "\n\n".join([f"{s['title']}\n{s['body']}" for s in sections]),
                "matched_pipeline": "CodeForge.Oracle.v1",
                "engine_version": "2.0.0",
                "plan": [s["title"] for s in sections],
                "diffs": None,
                "fidelity_score": fidelity_score,
                "matched_entries": [route_key],
                "message": "Output contract: web",
                "sections": sections,
                "fallback": contract_breach,
                "fallback_reason": "contract_breach" if contract_breach else None
            }
            if explain:
                response["explain"] = {
                    "plan": [s["title"] for s in sections],
                    "matched_entries": [route_key],
                    "fallback": contract_breach,
                    "fallback_reason": "contract_breach" if contract_breach else None
                }
            if telemetry_enabled:
                log_event("route_selected", {
                    "route_key": route_key,
                    "latency": latency,
                    "retries": 0,
                    "fidelity_score": fidelity_score,
                    "extra": {
                        "fallback": contract_breach,
                        "fallback_reason": "contract_breach" if contract_breach else None,
                        "matched_pipeline": "CodeForge.Oracle.v1"
                    }
                })
            if meta and meta.get("log_before_after"):
                log_before_after(before=input_data, after=response, consent=True, user_id=user_id)
            return response
        except ProRequiredError:
            if telemetry_enabled:
                log_event("pipeline_error", {"pipeline": "CodeForge.Oracle.v1", "user": user_id, "error": "Pro required"})
            raise
        except Exception as e:
            if telemetry_enabled:
                log_event("pipeline_error", {"pipeline": "CodeForge.Oracle.v1", "user": user_id, "error": str(e)})
            if fallback_to:
                # TODO: Actually resolve and call fallback pipeline node
                return {"output": None, "fallback": True, "fallback_reason": "pipeline_error"}
            return {"output": None, "fallback": True, "fallback_reason": str(e)}
