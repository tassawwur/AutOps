"""
Comprehensive test suite for AutOps agents and tools.
This file tests the complete workflow from query understanding to response generation.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from src.autops.agents.query_understanding_agent import QueryUnderstandingAgent
from src.autops.agents.planning_agent import create_plan
from src.autops.agents.information_retrieval_agent import InformationRetrievalAgent
from src.autops.agents.tool_execution_agent import ToolExecutionAgent
from src.autops.agents.verification_agent import VerificationAgent
from src.autops.tools.slack_client import SlackClient
from src.autops.utils.exceptions import (
    QueryUnderstandingError,
    ValidationError,
)


class TestQueryUnderstandingAgent:
    """Test suite for QueryUnderstandingAgent."""

    @pytest.fixture
    def agent(self):
        return QueryUnderstandingAgent()

    @pytest.mark.asyncio
    async def test_get_structured_query_success(self, agent):
        """Test successful query understanding."""
        with patch.object(agent, "_call_openai_api") as mock_api:
            mock_api.return_value = '{"intent": "get_ci_cd_status", "entities": {"service_name": "test-service"}, "confidence": 0.9}'

            result = await agent.get_structured_query("Is test-service build passing?")

            assert result["intent"] == "get_ci_cd_status"
            assert result["entities"]["service_name"] == "test-service"
            assert result["confidence"] == 0.9
            assert "original_query" in result
            assert "processing_time_ms" in result

    @pytest.mark.asyncio
    async def test_get_structured_query_validation_error(self, agent):
        """Test validation error handling."""
        with pytest.raises(ValidationError):
            await agent.get_structured_query("")

        with pytest.raises(ValidationError):
            await agent.get_structured_query("x" * 2001)  # Too long

    @pytest.mark.asyncio
    async def test_get_structured_query_api_error(self, agent):
        """Test API error handling."""
        with patch.object(agent, "_call_openai_api") as mock_api:
            mock_api.side_effect = Exception("API Error")

            with pytest.raises(QueryUnderstandingError):
                await agent.get_structured_query("test query")

    def test_validate_input_success(self, agent):
        """Test successful input validation."""
        agent.validate_input("Valid query")  # Should not raise

    def test_validate_input_empty_string(self, agent):
        """Test validation with empty string."""
        with pytest.raises(Exception):
            agent.validate_input("")

    def test_validate_input_too_long(self, agent):
        """Test validation with too long string."""
        with pytest.raises(Exception):
            agent.validate_input("x" * 2001)


class TestPlanningAgent:
    """Test suite for planning agent functions."""

    def test_create_plan_ci_cd_status(self):
        """Test plan creation for CI/CD status intent."""
        query = {
            "intent": "get_ci_cd_status",
            "entities": {"service_name": "test-service"},
            "original_query": "Is test-service build passing?",
        }

        plan = create_plan(query)

        assert plan["intent"] == "get_ci_cd_status"
        assert len(plan["steps"]) == 1
        assert plan["steps"][0]["agent"] == "ToolExecutionAgent"
        assert plan["steps"][0]["tool"] == "github_client"

    def test_create_plan_investigate_incident(self):
        """Test plan creation for incident investigation."""
        query = {
            "intent": "investigate_incident",
            "entities": {"service_name": "payment-service"},
            "original_query": "Payment service is down",
        }

        plan = create_plan(query)

        assert plan["intent"] == "investigate_incident"
        assert len(plan["steps"]) == 2
        assert plan["steps"][0]["agent"] == "InformationRetrievalAgent"
        assert plan["steps"][1]["agent"] == "PlanningAgent"

    def test_create_plan_missing_service_name(self):
        """Test error handling for missing service name."""
        query = {
            "intent": "get_ci_cd_status",
            "entities": {},
            "original_query": "Is build passing?",
        }

        plan = create_plan(query)

        assert "error" in plan


class TestInformationRetrievalAgent:
    """Test suite for InformationRetrievalAgent."""

    @pytest.fixture
    def agent(self):
        return InformationRetrievalAgent()

    def test_gather_context_mock_mode(self, agent):
        """Test context gathering in mock mode."""
        with patch.dict("os.environ", {"USE_MOCK_DATA": "true"}):
            result = agent.gather_context("test-service")

            assert "metrics" in result
            assert "incidents" in result
            assert "deployment" in result
            assert result["metrics"]["service"] == "test-service"

    def test_gather_context_real_mode(self, agent):
        """Test context gathering with mocked real clients."""
        with patch.dict("os.environ", {"USE_MOCK_DATA": "false"}):
            with patch.object(agent, "datadog_client") as mock_dd:
                with patch.object(agent, "pagerduty_client") as mock_pd:
                    with patch.object(agent, "gitlab_client") as mock_gl:
                        mock_dd.get_error_rate_metrics.return_value = {
                            "error_rate": "1.5%"
                        }
                        mock_pd.get_active_incidents.return_value = {"incidents": []}
                        mock_gl.get_last_deployment.return_value = {"status": "success"}

                        result = agent.gather_context("test-service")

                        assert "metrics" in result
                        assert "incidents" in result
                        assert "deployment" in result


class TestToolExecutionAgent:
    """Test suite for ToolExecutionAgent."""

    @pytest.fixture
    def agent(self):
        return ToolExecutionAgent()

    def test_execute_step_github_client(self, agent):
        """Test GitHub client step execution."""
        step = {
            "agent": "ToolExecutionAgent",
            "tool": "github_client",
            "action": "get_latest_pipeline_status",
            "parameters": {"repo_name": "test-repo"},
        }

        with patch(
            "src.autops.tools.github_client.get_latest_pipeline_status"
        ) as mock_github:
            mock_github.return_value = {"status": "success", "conclusion": "success"}

            result = agent.execute_step(step)

            assert result["status"] == "completed"
            assert "result" in result

    def test_execute_step_unknown_tool(self, agent):
        """Test error handling for unknown tools."""
        step = {
            "agent": "ToolExecutionAgent",
            "tool": "unknown_tool",
            "action": "some_action",
            "parameters": {},
        }

        result = agent.execute_step(step)

        assert result["status"] == "failed"
        assert "error" in result


class TestVerificationAgent:
    """Test suite for VerificationAgent."""

    @pytest.fixture
    def agent(self):
        return VerificationAgent()

    def test_validate_execution_result_success(self, agent):
        """Test successful result validation."""
        step = {
            "status": "completed",
            "agent": "InformationRetrievalAgent",
            "action": "gather_context",
            "result": {
                "metrics": {"error_rate": "1.5%"},
                "incidents": {"incidents": []},
                "deployment": {"status": "success"},
            },
        }

        result = agent.validate_execution_result(step)

        assert result["valid"] is True
        assert result["confidence"] > 0.8

    def test_validate_execution_result_failure(self, agent):
        """Test validation of failed step."""
        step = {"status": "failed", "error": "API timeout"}

        result = agent.validate_execution_result(step)

        assert result["valid"] is False
        assert "Step failed" in result["issues"][0]

    @pytest.mark.asyncio
    async def test_reflect_on_workflow(self, agent):
        """Test workflow reflection."""
        plan = {"intent": "investigate_incident", "original_query": "Service is down"}

        execution_results = [
            {"status": "completed", "result": {"analysis": "High error rate detected"}}
        ]

        with patch.object(agent, "client") as mock_client:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = (
                '{"overall_success": true, "confidence_score": 0.9, "insights": {"successes": ["Data gathered"], "failures": [], "unexpected_findings": []}, "recommendations": {"immediate_actions": [], "future_improvements": []}, "risk_assessment": {"risk_level": "low", "risk_factors": []}}'
            )
            mock_client.chat.completions.create.return_value = mock_response

            result = await agent.reflect_on_workflow(plan, execution_results)

            assert result["overall_success"] is True
            assert "insights" in result
            assert "recommendations" in result


class TestSlackClient:
    """Test suite for SlackClient."""

    @pytest.fixture
    def client(self):
        return SlackClient()

    @pytest.mark.asyncio
    async def test_post_message_success(self, client):
        """Test successful message posting."""
        with patch.object(client, "client") as mock_slack:
            mock_slack.chat_postMessage = AsyncMock(return_value={"ok": True})

            result = await client.post_message("C123456", "Test message")

            assert result["ok"] is True
            mock_slack.chat_postMessage.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_message_with_blocks(self, client):
        """Test message posting with blocks."""
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Test"}}]

        with patch.object(client, "client") as mock_slack:
            mock_slack.chat_postMessage = AsyncMock(return_value={"ok": True})

            result = await client.post_message("C123456", "Test", blocks=blocks)

            assert result["ok"] is True


class TestIntegration:
    """Integration tests for the full workflow."""

    @pytest.mark.asyncio
    async def test_full_workflow_ci_cd_status(self):
        """Test complete workflow for CI/CD status check."""
        # Mock all dependencies
        with patch("src.autops.agents.query_understanding_agent.client") as mock_openai:
            with patch(
                "src.autops.tools.github_client.get_latest_pipeline_status"
            ) as mock_github:
                with patch("src.autops.tools.slack_client.slack_client") as mock_slack:
                    # Setup mocks
                    mock_openai.chat.completions.create.return_value.choices[
                        0
                    ].message.content = '{"intent": "get_ci_cd_status", "entities": {"service_name": "test-service"}, "confidence": 0.9}'
                    mock_github.return_value = {
                        "status": "success",
                        "conclusion": "success",
                    }
                    mock_slack.post_message = AsyncMock()

                    # Run workflow components
                    agent = QueryUnderstandingAgent()
                    query = await agent.get_structured_query(
                        "Is test-service build passing?"
                    )
                    plan = create_plan(query)

                    assert plan["intent"] == "get_ci_cd_status"
                    assert len(plan["steps"]) == 1

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self):
        """Test error handling in workflow."""
        with patch("src.autops.agents.query_understanding_agent.client") as mock_openai:
            mock_openai.chat.completions.create.side_effect = Exception("API Error")

            agent = QueryUnderstandingAgent()

            with pytest.raises(QueryUnderstandingError):
                await agent.get_structured_query("test query")


# Performance and load tests
class TestPerformance:
    """Performance test suite."""

    @pytest.mark.asyncio
    async def test_query_understanding_performance(self):
        """Test query understanding performance."""
        agent = QueryUnderstandingAgent()

        with patch.object(agent, "_call_openai_api") as mock_api:
            mock_api.return_value = (
                '{"intent": "get_ci_cd_status", "entities": {}, "confidence": 0.9}'
            )

            import time

            start_time = time.time()

            # Run multiple queries
            tasks = []
            for i in range(10):
                task = agent.get_structured_query(f"test query {i}")
                tasks.append(task)

            results = await asyncio.gather(*tasks)

            end_time = time.time()
            duration = end_time - start_time

            assert len(results) == 10
            assert duration < 5.0  # Should complete within 5 seconds

    def test_memory_usage(self):
        """Test memory usage doesn't grow excessively."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Create and destroy many agent instances
        for i in range(100):
            agent = QueryUnderstandingAgent()
            del agent

        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory

        # Memory growth should be reasonable (less than 50MB)
        assert memory_growth < 50 * 1024 * 1024


# Note: This file has been formatted for CI/CD compatibility with Unix line endings

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
