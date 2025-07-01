import json
import time
from typing import Dict, List, Any, Union, Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import structlog

from ..config import settings
from ..utils.exceptions import SlackAPIError
from ..utils.logging import log_error, log_agent_execution


class SlackClient:
    """Production-ready Slack client with comprehensive error handling and retry logic."""

    def __init__(self, token: Optional[str] = None) -> None:
        """
        Initialize Slack client.

        Args:
            token: Slack bot token. If not provided, uses settings.slack_bot_token
        """
        self.logger = structlog.get_logger(__name__)
        self.token = token or settings.slack_bot_token

        if not self.token:
            raise SlackAPIError("Slack bot token is required")

        self.client = WebClient(token=self.token)

        # Test authentication on initialization
        try:
            response = self.client.auth_test()
            self.bot_id = response["user_id"]
            self.team_id = response["team_id"]
            self.logger.info(
                "Slack client initialized successfully",
                bot_id=self.bot_id,
                team_id=self.team_id,
            )
        except SlackApiError as e:
            self.logger.error("Failed to authenticate with Slack", error=str(e))
            raise SlackAPIError(f"Slack authentication failed: {str(e)}")

    def validate_channel(self, channel: str) -> str:
        """Validate and format channel."""
        if not channel:
            raise SlackAPIError("Channel cannot be empty")

        if not (
            channel.startswith("#")
            or channel.startswith("C")
            or channel.startswith("D")
        ):
            # Assume it's a channel name without #
            return f"#{channel}"
        return channel

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(SlackApiError),
    )
    def post_message(
        self,
        channel: str,
        text: Optional[str] = None,
        blocks: Optional[List[Dict[str, Any]]] = None,
        thread_ts: Optional[str] = None,
        unfurl_links: bool = True,
        unfurl_media: bool = True,
    ) -> Dict[str, Any]:
        """
        Post a message to Slack channel.

        Args:
            channel: Channel ID or name (with or without #)
            text: Message text (required if blocks not provided)
            blocks: Slack Block Kit blocks
            thread_ts: Thread timestamp for replies
            unfurl_links: Whether to unfurl links
            unfurl_media: Whether to unfurl media

        Returns:
            Slack API response
        """
        start_time = time.time()

        try:
            channel = self.validate_channel(channel)

            if not text and not blocks:
                raise SlackAPIError("Either text or blocks must be provided")

            self.logger.info(
                "Posting message to Slack",
                channel=channel,
                has_text=bool(text),
                has_blocks=bool(blocks),
                thread_ts=thread_ts,
            )

            kwargs = {
                "channel": channel,
                "unfurl_links": unfurl_links,
                "unfurl_media": unfurl_media,
            }

            if text:
                kwargs["text"] = text
            if blocks:
                kwargs["blocks"] = blocks
            if thread_ts:
                kwargs["thread_ts"] = thread_ts

            response = self.client.chat_postMessage(**kwargs)  # type: ignore[arg-type]

            # Log execution
            duration_ms = (time.time() - start_time) * 1000
            log_agent_execution(
                self.logger,
                "SlackClient",
                "post_message",
                duration_ms,
                channel=channel,
                message_ts=response.get("ts"),
            )

            return dict(response.data)  # type: ignore[arg-type]

        except SlackApiError as e:
            self.logger.warning("Slack API error, retrying", error=str(e))
            raise
        except Exception as e:
            log_error(self.logger, e, {"channel": channel})
            raise SlackAPIError(f"Failed to post message: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(SlackApiError),
    )
    def post_interactive_message(
        self,
        channel: str,
        text: str,
        actions: List[Dict[str, Any]],
        callback_id: Optional[str] = None,
        color: str = "good",
    ) -> Dict[str, Any]:
        """
        Post an interactive message with buttons/actions.

        Args:
            channel: Channel ID or name
            text: Message text
            actions: List of action elements (buttons, etc.)
            callback_id: Callback ID for interactive components
            color: Message color (good, warning, danger)

        Returns:
            Slack API response
        """
        start_time = time.time()

        try:
            channel = self.validate_channel(channel)

            # Build blocks with actions
            blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]

            if actions:
                action_block = {"type": "actions", "elements": actions}
                if callback_id:
                    action_block["block_id"] = callback_id

                blocks.append(action_block)  # type: ignore[arg-type]

            self.logger.info(
                "Posting interactive message to Slack",
                channel=channel,
                actions_count=len(actions),
                callback_id=callback_id,
            )

            response = self.post_message(channel=channel, blocks=blocks)

            # Log execution
            duration_ms = (time.time() - start_time) * 1000
            log_agent_execution(
                self.logger,
                "SlackClient",
                "post_interactive_message",
                duration_ms,
                channel=channel,
                actions_count=len(actions),
            )

            return response

        except Exception as e:
            log_error(self.logger, e, {"channel": channel})
            raise SlackAPIError(f"Failed to post interactive message: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(SlackApiError),
    )
    def update_message(
        self, channel: str, ts: str, text: Optional[str] = None, blocks: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Update an existing message.

        Args:
            channel: Channel ID or name
            ts: Message timestamp
            text: New message text
            blocks: New blocks

        Returns:
            Slack API response
        """
        start_time = time.time()

        try:
            channel = self.validate_channel(channel)

            if not text and not blocks:
                raise SlackAPIError("Either text or blocks must be provided")

            self.logger.info(
                "Updating Slack message",
                channel=channel,
                ts=ts,
                has_text=bool(text),
                has_blocks=bool(blocks),
            )

            kwargs = {"channel": channel, "ts": ts}

            if text:
                kwargs["text"] = text
            if blocks:
                kwargs["blocks"] = blocks

            response = self.client.chat_update(**kwargs)

            # Log execution
            duration_ms = (time.time() - start_time) * 1000
            log_agent_execution(
                self.logger,
                "SlackClient",
                "update_message",
                duration_ms,
                channel=channel,
                ts=ts,
            )

            return response.data

        except SlackApiError as e:
            self.logger.warning("Slack API error, retrying", error=str(e))
            raise
        except Exception as e:
            log_error(self.logger, e, {"channel": channel, "ts": ts})
            raise SlackAPIError(f"Failed to update message: {str(e)}")

    def create_approval_blocks(
        self,
        title: str,
        description: str,
        action_id: str,
        approve_text: str = "Approve",
        deny_text: str = "Deny",
    ) -> List[Dict[str, Any]]:
        """
        Create standard approval message blocks.

        Args:
            title: Approval title
            description: Approval description
            action_id: Unique action ID
            approve_text: Text for approve button
            deny_text: Text for deny button

        Returns:
            List of Slack blocks
        """
        return [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{title}*\n\n{description}"},
            },
            {
                "type": "actions",
                "block_id": f"approval_actions_{action_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": approve_text},
                        "style": "primary",
                        "action_id": f"approve_{action_id}",
                        "value": "approve",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": deny_text},
                        "style": "danger",
                        "action_id": f"deny_{action_id}",
                        "value": "deny",
                    },
                ],
            },
        ]

    def create_status_blocks(
        self, title: str, status: str, details: Dict[str, Any], color: str = "good"
    ) -> List[Dict[str, Any]]:
        """
        Create standard status message blocks.

        Args:
            title: Status title
            status: Status value
            details: Additional details to display
            color: Message color

        Returns:
            List of Slack blocks
        """
        fields = []
        for key, value in details.items():
            fields.append(
                {
                    "type": "mrkdwn",
                    "text": f"*{key.replace('_', ' ').title()}:*\n{value}",
                }
            )

        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{title}*\n\nStatus: `{status}`"},
            }
        ]

        if fields:
            blocks.append({"type": "section", "fields": fields})

        return blocks


# Mock client for testing
class MockSlackClient:
    """Mock Slack client for testing and development."""

    def __init__(self, token: Optional[str] = None) -> None:
        self.logger = structlog.get_logger(__name__)
        self.bot_id = "mock_bot_id"
        self.team_id = "mock_team_id"
        self.logger.info("Mock Slack client initialized")

    def post_message(
        self, channel: str, text: Optional[str] = None, blocks: Optional[List[Dict[str, Any]]] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Mock posting a message to Slack."""
        print("\n" + "=" * 50)
        print(f"SLACK MESSAGE TO CHANNEL: {channel}")
        if text:
            print(f"MESSAGE: {text}")
        if blocks:
            print(f"BLOCKS: {json.dumps(blocks, indent=2)}")
        print("=" * 50 + "\n")

        return {"ok": True, "ts": "1234567890.123456", "channel": channel}

    def post_interactive_message(
        self, channel: str, text: str, actions: List[Dict[str, Any]], **kwargs: Any
    ) -> Dict[str, Any]:
        """Mock posting an interactive message."""
        return self.post_message(channel, text, actions)

    def update_message(
        self, channel: str, ts: str, text: Optional[str] = None, blocks: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Mock updating a message."""
        return self.post_message(channel, text, blocks)

    def create_approval_blocks(
        self, title: str, description: str, action_id: str, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Mock creating approval blocks."""
        return [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"{title}: {description}"},
            }
        ]

    def create_status_blocks(
        self, title: str, status: str, details: Dict[str, Any], **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Mock creating status blocks."""
        return [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"{title}: {status}"},
            }
        ]


# Global instance - lazy loaded
_slack_client = None


def get_slack_client() -> Union[SlackClient, MockSlackClient]:
    """Get Slack client instance (lazy loaded)."""
    global _slack_client
    if _slack_client is None:
        if settings.environment == "development" or not settings.slack_bot_token:
            _slack_client = MockSlackClient()
        else:
            _slack_client = SlackClient()
    return _slack_client


# For backward compatibility
slack_client = get_slack_client
