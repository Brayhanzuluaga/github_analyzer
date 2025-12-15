"""
Tests for GitHub API
"""

import os
import asyncio
import time
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock, AsyncMock
from dotenv import load_dotenv
from asgiref.sync import async_to_sync

load_dotenv()


class GitHubUserInfoViewTests(APITestCase):
    """Tests for GitHubUserInfoView"""
    
    def test_missing_token_returns_401(self):
        """Test that request without token returns 401"""
        response = self.client.get('/api/v1/github/user-info/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'Authentication required')
    
    def test_invalid_token_format_returns_401(self):
        """Test that invalid token format returns 401"""
        response = self.client.get(
            '/api/v1/github/user-info/',
            HTTP_AUTHORIZATION='InvalidFormat'
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    @patch('github_api.services.GitHubService.get_user_complete_info', new_callable=AsyncMock)
    def test_successful_request_returns_200(self, mock_get_user_info):
        """Test that valid request returns 200 with data"""
        # Mock the service method to return expected data (async method)
        mock_get_user_info.return_value = {
            'user': {
                'login': 'testuser',
                'name': 'Test User',
                'email': 'test@example.com',
                'bio': 'Test bio',
                'public_repos': 10,
                'followers': 5,
                'following': 3
            },
            'repositories': [],
            'repositories_metadata': {
                'total_fetched': 0,
                'has_more': False,
                'limit_reached': False,
                'pages_fetched': 0
            },
            'organizations': [],
            'pull_requests': [],
            'metadata': {
                'partial_failures': {
                    'repositories': False,
                    'organizations': False,
                    'pull_requests': False
                },
                'errors': None
            }
        }
        
        response = self.client.get(
            '/api/v1/github/user-info/',
            HTTP_AUTHORIZATION='Bearer test_token_123'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user', response.data)
        self.assertIn('repositories', response.data)
        self.assertIn('organizations', response.data)
        self.assertIn('pull_requests', response.data)


class GitHubServiceTests(TestCase):
    """Tests for GitHubService"""
    
    def test_transform_repositories(self):
        """Test repository data transformation"""
        from github_api.services import GitHubService
        
        service = GitHubService()
        raw_data = [
            {
                'name': 'test-repo',
                'full_name': 'user/test-repo',
                'private': False,
                'description': 'Test',
                'html_url': 'https://github.com/user/test-repo',
                'language': 'Python',
                'created_at': '2023-01-01T00:00:00Z',
                'updated_at': '2023-12-01T00:00:00Z',
                'stargazers_count': 10
            }
        ]
        
        result = service._transform_repositories(raw_data)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'test-repo')
        self.assertEqual(result[0]['language'], 'Python')


class GitHubIntegrationTests(APITestCase):
    """
    Integration tests with REAL GitHub API.
    
    These tests require a valid GitHub token in .env:
    GITHUB_TEST_TOKEN=ghp_your_token_here
    
    Run with: python manage.py test github_api.tests.GitHubIntegrationTests
    Skip if no token: Will skip automatically if token not found
    """
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.github_token = os.getenv('GITHUB_TEST_TOKEN')
    
    def setUp(self):
        """Skip tests if no GitHub token is available"""
        if not self.github_token:
            self.skipTest("GITHUB_TEST_TOKEN not found in .env - Skipping integration test")
    
    def test_real_github_api_integration(self):
        """
        Test with REAL GitHub API call.
        
        This test makes actual HTTP requests to GitHub.
        Requires GITHUB_TEST_TOKEN in .env file.
        """
        print(f"\n🔐 Using token: ...{self.github_token[-4:]}")
        
        response = self.client.get(
            '/api/v1/github/user-info/',
            HTTP_AUTHORIZATION=f'Bearer {self.github_token}'
        )
        
        # Print response for debugging
        print(f"📊 Status: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ User: {response.data.get('user', {}).get('login')}")
            print(f"📦 Repos: {len(response.data.get('repositories', []))}")
            print(f"🏢 Orgs: {len(response.data.get('organizations', []))}")
            print(f"🔀 PRs: {len(response.data.get('pull_requests', []))}")
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user', response.data)
        self.assertIn('repositories', response.data)
        self.assertIn('organizations', response.data)
        self.assertIn('pull_requests', response.data)
        
        # Validate user structure
        user = response.data['user']
        self.assertIn('login', user)
        self.assertIsNotNone(user['login'])
        
        # Validate repositories structure
        repositories = response.data['repositories']
        self.assertIsInstance(repositories, list)
        
        if len(repositories) > 0:
            first_repo = repositories[0]
            self.assertIn('name', first_repo)
            self.assertIn('full_name', first_repo)
            self.assertIn('private', first_repo)
            self.assertIn('html_url', first_repo)
    
    def test_real_github_api_invalid_token(self):
        """Test with invalid token returns 401 from real GitHub"""
        response = self.client.get(
            '/api/v1/github/user-info/',
            HTTP_AUTHORIZATION='Bearer ghp_invalid_token_12345'
        )
        
        print(f"\n❌ Invalid token test - Status: {response.status_code}")
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)


class CircuitBreakerTests(TestCase):
    """Tests for Circuit Breaker functionality"""
    
    def setUp(self):
        """Set up test client"""
        from github_api.api_client import GitHubAPIClient
        self.client = GitHubAPIClient()
    
    @async_to_sync
    async def test_circuit_opens_after_threshold(self):
        """Test that circuit breaker opens after N consecutive failures"""
        import httpx
        
        # Reset circuit breaker state
        self.client.circuit_open = False
        self.client.circuit_failures = 0
        
        # Mock the client returned by _get_client
        mock_response = MagicMock()
        mock_response.headers = {}
        
        # Create mock client that supports context manager
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=mock_response
        ))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        # Mock _get_client to return our mock client (different from _client to trigger context manager)
        with patch.object(self.client, '_get_client', return_value=mock_client):
            # Make 5 requests that will fail (threshold is 5)
            for i in range(5):
                try:
                    await self.client.get_user_info("test_token")
                except Exception:
                    pass  # Expected to fail
            
            # 6th request should fail with circuit open exception
            with self.assertRaises(Exception) as context:
                await self.client.get_user_info("test_token")
            
            self.assertIn("Circuit breaker is OPEN", str(context.exception))
            self.assertTrue(self.client.circuit_open)
            self.assertEqual(self.client.circuit_failures, 5)
    
    @async_to_sync
    async def test_circuit_closes_after_timeout(self):
        """Test that circuit closes after timeout period"""
        # Set circuit as open with old failure time
        self.client.circuit_open = True
        self.client.circuit_failures = 5
        self.client.circuit_last_failure_time = time.time() - 61  # More than 60s timeout
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "5000", "X-RateLimit-Reset": str(int(time.time()) + 3600)}
        mock_response.json.return_value = {"login": "testuser"}
        mock_response.raise_for_status = MagicMock()
        
        # Create mock client that supports context manager
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        # Mock _get_client to return our mock client (different from _client to trigger context manager)
        with patch.object(self.client, '_get_client', return_value=mock_client):
            # Should allow request and close circuit
            result = await self.client.get_user_info("test_token")
            
            self.assertFalse(self.client.circuit_open)
            self.assertEqual(self.client.circuit_failures, 0)
            self.assertEqual(result["login"], "testuser")
    
    @async_to_sync
    async def test_circuit_prevents_requests_when_open(self):
        """Test that circuit prevents requests when open and timeout not reached"""
        # Set circuit as open with recent failure
        self.client.circuit_open = True
        self.client.circuit_failures = 5
        self.client.circuit_last_failure_time = time.time() - 10  # Only 10s ago (less than 60s timeout)
        
        # Should raise exception immediately without making request
        with self.assertRaises(Exception) as context:
            await self.client.get_user_info("test_token")
        
        self.assertIn("Circuit breaker is OPEN", str(context.exception))
    
    @async_to_sync
    async def test_circuit_resets_on_success(self):
        """Test that circuit failures reset on successful request"""
        # Set some failures but not enough to open circuit
        self.client.circuit_open = False
        self.client.circuit_failures = 3
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "5000", "X-RateLimit-Reset": str(int(time.time()) + 3600)}
        mock_response.json.return_value = {"login": "testuser"}
        mock_response.raise_for_status = MagicMock()
        
        # Create mock client that supports context manager
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        # Mock _get_client to return our mock client (different from _client to trigger context manager)
        with patch.object(self.client, '_get_client', return_value=mock_client):
            await self.client.get_user_info("test_token")
            
            # Failures should reset to 0
            self.assertEqual(self.client.circuit_failures, 0)
            self.assertFalse(self.client.circuit_open)


class ConcurrencyTests(TestCase):
    """Tests for concurrent/parallel request handling"""
    
    def setUp(self):
        """Set up test service"""
        from github_api.services import GitHubService
        self.service = GitHubService()
    
    @async_to_sync
    async def test_parallel_requests_performance(self):
        """Test that parallel requests are faster than sequential"""
        # Mock with delays to simulate API calls
        async def delayed_mock_repos(*args, **kwargs):
            await asyncio.sleep(0.3)  # Simulate 300ms API call
            return ([], {"total_fetched": 0, "has_more": False, "limit_reached": False, "pages_fetched": 0})
        
        async def delayed_mock_orgs(*args, **kwargs):
            await asyncio.sleep(0.3)  # Simulate 300ms API call
            return []
        
        async def delayed_mock_prs(*args, **kwargs):
            await asyncio.sleep(0.3)  # Simulate 300ms API call
            return []
        
        with patch.object(self.service.api_client, 'get_user_info') as mock_user:
            mock_user.return_value = {"login": "testuser", "name": "Test"}
            
            with patch.object(self.service.api_client, 'get_repositories', delayed_mock_repos):
                with patch.object(self.service.api_client, 'get_organizations', delayed_mock_orgs):
                    with patch.object(self.service.api_client, 'get_pull_requests', delayed_mock_prs):
                        
                        start = time.time()
                        result = await self.service.get_user_complete_info("test_token")
                        elapsed = time.time() - start
                        
                        # With parallelization, should be ~0.3s (all run in parallel)
                        # Without parallelization would be ~0.9s (sequential)
                        # Allow some margin for overhead
                        self.assertLess(elapsed, 0.5, 
                                      f"Parallel requests took {elapsed:.2f}s, expected < 0.5s")
                        
                        # Verify result structure
                        self.assertIn('user', result)
                        self.assertIn('repositories', result)
                        self.assertIn('organizations', result)
                        self.assertIn('pull_requests', result)
    
    @async_to_sync
    async def test_concurrent_users(self):
        """Test handling multiple concurrent user requests"""
        # Mock successful responses
        mock_user_data = {
            "login": "testuser",
            "name": "Test User",
            "public_repos": 10,
            "followers": 5,
            "following": 3
        }
        
        with patch.object(self.service.api_client, 'get_user_info') as mock_user:
            mock_user.return_value = mock_user_data
            
            with patch.object(self.service.api_client, 'get_repositories') as mock_repos:
                mock_repos.return_value = ([], {"total_fetched": 0, "has_more": False, "limit_reached": False, "pages_fetched": 0})
                
                with patch.object(self.service.api_client, 'get_organizations') as mock_orgs:
                    mock_orgs.return_value = []
                    
                    with patch.object(self.service.api_client, 'get_pull_requests') as mock_prs:
                        mock_prs.return_value = []
                        
                        # Execute 3 requests concurrently
                        tokens = ["token1", "token2", "token3"]
                        results = await asyncio.gather(*[
                            self.service.get_user_complete_info(token) 
                            for token in tokens
                        ])
                        
                        # Verify all completed successfully
                        self.assertEqual(len(results), 3)
                        for result in results:
                            self.assertIn('user', result)
                            self.assertIn('repositories', result)
                            self.assertIn('organizations', result)
                            self.assertIn('pull_requests', result)
                        
                        # Verify all calls were made
                        self.assertEqual(mock_user.call_count, 3)
                        self.assertEqual(mock_repos.call_count, 3)
                        self.assertEqual(mock_orgs.call_count, 3)
                        self.assertEqual(mock_prs.call_count, 3)
    
    @async_to_sync
    async def test_partial_failure_handling(self):
        """Test that partial failures are handled gracefully"""
        mock_user_data = {
            "login": "testuser",
            "name": "Test User",
            "public_repos": 10,
            "followers": 5,
            "following": 3
        }
        
        with patch.object(self.service.api_client, 'get_user_info') as mock_user:
            mock_user.return_value = mock_user_data
            
            # Mock: repos succeed, orgs fail, prs succeed
            with patch.object(self.service.api_client, 'get_repositories') as mock_repos:
                mock_repos.return_value = ([{"name": "repo1"}], {"total_fetched": 1, "has_more": False, "limit_reached": False, "pages_fetched": 1})
                
                with patch.object(self.service.api_client, 'get_organizations') as mock_orgs:
                    mock_orgs.side_effect = Exception("Org API failed")
                    
                    with patch.object(self.service.api_client, 'get_pull_requests') as mock_prs:
                        mock_prs.return_value = [{"title": "PR1"}]
                        
                        result = await self.service.get_user_complete_info("test_token")
                        
                        # Should return partial data
                        self.assertIn('user', result)
                        self.assertEqual(len(result['repositories']), 1)
                        self.assertEqual(len(result['organizations']), 0)  # Failed
                        self.assertEqual(len(result['pull_requests']), 1)
                        
                        # Should indicate partial failure
                        self.assertTrue(result['metadata']['partial_failures']['organizations'])
                        self.assertFalse(result['metadata']['partial_failures']['repositories'])
                        self.assertFalse(result['metadata']['partial_failures']['pull_requests'])
                        self.assertIsNotNone(result['metadata']['errors'])
