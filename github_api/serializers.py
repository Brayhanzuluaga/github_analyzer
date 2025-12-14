"""
DRF Serializers for GitHub API
"""

from rest_framework import serializers


class RepositorySerializer(serializers.Serializer):
    """Serializer for repository information"""
    
    name = serializers.CharField()
    full_name = serializers.CharField()
    private = serializers.BooleanField()
    description = serializers.CharField(allow_null=True, required=False)
    html_url = serializers.URLField()
    language = serializers.CharField(allow_null=True, required=False)
    created_at = serializers.CharField()
    updated_at = serializers.CharField()
    stargazers_count = serializers.IntegerField()


class OrganizationSerializer(serializers.Serializer):
    """Serializer for organization information"""
    
    login = serializers.CharField()
    description = serializers.CharField(allow_null=True, required=False)
    url = serializers.URLField()


class PullRequestSerializer(serializers.Serializer):
    """Serializer for pull request information"""
    
    title = serializers.CharField()
    state = serializers.CharField()
    html_url = serializers.URLField()
    created_at = serializers.CharField()
    repository = serializers.CharField()


class UserSerializer(serializers.Serializer):
    """Serializer for user basic information"""
    
    login = serializers.CharField()
    name = serializers.CharField(allow_null=True, required=False)
    email = serializers.EmailField(allow_null=True, required=False)
    bio = serializers.CharField(allow_null=True, required=False)
    public_repos = serializers.IntegerField()
    followers = serializers.IntegerField()
    following = serializers.IntegerField()


class UserInfoResponseSerializer(serializers.Serializer):
    """Complete serializer for GitHub user information response"""
    
    user = UserSerializer()
    repositories = RepositorySerializer(many=True)
    organizations = OrganizationSerializer(many=True)
    pull_requests = PullRequestSerializer(many=True)


class ErrorResponseSerializer(serializers.Serializer):
    """Serializer for error responses"""
    
    error = serializers.CharField()
    detail = serializers.CharField(allow_null=True, required=False)
    status_code = serializers.IntegerField()

