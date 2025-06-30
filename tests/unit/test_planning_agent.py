"""Tests for the Planning Agent."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from autops.agents.planning_agent import PlanningAgent
from autops.utils.exceptions import PlanningError, ValidationError


class TestPlanningAgent:
    """Test suite for PlanningAgent."""

    @pytest.fixture
    def agent(self):
        """Create a PlanningAgent instance for testing."""
        return PlanningAgent()

    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM response for planning."""
        return {
            "steps": [
                {
                    "action": "check_ci_status",
                    "tool": "github",
                    "parameters": {"repo": "test/repo"},
                    "description": "Check CI status for the repository",
                },
                {
                    "action": "analyze_metrics",
                    "tool": "datadog",
                    "parameters": {"metric": "cpu_usage", "timeframe": "1h"},
                    "description": "Analyze CPU usage metrics",
                },
            ],
            "dependencies": [
                {"step": 0, "depends_on": []},
                {"step": 1, "depends_on": [0]},
            ],
            "estimated_duration": "5 minutes",
            "confidence": 0.85,
        }

    @pytest.mark.asyncio
    async def test_create_plan_success(self, agent, mock_llm_response):
        """Test successful plan creation."""
        query = "Check CI status and analyze CPU metrics"
        context = {"user": "test_user", "channel": "general"}

        with patch("autops.agents.planning_agent.openai") as mock_openai:
            mock_openai.ChatCompletion.acreate.return_value.choices = [
                Mock(message=Mock(content=str(mock_llm_response)))
            ]

            plan = await agent.create_plan(query, context)

            assert plan is not None
            assert "steps" in plan
            assert len(plan["steps"]) == 2
            assert plan["steps"][0]["action"] == "check_ci_status"
            assert plan["estimated_duration"] == "5 minutes"

    @pytest.mark.asyncio
    async def test_create_plan_empty_query(self, agent):
        """Test plan creation with empty query."""
        with pytest.raises(ValidationError, match="Query cannot be empty"):
            await agent.create_plan("", {})

    @pytest.mark.asyncio
    async def test_create_plan_llm_failure(self, agent):
        """Test plan creation when LLM fails."""
        query = "Test query"
        context = {"user": "test_user"}

        with patch("autops.agents.planning_agent.openai") as mock_openai:
            mock_openai.ChatCompletion.acreate.side_effect = Exception("API Error")

            with pytest.raises(PlanningError, match="Failed to create plan"):
                await agent.create_plan(query, context)

    @pytest.mark.asyncio
    async def test_validate_plan_success(self, agent, mock_llm_response):
        """Test successful plan validation."""
        is_valid = await agent.validate_plan(mock_llm_response)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_plan_missing_steps(self, agent):
        """Test plan validation with missing steps."""
        invalid_plan = {"dependencies": [], "estimated_duration": "5 minutes"}

        is_valid = await agent.validate_plan(invalid_plan)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_plan_empty_steps(self, agent):
        """Test plan validation with empty steps."""
        invalid_plan = {"steps": [], "dependencies": []}

        is_valid = await agent.validate_plan(invalid_plan)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_optimize_plan(self, agent, mock_llm_response):
        """Test plan optimization."""
        optimized = await agent.optimize_plan(mock_llm_response)

        assert optimized is not None
        assert "steps" in optimized
        # Should maintain the same structure but potentially reorder
        assert len(optimized["steps"]) >= len(mock_llm_response["steps"])

    @pytest.mark.asyncio
    async def test_estimate_complexity_simple(self, agent):
        """Test complexity estimation for simple plans."""
        simple_plan = {"steps": [{"action": "check_status", "tool": "github"}]}

        complexity = await agent.estimate_complexity(simple_plan)
        assert complexity == "low"

    @pytest.mark.asyncio
    async def test_estimate_complexity_complex(self, agent):
        """Test complexity estimation for complex plans."""
        complex_plan = {
            "steps": [
                {"action": "deploy", "tool": "kubernetes"},
                {"action": "monitor", "tool": "datadog"},
                {"action": "scale", "tool": "kubernetes"},
                {"action": "validate", "tool": "github"},
                {"action": "rollback", "tool": "kubernetes"},
            ]
        }

        complexity = await agent.estimate_complexity(complex_plan)
        assert complexity in ["medium", "high"]

    @pytest.mark.asyncio
    async def test_create_plan_with_timeout(self, agent):
        """Test plan creation with timeout."""
        query = "Test query"
        context = {"user": "test_user"}

        with patch("autops.agents.planning_agent.openai") as mock_openai:
            # Simulate a slow response
            mock_openai.ChatCompletion.acreate = AsyncMock()
            mock_openai.ChatCompletion.acreate.side_effect = TimeoutError(
                "Request timeout"
            )

            with pytest.raises(PlanningError, match="Failed to create plan"):
                await agent.create_plan(query, context)

    @pytest.mark.asyncio
    async def test_create_plan_invalid_json_response(self, agent):
        """Test plan creation with invalid JSON response from LLM."""
        query = "Test query"
        context = {"user": "test_user"}

        with patch("autops.agents.planning_agent.openai") as mock_openai:
            mock_openai.ChatCompletion.acreate.return_value.choices = [
                Mock(message=Mock(content="Invalid JSON response"))
            ]

            with pytest.raises(PlanningError, match="Failed to create plan"):
                await agent.create_plan(query, context)

    @pytest.mark.asyncio
    async def test_create_plan_with_context_variables(self, agent, mock_llm_response):
        """Test plan creation uses context variables."""
        query = "Deploy to production"
        context = {
            "user": "admin_user",
            "channel": "deployments",
            "environment": "production",
            "previous_deployments": ["v1.0.0", "v1.0.1"],
        }

        with patch("autops.agents.planning_agent.openai") as mock_openai:
            mock_openai.ChatCompletion.acreate.return_value.choices = [
                Mock(message=Mock(content=str(mock_llm_response)))
            ]

            await agent.create_plan(query, context)

            # Verify that the LLM was called with context
            call_args = mock_openai.ChatCompletion.acreate.call_args
            messages = call_args[1]["messages"]

            # Check that context was included in the prompt
            system_message = next(msg for msg in messages if msg["role"] == "system")
            assert "admin_user" in system_message["content"]
            assert "production" in system_message["content"]
