"""GitHub Markdown formatter.

GitHub uses standard markdown with some extensions (GFM - GitHub Flavored Markdown).
"""

from modules.im.formatters.base_formatter import BaseMarkdownFormatter


class GitHubFormatter(BaseMarkdownFormatter):
    """GitHub-specific markdown formatter.

    GitHub Flavored Markdown (GFM) supports:
    - Standard markdown formatting
    - Task lists
    - Tables
    - Autolinked references (issues, PRs)
    - Emoji shortcodes
    - <details> collapsible sections
    """

    def format_bold(self, text: str) -> str:
        """Format bold text using **."""
        return f"**{text}**"

    def format_italic(self, text: str) -> str:
        """Format italic text using *."""
        return f"*{text}*"

    def format_strikethrough(self, text: str) -> str:
        """Format strikethrough text using ~~."""
        return f"~~{text}~~"

    def format_link(self, text: str, url: str) -> str:
        """Format hyperlink using standard markdown."""
        return f"[{text}]({url})"

    def escape_special_chars(self, text: str) -> str:
        """Escape special markdown characters.

        GitHub markdown is fairly permissive, but we should escape
        characters that could be interpreted as formatting.
        """
        # Characters that need escaping in markdown
        escape_chars = ["\\", "`", "*", "_", "{", "}", "[", "]", "(", ")", "#", "+", "-", ".", "!"]

        result = text
        for char in escape_chars:
            # Only escape if it might be interpreted as formatting
            # Be conservative to avoid over-escaping
            if char in ["*", "_", "`", "~"]:
                # These are the main formatting characters
                # We'll escape them only at word boundaries
                pass  # For now, let GitHub handle it

        # For GitHub, we mainly need to escape backticks in code contexts
        # and angle brackets that might be interpreted as HTML
        result = result.replace("<", "&lt;").replace(">", "&gt;")

        return result

    def format_collapsible(self, summary: str, content: str) -> str:
        """Format collapsible section using <details>.

        Args:
            summary: Summary text shown when collapsed
            content: Content shown when expanded

        Returns:
            Formatted collapsible section
        """
        return f"""<details>
<summary>{summary}</summary>

{content}

</details>"""

    def format_task_item(self, text: str, checked: bool = False) -> str:
        """Format task list item.

        Args:
            text: Task text
            checked: Whether the task is completed

        Returns:
            Formatted task item
        """
        checkbox = "[x]" if checked else "[ ]"
        return f"- {checkbox} {text}"

    def format_mention(self, username: str) -> str:
        """Format a GitHub @mention.

        Args:
            username: GitHub username

        Returns:
            Formatted mention
        """
        return f"@{username}"

    def format_issue_ref(self, number: int) -> str:
        """Format an issue/PR reference.

        Args:
            number: Issue or PR number

        Returns:
            Formatted reference (auto-linked by GitHub)
        """
        return f"#{number}"

    def format_commit_ref(self, sha: str, short: bool = True) -> str:
        """Format a commit reference.

        Args:
            sha: Commit SHA
            short: Use short SHA (7 chars)

        Returns:
            Formatted commit reference (auto-linked by GitHub)
        """
        if short and len(sha) > 7:
            sha = sha[:7]
        return sha

    def format_status_badge(self, status: str) -> str:
        """Format a status badge/emoji.

        Args:
            status: Status type

        Returns:
            Formatted status with emoji
        """
        status_map = {
            "running": "🔄 Running",
            "success": "✅ Success",
            "error": "❌ Error",
            "pending": "⏳ Pending",
            "warning": "⚠️ Warning",
        }
        return status_map.get(status, f"• {status}")

    def format_bot_header(self) -> str:
        """Format the bot response header."""
        return "🤖 **Vibe Remote**"

    def format_processing_message(self) -> str:
        """Format the 'processing' status message."""
        return """🤖 **Vibe Remote**

⏳ Processing your request...

<details>
<summary>Execution Log</summary>

_Waiting for agent output..._

</details>"""

    def format_agent_response(
        self,
        status: str,
        log_content: str = "",
        result: str = "",
        duration_ms: int = 0,
    ) -> str:
        """Format a complete agent response.

        Args:
            status: Execution status ("running", "success", "error")
            log_content: Execution log content
            result: Final result text
            duration_ms: Execution duration in milliseconds

        Returns:
            Formatted response message
        """
        header = self.format_bot_header()
        status_badge = self.format_status_badge(status)

        # Format duration
        if duration_ms > 0:
            total_seconds = duration_ms / 1000
            minutes = int(total_seconds // 60)
            seconds = int(total_seconds % 60)
            if minutes > 0:
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = f"{seconds}s"
            duration_line = f"\n⏱️ Duration: {duration_str}"
        else:
            duration_line = ""

        # Format log section
        if log_content:
            log_section = self.format_collapsible(
                "Execution Log",
                f"```\n{log_content}\n```"
            )
        else:
            log_section = ""

        # Format result
        if result:
            result_section = f"\n\n{result}"
        else:
            result_section = ""

        return f"""{header}

{status_badge}{duration_line}

{log_section}{result_section}"""
