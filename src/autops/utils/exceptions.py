"""
Custom exception classes for AutOps.
"""

from typing import Any, Dict, Optional


class AutOpsException(Exception):
    """Base exception for AutOps application."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}


class AgentExecutionError(AutOpsException):
    """Raised when an agent fails to execute properly."""

    pass


class ToolExecutionError(AutOpsException):
    """Raised when a tool fails to execute properly."""

    pass


class QueryUnderstandingError(AutOpsException):
    """Raised when query understanding fails."""

    pass


class PlanningError(AutOpsException):
    """Raised when planning fails."""

    pass


class ExternalAPIError(AutOpsException):
    """Raised when external API calls fail."""

    def __init__(
        self,
        message: str,
        service: str,
        status_code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, context)
        self.service = service
        self.status_code = status_code


class SlackAPIError(ExternalAPIError):
    """Raised when Slack API calls fail."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, "Slack", status_code, context)


class GitHubAPIError(ExternalAPIError):
    """Raised when GitHub API calls fail."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, "GitHub", status_code, context)


class DatadogAPIError(ExternalAPIError):
    """Raised when Datadog API calls fail."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, "Datadog", status_code, context)


class PagerDutyAPIError(ExternalAPIError):
    """Raised when PagerDuty API calls fail."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, "PagerDuty", status_code, context)


class GitLabAPIError(ExternalAPIError):
    """Raised when GitLab API calls fail."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, "GitLab", status_code, context)


class ConfigurationError(AutOpsException):
    """Raised when configuration is invalid."""

    pass


class ValidationError(AutOpsException):
    """Raised when validation fails."""

    pass


class DatabaseError(AutOpsException):
    """Raised when database operations fail."""

    pass
