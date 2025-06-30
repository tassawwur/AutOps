"""
PagerDuty API Client for incident management and on-call information.
"""
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

import pdpyras
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..config import get_settings
from ..utils.logging import get_logger, log_error, log_agent_execution
from ..utils.exceptions import PagerDutyAPIError, ValidationError

settings = get_settings()
logger = get_logger(__name__)


class PagerDutyClient:
    """
    Production-ready PagerDuty API client for incident management and on-call data.
    """

    def __init__(self):
        self.logger = get_logger(f"{__name__}.PagerDutyClient")

        # Initialize PagerDuty API session
        self.session = pdpyras.APISession(settings.pagerduty_api_key)
        self.session.headers.update({"From": settings.pagerduty_email})

    def validate_service_name(self, service_name: str) -> None:
        """Validate service name parameter."""
        if not service_name or not isinstance(service_name, str):
            raise ValidationError("Service name must be a non-empty string")

        if len(service_name.strip()) == 0:
            raise ValidationError("Service name cannot be empty")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(pdpyras.PDClientError),
    )
    def get_active_incidents(self, service_name: str = None) -> Dict[str, Any]:
        """
        Get active incidents from PagerDuty, optionally filtered by service.

        Args:
            service_name: Optional service name to filter incidents

        Returns:
            Dictionary containing active incidents

        Raises:
            PagerDutyAPIError: If API call fails
            ValidationError: If input validation fails
        """
        start_time = time.time()

        try:
            if service_name:
                self.validate_service_name(service_name)

            self.logger.info("Fetching active incidents", service=service_name)

            # Build query parameters
            params = {
                "statuses[]": ["triggered", "acknowledged"],
                "sort_by": "created_at:desc",
                "limit": 100,
            }

            # If service name provided, find the service ID first
            service_id = None
            if service_name:
                service_id = self._find_service_by_name(service_name)
                if service_id:
                    params["service_ids[]"] = [service_id]

            try:
                response = self.session.list_all("incidents", params=params)

                incidents_data = {
                    "service": service_name,
                    "query_time": datetime.now().isoformat(),
                    "incidents": [],
                    "total_incidents": 0,
                    "by_status": {"triggered": 0, "acknowledged": 0},
                    "by_urgency": {"high": 0, "low": 0},
                }

                if response:
                    incidents_data["total_incidents"] = len(response)

                    for incident in response:
                        incident_info = {
                            "id": incident.get("id"),
                            "incident_number": incident.get("incident_number"),
                            "title": incident.get("title"),
                            "status": incident.get("status"),
                            "urgency": incident.get("urgency"),
                            "created_at": incident.get("created_at"),
                            "service": incident.get("service", {}).get(
                                "summary", "Unknown"
                            ),
                            "assigned_to": [],
                        }

                        # Extract assignees
                        assignments = incident.get("assignments", [])
                        for assignment in assignments:
                            assignee = assignment.get("assignee", {})
                            incident_info["assigned_to"].append(
                                {
                                    "name": assignee.get("summary", "Unknown"),
                                    "type": assignee.get("type", "user"),
                                }
                            )

                        incidents_data["incidents"].append(incident_info)

                        # Count by status and urgency
                        status = incident.get("status", "unknown")
                        if status in incidents_data["by_status"]:
                            incidents_data["by_status"][status] += 1

                        urgency = incident.get("urgency", "unknown")
                        if urgency in incidents_data["by_urgency"]:
                            incidents_data["by_urgency"][urgency] += 1

                # Log execution
                duration_ms = (time.time() - start_time) * 1000
                log_agent_execution(
                    self.logger,
                    "PagerDutyClient",
                    "get_active_incidents",
                    duration_ms,
                    service=service_name,
                    incidents_count=incidents_data["total_incidents"],
                )

                return incidents_data

            except pdpyras.PDClientError as e:
                self.logger.warning("PagerDuty API error, retrying", error=str(e))
                raise

        except ValidationError:
            raise
        except Exception as e:
            log_error(self.logger, e, {"service": service_name})
            raise PagerDutyAPIError(f"Failed to fetch active incidents: {str(e)}")

    def _find_service_by_name(self, service_name: str) -> Optional[str]:
        """
        Find PagerDuty service ID by name.

        Args:
            service_name: Name of the service to find

        Returns:
            Service ID if found, None otherwise
        """
        try:
            services = self.session.list_all("services", params={"query": service_name})

            # Look for exact match first
            for service in services:
                if service.get("name", "").lower() == service_name.lower():
                    return service.get("id")

            # Look for partial match
            for service in services:
                if service_name.lower() in service.get("name", "").lower():
                    return service.get("id")

            self.logger.warning("Service not found in PagerDuty", service=service_name)
            return None

        except Exception as e:
            self.logger.warning(
                "Failed to find service", service=service_name, error=str(e)
            )
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(pdpyras.PDClientError),
    )
    def get_oncall_users(self, service_name: str = None) -> Dict[str, Any]:
        """
        Get current on-call users, optionally filtered by service.

        Args:
            service_name: Optional service name to filter on-call users

        Returns:
            Dictionary containing on-call users
        """
        start_time = time.time()

        try:
            if service_name:
                self.validate_service_name(service_name)

            self.logger.info("Fetching on-call users", service=service_name)

            params = {}
            if service_name:
                service_id = self._find_service_by_name(service_name)
                if service_id:
                    params["service_ids[]"] = [service_id]

            try:
                response = self.session.list_all("oncalls", params=params)

                oncall_data = {
                    "service": service_name,
                    "query_time": datetime.now().isoformat(),
                    "oncall_users": [],
                    "total_oncall": 0,
                    "by_level": {"1": 0, "2": 0, "3": 0, "other": 0},
                }

                if response:
                    oncall_data["total_oncall"] = len(response)

                    for oncall in response:
                        user = oncall.get("user", {})
                        escalation_policy = oncall.get("escalation_policy", {})

                        oncall_info = {
                            "user_name": user.get("summary", "Unknown"),
                            "user_email": user.get("email", ""),
                            "escalation_policy": escalation_policy.get(
                                "summary", "Unknown"
                            ),
                            "escalation_level": oncall.get("escalation_level", 1),
                            "start": oncall.get("start"),
                            "end": oncall.get("end"),
                        }

                        oncall_data["oncall_users"].append(oncall_info)

                        # Count by escalation level
                        level = str(oncall.get("escalation_level", 1))
                        if level in oncall_data["by_level"]:
                            oncall_data["by_level"][level] += 1
                        else:
                            oncall_data["by_level"]["other"] += 1

                # Log execution
                duration_ms = (time.time() - start_time) * 1000
                log_agent_execution(
                    self.logger,
                    "PagerDutyClient",
                    "get_oncall_users",
                    duration_ms,
                    service=service_name,
                    oncall_count=oncall_data["total_oncall"],
                )

                return oncall_data

            except pdpyras.PDClientError as e:
                self.logger.warning("PagerDuty API error, retrying", error=str(e))
                raise

        except Exception as e:
            log_error(self.logger, e, {"service": service_name})
            raise PagerDutyAPIError(f"Failed to fetch on-call users: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(pdpyras.PDClientError),
    )
    def get_recent_incidents(
        self, service_name: str = None, days: int = 7
    ) -> Dict[str, Any]:
        """
        Get recent incidents from PagerDuty.

        Args:
            service_name: Optional service name to filter incidents
            days: Number of days to look back

        Returns:
            Dictionary containing recent incidents
        """
        start_time = time.time()

        try:
            if service_name:
                self.validate_service_name(service_name)

            self.logger.info(
                "Fetching recent incidents", service=service_name, days=days
            )

            # Calculate time range
            since = (datetime.now() - timedelta(days=days)).isoformat()

            params = {"since": since, "sort_by": "created_at:desc", "limit": 100}

            # If service name provided, find the service ID first
            if service_name:
                service_id = self._find_service_by_name(service_name)
                if service_id:
                    params["service_ids[]"] = [service_id]

            try:
                response = self.session.list_all("incidents", params=params)

                incidents_data = {
                    "service": service_name,
                    "days": days,
                    "query_time": datetime.now().isoformat(),
                    "incidents": [],
                    "total_incidents": 0,
                    "by_status": {},
                    "by_urgency": {},
                    "resolution_times": [],
                }

                if response:
                    incidents_data["total_incidents"] = len(response)

                    for incident in response[:20]:  # Limit to 20 most recent
                        incident_info = {
                            "id": incident.get("id"),
                            "incident_number": incident.get("incident_number"),
                            "title": incident.get("title"),
                            "status": incident.get("status"),
                            "urgency": incident.get("urgency"),
                            "created_at": incident.get("created_at"),
                            "resolved_at": incident.get("resolved_at"),
                            "service": incident.get("service", {}).get(
                                "summary", "Unknown"
                            ),
                        }

                        # Calculate resolution time if resolved
                        if incident.get("resolved_at") and incident.get("created_at"):
                            created = datetime.fromisoformat(
                                incident["created_at"].replace("Z", "+00:00")
                            )
                            resolved = datetime.fromisoformat(
                                incident["resolved_at"].replace("Z", "+00:00")
                            )
                            resolution_time = (
                                resolved - created
                            ).total_seconds() / 60  # minutes
                            incident_info["resolution_time_minutes"] = resolution_time
                            incidents_data["resolution_times"].append(resolution_time)

                        incidents_data["incidents"].append(incident_info)

                        # Count by status and urgency
                        status = incident.get("status", "unknown")
                        incidents_data["by_status"][status] = (
                            incidents_data["by_status"].get(status, 0) + 1
                        )

                        urgency = incident.get("urgency", "unknown")
                        incidents_data["by_urgency"][urgency] = (
                            incidents_data["by_urgency"].get(urgency, 0) + 1
                        )

                # Calculate average resolution time
                if incidents_data["resolution_times"]:
                    incidents_data["avg_resolution_time_minutes"] = sum(
                        incidents_data["resolution_times"]
                    ) / len(incidents_data["resolution_times"])

                # Log execution
                duration_ms = (time.time() - start_time) * 1000
                log_agent_execution(
                    self.logger,
                    "PagerDutyClient",
                    "get_recent_incidents",
                    duration_ms,
                    service=service_name,
                    incidents_count=incidents_data["total_incidents"],
                )

                return incidents_data

            except pdpyras.PDClientError as e:
                self.logger.warning("PagerDuty API error, retrying", error=str(e))
                raise

        except Exception as e:
            log_error(self.logger, e, {"service": service_name})
            raise PagerDutyAPIError(f"Failed to fetch recent incidents: {str(e)}")

    def create_incident(
        self, title: str, service_name: str, urgency: str = "high", details: str = ""
    ) -> Dict[str, Any]:
        """
        Create a new incident in PagerDuty.

        Args:
            title: Incident title
            service_name: Service name to create incident for
            urgency: Incident urgency (high/low)
            details: Additional incident details

        Returns:
            Dictionary containing created incident information
        """
        start_time = time.time()

        try:
            self.validate_service_name(service_name)

            if not title or len(title.strip()) == 0:
                raise ValidationError("Incident title cannot be empty")

            self.logger.info(
                "Creating incident", title=title, service=service_name, urgency=urgency
            )

            # Find service ID
            service_id = self._find_service_by_name(service_name)
            if not service_id:
                raise PagerDutyAPIError(
                    f"Service '{service_name}' not found in PagerDuty"
                )

            incident_data = {
                "incident": {
                    "type": "incident",
                    "title": title,
                    "service": {"id": service_id, "type": "service_reference"},
                    "urgency": urgency,
                    "body": {"type": "incident_body", "details": details},
                }
            }

            try:
                response = self.session.post("incidents", json=incident_data)

                incident_info = {
                    "id": response.get("incident", {}).get("id"),
                    "incident_number": response.get("incident", {}).get(
                        "incident_number"
                    ),
                    "title": response.get("incident", {}).get("title"),
                    "status": response.get("incident", {}).get("status"),
                    "html_url": response.get("incident", {}).get("html_url"),
                    "created_at": response.get("incident", {}).get("created_at"),
                    "service": service_name,
                }

                # Log execution
                duration_ms = (time.time() - start_time) * 1000
                log_agent_execution(
                    self.logger,
                    "PagerDutyClient",
                    "create_incident",
                    duration_ms,
                    incident_id=incident_info["id"],
                    service=service_name,
                )

                return incident_info

            except pdpyras.PDClientError as e:
                self.logger.error("Failed to create incident", error=str(e))
                raise PagerDutyAPIError(f"Failed to create incident: {str(e)}")

        except Exception as e:
            log_error(self.logger, e, {"title": title, "service": service_name})
            raise PagerDutyAPIError(f"Failed to create incident: {str(e)}")


# Global instance - lazy loaded
_pagerduty_client = None


def get_pagerduty_client() -> PagerDutyClient:
    """Get PagerDuty client instance (lazy loaded)."""
    global _pagerduty_client
    if _pagerduty_client is None:
        _pagerduty_client = PagerDutyClient()
    return _pagerduty_client


# Backward compatibility functions
def get_active_incidents(service_name: str = None) -> Dict[str, Any]:
    """Convenience function for backward compatibility."""
    return get_pagerduty_client().get_active_incidents(service_name)


def get_oncall_users(service_name: str = None) -> Dict[str, Any]:
    """Convenience function for backward compatibility."""
    return get_pagerduty_client().get_oncall_users(service_name)


# For backward compatibility
pagerduty_client = get_pagerduty_client


if __name__ == "__main__":
    # Example usage for testing
    from ..utils.logging import configure_logging

    configure_logging(level="DEBUG", json_logs=False)

    client = PagerDutyClient()

    try:
        # Test active incidents
        active_incidents = client.get_active_incidents("test-service")
        print(f"Active Incidents: {active_incidents}")

        # Test on-call users
        oncall = client.get_oncall_users("test-service")
        print(f"On-call Users: {oncall}")

        # Test recent incidents
        recent = client.get_recent_incidents("test-service", days=7)
        print(f"Recent Incidents: {recent}")

    except Exception as e:
        print(f"PagerDuty Client Error: {e}")
