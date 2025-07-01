"""
Pytest configuration and shared fixtures for AutOps tests.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from typing import Generator, AsyncGenerator

from fastapi.testclient import TestClient
from httpx import AsyncClient

from src.autops.main import app
from src.autops.config import Settings, Environment


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings."""
    return Settings(
        environment=Environment.DEVELOPMENT,
        debug=True,
        log_level="DEBUG",
        openai_api_key="test-openai-key",
        slack_bot_token="test-slack-token",
        slack_signing_secret="test-slack-secret",
        github_token="test-github-token",
        github_owner="test-owner",
        datadog_api_key="test-datadog-key",
        datadog_app_key="test-datadog-app-key",
        pagerduty_api_key="test-pd-key",
        pagerduty_email="test@example.com",
        redis_url="redis://localhost:6379/15",  # Use different DB for tests
    )


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI application."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    mock = Mock()
    mock.chat.completions.create.return_value = Mock(
        choices=[
            Mock(
                message=Mock(
                    content='{"intent": "test_intent", "entities": {}, "confidence": 0.9}'
                )
            )
        ]
    )
    return mock


@pytest.fixture
def mock_github_client():
    """Mock GitHub client."""
    mock = Mock()
    mock.get_latest_pipeline_status.return_value = {
        "status": "completed",
        "conclusion": "success",
        "url": "https://github.com/test/repo/actions/runs/123",
    }
    return mock


@pytest.fixture
def mock_slack_client():
    """Mock Slack client."""
    mock = Mock()
    mock.post_message = AsyncMock()
    return mock


@pytest.fixture
def sample_user_query() -> str:
    """Sample user query for testing."""
    return "Is the latest build passing for the checkout-service?"


@pytest.fixture
def sample_structured_query() -> dict:
    """Sample structured query for testing."""
    return {
        "intent": "get_ci_cd_status",
        "entities": {"service_name": "checkout-service", "build_type": "latest"},
        "confidence": 0.95,
        "original_query": "Is the latest build passing for the checkout-service?",
    }


@pytest.fixture
def sample_incident_query() -> dict:
    """Sample incident query for testing."""
    return {
        "intent": "investigate_incident",
        "entities": {"service_name": "payment-service"},
        "confidence": 0.9,
        "original_query": "Payment service is down",
    }


@pytest.fixture
def sample_plan() -> dict:
    """Sample execution plan for testing."""
    return {
        "intent": "get_ci_cd_status",
        "original_query": "Is the latest build passing for the checkout-service?",
        "steps": [
            {
                "agent": "ToolExecutionAgent",
                "tool": "github_client",
                "action": "get_latest_pipeline_status",
                "parameters": {"repo_name": "checkout-service"},
                "status": "pending",
            }
        ],
    }


@pytest.fixture
def sample_slack_event() -> dict:
    """Sample Slack event for testing."""
    return {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "text": "Is the latest build passing for the checkout-service?",
            "channel": "C1234567890",
            "user": "U1234567890",
            "ts": "1234567890.123456",
        },
    }
