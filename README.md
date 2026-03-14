# telegram-mt5-bot

Low-latency Python bot that reads Telegram trading signals and executes MT5 orders safely.

## Requirements

- Python 3.11+
- MetaTrader 5 terminal (for execution phases)
- Telegram API credentials (for listener phases)

## Setup

```bash
# Clone repository
git clone <repo-url>
cd Forex

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your credentials and settings
```

## Configuration

All configuration is via environment variables in `.env`. See `.env.example` for all available keys:

| Category | Key | Description |
|----------|-----|-------------|
| Telegram | `TELEGRAM_API_ID` | Telegram API ID |
| Telegram | `TELEGRAM_API_HASH` | Telegram API hash |
| Telegram | `TELEGRAM_SOURCE_CHATS` | Comma-separated chat IDs |
| MT5 | `MT5_PATH` | Path to terminal64.exe |
| Risk | `RISK_MODE` | `FIXED_LOT` or `RISK_PERCENT` |
| Safety | `MAX_SPREAD_POINTS` | Max allowed spread |
| Safety | `SIGNAL_AGE_TTL_SECONDS` | Reject signals older than this |
| Safety | `PENDING_ORDER_TTL_MINUTES` | Auto-cancel pending orders after this |

## Running

```bash
# Activate virtual environment first
venv\Scripts\activate

# Run the bot
python main.py
```

## Testing the Parser

Use the debug CLI to test signal parsing without running the full bot:

```bash
# Parse a single signal
python tools/parse_cli.py --text "GOLD BUY @ 2030 SL 2020 TP 2040 TP2 2050"

# Parse from a file (signals separated by blank lines)
python tools/parse_cli.py --file docs/SIGNAL_DATASET.md

# Pipe from stdin
echo "EURUSD SELL 1.0800 SL 1.0850 TP 1.0750" | python tools/parse_cli.py
```

## Project Structure

```
Forex/
├── config/
│   └── settings.py          # Typed config loading from .env
├── core/
│   ├── models.py             # Data contracts (ParsedSignal, etc.)
│   ├── signal_parser/
│   │   ├── cleaner.py        # Message normalization
│   │   ├── symbol_detector.py
│   │   ├── side_detector.py
│   │   ├── entry_detector.py
│   │   ├── sl_detector.py
│   │   ├── tp_detector.py
│   │   └── parser.py         # Orchestrator
│   ├── signal_validator.py   # Safety validation
│   ├── risk_manager.py       # Position sizing
│   └── storage.py            # SQLite persistence
├── utils/
│   ├── logger.py             # Structured JSON logging
│   └── symbol_mapper.py      # Symbol alias resolution
├── tools/
│   └── parse_cli.py          # Parser debug CLI
├── docs/                     # Project documentation
├── data/                     # SQLite databases (auto-created)
├── logs/                     # Log files (auto-created)
├── main.py                   # Entry point
├── requirements.txt
├── .env.example
└── CHANGELOG.md
```

## Documentation

- [PROJECT.md](docs/PROJECT.md) — Project overview and goals
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — System architecture and data contracts
- [ROADMAP.md](docs/ROADMAP.md) — Development milestones
- [PLAN.md](docs/PLAN.md) — Current development phase
- [TASKS.md](docs/TASKS.md) — Task tracking
- [RULES.md](docs/RULES.md) — Agent and development rules
- [OBSERVABILITY.md](docs/OBSERVABILITY.md) — Logging and tracing
- [SIGNAL_DATASET.md](docs/SIGNAL_DATASET.md) — Signal message samples

## Version

Current: **v0.1.0** — P1 Signal Understanding
