# Signal Debug Messages

This system includes a powerful signal debugging feature that streams real-time decision logs directly to an admin Telegram chat whenever a signal is processed.

**This allows the operator to see:**
1. The exact raw signal received
2. The parsed fields (symbol, side, entry, sl, tp)
3. The live market conditions at the exact moment of processing (bid, ask, spread)
4. The bot's final decision: either the exact rejection reason OR the calculated order parameters.

## Configuration

To enable debug messages, configure the following in your `.env` file:

```env
TELEGRAM_ADMIN_CHAT=@yourusername  # OR numeric chat ID like 123456789
DEBUG_SIGNAL_DECISION=true
```

## How It Works

The debug system sits inside the signal processing pipeline (`main.py`). It fires at validation, drift guard, and order decision stages. Since v0.9.0, order execution is delegated to `SignalPipeline` — debug messages are emitted for the first order in multi-order scenarios.

Unlike standard alerts (which have a cooldown rate limit to prevent spam, e.g., circuit breaker open), **debug messages bypass rate limiting completely**. Every single processed signal will generate exactly one debug message to the admin chat.

There are three scenarios where a debug message is sent:

### Scenario 1: Validation Failed

If a signal violates safety rules (e.g., spread too high, entry distance too far, coherence failure), you will receive:

```text
📡 SIGNAL DEBUG — REJECTED

Raw:
XAUUSD BUY MARKET
SL: 2025
TP: 2035 2040

Parsed:
  symbol: XAUUSD
  side: BUY
  entry: None
  sl: 2025.0
  tp: [2035.0, 2040.0]

Market:
  bid: 2029.8  |  ask: 2030.2
  spread: 4.0 pts

❌ Rejected: spread (4.0 pips) exceeds max (5.0 pips)
```

### Scenario 2: Entry Drift Failed

If the signal had an exact entry price but the bot decides to place a `MARKET` order due to market tolerance, it checks the entry drift. If it has drifted beyond `MAX_ENTRY_DRIFT_PIPS`:

```text
📡 SIGNAL DEBUG — REJECTED

Raw:
...

Parsed:
...

Market:
...

❌ Rejected: entry drift: entry drift (15.0 pips) exceeds max (10.0 pips) for MARKET order
```

### Scenario 3: Order Decision Success

If the signal passes all checks and the bot successfully determines the order mapping (Market, Limit, Stop), it sends the final decision right before execution:

```text
📡 SIGNAL DEBUG — ORDER

Raw:
...

Parsed:
...

Market:
  bid: 2029.8  |  ask: 2030.2
  spread: 4.0 pts

✅ Decision:
  order_type: BUY_MARKET
  volume: 0.01
  price: 2030.2
  sl: 2025.0  |  tp: 2035.0
  deviation: 20
  dry_run: false
```

## Best Practices

- **Production Usage:** Leave `DEBUG_SIGNAL_DECISION=true` enabled during beta phases to ensure your parser is interpreting signals exactly as expected. Turn it `false` once stable to avoid Telegram spam for high-volume channels.
- **Troubleshooting:** If the bot isn't executing trades and you aren't sure why, turn this on. It will immediately show you the real-time spread and validation math that caused a rejection.

