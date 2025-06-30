"""
AutOps API Package

This package contains all the API endpoints and webhook handlers.
"""

from .webhooks import router

__all__ = ["router"]
