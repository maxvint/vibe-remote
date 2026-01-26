"""Factory for creating IM platform clients"""

import logging
from typing import Union, TYPE_CHECKING

from .base import BaseIMClient

# Use delayed imports to avoid circular import issues
if TYPE_CHECKING:
    from config.v2_config import V2Config

logger = logging.getLogger(__name__)


class IMFactory:
    """Factory class to create the appropriate IM client based on platform"""

    @staticmethod
    def create_client(config, platform: str = "slack") -> BaseIMClient:
        """Create and return the appropriate IM client based on configuration

        Args:
            config: Application configuration
            platform: Platform to create client for ("slack" or "github")

        Returns:
            Instance of platform-specific IM client

        Raises:
            ValueError: If platform is not supported
        """
        if platform == "github":
            from .github import GitHubIMClient

            if not config.github or not config.github.is_configured():
                raise ValueError("GitHub configuration not found or incomplete")
            logger.info("Creating GitHub client")
            return GitHubIMClient(config.github)

        # Default to Slack
        from .slack import SlackBot

        if not config.slack:
            raise ValueError("Slack configuration not found")
        logger.info("Creating Slack client")
        return SlackBot(config.slack)

    @staticmethod
    def get_supported_platforms() -> list[str]:
        """Get list of supported platforms

        Returns:
            List of supported platform names
        """
        return ["slack", "github"]

    @staticmethod
    def validate_platform_config(config, platform: str = "slack") -> None:
        """Validate platform configuration before creating client

        Args:
            config: Application configuration
            platform: Platform to validate ("slack" or "github")

        Raises:
            ValueError: If configuration is invalid
        """
        if platform == "github":
            if config.github is None:
                raise ValueError("Missing configuration for platform: github")
            config.github.validate()
        else:
            if config.slack is None:
                raise ValueError("Missing configuration for platform: slack")
            config.slack.validate()
