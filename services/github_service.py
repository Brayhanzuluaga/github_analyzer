"""
Business logic services for GitHub API
"""

import asyncio
import logging
from typing import Dict, Any
from services.github_api_client import GitHubAPIClient

logger = logging.getLogger(__name__)


class GitHubService:
    """
    Service layer for GitHub operations.
    Handles business logic and data transformation.
    """
    
    def __init__(self):
        self.api_client = GitHubAPIClient()
    
    async def get_user_complete_info(self, token: str) -> Dict[str, Any]:
        """
        Get complete GitHub user information including repos, orgs, and PRs.
        Uses parallel requests to optimize performance with partial failure handling.
        
        Args:
            token: GitHub Personal Access Token
            
        Returns:
            Dictionary with complete user information and metadata about partial failures
        """
        logger.info("Starting to fetch complete user information (parallel mode)")
        
        user_data = await self.api_client.get_user_info(token)
        
        username = user_data.get("login")
        if not username:
            logger.error(f"Missing 'login' field in user data. Available keys: {list(user_data.keys())}")
            raise ValueError("Unable to fetch username from GitHub API. 'login' field is missing.")
        
        logger.info(f"Fetched user info for: {username}")
        
        logger.info("Fetching repos, orgs, and PRs in parallel...")
        results = await asyncio.gather(
            self.api_client.get_repositories(token),
            self.api_client.get_organizations(token),
            self.api_client.get_pull_requests(token, username),
            return_exceptions=True
        )
        
        repos_result, orgs_result, prs_result = results
        
        repos_error = None
        orgs_error = None
        prs_error = None
        

        if isinstance(repos_result, Exception):
            logger.warning(f"Failed to fetch repositories: {type(repos_result).__name__}: {str(repos_result)}")
            repositories = []
            repos_metadata = {
                "total_fetched": 0,
                "has_more": False,
                "limit_reached": False,
                "pages_fetched": 0,
                "error": str(repos_result)
            }
            repos_error = str(repos_result)
        else:
            repos_data, repos_metadata = repos_result
            repositories = self._transform_repositories(repos_data)
            repos_metadata["total_fetched"] = len(repositories)
        
        if isinstance(orgs_result, Exception):
            logger.warning(f"Failed to fetch organizations: {type(orgs_result).__name__}: {str(orgs_result)}")
            organizations = []
            orgs_error = str(orgs_result)
        else:
            organizations = self._transform_organizations(orgs_result)
        
        if isinstance(prs_result, Exception):
            logger.warning(f"Failed to fetch pull requests: {type(prs_result).__name__}: {str(prs_result)}")
            pull_requests = []
            prs_error = str(prs_result)
        else:
            pull_requests = self._transform_pull_requests(prs_result)
        

        user_info = {
            "user": {
                "login": user_data.get("login"),
                "name": user_data.get("name"),
                "email": user_data.get("email"),
                "bio": user_data.get("bio"),
                "public_repos": user_data.get("public_repos"),
                "followers": user_data.get("followers"),
                "following": user_data.get("following"),
            },
            "repositories": repositories,
            "repositories_metadata": repos_metadata,
            "organizations": organizations,
            "pull_requests": pull_requests,
            "metadata": {
                "partial_failures": {
                    "repositories": repos_error is not None,
                    "organizations": orgs_error is not None,
                    "pull_requests": prs_error is not None,
                },
                "errors": {
                    "repositories": repos_error,
                    "organizations": orgs_error,
                    "pull_requests": prs_error,
                } if any([repos_error, orgs_error, prs_error]) else None
            }
        }
        
        success_count = sum([
            not isinstance(repos_result, Exception),
            not isinstance(orgs_result, Exception),
            not isinstance(prs_result, Exception)
        ])
        
        logger.info(
            f"Successfully fetched user info: "
            f"{len(repositories)} repos, "
            f"{len(organizations)} orgs, "
            f"{len(pull_requests)} PRs "
            f"({success_count}/3 endpoints succeeded)"
        )
        
        if any([repos_error, orgs_error, prs_error]):
            logger.warning("Some endpoints failed, but returning partial data")
        
        return user_info
    
    def _transform_repositories(self, repos_data: list) -> list:
        """Transform raw repository data to response format"""
        repositories = []
        for repo in repos_data:
            repositories.append({
                "name": repo.get("name"),
                "full_name": repo.get("full_name"),
                "private": repo.get("private", False),
                "description": repo.get("description"),
                "html_url": repo.get("html_url"),
                "language": repo.get("language"),
                "created_at": repo.get("created_at"),
                "updated_at": repo.get("updated_at"),
                "stargazers_count": repo.get("stargazers_count", 0),
            })
        return repositories
    
    def _transform_organizations(self, orgs_data: list) -> list:
        """Transform raw organization data to response format"""
        organizations = []
        for org in orgs_data:
            organizations.append({
                "login": org.get("login"),
                "description": org.get("description"),
                "url": org.get("url"),
            })
        return organizations
    
    def _transform_pull_requests(self, prs_data: list) -> list:
        """Transform raw pull request data to response format"""
        pull_requests = []
        for pr in prs_data:
            repo_url = pr.get("repository_url", "")
            repo_name = "/".join(repo_url.split("/")[-2:]) if repo_url else "unknown"
            
            pull_requests.append({
                "title": pr.get("title"),
                "state": pr.get("state"),
                "html_url": pr.get("html_url"),
                "created_at": pr.get("created_at"),
                "repository": repo_name,
            })
        return pull_requests