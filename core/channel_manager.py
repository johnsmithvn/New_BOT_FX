"""
core/channel_manager.py

Manage per-channel configuration for multi-channel signal processing.

Loads channel definitions from config/channels.json.
Provides per-channel rules (breakeven, trailing, partial close).
Falls back to "default" section or global .env values when
a channel is not configured.

P9: Added strategy, risk, and validation config per channel.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utils.logger import log_event


_DEFAULT_CONFIG_PATH = "config/channels.json"

# Default strategy config — used when channels.json has no strategy section.
_DEFAULT_STRATEGY: dict[str, Any] = {
    "mode": "single",
    "max_entries": 1,
    "reentry_enabled": False,
    "reentry_step_pips": 0,
    "signal_ttl_minutes": 15,
    "volume_split": "equal",
}


class ChannelManager:
    """In-memory holder for per-channel configuration.

    Loads channels.json on init. Provides rule lookups with
    fallback to default section.

    P9: Also provides strategy, risk, and validation config per channel.
    """

    def __init__(self, config_path: str = _DEFAULT_CONFIG_PATH) -> None:
        self._config_path = config_path
        self._default_rules: dict[str, Any] = {}
        self._default_strategy: dict[str, Any] = {}
        self._default_risk: dict[str, Any] = {}
        self._default_validation: dict[str, Any] = {}
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

            # Parse default sections
            default_section = data.get("default", {})
            self._default_rules = default_section.get("rules", {})
            self._default_strategy = {
                **_DEFAULT_STRATEGY,
                **default_section.get("strategy", {}),
            }
            self._default_risk = default_section.get("risk", {})
            self._default_validation = default_section.get("validation", {})

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

    def get_channel_name(self, chat_id: str) -> str:
        """Get human-readable channel name."""
        channel = self._channels.get(str(chat_id), {})
        return channel.get("name", str(chat_id))

    def _get_section(
        self,
        chat_id: str,
        section: str,
        defaults: dict[str, Any],
    ) -> dict[str, Any]:
        """Generic section lookup with default merge.

        Merges hardcoded defaults → JSON default section → channel override.
        """
        merged = dict(defaults)
        channel = self._channels.get(str(chat_id), {})
        channel_section = channel.get(section, {})
        merged.update(channel_section)
        return merged

    def get_rules(self, chat_id: str) -> dict[str, Any]:
        """Get per-channel position management rules.

        Merges default rules with channel-specific overrides.
        Channel rules take precedence over defaults.

        Returns:
            Dict with rule values. Missing keys use defaults.
        """
        return self._get_section(chat_id, "rules", self._default_rules)

    def get_strategy(self, chat_id: str) -> dict[str, Any]:
        """Get per-channel entry strategy config (P9).

        Keys: mode, max_entries, reentry_enabled, reentry_step_pips,
              signal_ttl_minutes, volume_split.

        Falls back to default strategy when channel has no override.
        """
        return self._get_section(chat_id, "strategy", self._default_strategy)

    def get_risk_config(self, chat_id: str) -> dict[str, Any]:
        """Get per-channel risk config (P9).

        Keys: mode, fixed_lot_size, risk_percent.

        Empty dict means: use global .env settings.
        """
        return self._get_section(chat_id, "risk", self._default_risk)

    def get_validation_config(self, chat_id: str) -> dict[str, Any]:
        """Get per-channel validation overrides (P9).

        Keys: max_entry_distance_pips, max_entry_drift_pips, max_spread_pips.

        Empty dict means: use global .env settings.
        """
        return self._get_section(chat_id, "validation", self._default_validation)

    def reload(self) -> None:
        """Hot-reload configuration from disk.

        Clears existing config and re-reads the file.
        """
        self._default_rules = {}
        self._default_strategy = {}
        self._default_risk = {}
        self._default_validation = {}
        self._channels = {}
        self._load()
        log_event("channel_manager_reloaded")

