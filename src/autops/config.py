"""
Configuration management for AutOps.
"""

import os
from enum import Enum
from typing import Optional, Any

from pydantic import validator
from pydantic_settings import BaseSettings

from .utils.exceptions import ConfigurationError


class Environment(str, Enum):
    """Environment types."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):  # type: ignore[misc]
    """Application settings with validation."""

    # Environment
    environment: Environment = Environment.DEVELOPMENT
    app_env: str = "development"  # Alternative environment field for compatibility
    debug: bool = False
    use_mock_data: bool = False  # Whether to use mock data for testing

    # Logging
    log_level: str = "INFO"
    json_logs: bool = True

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1

    # Security
    secret_key: str = "dev-secret-key"
    allowed_hosts: list[str] = ["*"]
    slack_signing_secret: str = "dev-signing-secret"
    encryption_key: Optional[str] = None

    # OpenAI
    openai_api_key: str = "sk-placeholder"
    openai_model: str = "gpt-4"
    openai_max_tokens: int = 2000
    openai_temperature: float = 0.7
    openai_timeout: int = 30
    openai_max_retries: int = 3

    # Slack
    slack_app_id: Optional[str] = None
    slack_client_id: Optional[str] = None
    slack_client_secret: Optional[str] = None
    slack_bot_token: str = "xoxb-placeholder"
    slack_verification_token: Optional[str] = None
    slack_app_token: Optional[str] = None

    # GitHub
    github_token: str = "ghp_placeholder"
    github_owner: str = "placeholder"
    github_webhook_secret: Optional[str] = None
    github_timeout: int = 30

    # GitLab
    gitlab_url: str = "https://gitlab.com"
    gitlab_token: Optional[str] = None
    gitlab_timeout: int = 30

    # Datadog
    datadog_api_key: Optional[str] = None
    datadog_app_key: Optional[str] = None
    datadog_site: str = "datadoghq.com"

    # PagerDuty
    pagerduty_api_key: Optional[str] = None
    pagerduty_email: Optional[str] = None

    # Redis (for caching and task queues)
    redis_url: str = "redis://localhost:6379/0"
    redis_pool_size: int = 10
    redis_timeout: int = 5

    # Celery (for background tasks)
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Database
    database_url: Optional[str] = None
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Monitoring
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    metrics_endpoint: str = "/metrics"
    health_check_endpoint: str = "/health"
    enable_metrics: bool = True

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period: int = 60

    # Docker Hub (for CI/CD)
    docker_username: Optional[str] = None
    docker_token: Optional[str] = None

    # Gemini API (for future use)
    gemini_api_key: Optional[str] = None

    # Circuit Breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("environment", pre=True)
    def validate_environment(cls, v: Any) -> Environment:
        if isinstance(v, str):
            try:
                return Environment(v.lower())
            except ValueError:
                raise ConfigurationError(f"Invalid environment: {v}")
        if isinstance(v, Environment):
            return v
        raise ConfigurationError(f"Invalid environment type: {type(v)}")

    @validator("debug")
    def validate_debug(cls, v: bool, values: dict[str, Any]) -> bool:
        env = values.get("environment")
        if env == Environment.PRODUCTION and v:
            raise ConfigurationError("Debug mode cannot be enabled in production")
        return v

    @validator("api_workers")
    def validate_workers(cls, v: int) -> int:
        if v < 1:
            raise ConfigurationError("API workers must be at least 1")
        return v

    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        # Strip whitespace and remove comments
        cleaned_value = (
            v.strip().split("#")[0].strip() if isinstance(v, str) else str(v)
        )
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if cleaned_value.upper() not in valid_levels:
            raise ConfigurationError(
                f"Invalid log level: {cleaned_value}. Valid options: {valid_levels}"
            )
        return cleaned_value.upper()

    @validator("allowed_hosts", pre=True)
    def parse_allowed_hosts(cls, v: Any) -> list[str]:
        """Parse allowed hosts from comma-separated string."""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        if isinstance(v, list):
            return v
        raise ConfigurationError(f"Invalid allowed_hosts type: {type(v)}")

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_staging(self) -> bool:
        """Check if running in staging mode."""
        return self.environment == Environment.STAGING

    @property
    def is_test(self) -> bool:
        """Check if running in test mode."""
        return self.environment == "test"

    def get_database_url(self) -> str:
        """Get database URL based on environment."""
        if self.is_production:
            return self.database_url or os.getenv("DATABASE_URL") or ""
        return "sqlite:///./autops_dev.db"


# Global settings instance
try:
    settings = Settings()
except Exception as e:
    raise ConfigurationError(f"Failed to load configuration: {e}")


def get_settings() -> Settings:
    """Get application settings."""
    return settings
