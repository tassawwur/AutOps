"""
DataDog MCP Server for AutOps integration.
Provides tools for querying DataDog metrics and monitoring data.
"""

import asyncio
from typing import Any, Dict, List, Optional, TypedDict
from pydantic import AnyUrl

from mcp.server.fastmcp import FastMCP
from mcp.types import Resource, TextContent

from ..tools.datadog_client import get_datadog_client
from ..config import get_settings
from ..utils.logging import get_logger


# Tool is defined inline since mcp.server.models.Tool may not exist
class Tool(TypedDict):
    name: str
    description: str
    inputSchema: Dict[str, Any]


# Initialize components
settings = get_settings()
logger = get_logger(__name__)
datadog_client = get_datadog_client()

# Create MCP server
mcp = FastMCP("AutOps DataDog Server")


class DataDogMCPServer:
    """DataDog MCP Server implementation."""

    def __init__(self) -> None:
        self.client = datadog_client
        self.logger = logger
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Set up all MCP handlers for DataDog tools."""

        @mcp.tool("datadog_error_rate")  # type: ignore[misc]
        async def handle_error_rate_metrics(
            service_name: str, time_window_minutes: int = 60
        ) -> List[TextContent]:
            """
            Get error rate metrics for a service from DataDog.

            Args:
                service_name: Name of the service to check
                time_window_minutes: Time window in minutes for metrics (default: 60)

            Returns:
                Error rate metrics and analysis
            """
            try:
                self.logger.info(f"Fetching error rate for service: {service_name}")
                metrics = self.client.get_error_rate_metrics(
                    service_name, time_window_minutes
                )

                response = f"""
**Error Rate Metrics for {service_name}**

Current Error Rate: {metrics.get('error_rate', 'N/A')}
Time Window: {time_window_minutes} minutes
Data Points: {metrics.get('data_points', 'N/A')}
Max Error Rate: {metrics.get('max_error_rate', 'N/A')}
Min Error Rate: {metrics.get('min_error_rate', 'N/A')}

Status: {'✅ Normal' if float(metrics.get('error_rate', '0').rstrip('%')) < 5 else '⚠️ Elevated'}
                """.strip()

                return [TextContent(type="text", text=response)]

            except Exception as e:
                self.logger.error(f"Error fetching metrics: {e}")
                return [
                    TextContent(
                        type="text",
                        text=f"Error fetching error rate metrics: {str(e)}",
                    )
                ]

        @mcp.tool("datadog_service_metrics")  # type: ignore[misc]
        async def handle_service_metrics(
            service_name: str,
            metrics: Optional[List[str]] = None,
            time_window_minutes: int = 60,
        ) -> List[TextContent]:
            """
            Get comprehensive service metrics from DataDog.

            Args:
                service_name: Name of the service to check
                metrics: List of specific metrics to fetch (optional)
                time_window_minutes: Time window in minutes (default: 60)

            Returns:
                Comprehensive service metrics
            """
            try:
                self.logger.info(f"Fetching service metrics for: {service_name}")
                service_metrics = self.client.get_service_metrics(
                    service_name, metrics, time_window_minutes
                )

                response = f"""
**Service Metrics for {service_name}**

Time Window: {time_window_minutes} minutes
Metrics Retrieved: {len(service_metrics.get('metrics', {}))}

Key Metrics:
{self._format_metrics(service_metrics.get('metrics', {}))}

Health Status: {service_metrics.get('health_status', 'Unknown')}
                """.strip()

                return [TextContent(type="text", text=response)]

            except Exception as e:
                self.logger.error(f"Error fetching service metrics: {e}")
                return [
                    TextContent(
                        type="text",
                        text=f"Error fetching service metrics: {str(e)}",
                    )
                ]

        @mcp.tool("datadog_recent_events")  # type: ignore[misc]
        async def handle_recent_events(
            service_name: str, hours: int = 24
        ) -> List[TextContent]:
            """
            Get recent events for a service from DataDog.

            Args:
                service_name: Name of the service to check
                hours: Number of hours to look back (default: 24)

            Returns:
                Recent events and alerts
            """
            try:
                self.logger.info(f"Fetching recent events for: {service_name}")
                events = self.client.get_recent_events(service_name, hours)

                response = f"""
**Recent Events for {service_name}**

Time Range: Last {hours} hours
Total Events: {events.get('total_events', 0)}

Recent Events:
{self._format_events(events.get('events', []))}
                """.strip()

                return [TextContent(type="text", text=response)]

            except Exception as e:
                self.logger.error(f"Error fetching events: {e}")
                return [
                    TextContent(
                        type="text", text=f"Error fetching recent events: {str(e)}"
                    )
                ]

    async def handle_call_tool(
        self, name: str, arguments: Dict[str, Any]
    ) -> List[TextContent]:
        """Handle tool calls from MCP clients."""
        self.logger.info(f"Handling tool call: {name} with args: {arguments}")

        # Tool calls are handled by the @mcp.tool decorators above
        # This method is kept for compatibility
        return [
            TextContent(
                type="text", text=f"Tool {name} called with arguments: {arguments}"
            )
        ]

    def _format_metrics(self, metrics: Dict[str, Any]) -> str:
        """Format metrics for display."""
        if not metrics:
            return "No metrics available"

        formatted = []
        for metric_name, value in metrics.items():
            formatted.append(f"  • {metric_name}: {value}")

        return "\n".join(formatted)

    def _format_events(self, events: List[Dict[str, Any]]) -> str:
        """Format events for display."""
        if not events:
            return "No recent events"

        formatted = []
        for event in events[:5]:  # Show top 5 events
            timestamp = event.get("timestamp", "N/A")
            title = event.get("title", "No title")
            status = event.get("status", "unknown")
            formatted.append(f"  • [{timestamp}] {title} (Status: {status})")

        return "\n".join(formatted)


# Global server instance
datadog_server = DataDogMCPServer()


# MCP Handler Registration
@mcp.list_tools()  # type: ignore[misc]
async def handle_list_tools() -> List[Tool]:
    """Return list of available DataDog tools."""
    return [
        Tool(
            name="datadog_error_rate",
            description="Get error rate metrics for a service from DataDog",
            inputSchema={
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service to check",
                    },
                    "time_window_minutes": {
                        "type": "integer",
                        "description": "Time window in minutes (default: 60)",
                        "default": 60,
                    },
                },
                "required": ["service_name"],
            },
        ),
        Tool(
            name="datadog_service_metrics",
            description="Get comprehensive service metrics from DataDog",
            inputSchema={
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service to check",
                    },
                    "metrics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of specific metrics to fetch (optional)",
                    },
                    "time_window_minutes": {
                        "type": "integer",
                        "description": "Time window in minutes (default: 60)",
                        "default": 60,
                    },
                },
                "required": ["service_name"],
            },
        ),
        Tool(
            name="datadog_recent_events",
            description="Get recent events for a service from DataDog",
            inputSchema={
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service to check",
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Number of hours to look back (default: 24)",
                        "default": 24,
                    },
                },
                "required": ["service_name"],
            },
        ),
    ]


@mcp.list_resources()  # type: ignore[misc]
async def handle_list_resources() -> List[Resource]:
    """Return list of available resources."""
    return [
        Resource(
            uri=AnyUrl("datadog://services"),
            name="DataDog Services",
            description="List of services monitored by DataDog",
            mimeType="application/json",
        ),
        Resource(
            uri=AnyUrl("datadog://dashboards"),
            name="DataDog Dashboards",
            description="Available DataDog dashboards",
            mimeType="application/json",
        ),
    ]


@mcp.read_resource()  # type: ignore[misc]
async def handle_read_resource(uri: str) -> str:
    """Handle resource reading requests."""
    if uri == "datadog://services":
        # Return mock service list - in production, this would query DataDog API
        services = {
            "services": [
                "payment-service",
                "user-auth-service",
                "notification-service",
                "order-processing-service",
            ],
            "total": 4,
            "note": "This is a sample list. Actual services would be fetched from DataDog API.",
        }
        return str(services)

    elif uri == "datadog://dashboards":
        # Return mock dashboard list
        dashboards = {
            "dashboards": [
                {
                    "id": "dashboard-1",
                    "name": "Service Overview",
                    "url": "https://app.datadoghq.com/dashboard/abc-123",
                },
                {
                    "id": "dashboard-2",
                    "name": "Infrastructure Metrics",
                    "url": "https://app.datadoghq.com/dashboard/def-456",
                },
            ],
            "total": 2,
        }
        return str(dashboards)

    else:
        return f"Resource not found: {uri}"


# Server management
async def run_datadog_server() -> None:
    """Run the DataDog MCP server."""
    logger.info("Starting DataDog MCP Server")
    try:
        await mcp.run()
    except KeyboardInterrupt:
        logger.info("DataDog MCP Server stopped by user")
    except Exception as e:
        logger.error(f"DataDog MCP Server error: {e}")
        raise


# Entry point
async def main() -> None:
    """Main entry point for the DataDog MCP server."""
    await run_datadog_server()


if __name__ == "__main__":
    asyncio.run(main())
