"""
GitHub API Client
Handles external API communication with GitHub
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
import httpx
from django.conf import settings
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
    RetryError
)

logger = logging.getLogger(__name__)


def is_transient_error(exception):
    """
    Determine if an error is transient and should be retried.
    
    Transient errors:
    - 5xx server errors
    - 429 rate limit errors
    - Timeout exceptions
    
    Permanent errors (should NOT be retried):
    - 4xx client errors (except 429)
    """
    if isinstance(exception, httpx.TimeoutException):
        return True
    
    if isinstance(exception, httpx.HTTPStatusError):
        status_code = exception.response.status_code
        if status_code >= 500 or status_code == 429:
            return True
        return False
    
    return False


class GitHubAPIClient:
    """
    Client for GitHub API communication.
    Handles all external HTTP requests to GitHub with rate limiting and circuit breaker.
    Uses shared AsyncClient with connection pooling for better performance.
    """
    
    def __init__(self):
        self.base_url = settings.GITHUB_API_BASE_URL
        self.api_version = settings.GITHUB_API_VERSION
        self.timeout = settings.GITHUB_API_TIMEOUT
        
        self.timeout_user = getattr(settings, 'GITHUB_API_TIMEOUT_USER', self.timeout)
        self.timeout_repos = getattr(settings, 'GITHUB_API_TIMEOUT_REPOS', 120)
        self.timeout_orgs = getattr(settings, 'GITHUB_API_TIMEOUT_ORGS', self.timeout)
        self.timeout_prs = getattr(settings, 'GITHUB_API_TIMEOUT_PRS', self.timeout)
        
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()
        
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = time.time() + 3600
        self._rate_limit_lock = asyncio.Lock()
        
        self.circuit_open = False
        self.circuit_failures = 0
        self.circuit_failure_threshold = 5
        self.circuit_reset_timeout = 60
        self.circuit_last_failure_time = None
        self._circuit_lock = asyncio.Lock()
    
    async def _get_client(self, timeout: Optional[float] = None) -> httpx.AsyncClient:
        """
        Get or create shared AsyncClient with connection pooling.
        Uses lazy initialization for better resource management.
        
        Args:
            timeout: Optional timeout override for this specific request
            
        Returns:
            Shared AsyncClient instance
        """
        if timeout and timeout != self.timeout:
            return httpx.AsyncClient(
                timeout=timeout,
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20
                )
            )
        
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    self._client = httpx.AsyncClient(
                        timeout=self.timeout,
                        limits=httpx.Limits(
                            max_keepalive_connections=10,
                            max_connections=20
                        )
                    )
                    logger.debug("Created shared AsyncClient with connection pooling")
        return self._client
    
    async def close(self):
        """Close shared client. Should be called when done with the client."""
        if self._client:
            async with self._client_lock:
                if self._client:
                    await self._client.aclose()
                    self._client = None
                    logger.debug("Closed shared AsyncClient")
    
    def _build_headers(self, token: str) -> Dict[str, str]:
        """Build headers for GitHub API requests"""
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": self.api_version,
        }
    
    async def _check_rate_limit(self):
        """
        Check GitHub API rate limit and wait if necessary.
        Updates rate limit from response headers.
        """
        async with self._rate_limit_lock:
            if self.rate_limit_remaining <= 10:
                wait_time = self.rate_limit_reset - time.time()
                if wait_time > 0:
                    logger.warning(
                        f"Rate limit approaching. Remaining: {self.rate_limit_remaining}. "
                        f"Waiting {wait_time:.1f}s until reset"
                    )
                    await asyncio.sleep(wait_time)
                    self.rate_limit_remaining = 5000
    
    async def _check_circuit_breaker(self):
        """
        Check if circuit breaker is open and should block requests.
        """
        async with self._circuit_lock:
            if self.circuit_open:
                if self.circuit_last_failure_time:
                    time_since_failure = time.time() - self.circuit_last_failure_time
                    if time_since_failure >= self.circuit_reset_timeout:
                        logger.info("Circuit breaker: Attempting to close circuit")
                        self.circuit_open = False
                        self.circuit_failures = 0
                    else:
                        raise Exception(
                            f"Circuit breaker is OPEN. "
                            f"Retry after {self.circuit_reset_timeout - time_since_failure:.1f}s"
                        )
    
    async def _record_success(self):
        """Record successful request for circuit breaker"""
        async with self._circuit_lock:
            if self.circuit_failures > 0:
                self.circuit_failures = 0
                if self.circuit_open:
                    logger.info("Circuit breaker: Closing circuit after successful request")
                    self.circuit_open = False
    
    async def _record_failure(self):
        """Record failed request for circuit breaker"""
        async with self._circuit_lock:
            self.circuit_failures += 1
            self.circuit_last_failure_time = time.time()
            
            if self.circuit_failures >= self.circuit_failure_threshold:
                self.circuit_open = True
                logger.error(
                    f"Circuit breaker: OPEN after {self.circuit_failures} failures. "
                    f"Will retry after {self.circuit_reset_timeout}s"
                )
    
    def _update_rate_limit_from_response(self, response: httpx.Response):
        """Update rate limit state from GitHub API response headers"""
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        
        if remaining:
            self.rate_limit_remaining = int(remaining)
        if reset:
            self.rate_limit_reset = int(reset)
    
    def _validate_response_structure(self, data: Any, expected_type: type, key: Optional[str] = None) -> bool:
        """
        Validate response structure before processing.
        
        Args:
            data: Data to validate
            expected_type: Expected type (dict, list, etc.)
            key: Optional key to check if data is dict
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(data, expected_type):
            logger.error(f"Invalid response type. Expected {expected_type.__name__}, got {type(data).__name__}")
            return False
        
        if key and isinstance(data, dict) and key not in data:
            logger.warning(f"Missing key '{key}' in response. Available keys: {list(data.keys())}")
            return False
        
        return True
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(is_transient_error)
    )
    async def get_user_info(self, token: str) -> Dict[str, Any]:
        """
        Fetch authenticated user information with rate limiting and circuit breaker.
        
        Args:
            token: GitHub Personal Access Token
            
        Returns:
            Dictionary with user information
            
        Raises:
            ValueError: If response structure is invalid
            Exception: If circuit breaker is open
        """
        await self._check_circuit_breaker()
        await self._check_rate_limit()
        
        url = f"{self.base_url}/user"
        headers = self._build_headers(token)
        
        logger.info(f"Fetching user info from: {url}")
        
        client = await self._get_client(timeout=self.timeout_user)
        use_context_manager = client != self._client
        
        try:
            if use_context_manager:
                async with client:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    
                    self._update_rate_limit_from_response(response)
                    
                    data = response.json()
            else:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                self._update_rate_limit_from_response(response)
                
                data = response.json()
            
            if not self._validate_response_structure(data, dict):
                raise ValueError("Invalid user info response structure")
            
            if "login" not in data:
                logger.error(f"Missing 'login' field in user response. Keys: {list(data.keys())}")
                raise ValueError("GitHub API response missing required 'login' field")
            
            await self._record_success()
            return data
                
        except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
            await self._record_failure()
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(is_transient_error)
    )
    async def get_repositories(self, token: str) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Fetch all repositories (public and private) for authenticated user.
        Reuses AsyncClient for better performance.
        
        Args:
            token: GitHub Personal Access Token
            
        Returns:
            Tuple of (repositories list, metadata dict with has_more and limit_reached flags)
            
        Raises:
            Exception: If circuit breaker is open
        """
        await self._check_circuit_breaker()
        await self._check_rate_limit()
        
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
        max_pages = 10
        has_more = False
        limit_reached = False
        
        client = await self._get_client(timeout=self.timeout_repos)
        use_context_manager = client != self._client
        
        try:
            if use_context_manager:
                async with client:
                    while page <= max_pages:
                        params["page"] = page
                        response = await client.get(url, headers=headers, params=params)
                        response.raise_for_status()
                        
                        if page == 1:
                            self._update_rate_limit_from_response(response)
                        
                        repos = response.json()
                        
                        if not self._validate_response_structure(repos, list):
                            logger.warning("Invalid repositories response structure, using empty list")
                            repos = []
                        
                        if not repos:
                            break
                        
                        all_repos.extend(repos)
                        
                        link_header = response.headers.get("Link", "")
                        if 'rel="next"' in link_header:
                            has_more = True
                            if page >= max_pages:
                                limit_reached = True
                        
                        page += 1
            else:
                while page <= max_pages:
                    params["page"] = page
                    response = await client.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    
                    if page == 1:
                        self._update_rate_limit_from_response(response)
                    
                    repos = response.json()
                    
                    if not self._validate_response_structure(repos, list):
                        logger.warning("Invalid repositories response structure, using empty list")
                        repos = []
                    
                    if not repos:
                        break
                    
                    all_repos.extend(repos)
                    
                    link_header = response.headers.get("Link", "")
                    if 'rel="next"' in link_header:
                        has_more = True
                        if page >= max_pages:
                            limit_reached = True
                    
                    page += 1
            
            if limit_reached:
                logger.warning(
                    f"Repository pagination limit reached. Fetched {len(all_repos)} repos, "
                    f"but user may have more than {max_pages * 100} repositories"
                )
            
            logger.info(f"Fetched {len(all_repos)} repositories (has_more: {has_more}, limit_reached: {limit_reached})")
            
            metadata = {
                "total_fetched": len(all_repos),
                "has_more": has_more,
                "limit_reached": limit_reached,
                "pages_fetched": page - 1
            }
            
            await self._record_success()
            return all_repos, metadata
            
        except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
            await self._record_failure()
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(is_transient_error)
    )
    async def get_organizations(self, token: str) -> List[Dict[str, Any]]:
        """
        Fetch organizations the authenticated user belongs to.
        
        Args:
            token: GitHub Personal Access Token
            
        Returns:
            List of organization dictionaries
            
        Raises:
            Exception: If circuit breaker is open
        """
        await self._check_circuit_breaker()
        await self._check_rate_limit()
        
        url = f"{self.base_url}/user/orgs"
        headers = self._build_headers(token)
        params = {"per_page": 100}
        
        logger.info(f"Fetching organizations from: {url}")
        
        client = await self._get_client(timeout=self.timeout_orgs)
        use_context_manager = client != self._client
        
        try:
            if use_context_manager:
                async with client:
                    response = await client.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    
                    self._update_rate_limit_from_response(response)
                    
                    orgs = response.json()
            else:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                self._update_rate_limit_from_response(response)
                
                orgs = response.json()
            
            if not self._validate_response_structure(orgs, list):
                logger.warning("Invalid organizations response structure, using empty list")
                orgs = []
            
            logger.info(f"Fetched {len(orgs)} organizations")
            
            await self._record_success()
            return orgs
                
        except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
            await self._record_failure()
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(is_transient_error)
    )
    async def get_pull_requests(self, token: str, username: str) -> List[Dict[str, Any]]:
        """
        Fetch pull requests created by the authenticated user.
        
        Args:
            token: GitHub Personal Access Token
            username: GitHub username to search PRs for
            
        Returns:
            List of pull request dictionaries
            
        Raises:
            ValueError: If username is invalid or response structure is invalid
            Exception: If circuit breaker is open
        """
        if not username:
            raise ValueError("Username is required to fetch pull requests")
        
        await self._check_circuit_breaker()
        await self._check_rate_limit()
        
        url = f"{self.base_url}/search/issues"
        headers = self._build_headers(token)
        params = {
            "q": f"is:pr author:{username}",
            "sort": "updated",
            "per_page": 100,
        }
        
        logger.info(f"Fetching pull requests from: {url} for user: {username}")
        
        client = await self._get_client(timeout=self.timeout_prs)
        use_context_manager = client != self._client
        
        try:
            if use_context_manager:
                async with client:
                    response = await client.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    
                    self._update_rate_limit_from_response(response)
                    
                    data = response.json()
            else:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                self._update_rate_limit_from_response(response)
                
                data = response.json()
            
            if not self._validate_response_structure(data, dict, key="items"):
                logger.warning("Invalid pull requests response structure, using empty list")
                return []
            
            items = data.get("items", [])
            if not isinstance(items, list):
                logger.error(f"Expected 'items' to be a list, got {type(items).__name__}")
                return []
            
            pull_requests = items
            logger.info(f"Fetched {len(pull_requests)} pull requests")
            
            await self._record_success()
            return pull_requests
                
        except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
            await self._record_failure()
            raise


