"""
Query Understanding Agent with enhanced error handling and logging.
"""

import json
import time
from typing import Dict, Any

import openai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..config import get_settings
from ..utils.logging import get_logger, log_error, log_agent_execution
from ..utils.exceptions import QueryUnderstandingError, ValidationError

settings = get_settings()
client = openai.OpenAI(
    api_key=settings.openai_api_key,
    timeout=settings.openai_timeout,
    max_retries=settings.openai_max_retries,
)
logger = get_logger(__name__)


class QueryUnderstandingAgent:
    """Enhanced Query Understanding Agent with production features."""

    def __init__(self) -> None:
        self.model = settings.openai_model
        self.logger = get_logger(f"{__name__}.QueryUnderstandingAgent")

    def validate_input(self, user_query: str) -> None:
        """Validate input parameters."""
        if not user_query or not isinstance(user_query, str):
            raise ValidationError("User query must be a non-empty string")

        if len(user_query.strip()) == 0:
            raise ValidationError("User query cannot be empty")

        if len(user_query) > 2000:  # Reasonable limit
            raise ValidationError("User query too long (max 2000 characters)")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError)),
    )
    def _call_openai_api(self, user_query: str) -> str:
        """Make API call to OpenAI with retry logic."""
        system_prompt = """
        You are an expert at understanding user requests for a DevOps AI assistant.
        Your task is to analyze the user's query and extract the core intent and any
        relevant entities. The output must be a JSON object with these keys: 'intent', 'entities', 'confidence'.

        Supported intents:
        - get_ci_cd_status: User wants to know about build/deployment status
        - investigate_incident: User reports a service issue or wants incident
          investigation
        - get_service_metrics: User wants metrics/monitoring data for a
          service
        - knowledge_query: User is asking for general information or
          documentation

        The 'intent' should be one of the supported intents above.
        The 'entities' should be a JSON object of key-value pairs.
        The 'confidence' should be a float between 0.0 and 1.0.
        If you cannot determine the intent, return intent as "unknown" with confidence < 0.5.

        Example:
        User Query: "Is the latest build passing for the checkout-service?"
        Output:
        {
          "intent": "get_ci_cd_status",
          "entities": {
            "service_name": "checkout-service",
            "build_type": "latest"
          },
          "confidence": 0.95
        }
        """

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            content = response.choices[0].message.content
            if not content:
                raise QueryUnderstandingError("Empty response from OpenAI API")
            return content
        except openai.RateLimitError as e:
            self.logger.warning("OpenAI rate limit hit, retrying", error=str(e))
            raise
        except openai.APITimeoutError as e:
            self.logger.warning("OpenAI API timeout, retrying", error=str(e))
            raise
        except Exception as e:
            log_error(self.logger, e, {"user_query": user_query[:100]})
            raise QueryUnderstandingError(f"OpenAI API call failed: {str(e)}")

    def get_structured_query(self, user_query: str) -> Dict[str, Any]:
        """
        Parse a user's natural language query into a structured JSON object.

        Args:
            user_query: The natural language query from the user

        Returns:
            Structured query with intent, entities, and metadata

        Raises:
            ValidationError: If input validation fails
            QueryUnderstandingError: If query processing fails
        """
        start_time = time.time()

        try:
            # Validate input
            self.validate_input(user_query)

            self.logger.info("Processing query", query_length=len(user_query))

            # Call OpenAI API
            response_content = self._call_openai_api(user_query)

            # Parse response
            try:
                structured_data = json.loads(response_content)
            except json.JSONDecodeError as e:
                log_error(self.logger, e, {"response_content": response_content})
                raise QueryUnderstandingError("Failed to parse LLM response as JSON")

            # Validate response structure
            required_fields = ["intent", "entities", "confidence"]
            missing_fields = [
                field for field in required_fields if field not in structured_data
            ]
            if missing_fields:
                raise QueryUnderstandingError(
                    f"LLM response missing fields: {missing_fields}"
                )

            # Add metadata
            structured_data.update(
                {
                    "original_query": user_query,
                    "model_used": self.model,
                    "processing_time_ms": (time.time() - start_time) * 1000,
                }
            )

            # Log successful execution
            duration_ms = (time.time() - start_time) * 1000
            log_agent_execution(
                self.logger,
                "QueryUnderstandingAgent",
                "get_structured_query",
                duration_ms,
                intent=structured_data.get("intent"),
                confidence=structured_data.get("confidence"),
            )

            return structured_data

        except (ValidationError, QueryUnderstandingError):
            raise
        except Exception as e:
            log_error(self.logger, e, {"user_query": user_query[:100]})
            raise QueryUnderstandingError(
                f"Unexpected error during query understanding: {str(e)}"
            )


# Global instance
query_understanding_agent = QueryUnderstandingAgent()


def get_structured_query(user_query: str) -> Dict[str, Any]:
    """Convenience function for backward compatibility."""
    return query_understanding_agent.get_structured_query(user_query)


if __name__ == "__main__":
    # Example usage for testing
    from ..utils.logging import configure_logging

    configure_logging(level="DEBUG", json_logs=False)

    agent = QueryUnderstandingAgent()

    test_queries = [
        "What caused the latency spike in the payment service?",
        "Is the latest build passing for the checkout-service?",
        "Show me the error rate for user-auth service",
        "How do I deploy to production?",
    ]

    for query in test_queries:
        try:
            result = agent.get_structured_query(query)
            print(f"Query: {query}")
            print(f"Result: {json.dumps(result, indent=2)}")
            print("-" * 50)
        except Exception as e:
            print(f"Error processing '{query}': {e}")
            print("-" * 50)
