"""GitHub REST API wrapper.

Provides high-level interface for GitHub Issue operations.
"""

import logging
from typing import Optional

import httpx

from .app import GitHubAppAuth

logger = logging.getLogger(__name__)


class GitHubAPI:
    """GitHub REST API client for issue operations.

    Uses GitHub App authentication via installation tokens.
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, app_auth: GitHubAppAuth):
        """Initialize GitHub API client.

        Args:
            app_auth: GitHub App authentication handler
        """
        self.app_auth = app_auth

    def _get_headers(self, token: str) -> dict:
        """Get common request headers.

        Args:
            token: GitHub access token

        Returns:
            Headers dict
        """
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def create_issue_comment(
        self,
        installation_id: str,
        owner: str,
        repo: str,
        issue_number: int,
        body: str,
    ) -> dict:
        """Create a comment on an issue.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            body: Comment body (markdown)

        Returns:
            Created comment data

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        token = await self.app_auth.get_installation_token(installation_id)
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/comments"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self._get_headers(token),
                json={"body": body},
            )
            response.raise_for_status()
            return response.json()

    async def edit_issue_comment(
        self,
        installation_id: str,
        owner: str,
        repo: str,
        comment_id: int,
        body: str,
    ) -> dict:
        """Edit an existing issue comment.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            comment_id: Comment ID
            body: New comment body (markdown)

        Returns:
            Updated comment data

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        token = await self.app_auth.get_installation_token(installation_id)
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/comments/{comment_id}"

        async with httpx.AsyncClient() as client:
            response = await client.patch(
                url,
                headers=self._get_headers(token),
                json={"body": body},
            )
            response.raise_for_status()
            return response.json()

    async def get_issue(
        self,
        installation_id: str,
        owner: str,
        repo: str,
        issue_number: int,
    ) -> dict:
        """Get issue details.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number

        Returns:
            Issue data

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        token = await self.app_auth.get_installation_token(installation_id)
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._get_headers(token),
            )
            response.raise_for_status()
            return response.json()

    async def get_issue_comment(
        self,
        installation_id: str,
        owner: str,
        repo: str,
        comment_id: int,
    ) -> dict:
        """Get a specific issue comment.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            comment_id: Comment ID

        Returns:
            Comment data

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        token = await self.app_auth.get_installation_token(installation_id)
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/comments/{comment_id}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._get_headers(token),
            )
            response.raise_for_status()
            return response.json()

    async def list_issue_comments(
        self,
        installation_id: str,
        owner: str,
        repo: str,
        issue_number: int,
        per_page: int = 100,
    ) -> list[dict]:
        """List all comments on an issue.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            per_page: Number of results per page

        Returns:
            List of comment dicts

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        token = await self.app_auth.get_installation_token(installation_id)
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/comments"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._get_headers(token),
                params={"per_page": per_page},
            )
            response.raise_for_status()
            return response.json()

    async def add_reaction(
        self,
        installation_id: str,
        owner: str,
        repo: str,
        comment_id: int,
        reaction: str,
    ) -> dict:
        """Add a reaction to an issue comment.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            comment_id: Comment ID
            reaction: Reaction type (+1, -1, laugh, confused, heart, hooray, rocket, eyes)

        Returns:
            Reaction data

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        token = await self.app_auth.get_installation_token(installation_id)
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/comments/{comment_id}/reactions"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self._get_headers(token),
                json={"content": reaction},
            )
            response.raise_for_status()
            return response.json()

    async def list_reactions(
        self,
        installation_id: str,
        owner: str,
        repo: str,
        comment_id: int,
    ) -> list:
        """List reactions on an issue comment.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            comment_id: Comment ID

        Returns:
            List of reactions

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        token = await self.app_auth.get_installation_token(installation_id)
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/comments/{comment_id}/reactions"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._get_headers(token),
            )
            response.raise_for_status()
            return response.json()

    async def remove_reaction(
        self,
        installation_id: str,
        owner: str,
        repo: str,
        comment_id: int,
        reaction_id: int,
    ) -> bool:
        """Remove a reaction from an issue comment.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            comment_id: Comment ID
            reaction_id: Reaction ID to remove

        Returns:
            True if successful

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        token = await self.app_auth.get_installation_token(installation_id)
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/comments/{comment_id}/reactions/{reaction_id}"

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                url,
                headers=self._get_headers(token),
            )
            # 204 No Content is success for DELETE
            return response.status_code == 204

    async def get_user(
        self,
        installation_id: str,
        username: str,
    ) -> dict:
        """Get user information.

        Args:
            installation_id: GitHub App installation ID
            username: GitHub username

        Returns:
            User data

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        token = await self.app_auth.get_installation_token(installation_id)
        url = f"{self.BASE_URL}/users/{username}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._get_headers(token),
            )
            response.raise_for_status()
            return response.json()

    async def get_repo(
        self,
        installation_id: str,
        owner: str,
        repo: str,
    ) -> dict:
        """Get repository information.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name

        Returns:
            Repository data

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        token = await self.app_auth.get_installation_token(installation_id)
        url = f"{self.BASE_URL}/repos/{owner}/{repo}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._get_headers(token),
            )
            response.raise_for_status()
            return response.json()
