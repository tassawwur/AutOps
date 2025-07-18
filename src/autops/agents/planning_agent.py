import json
import openai
from typing import Dict, Any, Optional, Tuple
from ..config import settings
from ..utils.logging import get_logger

client = openai.OpenAI(api_key=settings.openai_api_key)
logger = get_logger(__name__)

# Define supported tools and their implementation status
TOOL_SUPPORT = {
    "github_client": {
        "supported": True,
        "actions": [
            "get_latest_pipeline_status",
            "get_repository_info",
            "get_pull_requests",
        ],
    },
    "gitlab_client": {
        "supported": False,
        "actions": [],
        "message": "GitLab integration is not yet implemented",
    },
    "datadog_client": {
        "supported": False,
        "actions": [],
        "message": "Datadog integration is not yet implemented",
    },
    "pagerduty_client": {
        "supported": False,
        "actions": [],
        "message": "PagerDuty integration is not yet implemented",
    },
    "slack_client": {
        "supported": True,
        "actions": ["post_message", "update_message", "post_interactive_message"],
    },
}


def validate_tool_support(tool: str, action: Optional[str] = None) -> Tuple[bool, str]:
    """
    Validates if a tool and action are supported.
    Returns (is_supported, error_message)
    """
    if tool not in TOOL_SUPPORT:
        return False, f"Unknown tool: {tool}"

    tool_info = TOOL_SUPPORT[tool]
    if not tool_info["supported"]:
        message = tool_info.get("message", f"{tool} is not yet implemented")
        return False, str(message)

    if action is not None and str(action) not in tool_info.get("actions", []):  # type: ignore[operator]
        return False, f"Action '{action}' is not supported for {tool}"

    return True, ""


def create_plan(structured_query: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a basic execution plan based on the structured query's intent.
    """
    intent = structured_query.get("intent")

    if not intent:
        return {"error": "No intent found in the structured query."}

    plan = {
        "intent": intent,
        "original_query": structured_query.get("original_query"),
        "steps": [],
    }

    if intent == "get_ci_cd_status":
        service_name = structured_query.get("entities", {}).get("service_name")
        if not service_name:
            return {
                "error": "Missing 'service_name' entity for intent 'get_ci_cd_status'."
            }

        # Validate tool support
        tool = "github_client"
        action = "get_latest_pipeline_status"
        is_supported, error_msg = validate_tool_support(tool, action)

        if not is_supported:
            logger.warning(f"Tool validation failed: {error_msg}")
            plan["steps"] = [
                {
                    "agent": "ResponseGenerationAgent",
                    "action": "generate_error_response",
                    "parameters": {
                        "message": f"I can't complete this request yet: {error_msg}. Please check GitHub manually or try a different request."
                    },
                    "status": "pending",
                }
            ]
        else:
            plan["steps"] = [
                {
                    "agent": "ToolExecutionAgent",
                    "tool": tool,
                    "action": action,
                    "parameters": {"repo_name": service_name},
                    "status": "pending",
                }
            ]
    elif intent == "investigate_incident":
        service_name = structured_query.get("entities", {}).get("service_name")
        if not service_name:
            return {
                "error": "Missing 'service_name' entity for intent "
                "'investigate_incident'."
            }

        plan["steps"] = [
            {
                "agent": "InformationRetrievalAgent",
                "action": "gather_context",
                "parameters": {"service_name": service_name},
                "status": "pending",
            },
            {
                "agent": "PlanningAgent",
                "action": "analyze_context_and_suggest_fix",
                "parameters": {"context": "output_of_previous_step"},
                "status": "pending",
            },
        ]
    else:
        # For now, we only handle two intents.
        plan["steps"] = [
            {
                "agent": "ResponseGenerationAgent",
                "action": "generate_not_implemented_response",
                "parameters": {
                    "message": f"I don't know how to handle the intent '{intent}' yet."
                },
                "status": "pending",
            }
        ]

    return plan


def analyze_context_and_suggest_fix(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Uses an LLM to analyze incident context and suggest a fix.
    """
    system_prompt = """
    You are an expert Senior Site Reliability Engineer. Your task is to analyze
    the provided context from various monitoring tools and determine the most
    likely root cause of an incident. Based on your analysis, you must suggest
    a single, simple remediation action. The output must be a JSON object
    containing your analysis and the suggested remediation.

    Example Output:
    {
      "analysis": "High error rates started immediately after the latest "
                 "deployment (deploy-123), which points to a bad code change.",
      "suggested_remediation": {
        "action": "rollback_deployment",
        "parameters": {
          "deployment_id": "deploy-123"
        }
      }
    }
    """

    context_str = json.dumps(context, indent=2)
    user_prompt = f"Here is the context for the incident:\n{context_str}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )

        content = response.choices[0].message.content
        if not content:
            raise Exception("Empty response from LLM")
        return json.loads(content)  # type: ignore[no-any-return]

    except Exception as e:
        error_msg = str(e)
        logger.error("LLM analysis failed", error=error_msg)
        return {
            "analysis": f"Failed to analyze context: {error_msg}",
            "suggested_remediation": {
                "action": "manual_investigation",
                "parameters": {"message": "Please investigate manually"},
            },
        }


if __name__ == "__main__":
    # Example usage for testing
    logger.info("Testing planning agent functionality")

    test_query = {
        "intent": "get_ci_cd_status",
        "entities": {"service_name": "checkout-service", "build_type": "latest"},
        "original_query": "Is the latest build passing for the checkout-service?",
    }

    result = create_plan(test_query)
    print(json.dumps(result, indent=2))

    parsed_plan = create_plan(test_query)
