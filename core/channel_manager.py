"""
core/channel_manager.py

Manage per-channel configuration for multi-channel signal processing.

Loads channel definitions from config/channels.json.
Provides per-channel rules (breakeven, trailing, partial close).
Falls back to "default" section or global .env values when
a channel is not configured.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utils.logger import log_event


_DEFAULT_CONFIG_PATH = "config/channels.json"


class ChannelManager:
    """In-memory holder for per-channel configuration.

    Loads channels.json on init. Provides rule lookups with
    fallback to default section.
    """

    def __init__(self, config_path: str = _DEFAULT_CONFIG_PATH) -> None:
        self._config_path = config_path
        self._default_rules: dict[str, Any] = {}
        self._channels: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load channel config from JSON file.

        If file doesn't exist, all channels use global defaults.
        """
        path = Path(self._config_path)
        if not path.exists():
            log_event(
                "channel_manager_no_config",
                path=self._config_path,
            )
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Parse default rules
            default_section = data.get("default", {})
            self._default_rules = default_section.get("rules", {})

            # Parse channel-specific configs
            channels_section = data.get("channels", {})
            for chat_id, channel_data in channels_section.items():
                self._channels[str(chat_id)] = channel_data

            log_event(
                "channel_manager_loaded",
                channels_count=len(self._channels),
                default_rules=list(self._default_rules.keys()),
            )
        except (json.JSONDecodeError, OSError) as exc:
            log_event(
                "channel_manager_load_error",
                path=self._config_path,
                error=str(exc),
            )

    def is_known_channel(self, chat_id: str) -> bool:
        """Check if a channel has explicit configuration."""
        return str(chat_id) in self._channels

    def get_channel_name(self, chat_id: str) -> str:
        """Get human-readable channel name."""
        channel = self._channels.get(str(chat_id), {})
        return channel.get("name", str(chat_id))

    def get_rules(self, chat_id: str) -> dict[str, Any]:
        """Get per-channel position management rules.

        Merges default rules with channel-specific overrides.
        Channel rules take precedence over defaults.

        Returns:
            Dict with rule values. Missing keys use defaults.
        """
        merged = dict(self._default_rules)  # copy defaults
        channel = self._channels.get(str(chat_id), {})
        channel_rules = channel.get("rules", {})
        merged.update(channel_rules)
        return merged

    def get_all_channel_ids(self) -> list[str]:
        """Return all configured channel IDs."""
        return list(self._channels.keys())

    def reload(self) -> None:
        """Hot-reload configuration from disk.

        Clears existing config and re-reads the file.
        """
        self._default_rules = {}
        self._channels = {}
        self._load()
        log_event("channel_manager_reloaded")
