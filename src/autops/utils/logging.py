"""
Structured logging configuration for AutOps.
"""
import logging
import sys
from typing import Any, Dict

import structlog
from structlog import stdlib


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    """Configure structured logging for the application."""
    log_level = getattr(logging, level.upper())

    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Configure structlog
    structlog.configure(
        processors=[
            stdlib.filter_by_level,
            stdlib.add_logger_name,
            stdlib.add_log_level,
            stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
            if json_logs
            else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=stdlib.LoggerFactory(),
        wrapper_class=stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def log_api_request(
    logger: structlog.stdlib.BoundLogger, method: str, path: str, **kwargs: Any
) -> None:
    """Log API request with structured data."""
    logger.info("api_request", method=method, path=path, **kwargs)


def log_agent_execution(
    logger: structlog.stdlib.BoundLogger,
    agent_name: str,
    action: str,
    duration_ms: float,
    **kwargs: Any,
) -> None:
    """Log agent execution with structured data."""
    logger.info(
        "agent_execution",
        agent_name=agent_name,
        action=action,
        duration_ms=duration_ms,
        **kwargs,
    )


def log_error(
    logger: structlog.stdlib.BoundLogger,
    error: Exception,
    context: Dict[str, Any] = None,
) -> None:
    """Log error with structured context."""
    logger.error(
        "error_occurred",
        error_type=type(error).__name__,
        error_message=str(error),
        context=context or {},
        exc_info=True,
    )
