"""
Tests for GitHub API
"""

import os
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

# Load .env for tests
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
    
    @patch('github_api.api_client.httpx.Client')
    def test_successful_request_returns_200(self, mock_client):
        """Test that valid request returns 200 with data"""
        # Mock GitHub API responses
        mock_context = MagicMock()
        mock_client.return_value.__enter__.return_value = mock_context
        
        # Mock user info
        mock_user_response = MagicMock()
        mock_user_response.json.return_value = {
            'login': 'testuser',
            'name': 'Test User',
            'email': 'test@example.com',
            'bio': 'Test bio',
            'public_repos': 10,
            'followers': 5,
            'following': 3
        }
        mock_user_response.raise_for_status = MagicMock()
        
        # Mock repositories
        mock_repos_response = MagicMock()
        mock_repos_response.json.return_value = []
        mock_repos_response.raise_for_status = MagicMock()
        
        # Mock organizations
        mock_orgs_response = MagicMock()
        mock_orgs_response.json.return_value = []
        mock_orgs_response.raise_for_status = MagicMock()
        
        # Mock pull requests
        mock_prs_response = MagicMock()
        mock_prs_response.json.return_value = {'items': []}
        mock_prs_response.raise_for_status = MagicMock()
        
        mock_context.get.side_effect = [
            mock_user_response,
            mock_repos_response,
            mock_orgs_response,
            mock_prs_response
        ]
        
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
