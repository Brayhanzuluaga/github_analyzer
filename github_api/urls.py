"""
URL Configuration for GitHub API endpoints
"""

from django.urls import path
from github_api.views import GitHubUserInfoView

app_name = 'github_api'

urlpatterns = [
    path('github/user-info/', GitHubUserInfoView.as_view(), name='github-user-info'),
]
