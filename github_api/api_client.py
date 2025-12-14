"""
GitHub API Client
Handles external API communication with GitHub
"""

import logging
from typing import List, Dict, Any
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class GitHubAPIClient:
    """
    Client for GitHub API communication.
    Handles all external HTTP requests to GitHub.
    """
    
    def __init__(self):
        self.base_url = settings.GITHUB_API_BASE_URL
        self.api_version = settings.GITHUB_API_VERSION
        self.timeout = settings.GITHUB_API_TIMEOUT
    
    def _build_headers(self, token: str) -> Dict[str, str]:
        """Build headers for GitHub API requests"""
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": self.api_version,
        }
    
    def get_user_info(self, token: str) -> Dict[str, Any]:
        """Fetch authenticated user information"""
        url = f"{self.base_url}/user"
        headers = self._build_headers(token)
        
        logger.info(f"Fetching user info from: {url}")
        
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    
    def get_repositories(self, token: str) -> List[Dict[str, Any]]:
        """Fetch all repositories (public and private) for authenticated user"""
        url = f"{self.base_url}/user/repos"
        headers = self._build_headers(token)
        params = {
            "per_page": 100,
            "type": "all",
            "sort": "updated",
        }
        
        logger.info(f"Fetching repositories from: {url}")
        
        all_repos = []
        page = 1
        
        with httpx.Client(timeout=self.timeout) as client:
            while True:
                params["page"] = page
                response = client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                repos = response.json()
                if not repos:
                    break
                
                all_repos.extend(repos)
                page += 1
                
                if page > 10:
                    break
        
        logger.info(f"Fetched {len(all_repos)} repositories")
        return all_repos
    
    def get_organizations(self, token: str) -> List[Dict[str, Any]]:
        """Fetch organizations the authenticated user belongs to"""
        url = f"{self.base_url}/user/orgs"
        headers = self._build_headers(token)
        params = {"per_page": 100}
        
        logger.info(f"Fetching organizations from: {url}")
        
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, headers=headers, params=params)
            response.raise_for_status()
            orgs = response.json()
        
        logger.info(f"Fetched {len(orgs)} organizations")
        return orgs
    
    def get_pull_requests(self, token: str, username: str) -> List[Dict[str, Any]]:
        """Fetch pull requests created by the authenticated user"""
        url = f"{self.base_url}/search/issues"
        headers = self._build_headers(token)
        params = {
            "q": f"is:pr author:{username}",
            "sort": "updated",
            "per_page": 100,
        }
        
        logger.info(f"Fetching pull requests from: {url}")
        
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
        
        pull_requests = data.get("items", [])
        logger.info(f"Fetched {len(pull_requests)} pull requests")
        return pull_requests

