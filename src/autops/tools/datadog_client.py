"""
DataDog API Client for metrics and monitoring data retrieval.
"""
import time
from typing import Dict, Any, List
from datetime import datetime, timedelta

from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v1.api.metrics_api import MetricsApi
from datadog_api_client.v1.api.events_api import EventsApi
from datadog_api_client.v1.api.monitors_api import MonitorsApi
from datadog_api_client.v1.model.metrics_query_response import MetricsQueryResponse
from datadog_api_client.exceptions import ApiException, UnauthorizedException
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..config import get_settings
from ..utils.logging import get_logger, log_error, log_agent_execution
from ..utils.exceptions import DatadogAPIError, ValidationError

settings = get_settings()
logger = get_logger(__name__)


class DatadogClient:
    """
    Production-ready DataDog API client for retrieving metrics and monitoring data.
    """

    def __init__(self):
        self.logger = get_logger(f"{__name__}.DatadogClient")

        # Configure DataDog API client
        configuration = Configuration()
        configuration.api_key["apiKeyAuth"] = settings.datadog_api_key
        configuration.api_key["appKeyAuth"] = settings.datadog_app_key
        configuration.server_variables["site"] = settings.datadog_site

        self.api_client = ApiClient(configuration)
        self.metrics_api = MetricsApi(self.api_client)
        self.events_api = EventsApi(self.api_client)
        self.monitors_api = MonitorsApi(self.api_client)

    def validate_service_name(self, service_name: str) -> None:
        """Validate service name parameter."""
        if not service_name or not isinstance(service_name, str):
            raise ValidationError("Service name must be a non-empty string")

        if len(service_name.strip()) == 0:
            raise ValidationError("Service name cannot be empty")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(ApiException),
    )
    def get_error_rate_metrics(
        self, service_name: str, time_window_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Get error rate metrics for a service from DataDog.

        Args:
            service_name: Name of the service
            time_window_minutes: Time window to look back in minutes

        Returns:
            Dictionary containing error rate metrics

        Raises:
            DatadogAPIError: If API call fails
            ValidationError: If input validation fails
        """
        start_time = time.time()

        try:
            self.validate_service_name(service_name)
            self.logger.info(
                "Fetching error rate metrics",
                service=service_name,
                window=time_window_minutes,
            )

            # Calculate time range
            end_time = datetime.now()
            start_time_dt = end_time - timedelta(minutes=time_window_minutes)

            # Convert to Unix timestamps
            start_ts = int(start_time_dt.timestamp())
            end_ts = int(end_time.timestamp())

            # Query for error rate metrics
            # This query assumes you have error rate metrics tagged with service name
            query = f"avg:trace.http.request.errors{{service:{service_name}}} by {{service}}"

            try:
                response: MetricsQueryResponse = self.metrics_api.query_metrics(
                    _from=start_ts, to=end_ts, query=query
                )

                # Process the response
                metrics_data = {
                    "service": service_name,
                    "time_window_minutes": time_window_minutes,
                    "query_time": datetime.now().isoformat(),
                    "error_rate": "0.0%",  # Default
                    "data_points": 0,
                    "has_data": False,
                }

                if response.series and len(response.series) > 0:
                    series = response.series[0]
                    if series.pointlist and len(series.pointlist) > 0:
                        # Calculate average error rate from data points
                        values = [
                            point[1]
                            for point in series.pointlist
                            if point[1] is not None
                        ]
                        if values:
                            avg_error_rate = sum(values) / len(values)
                            metrics_data.update(
                                {
                                    "error_rate": f"{avg_error_rate:.2f}%",
                                    "data_points": len(values),
                                    "has_data": True,
                                    "raw_values": values[
                                        :10
                                    ],  # Include up to 10 raw values
                                    "max_error_rate": f"{max(values):.2f}%",
                                    "min_error_rate": f"{min(values):.2f}%",
                                }
                            )

                # Log execution
                duration_ms = (time.time() - start_time) * 1000
                log_agent_execution(
                    self.logger,
                    "DatadogClient",
                    "get_error_rate_metrics",
                    duration_ms,
                    service=service_name,
                    has_data=metrics_data["has_data"],
                )

                return metrics_data

            except UnauthorizedException as e:
                self.logger.error("DataDog authentication failed", error=str(e))
                raise DatadogAPIError(
                    "Authentication failed. Check API keys.",
                    context={"service": service_name},
                )
            except ApiException as e:
                self.logger.warning(
                    "DataDog API error, retrying", error=str(e), status_code=e.status
                )
                raise

        except ValidationError:
            raise
        except DatadogAPIError:
            raise
        except Exception as e:
            log_error(self.logger, e, {"service": service_name})
            raise DatadogAPIError(f"Failed to fetch error rate metrics: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(ApiException),
    )
    def get_service_metrics(
        self,
        service_name: str,
        metrics: List[str] = None,
        time_window_minutes: int = 60,
    ) -> Dict[str, Any]:
        """
        Get comprehensive service metrics from DataDog.

        Args:
            service_name: Name of the service
            metrics: List of specific metrics to fetch
            time_window_minutes: Time window to look back in minutes

        Returns:
            Dictionary containing service metrics
        """
        start_time = time.time()

        try:
            self.validate_service_name(service_name)

            if metrics is None:
                metrics = [
                    "trace.http.request.duration.95p",
                    "trace.http.request.errors",
                    "system.cpu.user",
                    "system.mem.used",
                ]

            self.logger.info(
                "Fetching service metrics", service=service_name, metrics=metrics
            )

            # Calculate time range
            end_time = datetime.now()
            start_time_dt = end_time - timedelta(minutes=time_window_minutes)
            start_ts = int(start_time_dt.timestamp())
            end_ts = int(end_time.timestamp())

            results = {
                "service": service_name,
                "time_window_minutes": time_window_minutes,
                "query_time": datetime.now().isoformat(),
                "metrics": {},
            }

            # Fetch each metric
            for metric in metrics:
                try:
                    query = f"avg:{metric}{{service:{service_name}}}"
                    response = self.metrics_api.query_metrics(
                        _from=start_ts, to=end_ts, query=query
                    )

                    metric_data = {"has_data": False, "value": None}

                    if response.series and len(response.series) > 0:
                        series = response.series[0]
                        if series.pointlist and len(series.pointlist) > 0:
                            values = [
                                point[1]
                                for point in series.pointlist
                                if point[1] is not None
                            ]
                            if values:
                                metric_data = {
                                    "has_data": True,
                                    "value": sum(values) / len(values),
                                    "data_points": len(values),
                                    "max": max(values),
                                    "min": min(values),
                                }

                    results["metrics"][metric] = metric_data

                except Exception as e:
                    self.logger.warning(
                        "Failed to fetch metric", metric=metric, error=str(e)
                    )
                    results["metrics"][metric] = {"has_data": False, "error": str(e)}

            # Log execution
            duration_ms = (time.time() - start_time) * 1000
            log_agent_execution(
                self.logger,
                "DatadogClient",
                "get_service_metrics",
                duration_ms,
                service=service_name,
                metrics_count=len(metrics),
            )

            return results

        except Exception as e:
            log_error(self.logger, e, {"service": service_name, "metrics": metrics})
            raise DatadogAPIError(f"Failed to fetch service metrics: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(ApiException),
    )
    def get_recent_events(self, service_name: str, hours: int = 24) -> Dict[str, Any]:
        """
        Get recent events related to a service from DataDog.

        Args:
            service_name: Name of the service
            hours: Number of hours to look back

        Returns:
            Dictionary containing recent events
        """
        start_time = time.time()

        try:
            self.validate_service_name(service_name)
            self.logger.info(
                "Fetching recent events", service=service_name, hours=hours
            )

            # Calculate time range
            end_time = datetime.now()
            start_time_dt = end_time - timedelta(hours=hours)

            try:
                response = self.events_api.list_events(
                    start=int(start_time_dt.timestamp()),
                    end=int(end_time.timestamp()),
                    tags=f"service:{service_name}",
                )

                events_data = {
                    "service": service_name,
                    "time_window_hours": hours,
                    "query_time": datetime.now().isoformat(),
                    "events": [],
                    "total_events": 0,
                }

                if response.events:
                    events_data["total_events"] = len(response.events)
                    events_data["events"] = [
                        {
                            "id": event.id,
                            "title": event.title,
                            "text": event.text[:200] + "..."
                            if len(event.text) > 200
                            else event.text,
                            "date_happened": event.date_happened,
                            "priority": event.priority,
                            "tags": event.tags,
                        }
                        for event in response.events[:10]  # Limit to 10 events
                    ]

                # Log execution
                duration_ms = (time.time() - start_time) * 1000
                log_agent_execution(
                    self.logger,
                    "DatadogClient",
                    "get_recent_events",
                    duration_ms,
                    service=service_name,
                    events_count=events_data["total_events"],
                )

                return events_data

            except ApiException as e:
                self.logger.warning("DataDog events API error", error=str(e))
                raise

        except Exception as e:
            log_error(self.logger, e, {"service": service_name})
            raise DatadogAPIError(f"Failed to fetch recent events: {str(e)}")

    def get_monitor_status(self, service_name: str) -> Dict[str, Any]:
        """
        Get monitor status for a service.

        Args:
            service_name: Name of the service

        Returns:
            Dictionary containing monitor status
        """
        start_time = time.time()

        try:
            self.validate_service_name(service_name)
            self.logger.info("Fetching monitor status", service=service_name)

            try:
                # Get monitors for the service
                response = self.monitors_api.list_monitors(
                    tags=f"service:{service_name}"
                )

                monitor_data = {
                    "service": service_name,
                    "query_time": datetime.now().isoformat(),
                    "monitors": [],
                    "total_monitors": 0,
                    "alerts": {"ok": 0, "warn": 0, "alert": 0, "no_data": 0},
                }

                if response:
                    monitor_data["total_monitors"] = len(response)

                    for monitor in response:
                        monitor_info = {
                            "id": monitor.id,
                            "name": monitor.name,
                            "status": monitor.overall_state,
                            "type": monitor.type,
                        }
                        monitor_data["monitors"].append(monitor_info)

                        # Count alerts by status
                        status = monitor.overall_state
                        if status in monitor_data["alerts"]:
                            monitor_data["alerts"][status] += 1

                # Log execution
                duration_ms = (time.time() - start_time) * 1000
                log_agent_execution(
                    self.logger,
                    "DatadogClient",
                    "get_monitor_status",
                    duration_ms,
                    service=service_name,
                    monitors_count=monitor_data["total_monitors"],
                )

                return monitor_data

            except ApiException as e:
                self.logger.warning("DataDog monitors API error", error=str(e))
                raise DatadogAPIError(
                    f"Monitor API error: {str(e)}", "DataDog", e.status
                )

        except Exception as e:
            log_error(self.logger, e, {"service": service_name})
            raise DatadogAPIError(f"Failed to fetch monitor status: {str(e)}")


# Global instance - lazy loaded
_datadog_client = None


def get_datadog_client() -> DatadogClient:
    """Get DataDog client instance (lazy loaded)."""
    global _datadog_client
    if _datadog_client is None:
        _datadog_client = DatadogClient()
    return _datadog_client


# Backward compatibility functions
def get_error_rate_metrics(service_name: str) -> Dict[str, Any]:
    """Convenience function for backward compatibility."""
    return get_datadog_client().get_error_rate_metrics(service_name)


def get_service_metrics(service_name: str, metrics: List[str] = None) -> Dict[str, Any]:
    """Convenience function for backward compatibility."""
    return get_datadog_client().get_service_metrics(service_name, metrics)


# For backward compatibility
datadog_client = get_datadog_client


if __name__ == "__main__":
    # Example usage for testing
    from ..utils.logging import configure_logging

    configure_logging(level="DEBUG", json_logs=False)

    client = DatadogClient()

    try:
        # Test error rate metrics
        error_metrics = client.get_error_rate_metrics("test-service")
        print(f"Error Rate Metrics: {error_metrics}")

        # Test service metrics
        service_metrics = client.get_service_metrics("test-service")
        print(f"Service Metrics: {service_metrics}")

        # Test recent events
        events = client.get_recent_events("test-service")
        print(f"Recent Events: {events}")

        # Test monitor status
        monitors = client.get_monitor_status("test-service")
        print(f"Monitor Status: {monitors}")

    except Exception as e:
        print(f"DataDog Client Error: {e}")
