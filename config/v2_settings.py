import json
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from config import paths

logger = logging.getLogger(__name__)

DEFAULT_SHOW_MESSAGE_TYPES: List[str] = []
ALLOWED_MESSAGE_TYPES = {"system", "assistant", "toolcall"}


def normalize_show_message_types(show_message_types: Optional[List[str]]) -> List[str]:
    if show_message_types is None:
        return DEFAULT_SHOW_MESSAGE_TYPES.copy()
    return [msg for msg in show_message_types if msg in ALLOWED_MESSAGE_TYPES]


@dataclass
class RoutingSettings:
    agent_backend: Optional[str] = None
    opencode_agent: Optional[str] = None
    opencode_model: Optional[str] = None
    opencode_reasoning_effort: Optional[str] = None


@dataclass
class ChannelSettings:
    enabled: bool = False
    show_message_types: List[str] = field(
        default_factory=lambda: DEFAULT_SHOW_MESSAGE_TYPES.copy()
    )
    custom_cwd: Optional[str] = None
    routing: RoutingSettings = field(default_factory=RoutingSettings)
    # Per-channel require_mention override: None=use global default, True=require, False=don't require
    require_mention: Optional[bool] = None


@dataclass
class GitHubRepoSettings:
    """Per-repository settings for GitHub integration."""
    enabled: bool = True
    agent: str = "claude"  # Agent backend to use
    cwd: Optional[str] = None  # Working directory (None = auto clone)
    allowed_users: List[str] = field(default_factory=list)  # Empty = all users allowed


@dataclass
class GitHubInstallationSettings:
    """Per-installation settings (GitHub App installation level)."""
    account: str = ""  # GitHub account name (user or org)
    account_type: str = "User"  # "User" or "Organization"
    repos: Dict[str, GitHubRepoSettings] = field(default_factory=dict)


@dataclass
class GitHubSettings:
    """GitHub integration settings."""
    installations: Dict[str, GitHubInstallationSettings] = field(default_factory=dict)


@dataclass
class SettingsState:
    channels: Dict[str, ChannelSettings] = field(default_factory=dict)
    github: GitHubSettings = field(default_factory=GitHubSettings)


class SettingsStore:
    def __init__(self, settings_path: Optional[Path] = None):
        self.settings_path = settings_path or paths.get_settings_path()
        self.settings: SettingsState = SettingsState()
        self._load()

    def _load(self) -> None:
        if not self.settings_path.exists():
            return
        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("Failed to load settings: %s", exc)
            return
        raw_channels = payload.get("channels") if isinstance(payload, dict) else None
        if raw_channels is None:
            logger.error("Failed to load settings: invalid format")
            return
        if not isinstance(raw_channels, dict):
            logger.error("Failed to load settings: channels must be an object")
            return
        channels = {}
        for channel_id, channel_payload in raw_channels.items():
            if not isinstance(channel_payload, dict):
                continue
            routing_payload = channel_payload.get("routing") or {}
            routing = RoutingSettings(
                agent_backend=routing_payload.get("agent_backend"),
                opencode_agent=routing_payload.get("opencode_agent"),
                opencode_model=routing_payload.get("opencode_model"),
                opencode_reasoning_effort=routing_payload.get("opencode_reasoning_effort"),
            )
            channels[channel_id] = ChannelSettings(
                enabled=channel_payload.get("enabled", False),
                show_message_types=normalize_show_message_types(
                    channel_payload.get("show_message_types")
                ),
                custom_cwd=channel_payload.get("custom_cwd"),
                routing=routing,
                require_mention=channel_payload.get("require_mention"),
            )
        # Load GitHub settings
        github = self._load_github_settings(payload.get("github"))
        self.settings = SettingsState(channels=channels, github=github)

    def _load_github_settings(self, raw_github: Optional[dict]) -> GitHubSettings:
        """Load GitHub settings from raw payload."""
        github = GitHubSettings()
        if not raw_github or not isinstance(raw_github, dict):
            return github

        raw_installations = raw_github.get("installations")
        if not raw_installations or not isinstance(raw_installations, dict):
            return github

        for installation_id, installation_payload in raw_installations.items():
            if not isinstance(installation_payload, dict):
                continue
            repos = {}
            raw_repos = installation_payload.get("repos") or {}
            for repo_name, repo_payload in raw_repos.items():
                if not isinstance(repo_payload, dict):
                    continue
                repos[repo_name] = GitHubRepoSettings(
                    enabled=repo_payload.get("enabled", True),
                    agent=repo_payload.get("agent", "claude"),
                    cwd=repo_payload.get("cwd"),
                    allowed_users=repo_payload.get("allowed_users") or [],
                )
            github.installations[installation_id] = GitHubInstallationSettings(
                account=installation_payload.get("account", ""),
                account_type=installation_payload.get("account_type", "User"),
                repos=repos,
            )
        return github

    def save(self) -> None:
        paths.ensure_data_dirs()
        payload = {"channels": {}, "github": {"installations": {}}}
        for channel_id, settings in self.settings.channels.items():
            payload["channels"][channel_id] = {
                "enabled": settings.enabled,
                "show_message_types": settings.show_message_types,
                "custom_cwd": settings.custom_cwd,
                "routing": {
                    "agent_backend": settings.routing.agent_backend,
                    "opencode_agent": settings.routing.opencode_agent,
                    "opencode_model": settings.routing.opencode_model,
                    "opencode_reasoning_effort": settings.routing.opencode_reasoning_effort,
                },
                "require_mention": settings.require_mention,
            }
        # Save GitHub settings
        for inst_id, inst in self.settings.github.installations.items():
            repos_payload = {}
            for repo_name, repo in inst.repos.items():
                repos_payload[repo_name] = {
                    "enabled": repo.enabled,
                    "agent": repo.agent,
                    "cwd": repo.cwd,
                    "allowed_users": repo.allowed_users,
                }
            payload["github"]["installations"][inst_id] = {
                "account": inst.account,
                "account_type": inst.account_type,
                "repos": repos_payload,
            }
        self.settings_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get_channel(self, channel_id: str) -> ChannelSettings:
        if channel_id not in self.settings.channels:
            self.settings.channels[channel_id] = ChannelSettings()
        return self.settings.channels[channel_id]

    def update_channel(self, channel_id: str, settings: ChannelSettings) -> None:
        self.settings.channels[channel_id] = settings
        self.save()

    # GitHub settings methods
    def get_github_repo(self, installation_id: str, repo: str) -> Optional[GitHubRepoSettings]:
        """Get settings for a specific GitHub repo."""
        inst = self.settings.github.installations.get(installation_id)
        if not inst:
            return None
        return inst.repos.get(repo)

    def update_github_installation(
        self, installation_id: str, settings: GitHubInstallationSettings
    ) -> None:
        """Update settings for a GitHub App installation."""
        self.settings.github.installations[installation_id] = settings
        self.save()

    def update_github_repo(
        self, installation_id: str, repo: str, settings: GitHubRepoSettings
    ) -> None:
        """Update settings for a specific GitHub repo."""
        if installation_id not in self.settings.github.installations:
            self.settings.github.installations[installation_id] = GitHubInstallationSettings()
        self.settings.github.installations[installation_id].repos[repo] = settings
        self.save()

    def is_github_repo_enabled(self, installation_id: str, repo: str) -> bool:
        """Check if a GitHub repo is enabled for bot integration."""
        repo_settings = self.get_github_repo(installation_id, repo)
        return repo_settings.enabled if repo_settings else False

    def get_github_repo_agent(self, installation_id: str, repo: str) -> str:
        """Get the agent backend for a GitHub repo."""
        repo_settings = self.get_github_repo(installation_id, repo)
        return repo_settings.agent if repo_settings else "claude"
