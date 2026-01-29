"""Issue extraction handler for /issue command.

Collects Slack channel discussions, extracts requirements using Claude,
and creates GitHub issues with confirmation flow.
"""

import json
import logging
import os
import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional

from modules.im import MessageContext, InlineKeyboard, InlineButton

logger = logging.getLogger(__name__)


@dataclass
class IssueDraft:
    """Represents a draft issue pending user confirmation."""

    title: str
    body: str
    repo: str
    labels: list[str] = field(default_factory=list)
    channel_id: str = ""
    user_id: str = ""
    created_at: float = field(default_factory=time.time)
    source_messages: list[dict] = field(default_factory=list)


class IssueHandler:
    """Handles /issue command and related callbacks."""

    # In-memory store for pending issue drafts
    # Key: draft_id (hash), Value: IssueDraft
    _pending_drafts: dict[str, IssueDraft] = {}

    def __init__(self, controller):
        """Initialize with reference to main controller."""
        self.controller = controller
        self.config = controller.config
        self.im_client = controller.im_client

    def _get_channel_context(self, context: MessageContext) -> MessageContext:
        """Get context for channel messages (no thread)."""
        if self.config.platform == "slack":
            return MessageContext(
                user_id=context.user_id,
                channel_id=context.channel_id,
                thread_id=None,
                platform_specific=context.platform_specific,
            )
        return context

    def _generate_draft_id(self, channel_id: str, user_id: str) -> str:
        """Generate a unique draft ID."""
        data = f"{channel_id}:{user_id}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:12]

    def _get_default_repo(self) -> Optional[str]:
        """Get default repository from config."""
        if self.config.github:
            # Try to get from issue_extraction config first
            issue_config = getattr(self.config, "issue_extraction", None)
            if issue_config and hasattr(issue_config, "default_repo"):
                return issue_config.default_repo

            # Fallback: use first repo from repo_mappings
            if self.config.github.repo_mappings:
                return next(iter(self.config.github.repo_mappings.keys()), None)

        return None

    def _get_installation_id(self, repo: str) -> Optional[str]:
        """Get GitHub installation ID for a repo."""
        if not self.config.github:
            return None

        # Check repo-specific installation
        repo_config = self.config.github.repo_mappings.get(repo, {})
        if isinstance(repo_config, dict):
            inst_id = repo_config.get("installation_id")
            if inst_id:
                return str(inst_id)

        # Fallback to default installation
        return getattr(self.config.github, "default_installation_id", None)

    async def handle_issue_command(
        self,
        context: MessageContext,
        args: str = "",
    ) -> None:
        """Handle /issue command.

        Args:
            context: Message context
            args: Command arguments (e.g., "--hours 24 --repo owner/repo")
        """
        channel_context = self._get_channel_context(context)

        # Check if we're in a thread
        is_thread = bool(context.thread_id)

        # Parse arguments
        hours = 24
        repo = self._get_default_repo()

        if args:
            parts = args.split()
            i = 0
            while i < len(parts):
                if parts[i] == "--hours" and i + 1 < len(parts):
                    try:
                        hours = int(parts[i + 1])
                    except ValueError:
                        pass
                    i += 2
                elif parts[i] == "--repo" and i + 1 < len(parts):
                    repo = parts[i + 1]
                    i += 2
                else:
                    i += 1

        # Validate repo
        if not repo:
            await self.im_client.send_message(
                channel_context,
                "❌ No repository configured. Use `--repo owner/repo` or configure a default repository.",
            )
            return

        # Check GitHub client availability
        if not hasattr(self.controller, "github_client") or not self.controller.github_client:
            await self.im_client.send_message(
                channel_context,
                "❌ GitHub integration is not configured. Please set up GitHub App credentials.",
            )
            return

        # Send initial status based on context
        if is_thread:
            status_msg_id = await self.im_client.send_message(
                channel_context,
                "📝 Collecting messages from this thread...",
            )
        else:
            status_msg_id = await self.im_client.send_message(
                channel_context,
                f"📝 Collecting messages from the last {hours} hours...",
            )

        try:
            # Collect messages based on context
            if is_thread:
                # In a thread: collect all thread replies
                messages = await self.im_client.get_thread_replies(
                    context.channel_id,
                    context.thread_id,
                )
            else:
                # In channel: collect recent channel history
                messages = await self.im_client.get_channel_history(
                    context.channel_id,
                    hours=hours,
                    limit=100,
                )

            if not messages:
                error_msg = (
                    "❌ No messages found in this thread."
                    if is_thread
                    else "❌ No messages found in the specified time range."
                )
                await self.im_client.update_message(
                    context.channel_id,
                    status_msg_id,
                    error_msg,
                )
                return

            # Update status
            await self.im_client.update_message(
                context.channel_id,
                status_msg_id,
                f"🤖 Analyzing {len(messages)} messages with AI...",
            )

            # Format messages for AI analysis
            formatted_messages = await self._format_messages_for_analysis(messages)

            # Extract requirements using Claude
            extracted = await self._extract_requirements(formatted_messages)

            if not extracted:
                await self.im_client.update_message(
                    context.channel_id,
                    status_msg_id,
                    "❌ Failed to extract requirements from the discussion.",
                )
                return

            # Create draft
            draft_id = self._generate_draft_id(context.channel_id, context.user_id)
            draft = IssueDraft(
                title=extracted.get("title", "Untitled Issue"),
                body=extracted.get("body", ""),
                repo=repo,
                labels=extracted.get("labels", []),
                channel_id=context.channel_id,
                user_id=context.user_id,
                source_messages=messages,
            )
            self._pending_drafts[draft_id] = draft

            # Delete status message
            try:
                await self.im_client.delete_message(context.channel_id, status_msg_id)
            except Exception:
                pass

            # Show preview with buttons
            await self._show_issue_preview(channel_context, draft_id, draft)

        except Exception as e:
            logger.error(f"Error in issue extraction: {e}", exc_info=True)
            try:
                await self.im_client.update_message(
                    context.channel_id,
                    status_msg_id,
                    f"❌ Error: {str(e)}",
                )
            except Exception:
                await self.im_client.send_message(
                    channel_context,
                    f"❌ Error extracting issue: {str(e)}",
                )

    async def _format_messages_for_analysis(self, messages: list[dict]) -> str:
        """Format messages for AI analysis."""
        lines = []
        for msg in messages:
            user_id = msg.get("user", "unknown")
            # Try to get display name
            try:
                display_name = await self.im_client.get_user_display_name(user_id)
            except Exception:
                display_name = user_id

            text = msg.get("text", "")
            lines.append(f"[{display_name}]: {text}")

        return "\n".join(lines)

    async def _extract_requirements(self, discussion: str) -> Optional[dict]:
        """Extract requirements from discussion using Claude API."""
        try:
            import anthropic

            client = anthropic.Anthropic()

            prompt = f"""Analyze the following Slack discussion and extract a software requirement or bug report.

<discussion>
{discussion}
</discussion>

Based on the discussion, create a GitHub issue. Return a JSON object with these fields:
- title: A concise issue title (max 80 characters)
- body: Detailed issue description in markdown format, including:
  - Summary of the problem or feature request
  - Key points from the discussion
  - Acceptance criteria if applicable
- labels: Array of suggested labels (e.g., ["bug", "enhancement", "documentation"])

Return ONLY the JSON object, no other text."""

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            content = response.content[0].text
            # Try to extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            return json.loads(content.strip())

        except ImportError:
            logger.error("anthropic package not installed")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error calling Claude API: {e}", exc_info=True)
            return None

    async def _show_issue_preview(
        self,
        context: MessageContext,
        draft_id: str,
        draft: IssueDraft,
    ) -> None:
        """Show issue preview with confirmation buttons."""
        labels_str = ", ".join(draft.labels) if draft.labels else "None"

        preview_text = f"""📋 **Issue Preview**

**Repository:** `{draft.repo}`
**Title:** {draft.title}
**Labels:** {labels_str}

**Description:**
{draft.body[:500]}{"..." if len(draft.body) > 500 else ""}"""

        buttons = [
            [
                InlineButton(text="✅ Create Issue", callback_data=f"issue_confirm:{draft_id}"),
                InlineButton(text="✏️ Edit", callback_data=f"issue_edit:{draft_id}"),
                InlineButton(text="❌ Cancel", callback_data=f"issue_cancel:{draft_id}"),
            ]
        ]

        keyboard = InlineKeyboard(buttons=buttons)
        await self.im_client.send_message_with_buttons(context, preview_text, keyboard)

    async def handle_confirm(self, context: MessageContext, draft_id: str) -> None:
        """Handle issue confirmation."""
        draft = self._pending_drafts.get(draft_id)
        if not draft:
            await self.im_client.send_message(
                context,
                "❌ Issue draft expired or not found. Please run `/issue` again.",
            )
            return

        # Get GitHub client and installation ID
        github_client = self.controller.github_client
        installation_id = self._get_installation_id(draft.repo)

        if not installation_id:
            await self.im_client.send_message(
                context,
                f"❌ No GitHub installation found for repository `{draft.repo}`.",
            )
            return

        try:
            # Parse repo
            owner, repo_name = draft.repo.split("/")

            # Add source reference to body
            body_with_source = f"""{draft.body}

---
📍 *Extracted from Slack discussion*
"""

            # Add solver mention if configured
            solver_mention = self._get_solver_mention()
            if solver_mention:
                body_with_source += f"\n{solver_mention} Please review and address this issue."

            # Create issue
            result = await github_client.api.create_issue(
                installation_id=installation_id,
                owner=owner,
                repo=repo_name,
                title=draft.title,
                body=body_with_source,
                labels=draft.labels if draft.labels else None,
            )

            issue_url = result.get("html_url", "")
            issue_number = result.get("number", "")

            # Clean up draft
            del self._pending_drafts[draft_id]

            # Send success message
            await self.im_client.send_message(
                context,
                f"✅ Issue created successfully!\n\n"
                f"**#{issue_number}** - {draft.title}\n"
                f"🔗 {issue_url}",
            )

        except Exception as e:
            logger.error(f"Error creating GitHub issue: {e}", exc_info=True)
            await self.im_client.send_message(
                context,
                f"❌ Failed to create issue: {str(e)}",
            )

    async def handle_edit(self, context: MessageContext, draft_id: str) -> None:
        """Handle edit button - open modal for editing."""
        draft = self._pending_drafts.get(draft_id)
        if not draft:
            await self.im_client.send_message(
                context,
                "❌ Issue draft expired or not found. Please run `/issue` again.",
            )
            return

        # Get trigger_id for modal
        trigger_id = (
            context.platform_specific.get("trigger_id")
            if context.platform_specific
            else None
        )

        if not trigger_id:
            await self.im_client.send_message(
                context,
                "❌ Cannot open edit dialog. Please try again.",
            )
            return

        # Open edit modal
        await self._open_edit_modal(trigger_id, draft_id, draft)

    async def handle_cancel(self, context: MessageContext, draft_id: str) -> None:
        """Handle cancel button."""
        if draft_id in self._pending_drafts:
            del self._pending_drafts[draft_id]

        await self.im_client.send_message(
            context,
            "🗑️ Issue creation cancelled.",
        )

    async def _open_edit_modal(
        self,
        trigger_id: str,
        draft_id: str,
        draft: IssueDraft,
    ) -> None:
        """Open Slack modal for editing issue."""
        modal = {
            "type": "modal",
            "callback_id": f"issue_edit_submit:{draft_id}",
            "private_metadata": draft.channel_id,
            "title": {"type": "plain_text", "text": "Edit Issue"},
            "submit": {"type": "plain_text", "text": "Save"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "title_block",
                    "label": {"type": "plain_text", "text": "Title"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "title_input",
                        "initial_value": draft.title,
                        "max_length": 200,
                    },
                },
                {
                    "type": "input",
                    "block_id": "body_block",
                    "label": {"type": "plain_text", "text": "Description"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "body_input",
                        "multiline": True,
                        "initial_value": draft.body,
                    },
                },
                {
                    "type": "input",
                    "block_id": "labels_block",
                    "label": {"type": "plain_text", "text": "Labels (comma-separated)"},
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "labels_input",
                        "initial_value": ", ".join(draft.labels),
                    },
                },
                {
                    "type": "input",
                    "block_id": "repo_block",
                    "label": {"type": "plain_text", "text": "Repository (owner/repo)"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "repo_input",
                        "initial_value": draft.repo,
                    },
                },
            ],
        }

        try:
            await self.im_client.web_client.views_open(
                trigger_id=trigger_id,
                view=modal,
            )
        except Exception as e:
            logger.error(f"Error opening edit modal: {e}", exc_info=True)

    async def handle_edit_submit(
        self,
        draft_id: str,
        values: dict,
        context: MessageContext,
    ) -> None:
        """Handle edit modal submission."""
        draft = self._pending_drafts.get(draft_id)
        if not draft:
            return

        # Update draft with new values
        try:
            draft.title = values["title_block"]["title_input"]["value"]
            draft.body = values["body_block"]["body_input"]["value"]
            draft.repo = values["repo_block"]["repo_input"]["value"]

            labels_str = values.get("labels_block", {}).get("labels_input", {}).get("value", "")
            draft.labels = [l.strip() for l in labels_str.split(",") if l.strip()]

            # Show updated preview
            channel_context = self._get_channel_context(context)
            await self._show_issue_preview(channel_context, draft_id, draft)

        except Exception as e:
            logger.error(f"Error processing edit submission: {e}", exc_info=True)

    def _get_solver_mention(self) -> Optional[str]:
        """Get the solver agent mention string."""
        issue_config = getattr(self.config, "issue_extraction", None)
        if issue_config and hasattr(issue_config, "solver_mention"):
            return issue_config.solver_mention

        # Default to GitHub trigger keyword if configured
        if self.config.github and self.config.github.trigger_keyword:
            return self.config.github.trigger_keyword

        return None

    def cleanup_expired_drafts(self, max_age_seconds: int = 3600) -> int:
        """Clean up expired drafts. Returns number of cleaned drafts."""
        now = time.time()
        expired = [
            draft_id
            for draft_id, draft in self._pending_drafts.items()
            if now - draft.created_at > max_age_seconds
        ]
        for draft_id in expired:
            del self._pending_drafts[draft_id]
        return len(expired)
