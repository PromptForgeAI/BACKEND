"""
🏗️ THE ARCHITECT - Advanced Project Planning Service
===================================================
Refactored to receive its core LLM dependency from the main application.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# Note: All local LLM logic has been removed. The service now expects an LLM instance.

# --- Pydantic Models ---


# --- Canonical Architect Input/Output Models ---
from typing import Optional, List

class Step(BaseModel):
    id: str
    title: str
    description: str
    status: str  # 'pending' | 'processing' | 'completed'
    details: Optional[List[str]] = None
    code: Optional[str] = None
    dependencies: Optional[List[str]] = None

class ArchitectInput(BaseModel):
    description: str
    techStack: List[str]
    architectureStyle: str


class ArchitectResponse(BaseModel):
    system_architecture: str
    framework_recommendation: str
    database_selection: str
    deployment_strategy: str
    tech_stack: List[str]
    name: Optional[str] = None
    steps: Optional[List[Step]] = None
    # Optionally include legacy fields for compatibility
    refined_prompt: Optional[str] = None
    draft: Optional[str] = None
    critique: Optional[str] = None
    prompt_id: Optional[str] = None
    version_number: int = 1
    new_credits: Optional[int] = None


class ArchitectService:
    def __init__(self, llm_instance: Any):
        self.logger = logging.getLogger(__name__)
        if not llm_instance:
            raise ValueError("ArchitectService requires a valid LLM instance.")
        self.llm = llm_instance
        self.logger.info("✅ ArchitectService initialized with injected LLM.")


    async def architect(self, input_data: ArchitectInput, user_id: str) -> ArchitectResponse:
        """
        Architects a new software system and returns a full architecture breakdown.
        """
        self.logger.info(f"Starting prompt architecture for user: {user_id}")
        try:
            # Compose a prompt for the LLM to generate all required fields
            meta_prompt = f'''
You are a world-class software architect. Given the following project description, tech stack, and architecture style, generate a production-grade architecture plan.

Project Description: {input_data.description}
Tech Stack: {', '.join(input_data.techStack)}
Architecture Style: {input_data.architectureStyle}

Return ONLY valid JSON with the following fields:
{{
  "system_architecture": str,
  "framework_recommendation": str,
  "database_selection": str,
  "deployment_strategy": str,
  "tech_stack": list of str,
  "name": str (optional),
  "steps": [{{"id": str, "title": str, "description": str, "status": str, "details": list of str (optional), "code": str (optional), "dependencies": list of str (optional)}}] (optional)
}}
'''
            llm_result = await self.llm.ainvoke(meta_prompt)
            from dependencies import safe_parse_json
            try:
                result_json = safe_parse_json(llm_result.content)
            except Exception as e:
                self.logger.error(f"Failed to parse LLM output as JSON: {e}\nRaw: {llm_result.content}")
                raise

            # Defensive: ensure all required fields are present
            return ArchitectResponse(
                system_architecture=result_json.get("system_architecture", ""),
                framework_recommendation=result_json.get("framework_recommendation", ""),
                database_selection=result_json.get("database_selection", ""),
                deployment_strategy=result_json.get("deployment_strategy", ""),
                tech_stack=result_json.get("tech_stack", []),
                name=result_json.get("name"),
                steps=[Step(**step) for step in result_json.get("steps", [])] if result_json.get("steps") else None
            )
        except Exception as e:
            self.logger.error(f"Architecture process failed for user {user_id}: {e}", exc_info=True)
            raise

# No singleton export; use DI via app.state.architect