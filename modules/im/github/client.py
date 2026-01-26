"""GitHub IM Client implementation.

Implements BaseIMClient for GitHub Issues as an IM platform.
"""

import asyncio
import logging
from typing import Optional, Callable, Dict, Any

from modules.im.base import BaseIMClient, MessageContext, InlineKeyboard
from config.v2_config import GitHubConfig

from .app import GitHubAppAuth
from .api import GitHubAPI
from .consumer import GitHubEventConsumer
from .formatter import GitHubFormatter

logger = logging.getLogger(__name__)


class GitHubIMClient(BaseIMClient):
    """GitHub IM client using Issues for communication.

    Receives events via Cloudflare Worker polling and sends
    responses via GitHub API.
    """

    def __init__(self, config: GitHubConfig):
        """Initialize GitHub IM client.

        Args:
            config: GitHub configuration
        """
        super().__init__(config)
        self.config: GitHubConfig = config

        # Initialize components
        self.app_auth = GitHubAppAuth(
            app_id=config.app_id,
            private_key=config.private_key,
        )
        self.api = GitHubAPI(self.app_auth)
        self.consumer = GitHubEventConsumer(
            worker_url=config.worker_url,
            worker_token=config.worker_token,
        )
        self.formatter = GitHubFormatter()

        # Settings manager (will be injected)
        self.settings_manager = None
        self._controller = None
        self._on_ready: Optional[Callable] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[asyncio.Event] = None

    def set_settings_manager(self, settings_manager) -> None:
        """Set the settings manager for repo configuration."""
        self.settings_manager = settings_manager

    def set_controller(self, controller) -> None:
        """Set the controller reference."""
        self._controller = controller

    def get_default_parse_mode(self) -> str:
        """Get the default parse mode for GitHub."""
        return "markdown"

    def should_use_thread_for_reply(self) -> bool:
        """GitHub uses issue threads."""
        return True

    def _extract_context_info(self, context: MessageContext) -> tuple[str, str, str, int]:
        """Extract owner, repo, installation_id, issue_number from context.

        Returns:
            Tuple of (owner, repo, installation_id, issue_number)
        """
        ps = context.platform_specific or {}
        owner = ps.get("owner", "")
        repo = ps.get("repo", "")
        installation_id = ps.get("installation_id", "")
        issue_number = ps.get("issue_number", 0)

        # Fallback: parse from channel_id if needed
        if not owner or not repo:
            channel_id = context.channel_id
            if channel_id.startswith("github:"):
                repo_full = channel_id[7:]  # Remove "github:" prefix
                parts = repo_full.split("/")
                if len(parts) >= 2:
                    owner = parts[0]
                    repo = parts[1]

        # Fallback: parse issue_number from thread_id
        if not issue_number:
            thread_id = context.thread_id or ""
            if thread_id.startswith("issue:"):
                try:
                    issue_number = int(thread_id[6:])
                except ValueError:
                    pass

        return owner, repo, installation_id, issue_number

    async def send_message(
        self,
        context: MessageContext,
        text: str,
        parse_mode: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> str:
        """Send a message (create issue comment).

        Args:
            context: Message context
            text: Message text (markdown)
            parse_mode: Ignored (GitHub always uses markdown)
            reply_to: Ignored (GitHub doesn't support direct replies)

        Returns:
            Comment ID as string
        """
        owner, repo, installation_id, issue_number = self._extract_context_info(context)

        if not all([owner, repo, installation_id, issue_number]):
            logger.error(
                f"Missing context info: owner={owner}, repo={repo}, "
                f"installation_id={installation_id}, issue_number={issue_number}"
            )
            raise ValueError("Invalid message context for GitHub")

        try:
            result = await self.api.create_issue_comment(
                installation_id=installation_id,
                owner=owner,
                repo=repo,
                issue_number=issue_number,
                body=text,
            )
            comment_id = str(result.get("id", ""))
            logger.info(f"Created comment {comment_id} on {owner}/{repo}#{issue_number}")
            return comment_id
        except Exception as e:
            logger.error(f"Failed to create comment: {e}")
            raise

    async def send_message_with_buttons(
        self,
        context: MessageContext,
        text: str,
        keyboard: InlineKeyboard,
        parse_mode: Optional[str] = None,
    ) -> str:
        """Send a message with buttons.

        GitHub doesn't support inline buttons, so we just send the text.

        Args:
            context: Message context
            text: Message text
            keyboard: Ignored (GitHub doesn't support buttons)
            parse_mode: Ignored

        Returns:
            Comment ID
        """
        # GitHub doesn't support inline buttons
        # We could potentially add button text as links, but for now just send text
        return await self.send_message(context, text, parse_mode)

    async def edit_message(
        self,
        context: MessageContext,
        message_id: str,
        text: Optional[str] = None,
        keyboard: Optional[InlineKeyboard] = None,
        parse_mode: Optional[str] = None,
    ) -> bool:
        """Edit an existing comment.

        Args:
            context: Message context
            message_id: Comment ID to edit
            text: New text
            keyboard: Ignored
            parse_mode: Ignored

        Returns:
            Success status
        """
        if not text:
            return True  # Nothing to edit

        owner, repo, installation_id, _ = self._extract_context_info(context)

        if not all([owner, repo, installation_id, message_id]):
            logger.error("Missing context info for edit")
            return False

        try:
            comment_id = int(message_id)
            await self.api.edit_issue_comment(
                installation_id=installation_id,
                owner=owner,
                repo=repo,
                comment_id=comment_id,
                body=text,
            )
            logger.info(f"Edited comment {comment_id} on {owner}/{repo}")
            return True
        except Exception as e:
            logger.error(f"Failed to edit comment: {e}")
            return False

    async def answer_callback(
        self,
        callback_id: str,
        text: Optional[str] = None,
        show_alert: bool = False,
    ) -> bool:
        """Answer a callback query.

        GitHub doesn't support callbacks, so this is a no-op.
        """
        return True

    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get GitHub user information.

        Note: This requires an installation_id which we don't have here.
        We'll return a minimal user info dict.

        Args:
            user_id: GitHub username

        Returns:
            User info dict
        """
        return {
            "id": user_id,
            "username": user_id,
            "display_name": user_id,
            "platform": "github",
        }

    async def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Get GitHub repo/issue information.

        Args:
            channel_id: Channel ID in format "github:owner/repo"

        Returns:
            Channel info dict
        """
        if channel_id.startswith("github:"):
            repo_full = channel_id[7:]
            parts = repo_full.split("/")
            owner = parts[0] if len(parts) >= 1 else ""
            repo = parts[1] if len(parts) >= 2 else ""
            return {
                "id": channel_id,
                "name": repo_full,
                "owner": owner,
                "repo": repo,
                "platform": "github",
            }
        return {
            "id": channel_id,
            "name": channel_id,
            "platform": "github",
        }

    async def add_reaction(
        self,
        context: MessageContext,
        message_id: str,
        emoji: str,
    ) -> bool:
        """Add a reaction to a comment.

        Args:
            context: Message context
            message_id: Comment ID
            emoji: Reaction emoji (GitHub supports: +1, -1, laugh, confused, heart, hooray, rocket, eyes)

        Returns:
            Success status
        """
        owner, repo, installation_id, _ = self._extract_context_info(context)

        if not all([owner, repo, installation_id, message_id]):
            return False

        # Map common emoji to GitHub reaction content
        emoji_map = {
            "👍": "+1",
            "👎": "-1",
            "😄": "laugh",
            "😕": "confused",
            "❤️": "heart",
            "🎉": "hooray",
            "🚀": "rocket",
            "👀": "eyes",
            # Also accept GitHub reaction names directly
            "+1": "+1",
            "-1": "-1",
            "laugh": "laugh",
            "confused": "confused",
            "heart": "heart",
            "hooray": "hooray",
            "rocket": "rocket",
            "eyes": "eyes",
        }

        reaction = emoji_map.get(emoji)
        if not reaction:
            logger.warning(f"Unsupported reaction emoji: {emoji}")
            return False

        try:
            comment_id = int(message_id)
            await self.api.add_reaction(
                installation_id=installation_id,
                owner=owner,
                repo=repo,
                comment_id=comment_id,
                reaction=reaction,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add reaction: {e}")
            return False

    async def remove_reaction(
        self,
        context: MessageContext,
        message_id: str,
        emoji: str,
    ) -> bool:
        """Remove a reaction from a comment.

        Args:
            context: Message context
            message_id: Comment ID
            emoji: Reaction emoji to remove

        Returns:
            Success status
        """
        owner, repo, installation_id, _ = self._extract_context_info(context)

        if not all([owner, repo, installation_id, message_id]):
            return False

        # Map emoji to GitHub reaction content
        emoji_map = {
            "👍": "+1",
            "👎": "-1",
            "😄": "laugh",
            "😕": "confused",
            "❤️": "heart",
            "🎉": "hooray",
            "🚀": "rocket",
            "👀": "eyes",
            "+1": "+1",
            "-1": "-1",
            "laugh": "laugh",
            "confused": "confused",
            "heart": "heart",
            "hooray": "hooray",
            "rocket": "rocket",
            "eyes": "eyes",
        }

        reaction_content = emoji_map.get(emoji)
        if not reaction_content:
            logger.warning(f"Unsupported reaction emoji for removal: {emoji}")
            return False

        try:
            comment_id = int(message_id)
            # Get all reactions on this comment
            reactions = await self.api.list_reactions(
                installation_id=installation_id,
                owner=owner,
                repo=repo,
                comment_id=comment_id,
            )

            # Find our reaction (by content type)
            # Note: This will remove the first matching reaction, which should be ours
            for reaction in reactions:
                if reaction.get("content") == reaction_content:
                    reaction_id = reaction.get("id")
                    if reaction_id:
                        await self.api.remove_reaction(
                            installation_id=installation_id,
                            owner=owner,
                            repo=repo,
                            comment_id=comment_id,
                            reaction_id=reaction_id,
                        )
                        logger.info(f"Removed reaction {reaction_content} from comment {comment_id}")
                        return True

            logger.info(f"No matching reaction {reaction_content} found to remove")
            return False
        except Exception as e:
            logger.error(f"Failed to remove reaction: {e}")
            return False

    def format_markdown(self, text: str) -> str:
        """Format markdown text for GitHub.

        GitHub uses standard markdown, so minimal conversion needed.

        Args:
            text: Input text

        Returns:
            GitHub-formatted text
        """
        return text  # GitHub uses standard markdown

    def register_handlers(self) -> None:
        """Register message handlers with the event consumer."""
        # The consumer will call our message callback when events arrive
        pass

    def register_callbacks(
        self,
        on_message: Optional[Callable] = None,
        on_command: Optional[Dict[str, Callable]] = None,
        on_callback_query: Optional[Callable] = None,
        **kwargs,
    ) -> None:
        """Register callback functions.

        Args:
            on_message: Callback for text messages
            on_command: Dict of command callbacks (not used for GitHub)
            on_callback_query: Callback for button clicks (not used for GitHub)
            **kwargs: Additional callbacks including on_ready
        """
        super().register_callbacks(on_message, on_command, on_callback_query, **kwargs)

        # Store on_ready callback
        if "on_ready" in kwargs:
            self._on_ready = kwargs["on_ready"]

        # Set up event consumer to call our message handler
        if on_message:
            self.consumer.set_event_handler(on_message)

    def run(self) -> None:
        """Start the GitHub IM client.

        This starts the event consumer polling loop.
        """
        logger.info("Starting GitHub IM client")

        # Create event loop
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._stop_event = asyncio.Event()

        async def _run():
            # Start the event consumer
            await self.consumer.start()

            # Call on_ready callback
            if self._on_ready:
                try:
                    await self._on_ready()
                except Exception as e:
                    logger.error(f"Error in on_ready callback: {e}")

            # Wait until stop is requested
            await self._stop_event.wait()

        try:
            self._loop.run_until_complete(_run())
        except KeyboardInterrupt:
            logger.info("GitHub IM client interrupted")
        finally:
            self.consumer.stop()
            self._loop.close()

    async def shutdown(self) -> None:
        """Shutdown the client."""
        self.consumer.stop()
        if self._stop_event:
            self._stop_event.set()
