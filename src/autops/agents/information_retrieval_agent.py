import json
import os
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Mock mode flag - set to True for demos without real API keys
USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "false").lower() == "true"


# Mock clients for demo purposes
class MockDatadogClient:
    def get_error_rate_metrics(self, service_name: str) -> dict:
        logger.info(f"MOCK: Fetching error rates for '{service_name}' from Datadog.")
        return {
            "service": service_name,
            "error_rate": "2.1%",
            "time_window_minutes": 60,
            "has_data": True,
            "data_points": 12,
            "max_error_rate": "3.5%",
            "min_error_rate": "0.8%",
        }


class MockPagerDutyClient:
    def get_active_incidents(self, service_name: str) -> dict:
        logger.info(
            f"MOCK: Fetching active incidents for '{service_name}' from PagerDuty."
        )
        return {
            "service": service_name,
            "total_incidents": 1,
            "incidents": [
                {
                    "id": "PINCIDENT123",
                    "title": f"High error rate on {service_name}",
                    "status": "acknowledged",
                    "urgency": "high",
                    "created_at": "2024-01-15T10:30:00Z",
                }
            ],
            "by_status": {"triggered": 0, "acknowledged": 1},
            "by_urgency": {"high": 1, "low": 0},
        }


class MockGitLabClient:
    def get_last_deployment(self, service_name: str) -> dict:
        logger.info(f"MOCK: Fetching last deployment for '{service_name}' from GitLab.")
        return {
            "service": service_name,
            "has_deployments": True,
            "deployment": {
                "id": "deploy-456",
                "status": "success",
                "created_at": "2024-01-15T09:45:00Z",
                "environment": "production",
                "ref": "main",
                "sha": "a1b2c3d4e5f6",
                "commit": {
                    "title": "fix: resolve payment processing timeout",
                    "author_name": "Jane Developer",
                    "short_id": "a1b2c3d",
                },
            },
        }


if USE_MOCK_DATA:
    # Use mock clients for demo
    datadog_client = MockDatadogClient()
    pagerduty_client = MockPagerDutyClient()
    gitlab_client = MockGitLabClient()
    logger.info("Using MOCK data clients for demo mode")
else:
    # Use real clients for production
    from ..tools import datadog_client, pagerduty_client, gitlab_client

    logger.info("Using REAL API clients for production mode")


# Agent class
class InformationRetrievalAgent:
    def __init__(self):
        self.datadog_client = datadog_client
        self.pagerduty_client = pagerduty_client
        self.gitlab_client = gitlab_client

    def gather_context(self, service_name: str) -> dict:
        """
        Gathers context about a service from various tools.
        """
        logger.info(
            f"AGENT LOG: InformationRetrievalAgent gathering context for "
            f"'{service_name}'."
        )

        # These now call either real or mock clients based on USE_MOCK_DATA flag
        error_metrics = self.datadog_client.get_error_rate_metrics(service_name)
        active_incidents = self.pagerduty_client.get_active_incidents(service_name)
        last_deployment = self.gitlab_client.get_last_deployment(service_name)

        return {
            "metrics": error_metrics,
            "incidents": active_incidents,
            "deployment": last_deployment,
        }


if __name__ == "__main__":
    agent = InformationRetrievalAgent()
    context = agent.gather_context("payment-service")
    print(json.dumps(context, indent=2))
