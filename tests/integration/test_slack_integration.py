"""Integration tests for Slack integration."""

import pytest
import json
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from autops.main import app


class TestSlackIntegration:
    """Integration tests for Slack webhook and interaction handling."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    @pytest.fixture
    def slack_event_payload(self):
        """Sample Slack event payload."""
        return {
            "token": "test-token",
            "team_id": "T123456",
            "api_app_id": "A123456",
            "event": {
                "type": "message",
                "user": "U123456",
                "text": "What's the CI status for main branch?",
                "ts": "1234567890.123456",
                "channel": "C123456",
                "channel_type": "channel",
            },
            "type": "event_callback",
            "event_id": "Ev123456",
            "event_time": 1234567890,
        }

    @pytest.fixture
    def slack_interaction_payload(self):
        """Sample Slack interactive component payload."""
        return {
            "type": "interactive_message",
            "actions": [
                {"name": "approve", "type": "button", "value": "deploy_prod_12345"}
            ],
            "callback_id": "approval_request",
            "team": {"id": "T123456", "domain": "test-team"},
            "channel": {"id": "C123456", "name": "deployments"},
            "user": {"id": "U123456", "name": "admin_user"},
            "message_ts": "1234567890.123456",
            "response_url": "https://hooks.slack.com/actions/123/456/789",
        }

    def test_slack_webhook_challenge(self, client):
        """Test Slack URL verification challenge."""
        challenge_payload = {
            "token": "test-token",
            "challenge": "test-challenge-string",
            "type": "url_verification",
        }

        response = client.post("/webhooks/slack", json=challenge_payload)

        assert response.status_code == 200
        assert response.json() == {"challenge": "test-challenge-string"}

    @patch("autops.main.orchestrator")
    def test_slack_message_event(self, mock_orchestrator, client, slack_event_payload):
        """Test handling of Slack message events."""
        mock_orchestrator.process_query.return_value = {
            "status": "success",
            "response": {
                "message": "✅ CI status: All checks passed",
                "confidence": 0.9,
            },
        }

        response = client.post("/webhooks/slack", json=slack_event_payload)

        assert response.status_code == 200
        mock_orchestrator.process_query.assert_called_once_with(
            "What's the CI status for main branch?",
            {"user": "U123456", "channel": "C123456", "timestamp": "1234567890.123456"},
        )

    @patch("autops.main.orchestrator")
    def test_slack_bot_mention(self, mock_orchestrator, client):
        """Test handling of bot mentions in Slack."""
        mention_payload = {
            "token": "test-token",
            "team_id": "T123456",
            "event": {
                "type": "app_mention",
                "user": "U123456",
                "text": "<@UBOT123> check deployment status",
                "ts": "1234567890.123456",
                "channel": "C123456",
            },
            "type": "event_callback",
        }

        mock_orchestrator.process_query.return_value = {
            "status": "success",
            "response": {
                "message": "🚀 Deployment status: In progress",
                "confidence": 0.85,
            },
        }

        response = client.post("/webhooks/slack", json=mention_payload)

        assert response.status_code == 200
        # Should process the mention without the bot tag
        mock_orchestrator.process_query.assert_called_once_with(
            "check deployment status",
            {"user": "U123456", "channel": "C123456", "timestamp": "1234567890.123456"},
        )

    @patch("autops.main.orchestrator")
    @patch("autops.tools.slack_client.SlackClient")
    def test_slack_approval_interaction(
        self, mock_slack_client, mock_orchestrator, client
    ):
        """Test handling of Slack approval button interactions."""
        # Mock Slack client
        mock_slack_instance = Mock()
        mock_slack_client.return_value = mock_slack_instance

        # Create form-encoded payload (as Slack sends it)
        interaction_payload = {
            "payload": json.dumps(
                {
                    "type": "interactive_message",
                    "actions": [
                        {
                            "name": "approve",
                            "type": "button",
                            "value": "deploy_prod_12345",
                        }
                    ],
                    "callback_id": "approval_request",
                    "user": {"id": "U123456", "name": "admin_user"},
                    "channel": {"id": "C123456"},
                    "message_ts": "1234567890.123456",
                }
            )
        }

        mock_orchestrator.handle_approval.return_value = {
            "status": "approved",
            "message": "✅ Production deployment approved and initiated",
        }

        response = client.post("/webhooks/slack/interactive", data=interaction_payload)

        assert response.status_code == 200
        mock_orchestrator.handle_approval.assert_called_once_with(
            "deploy_prod_12345", "U123456", True  # approved
        )

    @patch("autops.main.orchestrator")
    def test_slack_error_handling(self, mock_orchestrator, client, slack_event_payload):
        """Test error handling in Slack webhook."""
        mock_orchestrator.process_query.side_effect = Exception("Processing error")

        response = client.post("/webhooks/slack", json=slack_event_payload)

        assert response.status_code == 200  # Still return 200 to Slack
        # Should log the error but not crash

    def test_slack_invalid_payload(self, client):
        """Test handling of invalid Slack payloads."""
        invalid_payload = {"invalid": "data"}

        response = client.post("/webhooks/slack", json=invalid_payload)

        # Should handle gracefully
        assert response.status_code in [200, 400]

    @patch("autops.tools.slack_client.SlackClient")
    def test_slack_rate_limiting(self, mock_slack_client, client):
        """Test handling of Slack rate limiting."""
        mock_slack_instance = Mock()
        mock_slack_instance.send_message.side_effect = Exception("Rate limited")
        mock_slack_client.return_value = mock_slack_instance

        payload = {
            "token": "test-token",
            "event": {
                "type": "message",
                "user": "U123456",
                "text": "test message",
                "channel": "C123456",
            },
            "type": "event_callback",
        }

        response = client.post("/webhooks/slack", json=payload)

        # Should handle rate limiting gracefully
        assert response.status_code == 200

    @patch("autops.main.orchestrator")
    def test_slack_direct_message(self, mock_orchestrator, client):
        """Test handling of direct messages to the bot."""
        dm_payload = {
            "token": "test-token",
            "event": {
                "type": "message",
                "user": "U123456",
                "text": "Help me debug the API issues",
                "ts": "1234567890.123456",
                "channel": "D123456",  # Direct message channel
                "channel_type": "im",
            },
            "type": "event_callback",
        }

        mock_orchestrator.process_query.return_value = {
            "status": "success",
            "response": {
                "message": "🔍 I'll help you debug the API issues. Let me check the logs.",
                "confidence": 0.9,
            },
        }

        response = client.post("/webhooks/slack", json=dm_payload)

        assert response.status_code == 200
        mock_orchestrator.process_query.assert_called_once()

    @patch("autops.main.orchestrator")
    def test_slack_thread_reply(self, mock_orchestrator, client):
        """Test handling of thread replies in Slack."""
        thread_payload = {
            "token": "test-token",
            "event": {
                "type": "message",
                "user": "U123456",
                "text": "Can you get more details on that incident?",
                "ts": "1234567890.123456",
                "channel": "C123456",
                "thread_ts": "1234567880.123456",  # Reply to thread
            },
            "type": "event_callback",
        }

        mock_orchestrator.process_query.return_value = {
            "status": "success",
            "response": {
                "message": "📊 Here are the detailed incident metrics...",
                "confidence": 0.8,
            },
        }

        response = client.post("/webhooks/slack", json=thread_payload)

        assert response.status_code == 200
        # Should include thread context
        call_args = mock_orchestrator.process_query.call_args
        context = call_args[0][1]
        assert "thread_ts" in context

    @patch("autops.main.orchestrator")
    def test_slack_file_upload_event(self, mock_orchestrator, client):
        """Test handling of file upload events in Slack."""
        file_upload_payload = {
            "token": "test-token",
            "event": {
                "type": "message",
                "subtype": "file_share",
                "user": "U123456",
                "text": "Here are the logs from the incident",
                "files": [
                    {
                        "id": "F123456",
                        "name": "incident_logs.txt",
                        "url_private": "https://files.slack.com/files-pri/123/456",
                    }
                ],
                "ts": "1234567890.123456",
                "channel": "C123456",
            },
            "type": "event_callback",
        }

        mock_orchestrator.process_query.return_value = {
            "status": "success",
            "response": {
                "message": "📁 I've received the log file. Analyzing for issues...",
                "confidence": 0.9,
            },
        }

        response = client.post("/webhooks/slack", json=file_upload_payload)

        assert response.status_code == 200
        # Should include file information in context
        call_args = mock_orchestrator.process_query.call_args
        context = call_args[0][1]
        assert "files" in context
