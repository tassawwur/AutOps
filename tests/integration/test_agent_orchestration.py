"""Integration tests for agent orchestration."""

import pytest
import asyncio
from unittest.mock import patch
from autops.main import AgentOrchestrator
from autops.config import Settings


class TestAgentOrchestration:
    """Integration tests for the full agent workflow."""

    @pytest.fixture
    def settings(self):
        """Test settings."""
        return Settings(
            openai_api_key="test-key",
            github_token="test-token",
            slack_bot_token="test-token",
            datadog_api_key="test-key",
            datadog_app_key="test-key",
            pagerduty_api_key="test-key",
        )

    @pytest.fixture
    def orchestrator(self, settings):
        """Create an orchestrator instance."""
        return AgentOrchestrator(settings)

    @pytest.mark.asyncio
    async def test_full_query_workflow_ci_status(self, orchestrator):
        """Test the complete workflow for checking CI status."""
        query = "What's the status of our main branch CI?"
        context = {"user": "test_user", "channel": "general"}

        # Mock all the agent responses
        with patch.object(
            orchestrator.query_agent, "understand_query"
        ) as mock_understand, patch.object(
            orchestrator.planning_agent, "create_plan"
        ) as mock_plan, patch.object(
            orchestrator.execution_agent, "execute_step"
        ) as mock_execute, patch.object(
            orchestrator.response_agent, "generate_response"
        ) as mock_response:
            # Mock query understanding
            mock_understand.return_value = {
                "intent": "check_ci_status",
                "entities": {"repository": "main_repo", "branch": "main"},
                "confidence": 0.9,
            }

            # Mock planning
            mock_plan.return_value = {
                "steps": [
                    {
                        "action": "check_ci_status",
                        "tool": "github",
                        "parameters": {"repo": "main_repo", "branch": "main"},
                    }
                ],
                "estimated_duration": "30 seconds",
            }

            # Mock execution
            mock_execute.return_value = {
                "status": "success",
                "data": {
                    "workflow_runs": [
                        {"status": "completed", "conclusion": "success", "name": "CI"}
                    ]
                },
            }

            # Mock response generation
            mock_response.return_value = {
                "message": "✅ CI status for main branch: All checks passed",
                "confidence": 0.95,
                "suggested_actions": [],
            }

            # Execute the full workflow
            result = await orchestrator.process_query(query, context)

            # Verify the workflow executed correctly
            assert result["status"] == "success"
            assert "CI status for main branch" in result["response"]["message"]

            # Verify all agents were called
            mock_understand.assert_called_once_with(query, context)
            mock_plan.assert_called_once()
            mock_execute.assert_called_once()
            mock_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_query_workflow_anomaly_detection(self, orchestrator):
        """Test the complete workflow for anomaly detection and remediation."""
        query = "Check if there are any performance anomalies and fix them"
        context = {"user": "admin_user", "channel": "alerts"}

        with patch.object(
            orchestrator.query_agent, "understand_query"
        ) as mock_understand, patch.object(
            orchestrator.planning_agent, "create_plan"
        ) as mock_plan, patch.object(
            orchestrator.execution_agent, "execute_step"
        ) as mock_execute, patch.object(
            orchestrator.response_agent, "generate_response"
        ) as mock_response:
            mock_understand.return_value = {
                "intent": "detect_and_remediate_anomalies",
                "entities": {"metric_type": "performance"},
                "confidence": 0.85,
            }

            mock_plan.return_value = {
                "steps": [
                    {
                        "action": "get_metrics",
                        "tool": "datadog",
                        "parameters": {"metric": "cpu.usage", "timeframe": "1h"},
                    },
                    {
                        "action": "analyze_anomalies",
                        "tool": "datadog",
                        "parameters": {"threshold": 80},
                    },
                    {
                        "action": "request_approval",
                        "tool": "slack",
                        "parameters": {"action": "scale_up", "reason": "high_cpu"},
                    },
                ],
                "estimated_duration": "5 minutes",
            }

            # Mock multiple execution steps
            mock_execute.side_effect = [
                {
                    "status": "success",
                    "data": {"metrics": [{"timestamp": 1234567890, "value": 85}]},
                },
                {
                    "status": "success",
                    "data": {"anomalies_detected": True, "severity": "high"},
                },
                {
                    "status": "success",
                    "data": {"approval_requested": True, "message_ts": "123.456"},
                },
            ]

            mock_response.return_value = {
                "message": "🚨 Performance anomaly detected: High CPU usage (85%). Approval requested for scaling.",
                "confidence": 0.9,
                "suggested_actions": ["scale_up", "investigate_processes"],
            }

            result = await orchestrator.process_query(query, context)

            assert result["status"] == "success"
            assert "anomaly detected" in result["response"]["message"].lower()
            assert mock_execute.call_count == 3  # Three steps executed

    @pytest.mark.asyncio
    async def test_error_handling_planning_failure(self, orchestrator):
        """Test error handling when planning fails."""
        query = "Invalid query that can't be planned"
        context = {"user": "test_user", "channel": "general"}

        with patch.object(
            orchestrator.query_agent, "understand_query"
        ) as mock_understand, patch.object(
            orchestrator.planning_agent, "create_plan"
        ) as mock_plan:
            mock_understand.return_value = {
                "intent": "unknown",
                "entities": {},
                "confidence": 0.3,
            }

            mock_plan.side_effect = Exception("Planning failed")

            result = await orchestrator.process_query(query, context)

            assert result["status"] == "error"
            assert "planning failed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_error_handling_execution_failure(self, orchestrator):
        """Test error handling when execution fails."""
        query = "Check CI status"
        context = {"user": "test_user", "channel": "general"}

        with patch.object(
            orchestrator.query_agent, "understand_query"
        ) as mock_understand, patch.object(
            orchestrator.planning_agent, "create_plan"
        ) as mock_plan, patch.object(
            orchestrator.execution_agent, "execute_step"
        ) as mock_execute:
            mock_understand.return_value = {
                "intent": "check_ci_status",
                "entities": {"repository": "test_repo"},
                "confidence": 0.9,
            }

            mock_plan.return_value = {
                "steps": [
                    {
                        "action": "check_ci_status",
                        "tool": "github",
                        "parameters": {"repo": "test_repo"},
                    }
                ]
            }

            mock_execute.side_effect = Exception("Execution failed")

            result = await orchestrator.process_query(query, context)

            assert result["status"] == "error"
            assert "execution failed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_concurrent_query_processing(self, orchestrator):
        """Test handling of concurrent queries."""
        queries = [
            ("Check CI status", {"user": "user1", "channel": "dev"}),
            ("Get CPU metrics", {"user": "user2", "channel": "ops"}),
            ("List open incidents", {"user": "user3", "channel": "alerts"}),
        ]

        with patch.object(
            orchestrator.query_agent, "understand_query"
        ) as mock_understand, patch.object(
            orchestrator.planning_agent, "create_plan"
        ) as mock_plan, patch.object(
            orchestrator.execution_agent, "execute_step"
        ) as mock_execute, patch.object(
            orchestrator.response_agent, "generate_response"
        ) as mock_response:
            # Mock successful responses for all queries
            mock_understand.return_value = {
                "intent": "test",
                "entities": {},
                "confidence": 0.9,
            }
            mock_plan.return_value = {
                "steps": [{"action": "test", "tool": "github", "parameters": {}}]
            }
            mock_execute.return_value = {"status": "success", "data": {}}
            mock_response.return_value = {"message": "Success", "confidence": 0.9}

            # Process queries concurrently
            tasks = [
                orchestrator.process_query(query, context) for query, context in queries
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All queries should succeed
            assert len(results) == 3
            assert all(
                isinstance(r, dict) and r["status"] == "success" for r in results
            )

    @pytest.mark.asyncio
    async def test_human_approval_workflow(self, orchestrator):
        """Test workflow that requires human approval."""
        query = "Deploy to production"
        context = {"user": "dev_user", "channel": "deployments"}

        with patch.object(
            orchestrator.query_agent, "understand_query"
        ) as mock_understand, patch.object(
            orchestrator.planning_agent, "create_plan"
        ) as mock_plan, patch.object(
            orchestrator.execution_agent, "execute_step"
        ) as mock_execute, patch.object(
            orchestrator.response_agent, "generate_response"
        ) as mock_response:
            mock_understand.return_value = {
                "intent": "deploy",
                "entities": {"environment": "production"},
                "confidence": 0.95,
            }

            mock_plan.return_value = {
                "steps": [
                    {
                        "action": "request_approval",
                        "tool": "slack",
                        "parameters": {
                            "action": "deploy_production",
                            "requester": "dev_user",
                            "environment": "production",
                        },
                    }
                ],
                "requires_approval": True,
            }

            mock_execute.return_value = {
                "status": "pending_approval",
                "data": {"approval_id": "12345", "message_ts": "123.456"},
            }

            mock_response.return_value = {
                "message": "🚀 Production deployment requested. Waiting for approval.",
                "confidence": 0.95,
                "approval_required": True,
            }

            result = await orchestrator.process_query(query, context)

            assert result["status"] == "pending_approval"
            assert "waiting for approval" in result["response"]["message"].lower()

    @pytest.mark.asyncio
    async def test_knowledge_gap_handling(self, orchestrator):
        """Test handling of queries with knowledge gaps."""
        query = "What caused the outage last Tuesday?"
        context = {"user": "sre_user", "channel": "incidents"}

        with patch.object(
            orchestrator.query_agent, "understand_query"
        ) as mock_understand, patch.object(
            orchestrator.info_retrieval_agent, "search_knowledge_base"
        ) as mock_search, patch.object(
            orchestrator.response_agent, "generate_response"
        ) as mock_response:
            mock_understand.return_value = {
                "intent": "investigate_outage",
                "entities": {"timeframe": "last Tuesday"},
                "confidence": 0.8,
                "requires_knowledge_search": True,
            }

            mock_search.return_value = {
                "relevant_docs": [
                    {"title": "Incident Report - Database Outage", "content": "..."},
                    {"title": "Post-mortem Analysis", "content": "..."},
                ],
                "confidence": 0.85,
            }

            mock_response.return_value = {
                "message": "Based on incident reports, last Tuesday's outage was caused by database connection issues.",
                "confidence": 0.85,
                "sources": [
                    "Incident Report - Database Outage",
                    "Post-mortem Analysis",
                ],
            }

            result = await orchestrator.process_query(query, context)

            assert result["status"] == "success"
            assert "database connection issues" in result["response"]["message"]
            assert "sources" in result["response"]
