import json
from typing import Dict, Any, Optional, Union
from ..tools.github_client import github_client
from ..agents.information_retrieval_agent import InformationRetrievalAgent
from ..agents.planning_agent import analyze_context_and_suggest_fix

# Agent and Tool mapping
AGENTS = {
    "InformationRetrievalAgent": InformationRetrievalAgent(),
    # The PlanningAgent's analysis function is treated like a tool here
    "PlanningAgent": {
        "analyze_context_and_suggest_fix": analyze_context_and_suggest_fix
    },
}
TOOLS = {"github_client": github_client}


def execute_step(step: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Executes a single step from a plan by calling the specified agent or tool.
    """
    agent_name = step.get("agent")
    tool_name = step.get("tool")
    action = step.get("action")
    parameters = step.get("parameters", {})

    # If the step requires context from a previous step, inject it.
    if parameters.get("context") == "output_of_previous_step":
        parameters["context"] = context

    try:
        if agent_name:
            agent = AGENTS[agent_name]
            method_to_call = (
                agent[action] if isinstance(agent, dict) else getattr(agent, action)
            )
            result = method_to_call(**parameters)
        elif tool_name:
            tool = TOOLS[tool_name]
            method_to_call = getattr(tool, action)
            result = method_to_call(**parameters)
        else:
            raise ValueError("Step must specify an agent or a tool.")

        step["status"] = "completed"
        step["result"] = result
    except Exception as e:
        step["status"] = "failed"
        step["error"] = str(e)

    return step


if __name__ == "__main__":
    # Example for multi-step incident investigation
    incident_plan = {
        "intent": "investigate_incident",
        "steps": [
            {
                "agent": "InformationRetrievalAgent",
                "action": "gather_context",
                "parameters": {"service_name": "payment-service"},
                "status": "pending",
            },
            {
                "agent": "PlanningAgent",
                "action": "analyze_context_and_suggest_fix",
                "parameters": {"context": "output_of_previous_step"},
                "status": "pending",
            },
        ],
    }

    # Step 1: Gather Context
    step1 = incident_plan["steps"][0]
    print("--- EXECUTING STEP 1 ---")
    step1_result = execute_step(step1)
    print(json.dumps(step1_result, indent=2))

    print("\n" + "=" * 50 + "\n")

    # Step 2: Analyze Context
    if step1_result["status"] == "completed":
        step2 = incident_plan["steps"][1]
        print("--- EXECUTING STEP 2 ---")
        # Pass the result of step 1 as context to step 2
        step2_result = execute_step(step2, context=step1_result["result"])
        print(json.dumps(step2_result, indent=2))
