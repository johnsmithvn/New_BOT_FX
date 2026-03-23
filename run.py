"""
run.py

Unified launcher for telegram-mt5-bot.
Starts bot, dashboards, or combinations with a single command.

Usage:
    python run.py                  # Interactive menu
    python run.py bot              # Trading bot only
    python run.py dash             # Dashboard V1 only (port 8000)
    python run.py v2               # Dashboard V2 only (port 5173)
    python run.py dash+bot         # V1 dashboard + bot
    python run.py v2+bot           # V2 dashboard + bot

Note: Dashboards read from the SQLite database (data/bot.db).
      The bot does NOT need to be running for dashboards to work.
      However, without the bot, data won't update.
"""

from __future__ import annotations

# Ensure UTF-8 output on Windows
import sys as _sys
if _sys.platform == "win32":
    try:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        _sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).parent
V2_DIR = ROOT / "dashboard-v2"

# ── Component Runners ────────────────────────────────────────────


def run_bot() -> None:
    """Run the trading bot (blocking)."""
    print("🤖 Starting trading bot ...")
    # Import inline to avoid loading heavy deps when not needed
    from main import Bot
    import asyncio
    bot = Bot()
    asyncio.run(bot.run())


def run_dashboard_v1() -> None:
    """Run Dashboard V1 — FastAPI + Jinja2 on port 8000."""
    print("📊 Starting Dashboard V1 on http://localhost:8000 ...")
    import uvicorn
    uvicorn.run(
        "dashboard.dashboard:app",
        host=os.getenv("DASHBOARD_HOST", "0.0.0.0"),
        port=int(os.getenv("DASHBOARD_PORT", "8000")),
        reload=False,
        log_level="info",
    )


def run_dashboard_v2() -> None:
    """Run Dashboard V2 — Vite React dev server on port 5173."""
    if not V2_DIR.exists():
        print(f"❌ dashboard-v2/ not found at {V2_DIR}")
        sys.exit(1)

    node_modules = V2_DIR / "node_modules"
    if not node_modules.exists():
        print("📦 Installing V2 dependencies (first time) ...")
        subprocess.run(
            ["npm", "install"],
            cwd=str(V2_DIR),
            shell=True,
            check=True,
        )

    print("⚛️  Starting Dashboard V2 on http://localhost:5173 ...")
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(V2_DIR),
        shell=True,
    )
    _CHILD_PROCS.append(proc)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()


# ── Thread-based combo launcher ─────────────────────────────────


def _thread(target, name):
    """Create a daemon thread."""
    t = threading.Thread(target=target, name=name, daemon=True)
    t.start()
    return t


_CHILD_PROCS: list[subprocess.Popen] = []


def run_combo(components: list[str]) -> None:
    """Run multiple components in parallel threads."""
    threads = []
    names = []

    # Start FastAPI backend first so Vite proxy has a target
    if "dash" in components:
        threads.append(_thread(run_dashboard_v1, "dash-v1"))
        names.append("📊 API Backend")
        time.sleep(3)  # Let FastAPI boot before Vite starts proxying

    for c in components:
        if c == "bot":
            threads.append(_thread(run_bot, "bot"))
            names.append("🤖 Bot")
        elif c == "v2":
            threads.append(_thread(run_dashboard_v2, "dash-v2"))
            names.append("⚛️  Dashboard V2")
        # "dash" already started above

    print(f"\n✅ Running: {' + '.join(names)}")
    print("   Press Ctrl+C to stop all.\n")

    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down ...")
        # Terminate any child subprocesses (e.g. npm dev server)
        for proc in _CHILD_PROCS:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        sys.exit(0)


# ── Mode Definitions ────────────────────────────────────────────

MODES = {
    "bot":       {"components": ["bot"],                  "desc": "Trading Bot only"},
    "dash":      {"components": ["dash"],                  "desc": "Dashboard V1 (port 8000)"},
    "v2":        {"components": ["dash", "v2"],            "desc": "Dashboard V2 (API + Vite)"},
    "dash+bot":  {"components": ["dash", "bot"],           "desc": "Dashboard V1 + Bot"},
    "v2+bot":    {"components": ["dash", "v2", "bot"],     "desc": "Dashboard V2 + Bot (full)"},
}


def show_menu() -> str:
    """Interactive mode selection."""
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║       🚀 Forex Bot — Launcher               ║")
    print("╠══════════════════════════════════════════════╣")
    print("║                                              ║")
    print("║  1) bot        — Trading Bot only            ║")
    print("║  2) dash       — Dashboard V1 (port 8000)    ║")
    print("║  3) v2         — Dashboard V2 (port 5173)    ║")
    print("║  4) dash+bot   — Dashboard V1 + Bot          ║")
    print("║  5) v2+bot     — Dashboard V2 + Bot          ║")
    print("║                                              ║")
    print("║  ℹ  Dashboard only reads the database.       ║")
    print("║     Bot does NOT need to run for dashboards. ║")
    print("║     But without bot, data won't update.      ║")
    print("║                                              ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    shortcuts = {"1": "bot", "2": "dash", "3": "v2", "4": "dash+bot", "5": "v2+bot"}

    choice = input("Select mode (1-5 or name): ").strip().lower()
    return shortcuts.get(choice, choice)


# ── Entry Point ──────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    else:
        mode = show_menu()

    if mode not in MODES:
        print(f"❌ Unknown mode: '{mode}'")
        print(f"   Available: {', '.join(MODES.keys())}")
        sys.exit(1)

    cfg = MODES[mode]
    components = cfg["components"]

    if len(components) == 1:
        # Single component — run directly (no threads)
        c = components[0]
        if c == "bot":
            run_bot()
        elif c == "dash":
            run_dashboard_v1()
        elif c == "v2":
            run_dashboard_v2()
    else:
        # Multiple components — run in threads
        run_combo(components)


if __name__ == "__main__":
    main()
