"""
settings.py — Environment-driven configuration using pydantic-settings.

Pattern inspired by: deliberate/server/src/deliberate_server/config.py
All settings are loaded from environment variables with sensible defaults
for local development. The application fails fast on missing required values.

Usage:
    from src.config.settings import settings
    print(settings.llm_provider)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("email_assistant.config")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "AI Email Assistant Harness"
    app_version: str = "1.0.0"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # ── LLM Provider ─────────────────────────────────────────────────────────
    llm_provider: Literal["openai", "gemini"] = "openai"
    openai_api_key: str = ""
    gemini_api_key: str = ""
    # Task-specific model routing (inspired by deliberate's policy routing)
    llm_model_draft: str = "gpt-4o"
    llm_model_summarize: str = "gpt-4o-mini"
    llm_model_triage: str = "gpt-4o-mini"
    llm_request_timeout: int = 30
    llm_max_retries: int = 3

    # ── Gmail OAuth ───────────────────────────────────────────────────────────
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:8080/oauth/callback"
    gmail_credentials_path: str = "credentials/gmail_credentials.json"
    gmail_token_path: str = "credentials/gmail_token.json"
    # Local port for the one-time OAuth callback server. 0 = auto-pick a free
    # port (avoids conflicts, e.g. when Apache/XAMPP already holds 8080).
    gmail_oauth_port: int = 0
    # The Gmail address the assistant operates on behalf of
    gmail_user_email: str = "me"

    # ── Database ──────────────────────────────────────────────────────────────
    # Default: SQLite for local dev (inspired by deliberate's PostgreSQL setup)
    database_url: str = "sqlite+aiosqlite:///./ai_email_assistant.db"
    sqlalchemy_echo: bool = False

    # ── Redis / Cache ─────────────────────────────────────────────────────────
    redis_url: str = ""  # Empty → fall back to InMemoryCache

    # ── Storage ───────────────────────────────────────────────────────────────
    storage_backend: Literal["local", "gcs", "s3"] = "local"
    storage_local_dir: str = "./data/storage"

    # ── Approval Gate ─────────────────────────────────────────────────────────
    # How long the system waits for human approval before timing out (seconds)
    approval_timeout_seconds: int = 3600  # 1 hour
    # Email to notify when a draft is awaiting approval
    reviewer_email: str = ""

    # ── Audit ─────────────────────────────────────────────────────────────────
    audit_log_path: str = "./data/audit/audit.jsonl"

    # ── Guardrails ────────────────────────────────────────────────────────────
    guardrails_enable_input: bool = True
    guardrails_enable_output: bool = True
    # Declarative rail policy (patterns, thresholds, per-rail enable/fail-mode).
    # Relative paths resolve against the repo root. Absent → built-in defaults.
    # Copy config/guardrails.example.yaml → config/guardrails.yaml to customise.
    guardrails_policy_path: str = "config/guardrails.yaml"
    # Hard timeout (seconds) for an LLM-judge rail before it fails open to ALLOW.
    guardrails_llm_timeout: int = 15
    # Comma-separated recipient domains that may be emailed WITHOUT extra approval.
    # Empty → every recipient is treated as external and escalated to human review.
    # (Draft length bounds live in the guardrail policy, not here — see policy.py.)
    guardrails_allowed_recipient_domains: str = ""

    @property
    def allowed_recipient_domains(self) -> set[str]:
        """Parse the comma-separated allowlist into a normalised set of domains."""
        raw = self.guardrails_allowed_recipient_domains
        return {d.strip().lower() for d in raw.split(",") if d.strip()}

    # ── Polling ───────────────────────────────────────────────────────────────
    # How often to poll Gmail inbox (seconds) when in polling mode
    polling_interval_seconds: int = 60

    # ── Security ─────────────────────────────────────────────────────────────
    secret_key: str = "dev-secret-key-change-in-production"

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def gmail_credentials_file(self) -> Path:
        return BASE_DIR / self.gmail_credentials_path

    @property
    def gmail_token_file(self) -> Path:
        return BASE_DIR / self.gmail_token_path

    @property
    def active_llm_api_key(self) -> str:
        if self.llm_provider == "openai":
            return self.openai_api_key
        return self.gemini_api_key


def get_settings() -> Settings:
    """Load and validate settings. Warn on missing optional values."""
    s = Settings()

    if s.is_production and s.secret_key == "dev-secret-key-change-in-production":
        print(
            "FATAL: SECRET_KEY is set to the development default in production. "
            "Set a strong SECRET_KEY environment variable.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not s.active_llm_api_key:
        logger.warning(
            "No LLM API key configured for provider '%s'. "
            "Set %s environment variable.",
            s.llm_provider,
            "OPENAI_API_KEY" if s.llm_provider == "openai" else "GEMINI_API_KEY",
        )

    return s


# Singleton settings instance
settings = get_settings()
