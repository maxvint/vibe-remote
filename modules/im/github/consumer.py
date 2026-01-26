"""Cloudflare KV event consumer for GitHub webhook events.

Polls the Cloudflare Worker for pending GitHub events and processes them.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Callable, Any

import httpx

from modules.im.base import MessageContext

logger = logging.getLogger(__name__)


@dataclass
class GitHubEvent:
    """Parsed GitHub event from Cloudflare KV."""
    id: str
    event_type: str  # "issue_comment", "issues", etc.
    repo: str  # "owner/repo"
    issue_number: int
    comment_id: Optional[int]
    user: str
    body: str
    created_at: str
    installation_id: str
    # Additional context
    issue_title: Optional[str] = None
    issue_body: Optional[str] = None
    html_url: Optional[str] = None


class GitHubEventConsumer:
    """Consumer for GitHub events from Cloudflare Worker.

    Polls the worker API for pending events and dispatches them
    to the message handler.
    """

    def __init__(
        self,
        worker_url: str,
        worker_token: str,
        poll_interval: float = 5.0,
    ):
        """Initialize event consumer.

        Args:
            worker_url: Cloudflare Worker base URL
            worker_token: Bearer token for worker API authentication
            poll_interval: Seconds between poll requests
        """
        self.worker_url = worker_url.rstrip("/")
        self.worker_token = worker_token
        self.poll_interval = poll_interval
        self._running = False
        self._on_event: Optional[Callable[[MessageContext, str], Any]] = None
        self._processed_events: set[str] = set()

    def set_event_handler(
        self, handler: Callable[[MessageContext, str], Any]
    ) -> None:
        """Set the event handler callback.

        Args:
            handler: Async callback (context, message_text) -> None
        """
        self._on_event = handler

    def _get_headers(self) -> dict:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Bearer {self.worker_token}",
            "Content-Type": "application/json",
        }

    async def fetch_events(self) -> list[dict]:
        """Fetch pending events from Cloudflare Worker.

        Returns:
            List of event dicts
        """
        url = f"{self.worker_url}/events"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
                return data.get("events", [])
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch events: {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            return []

    async def mark_event_processed(self, event_id: str) -> bool:
        """Mark an event as processed in Cloudflare KV.

        Args:
            event_id: Event ID to mark as processed

        Returns:
            True if successful
        """
        url = f"{self.worker_url}/events/{event_id}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(url, headers=self._get_headers())
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to mark event {event_id} as processed: {e}")
            return False

    def parse_event(self, raw_event: dict) -> Optional[GitHubEvent]:
        """Parse raw event dict into GitHubEvent.

        Args:
            raw_event: Raw event dict from Cloudflare KV

        Returns:
            Parsed GitHubEvent or None if invalid
        """
        try:
            return GitHubEvent(
                id=raw_event["id"],
                event_type=raw_event.get("type", "issue_comment"),
                repo=raw_event["repo"],
                issue_number=raw_event["issue_number"],
                comment_id=raw_event.get("comment_id"),
                user=raw_event["user"],
                body=raw_event["body"],
                created_at=raw_event.get("created_at", ""),
                installation_id=str(raw_event.get("installation_id", "")),
                issue_title=raw_event.get("issue_title"),
                issue_body=raw_event.get("issue_body"),
                html_url=raw_event.get("html_url"),
            )
        except KeyError as e:
            logger.error(f"Missing required field in event: {e}")
            return None

    def event_to_context(self, event: GitHubEvent) -> MessageContext:
        """Convert GitHubEvent to MessageContext.

        Args:
            event: Parsed GitHub event

        Returns:
            Platform-agnostic message context
        """
        # Parse owner/repo
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

    async def process_event(self, raw_event: dict) -> bool:
        """Process a single event.

        Args:
            raw_event: Raw event dict

        Returns:
            True if processed successfully
        """
        event = self.parse_event(raw_event)
        if not event:
            return False

        # Skip if already processed (in case of duplicate delivery)
        if event.id in self._processed_events:
            logger.debug(f"Skipping duplicate event {event.id}")
            return True

        logger.info(
            f"Processing GitHub event: {event.event_type} from {event.user} "
            f"on {event.repo}#{event.issue_number}"
        )

        # Convert to context and dispatch
        context = self.event_to_context(event)

        if self._on_event:
            try:
                await self._on_event(context, event.body)
                self._processed_events.add(event.id)
                # Limit processed events cache size
                if len(self._processed_events) > 1000:
                    # Remove oldest entries (set doesn't preserve order, but this is fine)
                    self._processed_events = set(list(self._processed_events)[-500:])
            except Exception as e:
                logger.error(f"Error handling event {event.id}: {e}")
                return False

        # Mark as processed in Cloudflare
        await self.mark_event_processed(event.id)
        return True

    async def poll_loop(self) -> None:
        """Main polling loop."""
        logger.info(f"Starting GitHub event consumer, polling {self.worker_url}")
        self._running = True

        while self._running:
            try:
                events = await self.fetch_events()
                for event in events:
                    await self.process_event(event)
            except Exception as e:
                logger.error(f"Error in poll loop: {e}")

            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False
        logger.info("GitHub event consumer stopped")

    async def start(self) -> None:
        """Start the consumer (non-blocking)."""
        asyncio.create_task(self.poll_loop())
