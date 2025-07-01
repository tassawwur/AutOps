"""Tests for the Tool Execution Agent."""

import pytest
from unittest.mock import Mock, patch
from autops.agents.tool_execution_agent import ToolExecutionAgent
from autops.utils.exceptions import ToolExecutionError, ValidationError


class TestToolExecutionAgent:
    """Test suite for ToolExecutionAgent."""

    @pytest.fixture
    def agent(self):
        """Create a ToolExecutionAgent instance for testing."""
        return ToolExecutionAgent()

    @pytest.fixture
    def sample_step(self):
        """Sample execution step."""
        return {
            "action": "check_ci_status",
            "tool": "github",
            "parameters": {"repo": "test/repo", "branch": "main"},
            "description": "Check CI status for main branch",
        }

    @pytest.mark.asyncio
    async def test_execute_step_success(self, agent, sample_step):
        """Test successful step execution."""
        with patch.object(agent, "_execute_github_action") as mock_github:
            mock_github.return_value = {
                "status": "success",
                "data": {"ci_status": "passed"},
            }

            result = await agent.execute_step(sample_step)

            assert result["status"] == "success"
            assert "data" in result
            mock_github.assert_called_once_with(
                "check_ci_status", sample_step["parameters"]
            )

    @pytest.mark.asyncio
    async def test_execute_step_unknown_tool(self, agent):
        """Test execution with unknown tool."""
        step = {"action": "test_action", "tool": "unknown_tool", "parameters": {}}

        with pytest.raises(ToolExecutionError, match="Unknown tool: unknown_tool"):
            await agent.execute_step(step)

    @pytest.mark.asyncio
    async def test_execute_step_missing_parameters(self, agent):
        """Test execution with missing parameters."""
        step = {
            "action": "check_ci_status",
            "tool": "github",
            # Missing parameters
        }

        with pytest.raises(ValidationError, match="Step must contain parameters"):
            await agent.execute_step(step)

    @pytest.mark.asyncio
    async def test_execute_github_action_success(self, agent):
        """Test GitHub action execution."""
        action = "check_ci_status"
        parameters = {"repo": "test/repo", "branch": "main"}

        with patch("autops.tools.github_client.GitHubClient") as mock_client:
            mock_instance = Mock()
            mock_instance.get_workflow_runs.return_value = [
                {"status": "completed", "conclusion": "success"}
            ]
            mock_client.return_value = mock_instance

            result = await agent._execute_github_action(action, parameters)

            assert result["status"] == "success"
            assert "workflow_runs" in result["data"]

    @pytest.mark.asyncio
    async def test_execute_datadog_action_success(self, agent):
        """Test Datadog action execution."""
        action = "get_metrics"
        parameters = {"metric": "cpu.usage", "timeframe": "1h"}

        with patch("autops.tools.datadog_client.DatadogClient") as mock_client:
            mock_instance = Mock()
            mock_instance.get_metric.return_value = {
                "series": [{"metric": "cpu.usage", "points": [[1234567890, 75.5]]}]
            }
            mock_client.return_value = mock_instance

            result = await agent._execute_datadog_action(action, parameters)

            assert result["status"] == "success"
            assert "metrics" in result["data"]

    @pytest.mark.asyncio
    async def test_execute_slack_action_success(self, agent):
        """Test Slack action execution."""
        action = "send_message"
        parameters = {"channel": "#general", "message": "Test message"}

        with patch("autops.tools.slack_client.SlackClient") as mock_client:
            mock_instance = Mock()
            mock_instance.send_message.return_value = {
                "ok": True,
                "ts": "1234567890.123",
            }
            mock_client.return_value = mock_instance

            result = await agent._execute_slack_action(action, parameters)

            assert result["status"] == "success"
            assert "message_ts" in result["data"]

    @pytest.mark.asyncio
    async def test_execute_pagerduty_action_success(self, agent):
        """Test PagerDuty action execution."""
        action = "get_incidents"
        parameters = {"status": "open", "limit": 10}

        with patch("autops.tools.pagerduty_client.PagerDutyClient") as mock_client:
            mock_instance = Mock()
            mock_instance.get_incidents.return_value = {
                "incidents": [{"id": "123", "title": "Test incident"}]
            }
            mock_client.return_value = mock_instance

            result = await agent._execute_pagerduty_action(action, parameters)

            assert result["status"] == "success"
            assert "incidents" in result["data"]

    @pytest.mark.asyncio
    async def test_execute_step_with_retry(self, agent, sample_step):
        """Test step execution with retry mechanism."""
        with patch.object(agent, "_execute_github_action") as mock_github:
            # First call fails, second succeeds
            mock_github.side_effect = [
                Exception("Temporary failure"),
                {"status": "success", "data": {"ci_status": "passed"}},
            ]

            result = await agent.execute_step(sample_step)

            assert result["status"] == "success"
            assert mock_github.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_step_max_retries_exceeded(self, agent, sample_step):
        """Test step execution when max retries are exceeded."""
        with patch.object(agent, "_execute_github_action") as mock_github:
            mock_github.side_effect = Exception("Persistent failure")

            with pytest.raises(
                ToolExecutionError, match="Failed to execute step after 3 attempts"
            ):
                await agent.execute_step(sample_step)

            assert mock_github.call_count == 3

    @pytest.mark.asyncio
    async def test_validate_step_parameters_github(self, agent):
        """Test parameter validation for GitHub actions."""
        # Valid parameters
        valid_params = {"repo": "test/repo", "branch": "main"}
        assert agent._validate_step_parameters(
            "github", "check_ci_status", valid_params
        )

        # Invalid parameters - missing repo
        invalid_params = {"branch": "main"}
        assert not agent._validate_step_parameters(
            "github", "check_ci_status", invalid_params
        )

    @pytest.mark.asyncio
    async def test_validate_step_parameters_datadog(self, agent):
        """Test parameter validation for Datadog actions."""
        # Valid parameters
        valid_params = {"metric": "cpu.usage", "timeframe": "1h"}
        assert agent._validate_step_parameters("datadog", "get_metrics", valid_params)

        # Invalid parameters - missing metric
        invalid_params = {"timeframe": "1h"}
        assert not agent._validate_step_parameters(
            "datadog", "get_metrics", invalid_params
        )

    @pytest.mark.asyncio
    async def test_execute_step_timeout(self, agent, sample_step):
        """Test step execution with timeout."""
        with patch.object(agent, "_execute_github_action") as mock_github:
            mock_github.side_effect = TimeoutError("Request timeout")

            with pytest.raises(
                ToolExecutionError, match="Failed to execute step after 3 attempts"
            ):
                await agent.execute_step(sample_step)

    @pytest.mark.asyncio
    async def test_execute_multiple_steps(self, agent):
        """Test execution of multiple steps."""
        steps = [
            {
                "action": "check_ci_status",
                "tool": "github",
                "parameters": {"repo": "test/repo"},
            },
            {
                "action": "get_metrics",
                "tool": "datadog",
                "parameters": {"metric": "cpu.usage", "timeframe": "1h"},
            },
        ]

        with (
            patch.object(agent, "_execute_github_action") as mock_github,
            patch.object(agent, "_execute_datadog_action") as mock_datadog,
        ):
            mock_github.return_value = {
                "status": "success",
                "data": {"ci_status": "passed"},
            }
            mock_datadog.return_value = {"status": "success", "data": {"metrics": []}}

            results = []
            for step in steps:
                result = await agent.execute_step(step)
                results.append(result)

            assert len(results) == 2
            assert all(r["status"] == "success" for r in results)
            mock_github.assert_called_once()
            mock_datadog.assert_called_once()
