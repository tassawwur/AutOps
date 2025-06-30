"""
AutOps - AI-Powered DevOps Automation Platform
"""

__version__ = "0.1.0"
__author__ = "AutOps AI"
__description__ = "An autonomous AI teammate for your entire engineering organization"

# Package-level imports for easier access
from .config import get_settings

__all__ = ["get_settings", "__version__"]
