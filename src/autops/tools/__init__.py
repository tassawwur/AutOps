"""
AutOps Tools Package

This package contains clients for integrating with external DevOps tools
and services like GitHub, Slack, Datadog, PagerDuty, etc.
"""

from .github_client import github_client
from .slack_client import slack_client

# Tool clients will be imported as they are implemented
__all__ = [
    "github_client",
    "slack_client",
]
