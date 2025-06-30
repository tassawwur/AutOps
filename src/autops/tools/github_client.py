import time
from datetime import datetime, timedelta
from typing import Dict, Any
from github import Github, GithubException
from github.Repository import Repository
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import structlog

from ..config import settings
from ..utils.exceptions import GitHubAPIError, ValidationError
from ..utils.logging import log_error, log_agent_execution


class GitHubClient:
    """Production-ready GitHub client with comprehensive functionality."""

    def __init__(self, token: str = None, owner: str = None):
        """
        Initialize GitHub client.

        Args:
            token: GitHub token. If not provided, uses settings.github_token
            owner: GitHub repository owner. If not provided, uses settings.github_owner
        """
        self.logger = structlog.get_logger(__name__)
        self.token = token or settings.github_token
        self.owner = owner or settings.github_owner

        if not self.token:
            raise GitHubAPIError("GitHub token is required")
        if not self.owner:
            raise GitHubAPIError("GitHub owner is required")

        self._client = Github(self.token)

        # Verify authentication
        try:
            user = self._client.get_user()
            self.authenticated_user = user.login
            self.logger.info(
                "GitHub client initialized successfully",
                user=self.authenticated_user,
                owner=self.owner,
            )
        except GithubException as e:
            self.logger.error("Failed to authenticate with GitHub", error=str(e))
            raise GitHubAPIError(f"GitHub authentication failed: {str(e)}")

    def validate_repo_name(self, repo_name: str) -> None:
        """Validate repository name format."""
        if not repo_name:
            raise ValidationError("Repository name cannot be empty")

        if "/" in repo_name:
            raise ValidationError("Repository name should not contain owner prefix")

    def _get_repository(self, repo_name: str) -> Repository:
        """Get repository object with error handling."""
        try:
            self.validate_repo_name(repo_name)
            full_name = f"{self.owner}/{repo_name}"
            return self._client.get_repo(full_name)
        except GithubException as e:
            if e.status == 404:
                raise GitHubAPIError(
                    f"Repository '{repo_name}' not found in '{self.owner}'"
                )
            else:
                raise GitHubAPIError(f"GitHub API error: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(GithubException),
    )
    def get_latest_pipeline_status(
        self, repo_name: str, branch: str = None
    ) -> Dict[str, Any]:
        """
        Get the status of the latest GitHub Actions workflow run.

        Args:
            repo_name: Repository name
            branch: Branch name (defaults to default branch)

        Returns:
            Dictionary containing pipeline status information
        """
        start_time = time.time()

        try:
            self.logger.info(
                "Fetching latest pipeline status", repo=repo_name, branch=branch
            )

            repo = self._get_repository(repo_name)
            target_branch = branch or repo.default_branch

            # Get workflow runs for the branch
            workflow_runs = repo.get_workflow_runs(branch=target_branch)

            pipeline_data = {
                "repository": repo_name,
                "owner": self.owner,
                "branch": target_branch,
                "query_time": datetime.now().isoformat(),
                "has_runs": False,
                "latest_run": None,
                "workflow_summary": {},
            }

            if workflow_runs.totalCount == 0:
                pipeline_data.update(
                    {
                        "status": "neutral",
                        "conclusion": "no_runs",
                        "message": "No workflow runs found.",
                    }
                )
            else:
                pipeline_data["has_runs"] = True
                latest_run = workflow_runs[0]

                # Get workflow details
                workflow = None
                try:
                    workflow = repo.get_workflow(latest_run.workflow_id)
                except Exception:
                    pass

                pipeline_data["latest_run"] = {
                    "id": latest_run.id,
                    "number": latest_run.run_number,
                    "status": latest_run.status,
                    "conclusion": latest_run.conclusion,
                    "url": latest_run.html_url,
                    "created_at": latest_run.created_at.isoformat()
                    if latest_run.created_at
                    else None,
                    "updated_at": latest_run.updated_at.isoformat()
                    if latest_run.updated_at
                    else None,
                    "head_sha": latest_run.head_sha,
                    "head_branch": latest_run.head_branch,
                    "event": latest_run.event,
                    "workflow_name": workflow.name if workflow else "Unknown",
                }

                # Calculate duration if completed
                if latest_run.created_at and latest_run.updated_at:
                    duration = (
                        latest_run.updated_at - latest_run.created_at
                    ).total_seconds()
                    pipeline_data["latest_run"]["duration_seconds"] = duration

                # Get jobs for the latest run
                try:
                    jobs = latest_run.jobs()
                    pipeline_data["latest_run"]["jobs"] = []

                    for job in jobs:
                        job_info = {
                            "id": job.id,
                            "name": job.name,
                            "status": job.status,
                            "conclusion": job.conclusion,
                            "started_at": job.started_at.isoformat()
                            if job.started_at
                            else None,
                            "completed_at": job.completed_at.isoformat()
                            if job.completed_at
                            else None,
                            "url": job.html_url,
                        }
                        pipeline_data["latest_run"]["jobs"].append(job_info)

                except Exception as e:
                    self.logger.warning("Failed to fetch job details", error=str(e))

                # Set overall status for backward compatibility
                pipeline_data.update(
                    {
                        "status": latest_run.status,
                        "conclusion": latest_run.conclusion,
                        "url": latest_run.html_url,
                    }
                )

                # Get workflow summary
                try:
                    recent_runs = list(workflow_runs[:10])
                    summary = {"total_runs": len(recent_runs), "by_conclusion": {}}

                    for run in recent_runs:
                        conclusion = run.conclusion or "in_progress"
                        summary["by_conclusion"][conclusion] = (
                            summary["by_conclusion"].get(conclusion, 0) + 1
                        )

                    pipeline_data["workflow_summary"] = summary
                except Exception as e:
                    self.logger.warning(
                        "Failed to generate workflow summary", error=str(e)
                    )

            # Log execution
            duration_ms = (time.time() - start_time) * 1000
            log_agent_execution(
                self.logger,
                "GitHubClient",
                "get_latest_pipeline_status",
                duration_ms,
                repo=repo_name,
                has_runs=pipeline_data["has_runs"],
            )

            return pipeline_data

        except GithubException as e:
            self.logger.warning("GitHub API error, retrying", error=str(e))
            raise
        except Exception as e:
            log_error(self.logger, e, {"repo": repo_name, "branch": branch})
            raise GitHubAPIError(f"Failed to fetch pipeline status: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(GithubException),
    )
    def get_recent_commits(
        self, repo_name: str, branch: str = None, days: int = 7
    ) -> Dict[str, Any]:
        """
        Get recent commits for a repository.

        Args:
            repo_name: Repository name
            branch: Branch name (defaults to default branch)
            days: Number of days to look back

        Returns:
            Dictionary containing recent commits
        """
        start_time = time.time()

        try:
            self.logger.info(
                "Fetching recent commits", repo=repo_name, branch=branch, days=days
            )

            repo = self._get_repository(repo_name)
            target_branch = branch or repo.default_branch

            # Calculate time range
            since = datetime.now() - timedelta(days=days)

            commits = repo.get_commits(sha=target_branch, since=since)

            commits_data = {
                "repository": repo_name,
                "owner": self.owner,
                "branch": target_branch,
                "days": days,
                "query_time": datetime.now().isoformat(),
                "commits": [],
                "total_commits": 0,
                "contributors": set(),
                "commit_activity": {"by_day": {}, "by_hour": {}},
            }

            commit_list = list(commits)
            commits_data["total_commits"] = len(commit_list)

            for commit in commit_list[:50]:  # Limit to 50 commits
                commit_info = {
                    "sha": commit.sha,
                    "short_sha": commit.sha[:7],
                    "message": commit.commit.message,
                    "author": {
                        "name": commit.commit.author.name,
                        "email": commit.commit.author.email,
                        "date": commit.commit.author.date.isoformat()
                        if commit.commit.author.date
                        else None,
                    },
                    "committer": {
                        "name": commit.commit.committer.name,
                        "email": commit.commit.committer.email,
                        "date": commit.commit.committer.date.isoformat()
                        if commit.commit.committer.date
                        else None,
                    },
                    "url": commit.html_url,
                    "stats": {
                        "additions": commit.stats.additions if commit.stats else 0,
                        "deletions": commit.stats.deletions if commit.stats else 0,
                        "total": commit.stats.total if commit.stats else 0,
                    },
                }

                commits_data["commits"].append(commit_info)
                commits_data["contributors"].add(commit.commit.author.name)

                # Track activity patterns
                if commit.commit.author.date:
                    commit_date = commit.commit.author.date
                    day_key = commit_date.strftime("%Y-%m-%d")
                    hour_key = str(commit_date.hour)

                    commits_data["commit_activity"]["by_day"][day_key] = (
                        commits_data["commit_activity"]["by_day"].get(day_key, 0) + 1
                    )
                    commits_data["commit_activity"]["by_hour"][hour_key] = (
                        commits_data["commit_activity"]["by_hour"].get(hour_key, 0) + 1
                    )

            # Convert set to list for JSON serialization
            commits_data["contributors"] = list(commits_data["contributors"])
            commits_data["unique_contributors"] = len(commits_data["contributors"])

            # Log execution
            duration_ms = (time.time() - start_time) * 1000
            log_agent_execution(
                self.logger,
                "GitHubClient",
                "get_recent_commits",
                duration_ms,
                repo=repo_name,
                commits_count=commits_data["total_commits"],
            )

            return commits_data

        except GithubException as e:
            self.logger.warning("GitHub API error, retrying", error=str(e))
            raise
        except Exception as e:
            log_error(self.logger, e, {"repo": repo_name, "branch": branch})
            raise GitHubAPIError(f"Failed to fetch recent commits: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(GithubException),
    )
    def get_pull_requests(
        self, repo_name: str, state: str = "open", limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get pull requests for a repository.

        Args:
            repo_name: Repository name
            state: PR state (open, closed, all)
            limit: Maximum number of PRs to return

        Returns:
            Dictionary containing pull requests
        """
        start_time = time.time()

        try:
            self.logger.info(
                "Fetching pull requests", repo=repo_name, state=state, limit=limit
            )

            repo = self._get_repository(repo_name)

            pulls = repo.get_pulls(state=state, sort="updated", direction="desc")

            prs_data = {
                "repository": repo_name,
                "owner": self.owner,
                "state": state,
                "query_time": datetime.now().isoformat(),
                "pull_requests": [],
                "total_count": 0,
                "summary": {"by_state": {}, "by_author": {}},
            }

            pr_list = list(pulls)[:limit]
            prs_data["total_count"] = len(pr_list)

            for pr in pr_list:
                pr_info = {
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "author": pr.user.login if pr.user else "Unknown",
                    "created_at": pr.created_at.isoformat() if pr.created_at else None,
                    "updated_at": pr.updated_at.isoformat() if pr.updated_at else None,
                    "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                    "head_branch": pr.head.ref,
                    "base_branch": pr.base.ref,
                    "url": pr.html_url,
                    "mergeable": pr.mergeable,
                    "draft": pr.draft,
                    "additions": pr.additions,
                    "deletions": pr.deletions,
                    "changed_files": pr.changed_files,
                    "comments": pr.comments,
                    "review_comments": pr.review_comments,
                    "commits": pr.commits,
                }

                prs_data["pull_requests"].append(pr_info)

                # Summary statistics
                prs_data["summary"]["by_state"][pr.state] = (
                    prs_data["summary"]["by_state"].get(pr.state, 0) + 1
                )

                author = pr.user.login if pr.user else "Unknown"
                prs_data["summary"]["by_author"][author] = (
                    prs_data["summary"]["by_author"].get(author, 0) + 1
                )

            # Log execution
            duration_ms = (time.time() - start_time) * 1000
            log_agent_execution(
                self.logger,
                "GitHubClient",
                "get_pull_requests",
                duration_ms,
                repo=repo_name,
                prs_count=prs_data["total_count"],
            )

            return prs_data

        except GithubException as e:
            self.logger.warning("GitHub API error, retrying", error=str(e))
            raise
        except Exception as e:
            log_error(self.logger, e, {"repo": repo_name, "state": state})
            raise GitHubAPIError(f"Failed to fetch pull requests: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(GithubException),
    )
    def get_repository_info(self, repo_name: str) -> Dict[str, Any]:
        """
        Get comprehensive repository information.

        Args:
            repo_name: Repository name

        Returns:
            Dictionary containing repository information
        """
        start_time = time.time()

        try:
            self.logger.info("Fetching repository info", repo=repo_name)

            repo = self._get_repository(repo_name)

            repo_data = {
                "name": repo.name,
                "full_name": repo.full_name,
                "description": repo.description,
                "private": repo.private,
                "fork": repo.fork,
                "created_at": repo.created_at.isoformat() if repo.created_at else None,
                "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
                "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
                "size": repo.size,
                "stargazers_count": repo.stargazers_count,
                "watchers_count": repo.watchers_count,
                "forks_count": repo.forks_count,
                "open_issues_count": repo.open_issues_count,
                "default_branch": repo.default_branch,
                "language": repo.language,
                "languages": {},
                "topics": list(repo.get_topics()),
                "url": repo.html_url,
                "clone_url": repo.clone_url,
                "has_issues": repo.has_issues,
                "has_projects": repo.has_projects,
                "has_wiki": repo.has_wiki,
                "has_pages": repo.has_pages,
                "has_downloads": repo.has_downloads,
                "archived": repo.archived,
                "disabled": repo.disabled,
                "visibility": repo.visibility
                if hasattr(repo, "visibility")
                else "public",
            }

            # Get languages
            try:
                languages = repo.get_languages()
                total_bytes = sum(languages.values())
                repo_data["languages"] = {
                    lang: {
                        "bytes": bytes_count,
                        "percentage": round((bytes_count / total_bytes) * 100, 2)
                        if total_bytes > 0
                        else 0,
                    }
                    for lang, bytes_count in languages.items()
                }
            except Exception as e:
                self.logger.warning("Failed to fetch languages", error=str(e))

            # Get recent activity summary
            try:
                recent_commits = list(repo.get_commits()[:10])
                repo_data["recent_activity"] = {
                    "recent_commits_count": len(recent_commits),
                    "last_commit_date": recent_commits[0].commit.author.date.isoformat()
                    if recent_commits and recent_commits[0].commit.author.date
                    else None,
                }
            except Exception as e:
                self.logger.warning("Failed to fetch recent activity", error=str(e))

            # Log execution
            duration_ms = (time.time() - start_time) * 1000
            log_agent_execution(
                self.logger,
                "GitHubClient",
                "get_repository_info",
                duration_ms,
                repo=repo_name,
                stars=repo_data["stargazers_count"],
            )

            return repo_data

        except GithubException as e:
            self.logger.warning("GitHub API error, retrying", error=str(e))
            raise
        except Exception as e:
            log_error(self.logger, e, {"repo": repo_name})
            raise GitHubAPIError(f"Failed to fetch repository info: {str(e)}")

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get GitHub API rate limit status."""
        try:
            rate_limit = self._client.get_rate_limit()
            return {
                "core": {
                    "limit": rate_limit.core.limit,
                    "remaining": rate_limit.core.remaining,
                    "reset": rate_limit.core.reset.isoformat()
                    if rate_limit.core.reset
                    else None,
                },
                "search": {
                    "limit": rate_limit.search.limit,
                    "remaining": rate_limit.search.remaining,
                    "reset": rate_limit.search.reset.isoformat()
                    if rate_limit.search.reset
                    else None,
                },
            }
        except Exception as e:
            log_error(self.logger, e)
            raise GitHubAPIError(f"Failed to fetch rate limit status: {str(e)}")


# Global instance - lazy loaded
_github_client = None


def get_github_client() -> GitHubClient:
    """Get GitHub client instance (lazy loaded)."""
    global _github_client
    if _github_client is None:
        _github_client = GitHubClient(
            token=settings.github_token, owner=settings.github_owner
        )
    return _github_client


# Backward compatibility functions
def get_latest_pipeline_status(repo_name: str) -> Dict[str, Any]:
    """Convenience function for backward compatibility."""
    return get_github_client().get_latest_pipeline_status(repo_name)


def get_recent_commits(repo_name: str, days: int = 7) -> Dict[str, Any]:
    """Convenience function for backward compatibility."""
    return get_github_client().get_recent_commits(repo_name, days=days)


def get_pull_requests(repo_name: str, state: str = "open") -> Dict[str, Any]:
    """Convenience function for backward compatibility."""
    return get_github_client().get_pull_requests(repo_name, state=state)


# For backward compatibility
github_client = get_github_client
