"""
Production-ready FastAPI application for AutOps.
"""
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

import structlog
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from .api import webhooks

# create_plan import removed - using agents.__init__ instead
from .agents.tool_execution_agent import execute_step
from .agents.response_generation_agent import (
    generate_response,
    generate_incident_remediation_message,
)
from .config import get_settings
from .tools.slack_client import slack_client
from .utils.logging import configure_logging, get_logger, log_api_request, log_error
from .utils.exceptions import AutOpsException
from .utils.database import initialize_database, db_manager

# Configure logging
settings = get_settings()
configure_logging(level=settings.log_level, json_logs=settings.json_logs)
logger = get_logger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "autops_requests_total", "Total requests", ["method", "endpoint", "status"]
)
REQUEST_DURATION = Histogram("autops_request_duration_seconds", "Request duration")
AGENT_EXECUTION_COUNT = Counter(
    "autops_agent_executions_total", "Agent executions", ["agent", "status"]
)
AGENT_EXECUTION_DURATION = Histogram(
    "autops_agent_duration_seconds", "Agent execution duration", ["agent"]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info(
        "Starting AutOps application", version="0.1.0", environment=settings.environment
    )

    # Health checks for external dependencies
    await perform_startup_checks()

    yield

    # Shutdown
    logger.info("Shutting down AutOps application")


async def perform_startup_checks():
    """Perform health checks on startup."""
    logger.info("Performing startup health checks")

    # Initialize database
    try:
        initialize_database()
        logger.info("Database initialization completed")
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        # Don't fail startup for now, but log the error

    # Check OpenAI API
    try:
        from .agents.query_understanding_agent import query_understanding_agent

        # Test query understanding agent
        await query_understanding_agent.get_structured_query("test query")
        logger.info("OpenAI API check passed")
    except Exception as e:
        logger.error("OpenAI API check failed", error=str(e))
        # Don't fail startup for now, but log the error

    # Add other health checks as needed
    logger.info("Startup checks completed")


app = FastAPI(
    title="AutOps",
    description="An autonomous AI teammate for your entire engineering organization.",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# Security middleware
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "*"],  # Configure appropriately
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],  # Configure appropriately
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log all requests with timing and metrics."""
    start_time = time.time()

    # Log request
    log_api_request(
        logger,
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", ""),
    )

    response = None
    status_code = 500

    try:
        with REQUEST_DURATION.time():
            response = await call_next(request)
            status_code = response.status_code
    except Exception as e:
        log_error(logger, e, {"path": request.url.path, "method": request.method})
        status_code = 500
        response = JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred",
            },
        )
    finally:
        # Record metrics
        REQUEST_COUNT.labels(
            method=request.method, endpoint=request.url.path, status=status_code
        ).inc()

        # Log response
        duration = time.time() - start_time
        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration * 1000,
        )

    return response


@app.exception_handler(AutOpsException)
async def autops_exception_handler(request: Request, exc: AutOpsException):
    """Handle custom AutOps exceptions."""
    log_error(logger, exc, exc.context)
    return JSONResponse(
        status_code=400,
        content={
            "error": type(exc).__name__,
            "message": exc.message,
            "context": exc.context,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "HTTP error", "message": exc.detail},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    log_error(logger, exc, {"path": request.url.path, "method": request.method})
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
        },
    )


# Include routers
app.include_router(webhooks.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to AutOps!",
        "version": "0.1.0",
        "environment": settings.environment,
        "status": "healthy",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check database health
    db_health = db_manager.health_check()

    return {
        "status": "healthy" if db_health["healthy"] else "unhealthy",
        "timestamp": time.time(),
        "environment": settings.environment,
        "database": db_health,
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    if not settings.enable_metrics:
        raise HTTPException(status_code=404, detail="Metrics disabled")

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/ready")
async def readiness_check():
    """Kubernetes readiness check."""
    # Add checks for external dependencies
    checks = {
        "redis": True,  # Add actual Redis check
        "database": True,  # Add actual database check
    }

    if all(checks.values()):
        return {"status": "ready", "checks": checks}
    else:
        raise HTTPException(
            status_code=503, detail={"status": "not ready", "checks": checks}
        )


async def run_orchestrator(plan: Dict[str, Any], channel: str) -> None:
    """
    Enhanced orchestrator with monitoring and error handling.
    """
    start_time = time.time()
    orchestrator_logger = get_logger(f"{__name__}.orchestrator")

    try:
        orchestrator_logger.info(
            "Orchestrator starting", plan_intent=plan.get("intent")
        )

        step_result = None
        last_successful_output = None
        failed_step = None

        for i, step in enumerate(plan.get("steps", [])):
            if step.get("status") == "pending":
                step_start = time.time()
                agent_name = step.get("agent", "unknown")

                try:
                    with AGENT_EXECUTION_DURATION.labels(agent=agent_name).time():
                        step_result = execute_step(step, context=last_successful_output)

                    step_duration = time.time() - step_start
                    orchestrator_logger.info(
                        "Step completed",
                        step_index=i,
                        agent=agent_name,
                        status=step_result.get("status"),
                        duration_ms=step_duration * 1000,
                    )

                    if step_result.get("status") == "completed":
                        last_successful_output = step_result.get("result")
                        AGENT_EXECUTION_COUNT.labels(
                            agent=agent_name, status="success"
                        ).inc()
                    else:
                        failed_step = step_result
                        AGENT_EXECUTION_COUNT.labels(
                            agent=agent_name, status="failure"
                        ).inc()
                        break

                except Exception as e:
                    log_error(orchestrator_logger, e, {"step": step, "step_index": i})
                    AGENT_EXECUTION_COUNT.labels(agent=agent_name, status="error").inc()
                    failed_step = {"status": "failed", "error": str(e)}
                    break

        # Generate and send response
        await send_response(
            plan, last_successful_output, failed_step, channel, orchestrator_logger
        )

        duration = time.time() - start_time
        orchestrator_logger.info("Orchestrator completed", duration_ms=duration * 1000)

    except Exception as e:
        log_error(orchestrator_logger, e, {"plan": plan, "channel": channel})
        # Send error response to user
        try:
            slack_client.post_message(
                channel=channel,
                text="I encountered an error while processing your request. "
                "Please try again later.",
            )
        except Exception as slack_error:
            log_error(orchestrator_logger, slack_error, {"original_error": str(e)})


async def send_response(
    plan: Dict[str, Any],
    last_successful_output: Any,
    failed_step: Any,
    channel: str,
    logger: structlog.stdlib.BoundLogger,
) -> None:
    """Send appropriate response based on execution results."""
    original_query = plan.get("original_query", "your request")

    try:
        if failed_step:
            # Send error response
            error_message = failed_step.get("error", "Unknown error occurred")
            slack_client.post_message(
                channel=channel,
                text=f"I encountered an error while processing your request: "
                f"{error_message}",
            )
        elif plan.get("intent") == "investigate_incident" and last_successful_output:
            # Send interactive incident response
            remediation_blocks = generate_incident_remediation_message(
                last_successful_output
            )
            slack_client.post_message(
                channel=channel,
                blocks=remediation_blocks,
                text="Incident analysis complete. Suggested remediation below.",
            )
        else:
            # Send standard response
            final_response = generate_response(
                original_query,
                {"status": "completed", "result": last_successful_output},
            )
            slack_client.post_message(channel=channel, text=final_response)

    except Exception as e:
        log_error(logger, e, {"plan": plan, "channel": channel})
        # Fallback message
        slack_client.post_message(
            channel=channel,
            text="I completed processing your request but encountered an error "
            "generating the response.",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.autops.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        log_level=settings.log_level.lower(),
        reload=settings.is_development,
    )
