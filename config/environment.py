# ===================================================================
# ENVIRONMENT CONFIGURATION SYSTEM
# ===================================================================

import os
from typing import Optional, Dict, Any
import json
from functools import lru_cache

class EnvironmentConfig:
    """Centralized environment configuration management"""
    
    def __init__(self):
        self.env = os.getenv("ENVIRONMENT", "development")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.load_config()
    
    def load_config(self):
        """Load environment-specific configuration"""
        config_files = [
            f"config/{self.env}.json",
            "config/default.json",
            ".env.json"
        ]
        
        self.config = {}
        for config_file in config_files:
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        file_config = json.load(f)
                        self.config.update(file_config)
                        break
                except Exception as e:
                    if self.debug:
                        print(f"Error loading {config_file}: {e}")
        
        # Override with environment variables
        self._load_env_overrides()
    
    def _load_env_overrides(self):
        """Load configuration from environment variables"""
        env_mapping = {
            "API_BASE_URL": "api.base_url",
            "DATABASE_URL": "database.url",
            "MONGODB_URL": "database.mongodb_url",
            "JWT_SECRET": "auth.jwt_secret",
            "FIREBASE_CONFIG": "auth.firebase_config",
            "PADDLE_VENDOR_ID": "billing.paddle.vendor_id",
            "PADDLE_API_KEY": "billing.paddle.api_key",
            "RAZORPAY_KEY_ID": "billing.razorpay.key_id",
            "RAZORPAY_KEY_SECRET": "billing.razorpay.key_secret",
            "STRIPE_SECRET_KEY": "billing.stripe.secret_key",
            "OPENAI_API_KEY": "ai.openai_api_key",
            "ANTHROPIC_API_KEY": "ai.anthropic_api_key",
            "GEMINI_API_KEY": "ai.gemini_api_key",
            "REDIS_URL": "cache.redis_url",
            "SENTRY_DSN": "monitoring.sentry_dsn",
            "LOG_LEVEL": "logging.level",
            "RATE_LIMIT_REDIS": "rate_limiting.redis_url",
            "CORS_ORIGINS": "security.cors_origins"
        }
        
        for env_var, config_path in env_mapping.items():
            value = os.getenv(env_var)
            if value:
                self._set_nested_config(config_path, value)
    
    def _set_nested_config(self, path: str, value: str):
        """Set nested configuration value from dot notation path"""
        keys = path.split('.')
        current = self.config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Handle special data types
        if value.lower() in ('true', 'false'):
            value = value.lower() == 'true'
        elif value.startswith('[') and value.endswith(']'):
            try:
                value = json.loads(value)
            except:
                pass
        elif value.isdigit():
            value = int(value)
        
        current[keys[-1]] = value
    
    def get(self, path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        keys = path.split('.')
        current = self.config
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default
    
    @property
    def api_base_url(self) -> str:
        """Get API base URL for current environment"""
        return self.get("api.base_url", self._default_api_url())
    
    @property
    def frontend_url(self) -> str:
        """Get frontend URL for current environment"""
        return self.get("frontend.url", self._default_frontend_url())
    
    @property
    def database_url(self) -> str:
        """Get database URL for current environment"""
        return self.get("database.mongodb_url", "mongodb+srv://shivadeepakdev_db_user:IazHjfnuOfLEnw40@testpfai.uoiqsww.mongodb.net/?retryWrites=true&w=majority&appName=testpfai")
    
    @property
    def cors_origins(self) -> list:
        """Get CORS origins for current environment"""
        origins = self.get("security.cors_origins", "")
        if isinstance(origins, str):
            return [origin.strip() for origin in origins.split(",") if origin.strip()]
        return origins or self._default_cors_origins()
    
    def _default_api_url(self) -> str:
        """Default API URL based on environment"""
        if self.env == "production":
            return "https://api.promptforgeai.tech"
        elif self.env == "staging":
            return "https://staging-api.promptforgeai.tech"
        else:
            return "http://localhost:8000"
    
    def _default_frontend_url(self) -> str:
        """Default frontend URL based on environment"""
        if self.env == "production":
            return "https://www.promptforgeai.tech"
        elif self.env == "staging":
            return "https://staging.promptforgeai.tech"
        else:
            return "http://localhost:3000"
    
    def _default_cors_origins(self) -> list:
        """Default CORS origins based on environment"""
        if self.env == "production":
            return [
                "https://www.promptforgeai.tech",
                "https://promptforgeai.tech",
                "chrome-extension://*"
            ]
        elif self.env == "staging":
            return [
                "https://staging.promptforgeai.tech",
                "chrome-extension://*"
            ]
        else:
            return [
                "http://localhost:3000",
                "http://localhost:3001",
                "http://127.0.0.1:3000",
                "chrome-extension://*"
            ]
    
    def get_extension_config(self) -> Dict[str, Any]:
        """Get configuration for Chrome extension"""
        return {
            "api_base": self.api_base_url + "/v1",
            "frontend_url": self.frontend_url,
            "environment": self.env,
            "features": {
                "telemetry": self.get("features.telemetry", True),
                "offline_mode": self.get("features.offline_mode", False),
                "auto_upgrade": self.get("features.auto_upgrade", True)
            },
            "rate_limits": {
                "requests_per_minute": self.get("rate_limits.extension.requests_per_minute", 30),
                "burst_limit": self.get("rate_limits.extension.burst_limit", 10)
            }
        }
    
    def get_vscode_config(self) -> Dict[str, Any]:
        """Get configuration for VS Code extension"""
        return {
            "apiBase": self.api_base_url + "/v1",
            "upgradeUrl": self.frontend_url + "/pricing",
            "environment": self.env,
            "telemetryEnabled": self.get("features.telemetry", True)
        }

# Global configuration instance
@lru_cache(maxsize=1)
def get_config() -> EnvironmentConfig:
    """Get singleton configuration instance"""
    return EnvironmentConfig()

# Export commonly used values
config = get_config()
API_BASE_URL = config.api_base_url
DATABASE_URL = config.database_url
FRONTEND_URL = config.frontend_url
CORS_ORIGINS = config.cors_origins
ENVIRONMENT = config.env
DEBUG = config.debug
