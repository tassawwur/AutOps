import openai
import json
from ..config import settings
from typing import Dict, List, Any, Optional
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

client = openai.OpenAI(api_key=settings.openai_api_key)


def generate_incident_remediation_message(analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Creates a Slack message with interactive buttons for remediation.
    """
    analysis = analysis_result.get("analysis", "No analysis provided.")
    suggestion = analysis_result.get("suggested_remediation", {})
    action = suggestion.get("action", "no_action")
    # Slack button values have a length limit, so we must be careful here
    params = json.dumps(suggestion.get("parameters", {}))

    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Incident Analysis:*\n{analysis}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"I suggest the following action: `{action}`",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve", "emoji": True},
                    "style": "primary",
                    "value": f"approve_{action}_{params}",
                    "action_id": "approve_remediation",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Deny", "emoji": True},
                    "style": "danger",
                    "value": f"deny_{action}",
                    "action_id": "deny_remediation",
                },
            ],
        },
    ]


def generate_response(query: str, verification_results: Dict[str, Any], 
                     tool_execution_results: Optional[List[Dict[str, Any]]] = None,
                     include_metrics: bool = True) -> Optional[str]:
    """
    Uses an LLM to generate a natural language response based on the
    execution result.
    """

    # Check for errors first
    if verification_results.get("status") == "failed":
        error = verification_results.get("error", "An unknown error occurred.")
        return f"I'm sorry, I couldn't complete your request. Reason: {error}"

    system_prompt = """
    You are a helpful DevOps AI assistant. Your task is to formulate a clear,
    concise, and friendly response to a user's query based on the data provided.
    The user is technical, so you can be direct. If the data includes a URL,
    make sure to include it in the response as a clickable link.
    """

    # We build a user message for the LLM that contains the original query
    # and the result data.
    result_data = json.dumps(verification_results.get("result", {}))
    user_prompt = f"""
    The user asked: '{query}'

    The data I retrieved is:
    {result_data}

    Please formulate a response based on this data.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"An unexpected error occurred while generating response: {e}")
        return "I encountered an error while trying to formulate a response."


if __name__ == "__main__":
    # Example usage
    test_query = "Is the latest build passing for the checkout-service?"
    test_result = {
        "status": "completed",
        "result": {
            "status": "success",
            "url": "https://github.com/example_org/checkout-service/actions/runs/12345",
        },
    }

    final_response = generate_response(test_query, test_result)
    print(final_response)

    test_result_failed = {
        "status": "failed",
        "error": "The repository 'checkout-service' does not exist.",
    }
    final_response_failed = generate_response(test_query, test_result_failed)
    print(final_response_failed)
