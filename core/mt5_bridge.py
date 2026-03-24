"""
core/mt5_bridge.py

Platform-aware MetaTrader5 abstraction.

On Windows:  uses native MetaTrader5 package (COM/DLL).
On Linux:    uses mt5linux rpyc bridge to Wine-hosted MT5.

All modules import mt5 from here instead of importing MetaTrader5 directly.

Usage:
    from core.mt5_bridge import mt5
"""

from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    # ── Windows: native MetaTrader5 ──────────────────────────────
    import MetaTrader5 as mt5  # type: ignore[import-untyped]
else:
    # ── Linux: mt5linux rpyc bridge ──────────────────────────────
    # Requires:
    #   1. Wine + MT5 terminal running
    #   2. Wine Python with MetaTrader5 + mt5linux installed
    #   3. rpyc server running: `wine python -m mt5linux`
    #
    # Connection defaults can be overridden via env vars:
    #   MT5_RPYC_HOST (default: localhost)
    #   MT5_RPYC_PORT (default: 18812)
    try:
        from mt5linux import MetaTrader5  # type: ignore[import-untyped]

        _host = os.getenv("MT5_RPYC_HOST", "localhost")
        _port = int(os.getenv("MT5_RPYC_PORT", "18812"))
        mt5 = MetaTrader5(host=_host, port=_port)
    except ImportError:
        # Fallback: allow import to succeed for testing/dry-run
        # without mt5linux installed. Runtime calls will fail.
        mt5 = None  # type: ignore[assignment]
