"""GitHub App authentication module.

Handles JWT generation and Installation Access Token management.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


@dataclass
class InstallationToken:
    """Cached installation access token."""
    token: str
    expires_at: float  # Unix timestamp


class GitHubAppAuth:
    """GitHub App authentication handler.

    Manages JWT generation and Installation Access Token caching.
    """

    # Token expiration buffer (refresh 5 minutes before expiry)
    TOKEN_BUFFER_SECONDS = 300

    # JWT validity period (10 minutes max per GitHub)
    JWT_EXPIRY_SECONDS = 600

    def __init__(self, app_id: str, private_key: str):
        """Initialize GitHub App auth.

        Args:
            app_id: GitHub App ID
            private_key: PEM-format private key content
        """
        self.app_id = app_id
        self.private_key = self._normalize_private_key(private_key)
        self._installation_tokens: dict[str, InstallationToken] = {}

    def _normalize_private_key(self, private_key: str) -> str:
        """Convert private key to PKCS#1 format if needed.

        GitHub expects PKCS#1 (RSA) format keys, but some tools generate PKCS#8.
        This method converts PKCS#8 to PKCS#1 if necessary.

        Args:
            private_key: PEM-format private key (PKCS#1 or PKCS#8)

        Returns:
            Private key in PKCS#1 format
        """
        if "BEGIN RSA PRIVATE KEY" in private_key:
            # Already in PKCS#1 format
            return private_key

        if "BEGIN PRIVATE KEY" in private_key:
            # PKCS#8 format - convert to PKCS#1
            try:
                key = serialization.load_pem_private_key(
                    private_key.encode(),
                    password=None,
                    backend=default_backend()
                )
                return key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()
                ).decode()
            except Exception as e:
                logger.warning(f"Failed to convert private key format: {e}")
                return private_key

        return private_key

    def _generate_jwt(self) -> str:
        """Generate a JWT for GitHub App authentication.

        Returns:
            JWT token string
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,  # Allow for clock drift
            "exp": now + self.JWT_EXPIRY_SECONDS,
            "iss": self.app_id,
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    async def get_installation_token(
        self, installation_id: str, force_refresh: bool = False
    ) -> str:
        """Get an installation access token, using cache if valid.

        Args:
            installation_id: GitHub App installation ID
            force_refresh: Force token refresh even if cached

        Returns:
            Installation access token

        Raises:
            httpx.HTTPStatusError: If token request fails
        """
        # Check cache
        if not force_refresh and installation_id in self._installation_tokens:
            cached = self._installation_tokens[installation_id]
            if time.time() < cached.expires_at - self.TOKEN_BUFFER_SECONDS:
                return cached.token

        # Request new token
        jwt_token = self._generate_jwt()
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            data = response.json()

        # Parse expiration (ISO 8601 format)
        expires_at_str = data.get("expires_at", "")
        # GitHub returns ISO format like "2024-01-25T10:00:00Z"
        # Parse and convert to Unix timestamp
        from datetime import datetime
        try:
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00")).timestamp()
        except (ValueError, AttributeError):
            # Default to 1 hour from now if parsing fails
            expires_at = time.time() + 3600

        token = data["token"]
        self._installation_tokens[installation_id] = InstallationToken(
            token=token,
            expires_at=expires_at,
        )

        logger.info(f"Obtained installation token for installation {installation_id}")
        return token

    async def get_app_info(self) -> dict:
        """Get information about the GitHub App.

        Returns:
            App information dict
        """
        jwt_token = self._generate_jwt()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/app",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_installations(self) -> list[dict]:
        """Get all installations of the GitHub App.

        Returns:
            List of installation dicts
        """
        jwt_token = self._generate_jwt()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/app/installations",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_installation_repos(self, installation_id: str) -> list[dict]:
        """Get repositories accessible to an installation.

        Args:
            installation_id: GitHub App installation ID

        Returns:
            List of repository dicts
        """
        token = await self.get_installation_token(installation_id)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/installation/repositories",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("repositories", [])
