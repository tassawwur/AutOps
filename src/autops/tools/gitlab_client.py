"""
GitLab API Client for CI/CD pipeline information and repository data.
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

import gitlab
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..config import get_settings
from ..utils.logging import get_logger, log_error, log_agent_execution
from ..utils.exceptions import GitLabAPIError, ValidationError

settings = get_settings()
logger = get_logger(__name__)


class GitLabClient:
    """
    Production-ready GitLab API client for CI/CD and repository operations.
    """

    def __init__(self) -> None:
        self.logger = get_logger(f"{__name__}.GitLabClient")

        # Initialize GitLab API client
        self.gl = gitlab.Gitlab(
            url=settings.gitlab_url, private_token=settings.gitlab_token
        )

        # Authenticate to validate token
        try:
            self.gl.auth()
            self.logger.info("GitLab client authenticated successfully")
        except Exception as e:
            self.logger.error("GitLab authentication failed", error=str(e))
            raise GitLabAPIError(f"GitLab authentication failed: {str(e)}")

    def validate_project_name(self, project_name: str) -> None:
        """Validate project name parameter."""
        if not project_name or not isinstance(project_name, str):
            raise ValidationError("Project name must be a non-empty string")

        if len(project_name.strip()) == 0:
            raise ValidationError("Project name cannot be empty")

    def _find_project(self, project_name: str) -> Optional[Any]:
        """
        Find GitLab project by name.

        Args:
            project_name: Name of the project to find

        Returns:
            Project object if found, None otherwise
        """
        try:
            # Try exact match first
            projects = self.gl.projects.list(search=project_name, simple=True)

            # Look for exact match
            for project in projects:
                if project.name.lower() == project_name.lower():
                    return self.gl.projects.get(project.id)

            # Look for partial match
            for project in projects:
                if project_name.lower() in project.name.lower():
                    return self.gl.projects.get(project.id)

            self.logger.warning("Project not found in GitLab", project=project_name)
            return None

        except Exception as e:
            self.logger.warning(
                "Failed to find project", project=project_name, error=str(e)
            )
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(gitlab.exceptions.GitlabError),
    )
    def get_last_deployment(self, service_name: str) -> Dict[str, Any]:
        """
        Get the last deployment information for a service/project.

        Args:
            service_name: Name of the service/project

        Returns:
            Dictionary containing deployment information

        Raises:
            GitLabAPIError: If API call fails
            ValidationError: If input validation fails
        """
        start_time = time.time()

        try:
            self.validate_project_name(service_name)
            self.logger.info("Fetching last deployment", service=service_name)

            # Find the project
            project = self._find_project(service_name)
            if not project:
                raise GitLabAPIError(f"Project '{service_name}' not found in GitLab")

            try:
                # Get deployments for the project
                deployments = project.deployments.list(
                    order_by="created_at", sort="desc", per_page=5
                )

                deployment_data = {
                    "service": service_name,
                    "project_id": project.id,
                    "query_time": datetime.now().isoformat(),
                    "deployment": None,
                    "has_deployments": False,
                }

                if deployments:
                    latest_deployment = deployments[0]

                    deployment_data.update(
                        {
                            "has_deployments": True,
                            "deployment": {
                                "id": latest_deployment.id,
                                "iid": latest_deployment.iid,
                                "status": latest_deployment.status,
                                "created_at": latest_deployment.created_at,
                                "updated_at": latest_deployment.updated_at,
                                "environment": (
                                    latest_deployment.environment.get("name", "Unknown")
                                    if hasattr(latest_deployment, "environment")
                                    else "Unknown"
                                ),
                                "ref": latest_deployment.ref,
                                "sha": latest_deployment.sha,
                                "web_url": (
                                    latest_deployment.web_url
                                    if hasattr(latest_deployment, "web_url")
                                    else None
                                ),
                            },
                        }
                    )

                    # Get commit information
                    try:
                        commit = project.commits.get(latest_deployment.sha)
                        deployment_data["deployment"]["commit"] = {
                            "id": commit.id,
                            "short_id": commit.short_id,
                            "title": commit.title,
                            "message": (
                                commit.message[:200] + "..."
                                if len(commit.message) > 200
                                else commit.message
                            ),
                            "author_name": commit.author_name,
                            "author_email": commit.author_email,
                            "created_at": commit.created_at,
                        }
                    except Exception as e:
                        self.logger.warning("Failed to fetch commit info", error=str(e))

                # Log execution
                duration_ms = (time.time() - start_time) * 1000
                log_agent_execution(
                    self.logger,
                    "GitLabClient",
                    "get_last_deployment",
                    duration_ms,
                    service=service_name,
                    has_deployments=deployment_data["has_deployments"],
                )

                return deployment_data

            except gitlab.exceptions.GitlabError as e:
                self.logger.warning("GitLab API error, retrying", error=str(e))
                raise

        except ValidationError:
            raise
        except GitLabAPIError:
            raise
        except Exception as e:
            log_error(self.logger, e, {"service": service_name})
            raise GitLabAPIError(f"Failed to fetch last deployment: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(gitlab.exceptions.GitlabError),
    )
    def get_pipeline_status(
        self, service_name: str, pipeline_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get pipeline status for a project.

        Args:
            service_name: Name of the service/project
            pipeline_id: Optional specific pipeline ID, otherwise gets latest

        Returns:
            Dictionary containing pipeline status
        """
        start_time = time.time()

        try:
            self.validate_project_name(service_name)
            self.logger.info(
                "Fetching pipeline status",
                service=service_name,
                pipeline_id=pipeline_id,
            )

            # Find the project
            project = self._find_project(service_name)
            if not project:
                raise GitLabAPIError(f"Project '{service_name}' not found in GitLab")

            try:
                if pipeline_id:
                    # Get specific pipeline
                    pipeline = project.pipelines.get(pipeline_id)
                    pipelines = [pipeline]
                else:
                    # Get latest pipelines
                    pipelines = project.pipelines.list(
                        order_by="created_at", sort="desc", per_page=5
                    )

                pipeline_data = {
                    "service": service_name,
                    "project_id": project.id,
                    "query_time": datetime.now().isoformat(),
                    "pipeline": None,
                    "has_pipelines": False,
                }

                if pipelines:
                    latest_pipeline = pipelines[0]

                    pipeline_data.update(
                        {
                            "has_pipelines": True,
                            "pipeline": {
                                "id": latest_pipeline.id,
                                "iid": latest_pipeline.iid,
                                "status": latest_pipeline.status,
                                "ref": latest_pipeline.ref,
                                "sha": latest_pipeline.sha,
                                "created_at": latest_pipeline.created_at,
                                "updated_at": latest_pipeline.updated_at,
                                "web_url": latest_pipeline.web_url,
                                "duration": latest_pipeline.duration,
                                "user": {
                                    "name": (
                                        latest_pipeline.user.get("name", "Unknown")
                                        if latest_pipeline.user
                                        else "Unknown"
                                    ),
                                    "username": (
                                        latest_pipeline.user.get("username", "Unknown")
                                        if latest_pipeline.user
                                        else "Unknown"
                                    ),
                                },
                            },
                        }
                    )

                    # Get pipeline jobs
                    try:
                        jobs = latest_pipeline.jobs.list(all=True)
                        pipeline_data["pipeline"]["jobs"] = []

                        for job in jobs:
                            job_info = {
                                "id": job.id,
                                "name": job.name,
                                "status": job.status,
                                "stage": job.stage,
                                "created_at": job.created_at,
                                "started_at": job.started_at,
                                "finished_at": job.finished_at,
                                "duration": job.duration,
                                "web_url": job.web_url,
                            }
                            pipeline_data["pipeline"]["jobs"].append(job_info)

                    except Exception as e:
                        self.logger.warning(
                            "Failed to fetch pipeline jobs", error=str(e)
                        )

                # Log execution
                duration_ms = (time.time() - start_time) * 1000
                log_agent_execution(
                    self.logger,
                    "GitLabClient",
                    "get_pipeline_status",
                    duration_ms,
                    service=service_name,
                    has_pipelines=pipeline_data["has_pipelines"],
                )

                return pipeline_data

            except gitlab.exceptions.GitlabError as e:
                self.logger.warning("GitLab API error, retrying", error=str(e))
                raise

        except Exception as e:
            log_error(self.logger, e, {"service": service_name})
            raise GitLabAPIError(f"Failed to fetch pipeline status: {str(e)}")

    def get_recent_commits(self, service_name: str, days: int = 7) -> Dict[str, Any]:
        """
        Get recent commits for a project.

        Args:
            service_name: Name of the service/project
            days: Number of days to look back

        Returns:
            Dictionary containing recent commits
        """
        start_time = time.time()

        try:
            self.validate_project_name(service_name)
            self.logger.info("Fetching recent commits", service=service_name, days=days)

            # Find the project
            project = self._find_project(service_name)
            if not project:
                raise GitLabAPIError(f"Project '{service_name}' not found in GitLab")

            # Calculate time range
            since = (datetime.now() - timedelta(days=days)).isoformat()

            try:
                commits = project.commits.list(
                    since=since, per_page=20, order="default"
                )

                commits_data = {
                    "service": service_name,
                    "project_id": project.id,
                    "days": days,
                    "query_time": datetime.now().isoformat(),
                    "commits": [],
                    "total_commits": len(commits),
                }

                for commit in commits:
                    commit_info = {
                        "id": commit.id,
                        "short_id": commit.short_id,
                        "title": commit.title,
                        "message": (
                            commit.message[:200] + "..."
                            if len(commit.message) > 200
                            else commit.message
                        ),
                        "author_name": commit.author_name,
                        "author_email": commit.author_email,
                        "created_at": commit.created_at,
                        "web_url": commit.web_url,
                    }
                    commits_data["commits"].append(commit_info)

                # Log execution
                duration_ms = (time.time() - start_time) * 1000
                log_agent_execution(
                    self.logger,
                    "GitLabClient",
                    "get_recent_commits",
                    duration_ms,
                    service=service_name,
                    commits_count=commits_data["total_commits"],
                )

                return commits_data

            except gitlab.exceptions.GitlabError as e:
                self.logger.warning("GitLab API error", error=str(e))
                raise GitLabAPIError(f"GitLab API error: {str(e)}")

        except Exception as e:
            log_error(self.logger, e, {"service": service_name})
            raise GitLabAPIError(f"Failed to fetch recent commits: {str(e)}")


# Global instance - lazy loaded
_gitlab_client = None


def get_gitlab_client() -> GitLabClient:
    """Get GitLab client instance (lazy loaded)."""
    global _gitlab_client
    if _gitlab_client is None:
        _gitlab_client = GitLabClient()
    return _gitlab_client


# Backward compatibility functions
def get_last_deployment(service_name: str) -> Dict[str, Any]:
    """Convenience function for backward compatibility."""
    return get_gitlab_client().get_last_deployment(service_name)


def get_pipeline_status(service_name: str, pipeline_id: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function for backward compatibility."""
    return get_gitlab_client().get_pipeline_status(service_name, pipeline_id)


# For backward compatibility
gitlab_client = get_gitlab_client


if __name__ == "__main__":
    # Example usage for testing
    from ..utils.logging import configure_logging

    configure_logging(level="DEBUG", json_logs=False)

    client = GitLabClient()

    try:
        # Test last deployment
        deployment = client.get_last_deployment("test-service")
        print(f"Last Deployment: {deployment}")

        # Test pipeline status
        pipeline = client.get_pipeline_status("test-service")
        print(f"Pipeline Status: {pipeline}")

        # Test recent commits
        commits = client.get_recent_commits("test-service")
        print(f"Recent Commits: {commits}")

    except Exception as e:
        print(f"GitLab Client Error: {e}")
