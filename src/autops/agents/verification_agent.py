"""
Verification Agent for validating execution results and providing feedback.
"""

import json
import time
from typing import Dict, Any, List

import openai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..config import get_settings
from ..utils.logging import get_logger, log_error, log_agent_execution
from ..utils.exceptions import AgentExecutionError

settings = get_settings()
client = openai.OpenAI(
    api_key=settings.openai_api_key,
    timeout=settings.openai_timeout,
    max_retries=settings.openai_max_retries,
)
logger = get_logger(__name__)


class VerificationAgent:
    """
    Agent responsible for verifying the results of executed actions
    and providing reflection on the overall workflow execution.
    """

    def __init__(self) -> None:
        self.model = settings.openai_model
        self.logger = get_logger(f"{__name__}.VerificationAgent")

    def validate_execution_result(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate if a step was executed successfully and the result is valid.

        Args:
            step: The executed step with its result

        Returns:
            Validation result with success status and details
        """
        start_time = time.time()

        try:
            self.logger.info(
                "Validating execution result", step_agent=step.get("agent")
            )

            validation_result = {
                "valid": False,
                "confidence": 0.0,
                "issues": [],
                "suggestions": [],
            }

            # Check basic execution status
            if step.get("status") != "completed":
                validation_result["issues"].append(
                    f"Step failed with status: {step.get('status')}"
                )
                validation_result["suggestions"].append(
                    "Retry the step or check error details"
                )
                return validation_result

            # Check if result exists
            result = step.get("result")
            if not result:
                validation_result["issues"].append(
                    "No result returned from step execution"
                )
                validation_result["suggestions"].append(
                    "Verify the agent/tool implementation"
                )
                return validation_result

            # Validate based on step type
            agent_name = step.get("agent")
            tool_name = step.get("tool")
            action = step.get("action")

            if agent_name == "InformationRetrievalAgent" and action == "gather_context":
                validation_result = self._validate_context_result(result)
            elif (
                tool_name == "github_client" and action == "get_latest_pipeline_status"
            ):
                validation_result = self._validate_github_result(result)
            elif (
                agent_name == "PlanningAgent"
                and action == "analyze_context_and_suggest_fix"
            ):
                validation_result = self._validate_analysis_result(result)
            else:
                # Generic validation
                validation_result["valid"] = True
                validation_result["confidence"] = 0.8
                validation_result["suggestions"].append(
                    "Manual review recommended for this result type"
                )

            # Log execution
            duration_ms = (time.time() - start_time) * 1000
            log_agent_execution(
                self.logger,
                "VerificationAgent",
                "validate_execution_result",
                duration_ms,
                valid=validation_result["valid"],
                confidence=validation_result["confidence"],
            )

            return validation_result

        except Exception as e:
            log_error(self.logger, e, {"step": step})
            raise AgentExecutionError(f"Verification failed: {str(e)}")

    def _validate_context_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate context gathering results."""
        validation = {"valid": True, "confidence": 0.9, "issues": [], "suggestions": []}

        required_keys = ["metrics", "incidents", "deployment"]
        missing_keys = [key for key in required_keys if key not in result]

        if missing_keys:
            validation["issues"].append(f"Missing context data: {missing_keys}")
            validation["valid"] = False
            validation["confidence"] = 0.3

        return validation

    def _validate_github_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate GitHub API results."""
        validation = {"valid": True, "confidence": 0.9, "issues": [], "suggestions": []}

        required_keys = ["status", "conclusion"]
        missing_keys = [key for key in required_keys if key not in result]

        if missing_keys:
            validation["issues"].append(f"Missing GitHub data: {missing_keys}")
            validation["valid"] = False
            validation["confidence"] = 0.4

        return validation

    def _validate_analysis_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate incident analysis results."""
        validation = {"valid": True, "confidence": 0.9, "issues": [], "suggestions": []}

        required_keys = ["analysis", "suggested_remediation"]
        missing_keys = [key for key in required_keys if key not in result]

        if missing_keys:
            validation["issues"].append(f"Missing analysis data: {missing_keys}")
            validation["valid"] = False
            validation["confidence"] = 0.2

        # Check if suggested remediation has required structure
        if "suggested_remediation" in result:
            remediation = result["suggested_remediation"]
            if not isinstance(remediation, dict) or "action" not in remediation:
                validation["issues"].append("Invalid remediation format")
                validation["confidence"] = max(0.4, validation["confidence"] - 0.3)

        return validation

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError)),
    )
    def reflect_on_workflow(
        self, plan: Dict[str, Any], execution_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Provide overall reflection on the workflow execution using LLM.

        Args:
            plan: The original execution plan
            execution_results: List of step execution results

        Returns:
            Reflection with insights and recommendations
        """
        start_time = time.time()

        try:
            self.logger.info(
                "Reflecting on workflow execution", plan_intent=plan.get("intent")
            )

            system_prompt = """
            You are an expert DevOps engineer reviewing the execution of an
            automated workflow. Your task is to analyze the workflow plan and
            execution results, then provide insights about what went well, what
            could be improved, and recommendations for future actions.

            Provide your response as a JSON object with the following structure:
            {
              "overall_success": boolean,
              "confidence_score": float (0.0-1.0),
              "insights": {
                "successes": ["list of things that went well"],
                "failures": ["list of things that failed or could be "
                             "improved"],
                "unexpected_findings": ["list of unexpected discoveries"]
              },
              "recommendations": {
                "immediate_actions": ["list of actions to take now"],
                "future_improvements": ["list of process "
                                       "improvements"]
              },
              "risk_assessment": {
                "risk_level": "low|medium|high",
                "risk_factors": ["list of identified risks"]
              }
            }
            """

            user_prompt = f"""
            Original Plan:
            {json.dumps(plan, indent=2)}

            Execution Results:
            {json.dumps(execution_results, indent=2)}

            Please analyze this workflow execution and provide your insights.
            """

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            reflection = json.loads(response.choices[0].message.content)

            # Add metadata
            reflection.update(
                {
                    "workflow_id": plan.get("id", "unknown"),
                    "intent": plan.get("intent"),
                    "total_steps": len(execution_results),
                    "successful_steps": len(
                        [r for r in execution_results if r.get("status") == "completed"]
                    ),
                    "reflection_time": time.time(),
                    "processing_time_ms": (time.time() - start_time) * 1000,
                }
            )

            # Log execution
            duration_ms = (time.time() - start_time) * 1000
            log_agent_execution(
                self.logger,
                "VerificationAgent",
                "reflect_on_workflow",
                duration_ms,
                overall_success=reflection.get("overall_success"),
                confidence_score=reflection.get("confidence_score"),
            )

            return reflection

        except json.JSONDecodeError as e:
            log_error(self.logger, e, {"plan": plan})
            raise AgentExecutionError("Failed to parse LLM reflection response")
        except Exception as e:
            log_error(self.logger, e, {"plan": plan})
            raise AgentExecutionError(f"Workflow reflection failed: {str(e)}")


# Global instance
verification_agent = VerificationAgent()


def validate_execution_result(step: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function for backward compatibility."""
    return verification_agent.validate_execution_result(step)


def reflect_on_workflow(
    plan: Dict[str, Any], execution_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Convenience function for backward compatibility."""
    return verification_agent.reflect_on_workflow(plan, execution_results)


if __name__ == "__main__":
    # Example usage for testing
    from ..utils.logging import configure_logging

    configure_logging(level="DEBUG", json_logs=False)

    agent = VerificationAgent()

    # Test step validation
    test_step = {
        "agent": "InformationRetrievalAgent",
        "action": "gather_context",
        "status": "completed",
        "result": {
            "metrics": {"service": "test-service", "error_rate": "2.1%"},
            "incidents": {"service": "test-service", "incidents": []},
            "deployment": {"service": "test-service", "deployment": "deploy-456"},
        },
    }

    try:
        validation = agent.validate_execution_result(test_step)
        print(f"Validation Result: {json.dumps(validation, indent=2)}")
    except Exception as e:
        print(f"Validation Error: {e}")

    # Test workflow reflection
    test_plan = {
        "intent": "investigate_incident",
        "original_query": "Payment service having issues",
        "steps": [],
    }

    test_results = [test_step]

    try:
        reflection = agent.reflect_on_workflow(test_plan, test_results)
        print(f"Workflow Reflection: {json.dumps(reflection, indent=2)}")
    except Exception as e:
        print(f"Reflection Error: {e}")
