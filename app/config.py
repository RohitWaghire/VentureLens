"""Application configuration loaded from environment variables.

All credentials and tunables live server-side (environment variables only).
No secret is ever sent to the browser. See .env.example for documentation.
"""

from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    """Read configuration from the process environment with sensible defaults."""

    def __init__(self) -> None:
        self.app_name = os.getenv("VL_APP_NAME", "VentureLens")
        self.tagline = os.getenv("VL_TAGLINE", "A clearer view of where to grow.")
        # Dev-only default; always set a real VL_SECRET_KEY before public deployment.
        self.secret_key = os.getenv("VL_SECRET_KEY", "dev-secret-change-me")
        self.debug = os.getenv("VL_DEBUG", "0") == "1"

        # Session lifecycle.
        self.session_max_age_seconds = int(os.getenv("VL_SESSION_MAX_AGE_SECONDS", "3600"))
        self.session_cookie_name = os.getenv("VL_SESSION_COOKIE_NAME", "vl_session")
        # Secure should be enabled in production (HTTPS). HttpOnly is always on.
        self.cookie_secure = os.getenv("VL_COOKIE_SECURE", "0") == "1"
        self.cookie_samesite = os.getenv("VL_COOKIE_SAMESITE", "lax")

        # Public-demo safety limits.
        self.rate_limit_per_ip = int(os.getenv("VL_RATE_LIMIT_PER_IP", "120"))
        self.rate_limit_window_seconds = int(os.getenv("VL_RATE_LIMIT_WINDOW_SECONDS", "60"))
        self.session_query_budget = int(os.getenv("VL_SESSION_QUERY_BUDGET", "30"))
        self.global_query_budget = int(os.getenv("VL_GLOBAL_QUERY_BUDGET", "200000"))
        self.request_max_bytes = int(os.getenv("VL_REQUEST_MAX_BYTES", str(1024 * 1024)))
        self.trusted_proxies = [
            p.strip() for p in os.getenv("VL_TRUSTED_PROXIES", "").split(",") if p.strip()
        ]
        self.allowed_origins = [
            o.strip()
            for o in os.getenv(
                "VL_ALLOWED_ORIGINS",
                "http://localhost:8000,http://127.0.0.1:8000",
            ).split(",")
            if o.strip()
        ]

        # Provider timeouts (bounded costs and latency).
        self.search_timeout_seconds = float(os.getenv("VL_SEARCH_TIMEOUT_SECONDS", "20"))
        self.qloo_timeout_seconds = float(os.getenv("VL_QLOO_TIMEOUT_SECONDS", "20"))
        self.llm_timeout_seconds = float(os.getenv("VL_LLM_TIMEOUT_SECONDS", "60"))

        # Provider selection. "demo" is a deterministic, credential-free provider so the
        # app runs and is fully testable before real credentials are configured.
        self.provider = os.getenv("VL_PROVIDER", "demo")

        # Optional credentials for real providers (adapter seams only; demo ignores them).
        self.llm_api_key = os.getenv("VL_LLM_API_KEY", "")
        self.llm_provider = os.getenv("VL_LLM_PROVIDER", "")
        self.llm_model = os.getenv("VL_LLM_MODEL", "")
        self.search_api_key = os.getenv("VL_SEARCH_API_KEY", "")
        self.search_provider = os.getenv("VL_SEARCH_PROVIDER", "")
        self.qloo_api_key = os.getenv("VL_QLOO_API_KEY", "")
        self.qloo_base_url = os.getenv("VL_QLOO_BASE_URL", "https://api.qloo.com")

    @property
    def cookie_secure_active(self) -> bool:
        return self.cookie_secure


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()