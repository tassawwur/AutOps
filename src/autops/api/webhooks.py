from fastapi import APIRouter, Request, BackgroundTasks, Form, Response, HTTPException
from typing import Annotated, Dict, Any, Optional
import json
import hmac
import hashlib
import time

# AsyncWebClient import removed - using slack_client wrapper instead

from ..config import get_settings
from ..utils.logging import get_logger
from ..agents import (
    get_structured_query,
    create_plan,
    execute_step,
    generate_response,
)
from ..tools.slack_client import slack_client

router = APIRouter(prefix="/api")
settings = get_settings()
logger = get_logger(__name__)


def verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """
    Verifies that the request came from Slack using the signing secret.
    """
    if abs(time.time() - float(timestamp)) > 60 * 5:
        # The request timestamp is more than five minutes old, could be a replay attack
        return False

    sig_basestring = f"v0:{timestamp}:{request_body.decode('utf-8')}"
    my_signature = (
        "v0="
        + hmac.new(
            settings.slack_signing_secret.encode("utf-8"),
            sig_basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(my_signature, signature)


async def run_autops_workflow(text: str, channel_id: str) -> None:
    """
    This function runs the full AutOps agent workflow as a background task.
    """
    try:
        # Step 1: Understand the query
        logger.info(f"Received query: {text}")
        structured_query = await get_structured_query(text)

        # Step 2: Create a plan
        plan = create_plan(structured_query)
        logger.info(f"Created plan: {plan}")

        # Step 3: Execute the plan
        results = []
        context = None
        for step in plan["steps"]:
            # Pass the result of the previous step as context if needed
            result_step = execute_step(step, context=context)
            results.append(result_step)
            if result_step["status"] == "completed":
                context = result_step.get("result")  # Update context for the next step
            else:
                # If a step fails, stop execution and report
                logger.error(f"Step failed: {result_step.get('error')}")
                break  # Exit the loop on failure

        # Step 4: Generate a response
        final_response_message = generate_response(plan, results)

        # Step 5: Send the response back to Slack
        client = slack_client()
        await client.post_message(channel_id, text=final_response_message)

    except Exception as e:
        logger.error(f"An error occurred during AutOps workflow: {e}", exc_info=True)
        error_message = f"Sorry, I encountered an error: {e}"
        client = slack_client()
        await client.post_message(channel_id, text=error_message)


@router.post("/slack/events")
async def slack_events(
    request: Request, background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    # Verify the request came from Slack
    body_bytes = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not verify_slack_signature(body_bytes, timestamp, signature):
        logger.warning("Invalid Slack signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    body = json.loads(body_bytes)

    if "challenge" in body:
        return {"challenge": body["challenge"]}

    event = body.get("event", {})
    if event.get("type") == "app_mention":
        user_text = event.get("text", "").strip()
        channel_id = event.get("channel")

        # Acknowledge the request immediately and run the workflow in the background
        background_tasks.add_task(run_autops_workflow, user_text, channel_id)

        return {"status": "ok"}

    return {"status": "event type not supported"}


@router.post("/slack/slash")
async def slack_slash_command(
    command: Annotated[Optional[str], Form()] = None,
    text: Annotated[str, Form()] = "",
    channel_id: Annotated[Optional[str], Form()] = None,
    user_id: Annotated[Optional[str], Form()] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> Dict[str, Any]:
    """
    Handles Slack slash commands (e.g., /autops).
    """
    logger.info(
        f"Slash command received: command={command}, text={text}, channel={channel_id}"
    )

    if not text.strip():
        return {
            "response_type": "ephemeral",
            "text": "Please provide a query. Example: `/autops What's the status of the payment service?`",
        }

    # Acknowledge immediately with a processing message
    # Run the actual workflow in the background
    background_tasks.add_task(run_autops_workflow, text, channel_id)

    return {
        "response_type": "in_channel",
        "text": f"Processing your request: `{text}`\nI'll respond shortly...",
    }


@router.post("/slack/interactive")
async def slack_interactive(payload: Annotated[str, Form()]) -> Response:
    """
    Handles interactive components like button clicks.
    """
    data = json.loads(payload)
    action_id = data["actions"][0]["action_id"]
    value = data["actions"][0]["value"]

    logger.info(f"Interactive payload: action_id='{action_id}', value='{value}'")

    channel = data["channel"]["id"]
    user = data["user"]["id"]

    if action_id.startswith("approve_"):
        # Execute the approved action
        logger.info(f"User {user} approved action: {value}")
        # Parse the approved action and execute it
        try:
            action_data = json.loads(value)
            # Execute the approved remediation action
            client = slack_client()
            client.post_message(
                channel=channel,
                text=f"🔄 Executing: {action_data.get('action', 'Unknown action')}...",
            )
        except json.JSONDecodeError:
            logger.error(f"Failed to parse action value: {value}")
            client = slack_client()
            client.post_message(
                channel=channel, text="❌ Failed to parse the approved action."
            )
        client = slack_client()
        client.post_message(
            channel=channel,
            text=f"✅ Remediation approved by <@{user}>. Executing action...",
        )
    elif action_id.startswith("deny_"):
        logger.info(f"User {user} denied action: {value}")
        client = slack_client()
        client.post_message(
            channel=channel, text=f"❌ Remediation denied by <@{user}>."
        )

    # Acknowledge the interaction
    return Response(status_code=200)
