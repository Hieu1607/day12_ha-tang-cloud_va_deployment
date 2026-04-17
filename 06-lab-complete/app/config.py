"""Production config — all values from environment variables (12-Factor)."""
import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    # Server
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")

    # App
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Economics AI Chatbot"))
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "1.0.0"))

    # Groq LLM
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"))

    # Security
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", "dev-key-change-me"))

    # Rate limiting
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    )

    # Budget — monthly per-user cap in USD
    monthly_budget_usd: float = field(
        default_factory=lambda: float(os.getenv("MONTHLY_BUDGET_USD", "10.0"))
    )

    # Redis (optional — falls back to in-memory if not set)
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", ""))

    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    def validate(self) -> "Settings":
        import logging
        logger = logging.getLogger(__name__)
        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY must be set")
        if self.environment == "production" and self.agent_api_key == "dev-key-change-me":
            raise ValueError("AGENT_API_KEY must be set in production")
        logger.info(f"Config loaded: env={self.environment} model={self.llm_model}")
        return self


settings = Settings().validate()
