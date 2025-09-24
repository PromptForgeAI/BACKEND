
# ==========================
# services/brain_engine/renderer.py
# ==========================
import json
import os
from string import Template
from typing import Any, Dict, List
from pathlib import Path

try:
    import jinja2
    from jinja2.sandbox import SandboxedEnvironment  # Secure Jinja2
    _HAS_JINJA = True
except Exception:
    _HAS_JINJA = False

class SecureFragmentRenderer:
    """Secure template renderer with path validation and sandboxing"""
    
    # Whitelist of allowed template paths
    ALLOWED_TEMPLATE_DIRS = {
        "fragments", "templates", "prompts"
    }
    
    # Safe context variables only
    SAFE_CONTEXT_KEYS = {
        "prompt_text", "json_schema", "examples", "persona", 
        "objective", "constraints", "n", "axes", "tools", "contexts",
        "user_input", "system_prompt", "instructions"
    }
    
    def __init__(self, fragments_root: str = "fragments"):
        self.root = Path(fragments_root).resolve()
        
        # Ensure fragments root exists and is safe
        if not self.root.exists():
            self.root.mkdir(parents=True, exist_ok=True)
        
        if _HAS_JINJA:
            # Use sandboxed environment for security
            self.env = SandboxedEnvironment(
                loader=jinja2.FileSystemLoader(str(self.root)),
                autoescape=True,  # Prevent XSS
                trim_blocks=True,
                lstrip_blocks=True
            )
            # Disable dangerous functions
            self.env.globals.clear()
            self.env.filters.clear()
            # Add only safe filters
            self.env.filters['safe'] = lambda x: str(x)
            self.env.filters['length'] = len
        else:
            self.env = None

class FragmentRenderer(SecureFragmentRenderer):
    """Legacy-compatible renderer with enhanced security"""
    
    def render(self, plan: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        # Sanitize context before rendering
        safe_context = self._sanitize_context(context)
        
        # Collect system/user strings in phase order: pre -> intra -> post
        phases = {"pre": [], "intra": [], "post": []}
        for item in plan.get("chosen", []):
            fr = item.get("fragments") or {}
            phs = item.get("phase") or []
            for role in ("system", "developer", "user"):
                if fr.get(role):
                    phases[phs[0] if phs else "intra"].append((role, fr[role]))
        
        # Render each fragment; concatenate per role
        rendered = {"system": [], "developer": [], "user": []}
        for phase in ("pre", "intra", "post"):
            for role, frag_path_or_text in phases[phase]:
                try:
                    rendered_fragment = self._render_fragment(frag_path_or_text, safe_context)
                    rendered[role].append(rendered_fragment)
                except Exception as e:
                    # Log error but continue with fallback
                    import logging
                    logging.error(f"Fragment rendering error: {e}")
                    rendered[role].append(f"[RENDER_ERROR: {str(e)[:100]}]")
        
        return {k: "\n\n".join(v) for k, v in rendered.items()}
    
    def _sanitize_context(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize context to prevent injection attacks"""
        safe_ctx = {}
        
        for key, value in ctx.items():
            # Only allow whitelisted keys
            if key not in self.SAFE_CONTEXT_KEYS:
                continue
                
            # Sanitize string values
            if isinstance(value, str):
                safe_ctx[key] = self._sanitize_string(value)
            elif isinstance(value, (int, float, bool)):
                safe_ctx[key] = value
            elif isinstance(value, (list, tuple)):
                safe_ctx[key] = [
                    self._sanitize_string(str(item)) if isinstance(item, str) else str(item)
                    for item in value[:10]  # Limit list size
                ]
            elif isinstance(value, dict):
                # Recursively sanitize dict values (limit depth)
                safe_ctx[key] = {
                    k: self._sanitize_string(str(v)) if isinstance(v, str) else str(v)
                    for k, v in list(value.items())[:10]  # Limit dict size
                }
            else:
                safe_ctx[key] = str(value)[:1000]  # Convert to string with limit
        
        return safe_ctx
    
    def _sanitize_string(self, text: str) -> str:
        """Basic string sanitization"""
        if not text:
            return ""
        
        # Limit length
        text = text[:5000]
        
        # Remove potential template injection patterns
        dangerous_patterns = [
            "{{", "}}", "{%", "%}", "<%", "%>", "<script", "</script>",
            "__import__", "eval(", "exec(", "subprocess", "os.system"
        ]
        
        for pattern in dangerous_patterns:
            text = text.replace(pattern, "")
        
        return text
    
    def _validate_template_path(self, template_path: str) -> bool:
        """Validate template path is within allowed directories"""
        try:
            # Resolve the path and check if it's within allowed directories
            resolved_path = (self.root / template_path).resolve()
            
            # Check if path is within fragments root
            if not str(resolved_path).startswith(str(self.root)):
                return False
            
            # Check if file exists and is a file
            if not resolved_path.exists() or not resolved_path.is_file():
                return False
            
            # Check file extension is safe
            safe_extensions = {'.txt', '.md', '.j2', '.jinja', '.template'}
            if resolved_path.suffix.lower() not in safe_extensions:
                return False
            
            return True
        except Exception:
            return False

    def _render_fragment(self, frag: str, ctx: Dict[str, Any]) -> str:
        # If looks like a file path, validate and render from file
        if any(x in frag for x in ("/", ".j2", "\\", ".template", ".txt")):
            # Validate path before proceeding
            if not self._validate_template_path(frag):
                return f"[INVALID_TEMPLATE_PATH: {frag}]"
            
            if _HAS_JINJA:
                try:
                    tmpl = self.env.get_template(frag)
                    return tmpl.render(**ctx)
                except Exception as e:
                    return f"[TEMPLATE_ERROR: {str(e)[:100]}]"
            else:
                # fallback: treat file as Template with ${var}
                try:
                    template_path = self.root / frag
                    src = template_path.read_text(encoding="utf-8")
                    return Template(src).safe_substitute(**ctx)
                except FileNotFoundError:
                    return f"[MISSING_FRAGMENT: {frag}]"
                except Exception as e:
                    return f"[FRAGMENT_ERROR: {str(e)[:100]}]"
        else:
            # Inline template - sanitize before processing
            safe_frag = self._sanitize_string(frag)
            try:
                return Template(safe_frag).safe_substitute(**ctx)
            except Exception as e:
                return f"[INLINE_TEMPLATE_ERROR: {str(e)[:100]}]"
