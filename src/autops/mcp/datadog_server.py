"""
DataDog MCP Server implementation for providing DataDog monitoring capabilities
via the Model Context Protocol.
"""
import asyncio
import json
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
)

from ..tools.datadog_client import datadog_client
from ..utils.logging import get_logger, log_error
from ..utils.exceptions import DatadogAPIError, ValidationError

logger = get_logger(__name__)


class DatadogMCPServer:
    """
    DataDog MCP Server that exposes DataDog monitoring capabilities
    through the Model Context Protocol.
    """

    def __init__(self):
        self.server = Server("datadog-mcp-server")
        self.logger = get_logger(f"{__name__}.DatadogMCPServer")
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up MCP server handlers."""

        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """Return list of available DataDog tools."""
            return [
                Tool(
                    name="get_error_rate_metrics",
                    description="Get error rate metrics for a service from DataDog",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "service_name": {
                                "type": "string",
                                "description": "Name of the service to get metrics for",
                            },
                            "time_window_minutes": {
                                "type": "integer",
                                "description": "Time window in minutes (default: 60)",
                                "default": 60,
                                "minimum": 5,
                                "maximum": 1440,
                            },
                        },
                        "required": ["service_name"],
                    },
                ),
                Tool(
                    name="get_service_metrics",
                    description="Get comprehensive service metrics from DataDog",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "service_name": {
                                "type": "string",
                                "description": "Name of the service to get metrics for",
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
                                "minimum": 5,
                                "maximum": 1440,
                            },
                        },
                        "required": ["service_name"],
                    },
                ),
                Tool(
                    name="get_recent_events",
                    description="Get recent events related to a service from DataDog",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "service_name": {
                                "type": "string",
                                "description": "Name of the service to get events for",
                            },
                            "hours": {
                                "type": "integer",
                                "description": "Number of hours to look back (default: 24)",
                                "default": 24,
                                "minimum": 1,
                                "maximum": 168,
                            },
                        },
                        "required": ["service_name"],
                    },
                ),
                Tool(
                    name="get_monitor_status",
                    description="Get monitor status for a service from DataDog",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "service_name": {
                                "type": "string",
                                "description": "Name of the service to get monitor status for",
                            }
                        },
                        "required": ["service_name"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> List[TextContent]:
            """Handle tool calls."""
            try:
                self.logger.info("MCP tool called", tool=name, args=arguments)

                if name == "get_error_rate_metrics":
                    service_name = arguments["service_name"]
                    time_window = arguments.get("time_window_minutes", 60)

                    result = datadog_client.get_error_rate_metrics(
                        service_name=service_name, time_window_minutes=time_window
                    )

                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "get_service_metrics":
                    service_name = arguments["service_name"]
                    metrics = arguments.get("metrics")
                    time_window = arguments.get("time_window_minutes", 60)

                    result = datadog_client.get_service_metrics(
                        service_name=service_name,
                        metrics=metrics,
                        time_window_minutes=time_window,
                    )

                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "get_recent_events":
                    service_name = arguments["service_name"]
                    hours = arguments.get("hours", 24)

                    result = datadog_client.get_recent_events(
                        service_name=service_name, hours=hours
                    )

                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "get_monitor_status":
                    service_name = arguments["service_name"]

                    result = datadog_client.get_monitor_status(
                        service_name=service_name
                    )

                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                else:
                    error_msg = f"Unknown tool: {name}"
                    self.logger.error(error_msg)
                    return [
                        TextContent(type="text", text=json.dumps({"error": error_msg}))
                    ]

            except ValidationError as e:
                error_msg = f"Validation error: {str(e)}"
                self.logger.error(error_msg, tool=name, args=arguments)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}))]

            except DatadogAPIError as e:
                error_msg = f"DataDog API error: {str(e)}"
                self.logger.error(error_msg, tool=name, args=arguments)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}))]

            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                log_error(self.logger, e, {"tool": name, "args": arguments})
                return [TextContent(type="text", text=json.dumps({"error": error_msg}))]

        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """Return list of available resources."""
            return [
                Resource(
                    uri="datadog://services",
                    name="DataDog Services",
                    description="List of services monitored by DataDog",
                    mimeType="application/json",
                ),
                Resource(
                    uri="datadog://metrics",
                    name="DataDog Metrics",
                    description="Available DataDog metrics",
                    mimeType="application/json",
                ),
            ]

        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Handle resource reading."""
            try:
                if uri == "datadog://services":
                    # This would typically fetch from DataDog API
                    services_info = {
                        "description": "DataDog monitored services",
                        "services": [
                            "payment-service",
                            "user-service",
                            "notification-service",
                            "api-gateway",
                        ],
                        "note": "This is a sample list. Actual services would be fetched from DataDog API.",
                    }
                    return json.dumps(services_info, indent=2)

                elif uri == "datadog://metrics":
                    metrics_info = {
                        "description": "Available DataDog metrics",
                        "common_metrics": [
                            "trace.http.request.duration.95p",
                            "trace.http.request.errors",
                            "system.cpu.user",
                            "system.mem.used",
                            "redis.info.memory.used_memory",
                            "postgres.connections",
                        ],
                        "note": "These are common metrics. Specific metrics depend on your DataDog setup.",
                    }
                    return json.dumps(metrics_info, indent=2)

                else:
                    raise ValueError(f"Unknown resource URI: {uri}")

            except Exception as e:
                error_msg = f"Error reading resource {uri}: {str(e)}"
                self.logger.error(error_msg)
                return json.dumps({"error": error_msg})

    async def run(self):
        """Run the MCP server."""
        try:
            self.logger.info("Starting DataDog MCP server")

            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="datadog-mcp-server",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=None, experimental_capabilities={}
                        ),
                    ),
                )
        except Exception as e:
            log_error(self.logger, e, {"operation": "run_mcp_server"})
            raise


# Global server instance
datadog_mcp_server = DatadogMCPServer()


async def main():
    """Main entry point for the DataDog MCP server."""
    await datadog_mcp_server.run()


if __name__ == "__main__":
    # Run the server
    asyncio.run(main())
