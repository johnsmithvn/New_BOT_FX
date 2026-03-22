"""
tests/test_channel_manager.py

Unit tests for core/channel_manager.py — per-channel config.
"""

import json
import os
import tempfile

from core.channel_manager import ChannelManager


def _write_config(data: dict) -> str:
    """Write channel config to a temp file, return path."""
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    return path


class TestLoadConfig:
    """Config loading behavior."""

    def test_missing_file_no_crash(self):
        cm = ChannelManager(config_path="/nonexistent/path.json")
        # Should not raise — empty defaults
        assert cm.get_rules("any_chat") == {}

    def test_invalid_json_no_crash(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            f.write("NOT VALID JSON {{{")
        cm = ChannelManager(config_path=path)
        assert cm.get_rules("any_chat") == {}
        os.unlink(path)

    def test_valid_config_loads(self):
        data = {
            "default": {"rules": {"breakeven_trigger_pips": 20}},
            "channels": {
                "123": {"name": "Gold Channel", "rules": {"breakeven_trigger_pips": 30}},
            },
        }
        path = _write_config(data)
        cm = ChannelManager(config_path=path)
        assert cm.get_channel_name("123") == "Gold Channel"
        os.unlink(path)


class TestGetRules:
    """Per-channel rule lookup with defaults."""

    def setup_method(self):
        data = {
            "default": {"rules": {"breakeven_trigger_pips": 20, "trailing_pips": 15}},
            "channels": {
                "123": {"rules": {"breakeven_trigger_pips": 30}},
            },
        }
        self.path = _write_config(data)
        self.cm = ChannelManager(config_path=self.path)

    def teardown_method(self):
        os.unlink(self.path)

    def test_channel_override(self):
        rules = self.cm.get_rules("123")
        assert rules["breakeven_trigger_pips"] == 30

    def test_default_fallback(self):
        rules = self.cm.get_rules("unknown_chat")
        assert rules["breakeven_trigger_pips"] == 20

    def test_merge_with_defaults(self):
        rules = self.cm.get_rules("123")
        # trailing_pips not overridden → should come from defaults
        assert rules.get("trailing_pips") == 15


class TestGetStrategy:
    """Per-channel strategy config."""

    def setup_method(self):
        data = {
            "default": {"strategy": {"mode": "single", "max_entries": 1}},
            "channels": {
                "456": {"strategy": {"mode": "range", "max_entries": 3}},
            },
        }
        self.path = _write_config(data)
        self.cm = ChannelManager(config_path=self.path)

    def teardown_method(self):
        os.unlink(self.path)

    def test_channel_strategy(self):
        strat = self.cm.get_strategy("456")
        assert strat["mode"] == "range"
        assert strat["max_entries"] == 3

    def test_default_strategy(self):
        strat = self.cm.get_strategy("unknown")
        assert strat["mode"] == "single"


class TestGetChannelName:
    """Channel name resolution."""

    def setup_method(self):
        data = {
            "default": {},
            "channels": {"789": {"name": "Forex VIP"}},
        }
        self.path = _write_config(data)
        self.cm = ChannelManager(config_path=self.path)

    def teardown_method(self):
        os.unlink(self.path)

    def test_known_channel(self):
        assert self.cm.get_channel_name("789") == "Forex VIP"

    def test_unknown_returns_chat_id(self):
        assert self.cm.get_channel_name("999") == "999"


class TestReload:
    """Hot-reload config."""

    def test_reload_clears_and_reloads(self):
        data1 = {"default": {}, "channels": {"1": {"name": "A"}}}
        path = _write_config(data1)
        cm = ChannelManager(config_path=path)
        assert cm.get_channel_name("1") == "A"

        # Overwrite file
        data2 = {"default": {}, "channels": {"1": {"name": "B"}}}
        with open(path, "w") as f:
            json.dump(data2, f)

        cm.reload()
        assert cm.get_channel_name("1") == "B"
        os.unlink(path)
