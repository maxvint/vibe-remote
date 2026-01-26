"""HTTP server to receive webhook pushes from vibe-webhook-server."""

import asyncio
import logging
from typing import Callable, Optional
from aiohttp import web

from modules.im import MessageContext
from .consumer import GitHubEvent

logger = logging.getLogger(__name__)


class GitHubWebhookServer:
    """HTTP server to receive GitHub events pushed from webhook-server."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5124,
        auth_token: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.auth_token = auth_token
        self._event_handler: Optional[Callable] = None
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None

    def set_event_handler(self, handler: Callable) -> None:
        """Set the event handler callback.

        Args:
            handler: Async function(context: MessageContext, message: str)
        """
        self._event_handler = handler

    async def start(self) -> None:
        """Start the HTTP server."""
        self._app = web.Application()
        self._app.router.add_post("/github/webhook", self._handle_webhook)
        self._app.router.add_get("/health", self._handle_health)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        logger.info(f"GitHub webhook server listening on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the HTTP server."""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        logger.info("GitHub webhook server stopped")

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({"status": "ok"})

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        """Handle incoming webhook push."""
        # Verify auth token if configured
        if self.auth_token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header != f"Bearer {self.auth_token}":
                return web.json_response({"error": "Unauthorized"}, status=401)

        try:
            data = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse webhook payload: {e}")
            return web.json_response({"error": "Invalid JSON"}, status=400)

        # Parse event
        event = self._parse_event(data)
        if not event:
            return web.json_response({"error": "Invalid event data"}, status=400)

        # Convert to MessageContext
        context = self._event_to_context(event)

        # Call event handler
        if self._event_handler:
            try:
                asyncio.create_task(
                    self._event_handler(context, event.body)
                )
                logger.info(f"Webhook event received and queued: {event.id}")
                return web.json_response({"success": True, "event_id": event.id})
            except Exception as e:
                logger.error(f"Failed to handle webhook event: {e}")
                return web.json_response({"error": str(e)}, status=500)
        else:
            logger.warning("No event handler registered")
            return web.json_response({"error": "No handler registered"}, status=503)

    def _parse_event(self, data: dict) -> Optional[GitHubEvent]:
        """Parse raw event dict into GitHubEvent."""
        try:
            return GitHubEvent(
                id=data["id"],
                event_type=data.get("type", "issue_comment"),
                repo=data["repo"],
                issue_number=data["issue_number"],
                comment_id=data.get("comment_id"),
                user=data["user"],
                body=data["body"],
                created_at=data.get("created_at", ""),
                installation_id=str(data.get("installation_id", "")),
                issue_title=data.get("issue_title"),
                issue_body=data.get("issue_body"),
                html_url=data.get("comment_url"),
            )
        except KeyError as e:
            logger.error(f"Missing required field in event: {e}")
            return None

    def _event_to_context(self, event: GitHubEvent) -> MessageContext:
        """Convert GitHubEvent to MessageContext."""
        parts = event.repo.split("/")
        owner = parts[0] if len(parts) >= 1 else ""
        repo = parts[1] if len(parts) >= 2 else ""

        return MessageContext(
            user_id=event.user,
            channel_id=f"github:{event.repo}",
            thread_id=f"issue:{event.issue_number}",
            message_id=str(event.comment_id) if event.comment_id else None,
            platform_specific={
                "platform": "github",
                "owner": owner,
                "repo": repo,
                "repo_full": event.repo,
                "issue_number": event.issue_number,
                "comment_id": event.comment_id,
                "issue_title": event.issue_title,
                "issue_body": event.issue_body,
                "html_url": event.html_url,
                "event_id": event.id,
                "installation_id": event.installation_id,
            },
        )
