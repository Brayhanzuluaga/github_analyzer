"""
Views for GitHub API endpoints
"""

import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.plumbing import build_bearer_security_scheme_object
from asgiref.sync import async_to_sync
import httpx

from github_api.services.github_service import GitHubService
from github_api.serializers import UserInfoResponseSerializer, ErrorResponseSerializer

logger = logging.getLogger(__name__)


class BearerTokenAuthentication(BaseAuthentication):
    """
    Custom authentication class for Bearer token.
    This allows drf-spectacular to automatically detect and show Bearer auth in Swagger.
    """
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header:
            return None
        
        parts = auth_header.split()
        if len(parts) != 2:
            return None
        
        auth_type, token = parts
        if auth_type.lower() in ["bearer", "token"]:
            return (None, token)
        return None


class BearerTokenScheme(OpenApiAuthenticationExtension):
    """
    OpenAPI extension for Bearer token authentication.
    This tells drf-spectacular how to represent Bearer auth in the OpenAPI schema.
    """
    target_class = BearerTokenAuthentication
    name = 'Bearer'
    
    def get_security_definition(self, auto_schema):
        return build_bearer_security_scheme_object(
            header_name='Authorization',
            token_prefix='Bearer'
        )


@extend_schema_view(
    get=extend_schema(
        summary="Get GitHub User Information",
        description=(
            "Retrieve complete information for an authenticated GitHub user, "
            "including repositories (public and private), organizations, and pull requests. "
            "Uses parallel requests for optimized performance. "
            "Includes rate limiting, circuit breaker protection, and graceful partial failure handling. "
            "Response includes metadata about pagination limits and any partial failures."
        ),
        responses={
            200: OpenApiResponse(
                response=UserInfoResponseSerializer,
                description="Successfully retrieved user information"
            ),
            401: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Authentication failed - Invalid or missing token"
            ),
            403: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Forbidden - Token lacks required permissions"
            ),
            500: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Internal server error"
            ),
        },
        tags=["GitHub API"],
    )
)
class GitHubUserInfoView(APIView):
    """
    API endpoint to retrieve authenticated GitHub user information.
    
    This view fetches:
    - User basic information
    - Public and private repositories
    - Organizations
    - Pull requests
    """
    
    authentication_classes = [BearerTokenAuthentication]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.github_service = GitHubService()
    
    def get(self, request):
        """
        Handle GET request to retrieve GitHub user information.
        Uses async/await for parallel API calls to GitHub.
        
        Expected header:
            Authorization: Bearer <github_token>
        
        Returns:
            Response with user information or error
        """
        try:
            auth_result = BearerTokenAuthentication().authenticate(request)
            if not auth_result:
                logger.warning("Request received without authentication token")
                return Response(
                    {
                        "error": "Authentication required",
                        "detail": "Please provide a valid GitHub token in Authorization header",
                        "status_code": 401,
                    },
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            _, token = auth_result
            
            logger.info(f"Fetching GitHub user info with token: ...{token[-4:]}")
            user_info = async_to_sync(self.github_service.get_user_complete_info)(token)
            
            return Response(user_info, status=status.HTTP_200_OK)
        
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e.response.status_code} - {e.response.text}")
            
            if e.response.status_code == 401:
                return Response(
                    {
                        "error": "Invalid GitHub token",
                        "detail": "The provided token is invalid or expired",
                        "status_code": 401,
                    },
                    status=status.HTTP_401_UNAUTHORIZED
                )
            elif e.response.status_code == 403:
                return Response(
                    {
                        "error": "Insufficient permissions",
                        "detail": "Token does not have required scopes (repo, read:org, read:user)",
                        "status_code": 403,
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            else:
                return Response(
                    {
                        "error": "GitHub API error",
                        "detail": f"GitHub returned status code {e.response.status_code}",
                        "status_code": e.response.status_code,
                    },
                    status=status.HTTP_502_BAD_GATEWAY
                )
        
        except httpx.TimeoutException:
            logger.error("GitHub API request timed out")
            return Response(
                {
                    "error": "Request timeout",
                    "detail": "GitHub API request took too long to respond",
                    "status_code": 408,
                },
                status=status.HTTP_408_REQUEST_TIMEOUT
            )
        
        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return Response(
                {
                    "error": "Internal server error",
                    "detail": str(e),
                    "status_code": 500,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


