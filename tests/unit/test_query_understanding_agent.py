"""
Unit tests for Query Understanding Agent.
"""
import pytest
from unittest.mock import Mock, patch
import json

from src.autops.agents.query_understanding_agent import QueryUnderstandingAgent
from src.autops.utils.exceptions import ValidationError, QueryUnderstandingError


class TestQueryUnderstandingAgent:
    """Test cases for Query Understanding Agent."""

    @pytest.fixture
    def agent(self, test_settings):
        """Create agent instance for testing."""
        with patch(
            "src.autops.agents.query_understanding_agent.get_settings",
            return_value=test_settings,
        ):
            return QueryUnderstandingAgent()

    def test_validate_input_valid_query(self, agent):
        """Test input validation with valid query."""
        # Should not raise any exception
        agent.validate_input("Is the build passing?")

    def test_validate_input_empty_string(self, agent):
        """Test input validation with empty string."""
        with pytest.raises(ValidationError, match="User query cannot be empty"):
            agent.validate_input("")

    def test_validate_input_whitespace_only(self, agent):
        """Test input validation with whitespace only."""
        with pytest.raises(ValidationError, match="User query cannot be empty"):
            agent.validate_input("   ")

    def test_validate_input_none(self, agent):
        """Test input validation with None."""
        with pytest.raises(
            ValidationError, match="User query must be a non-empty string"
        ):
            agent.validate_input(None)

    def test_validate_input_too_long(self, agent):
        """Test input validation with overly long query."""
        long_query = "x" * 2001
        with pytest.raises(ValidationError, match="User query too long"):
            agent.validate_input(long_query)

    @patch("src.autops.agents.query_understanding_agent.client")
    def test_get_structured_query_success(self, mock_client, agent):
        """Test successful query understanding."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content=json.dumps(
                        {
                            "intent": "get_ci_cd_status",
                            "entities": {"service_name": "test-service"},
                            "confidence": 0.9,
                        }
                    )
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        result = agent.get_structured_query("Is the build passing for test-service?")

        assert result["intent"] == "get_ci_cd_status"
        assert result["entities"]["service_name"] == "test-service"
        assert result["confidence"] == 0.9
        assert result["original_query"] == "Is the build passing for test-service?"
        assert "processing_time_ms" in result
        assert "model_used" in result

    @patch("src.autops.agents.query_understanding_agent.client")
    def test_get_structured_query_invalid_json(self, mock_client, agent):
        """Test handling of invalid JSON response."""
        # Mock OpenAI response with invalid JSON
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="invalid json"))]
        mock_client.chat.completions.create.return_value = mock_response

        with pytest.raises(
            QueryUnderstandingError, match="Failed to parse LLM response as JSON"
        ):
            agent.get_structured_query("Test query")

    @patch("src.autops.agents.query_understanding_agent.client")
    def test_get_structured_query_missing_fields(self, mock_client, agent):
        """Test handling of response missing required fields."""
        # Mock OpenAI response missing required fields
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content=json.dumps({"intent": "test"})))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        with pytest.raises(
            QueryUnderstandingError, match="LLM response missing fields"
        ):
            agent.get_structured_query("Test query")

    @patch("src.autops.agents.query_understanding_agent.client")
    def test_api_timeout_retry(self, mock_client, agent):
        """Test retry logic for API timeouts."""
        import openai

        # First call times out, second succeeds
        mock_client.chat.completions.create.side_effect = [
            openai.APITimeoutError("Timeout"),
            Mock(
                choices=[
                    Mock(
                        message=Mock(
                            content=json.dumps(
                                {
                                    "intent": "test_intent",
                                    "entities": {},
                                    "confidence": 0.8,
                                }
                            )
                        )
                    )
                ]
            ),
        ]

        result = agent.get_structured_query("Test query")
        assert result["intent"] == "test_intent"
        assert mock_client.chat.completions.create.call_count == 2

    @patch("src.autops.agents.query_understanding_agent.client")
    def test_api_rate_limit_retry(self, mock_client, agent):
        """Test retry logic for rate limits."""
        import openai

        # First call hits rate limit, second succeeds
        mock_client.chat.completions.create.side_effect = [
            openai.RateLimitError("Rate limit exceeded"),
            Mock(
                choices=[
                    Mock(
                        message=Mock(
                            content=json.dumps(
                                {
                                    "intent": "test_intent",
                                    "entities": {},
                                    "confidence": 0.8,
                                }
                            )
                        )
                    )
                ]
            ),
        ]

        result = agent.get_structured_query("Test query")
        assert result["intent"] == "test_intent"
        assert mock_client.chat.completions.create.call_count == 2

    @patch("src.autops.agents.query_understanding_agent.client")
    def test_api_general_error(self, mock_client, agent):
        """Test handling of general API errors."""
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        with pytest.raises(QueryUnderstandingError, match="OpenAI API call failed"):
            agent.get_structured_query("Test query")

    def test_supported_intents(self, agent):
        """Test that all supported intents are handled correctly."""
        supported_intents = [
            "get_ci_cd_status",
            "investigate_incident",
            "get_service_metrics",
            "knowledge_query",
        ]

        with patch("src.autops.agents.query_understanding_agent.client") as mock_client:
            for intent in supported_intents:
                mock_response = Mock()
                mock_response.choices = [
                    Mock(
                        message=Mock(
                            content=json.dumps(
                                {"intent": intent, "entities": {}, "confidence": 0.9}
                            )
                        )
                    )
                ]
                mock_client.chat.completions.create.return_value = mock_response

                result = agent.get_structured_query(f"Test query for {intent}")
                assert result["intent"] == intent
