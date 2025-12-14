"""
Business logic services for GitHub API
"""

import logging
from typing import Dict, Any
from github_api.api_client import GitHubAPIClient

logger = logging.getLogger(__name__)


class GitHubService:
    """
    Service layer for GitHub operations.
    Handles business logic and data transformation.
    """
    
    def __init__(self):
        self.api_client = GitHubAPIClient()
    
    def get_user_complete_info(self, token: str) -> Dict[str, Any]:
        """
        Get complete GitHub user information including repos, orgs, and PRs.
        
        Args:
            token: GitHub Personal Access Token
            
        Returns:
            Dictionary with complete user information
        """
        logger.info("Starting to fetch complete user information")
        
        # Fetch user basic info
        user_data = self.api_client.get_user_info(token)
        username = user_data.get("login")
        
        # Fetch repositories
        repos_data = self.api_client.get_repositories(token)
        repositories = self._transform_repositories(repos_data)
        
        # Fetch organizations
        orgs_data = self.api_client.get_organizations(token)
        organizations = self._transform_organizations(orgs_data)
        
        # Fetch pull requests
        prs_data = self.api_client.get_pull_requests(token, username)
        pull_requests = self._transform_pull_requests(prs_data)
        
        # Build complete response
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
            "organizations": organizations,
            "pull_requests": pull_requests,
        }
        
        logger.info(
            f"Successfully fetched user info: "
            f"{len(repositories)} repos, "
            f"{len(organizations)} orgs, "
            f"{len(pull_requests)} PRs"
        )
        
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

