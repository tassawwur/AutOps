"""
Configuration management for AutOps.
"""
import os
from enum import Enum
from typing import Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings

from .utils.exceptions import ConfigurationError


class Environment(str, Enum):
    """Environment types."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Application settings with validation."""

    # Environment
    environment: Environment = Field(default=Environment.DEVELOPMENT, env="APP_ENV")
    debug: bool = Field(default=False, env="DEBUG")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    json_logs: bool = Field(default=True)

    # API Configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    api_workers: int = Field(default=1)

    # Security
    secret_key: str = Field(default="dev-secret-key", env="SECRET_KEY")
    allowed_hosts: list[str] = Field(default=["*"], env="ALLOWED_HOSTS")
    slack_signing_secret: str = Field(..., env="SLACK_SIGNING_SECRET")
    encryption_key: Optional[str] = Field(default=None)

    # OpenAI
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4", env="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=2000, env="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(default=0.7, env="OPENAI_TEMPERATURE")
    openai_timeout: int = Field(default=30)
    openai_max_retries: int = Field(default=3)

    # Slack
    slack_app_id: Optional[str] = Field(None, env="SLACK_APP_ID")
    slack_client_id: Optional[str] = Field(None, env="SLACK_CLIENT_ID")
    slack_client_secret: Optional[str] = Field(None, env="SLACK_CLIENT_SECRET")
    slack_bot_token: str = Field(..., env="SLACK_BOT_TOKEN")
    slack_verification_token: Optional[str] = Field(
        None, env="SLACK_VERIFICATION_TOKEN"
    )
    slack_app_token: Optional[str] = Field(default=None)

    # GitHub
    github_token: str = Field(..., env="GITHUB_TOKEN")
    github_owner: str = Field(..., env="GITHUB_OWNER")
    github_webhook_secret: Optional[str] = Field(None, env="GITHUB_WEBHOOK_SECRET")
    github_timeout: int = Field(default=30)

    # GitLab
    gitlab_url: str = Field(default="https://gitlab.com", env="GITLAB_URL")
    gitlab_token: Optional[str] = Field(None, env="GITLAB_TOKEN")
    gitlab_timeout: int = Field(default=30)

    # Datadog
    datadog_api_key: Optional[str] = Field(None, env="DATADOG_API_KEY")
    datadog_app_key: Optional[str] = Field(None, env="DATADOG_APP_KEY")
    datadog_site: str = Field(default="datadoghq.com", env="DATADOG_SITE")

    # PagerDuty
    pagerduty_api_key: Optional[str] = Field(None, env="PAGERDUTY_API_KEY")
    pagerduty_email: Optional[str] = Field(None, env="PAGERDUTY_EMAIL")

    # Redis (for caching and task queues)
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_pool_size: int = Field(default=10, env="REDIS_POOL_SIZE")
    redis_timeout: int = Field(default=5, env="REDIS_TIMEOUT")

    # Celery (for background tasks)
    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")

    # Database
    database_url: Optional[str] = Field(None, env="DATABASE_URL")
    database_pool_size: int = Field(default=10, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, env="DATABASE_MAX_OVERFLOW")

    # Monitoring
    prometheus_enabled: bool = Field(default=True, env="PROMETHEUS_ENABLED")
    prometheus_port: int = Field(default=9090, env="PROMETHEUS_PORT")
    metrics_endpoint: str = Field(default="/metrics", env="METRICS_ENDPOINT")
    health_check_endpoint: str = Field(default="/health", env="HEALTH_CHECK_ENDPOINT")
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(default=60, env="RATE_LIMIT_PERIOD")

    # Docker Hub (for CI/CD)
    docker_username: Optional[str] = Field(None, env="DOCKER_USERNAME")
    docker_token: Optional[str] = Field(None, env="DOCKER_TOKEN")

    # Gemini API (for future use)
    gemini_api_key: Optional[str] = Field(None, env="GEMINI_API_KEY")

    # Circuit Breaker
    circuit_breaker_failure_threshold: int = Field(default=5)
    circuit_breaker_recovery_timeout: int = Field(default=60)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("environment", pre=True)
    def validate_environment(cls, v):
        if isinstance(v, str):
            try:
                return Environment(v.lower())
            except ValueError:
                raise ConfigurationError(f"Invalid environment: {v}")
        return v

    @validator("debug")
    def validate_debug(cls, v, values):
        env = values.get("environment")
        if env == Environment.PRODUCTION and v:
            raise ConfigurationError("Debug mode cannot be enabled in production")
        return v

    @validator("api_workers")
    def validate_workers(cls, v):
        if v < 1:
            raise ConfigurationError("API workers must be at least 1")
        return v

    @validator("log_level")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ConfigurationError(f"Invalid log level: {v}")
        return v.upper()

    @validator("allowed_hosts", pre=True)
    def parse_allowed_hosts(cls, v):
        """Parse allowed hosts from comma-separated string."""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v

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
            return self.database_url or os.getenv("DATABASE_URL", "")
        return "sqlite:///./autops_dev.db"


# Global settings instance
try:
    settings = Settings()
except Exception as e:
    raise ConfigurationError(f"Failed to load configuration: {e}")


def get_settings() -> Settings:
    """Get application settings."""
    return settings
