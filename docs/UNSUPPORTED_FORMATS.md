# Unsupported Signal Formats

## Purpose
Track signal formats encountered during testing that the parser does not handle.
Update this list when a new unsupported format is discovered.

## Known Unsupported Formats

### Not Yet Supported
- [x] Signals with multiple entry zones (e.g. `ENTRY 1: 2030, ENTRY 2: 2025`) — ✅ handled via P9 `EntryStrategy` range/scale_in mode (v0.9.0)
- [x] Signals with partial close instructions — ✅ handled via `PARTIAL_CLOSE_PERCENT` config + `CLOSE HALF` command
- [x] Signals with trailing stop instructions — ✅ handled via `TRAILING_STOP_PIPS` config in position manager
- [ ] Signals with risk/reward ratio only (no explicit SL/TP prices)
- [ ] Image-only signals (no text)
- [ ] Signals in non-English languages
- [ ] Signals using point/pip notation instead of price (e.g. `SL 100 pips`)
- [ ] Signals referencing previous signals (e.g. `Update previous GOLD signal`)
- [ ] Signals with conditional entries (e.g. `Buy if price breaks above 2050`)

### Edge Cases Observed
<!-- Add entries here during manual testing -->

## Adding New Entries

When a new unsupported format is discovered:
1. Add the raw message example below.
2. Add a checkbox item to the list above.
3. Evaluate priority for future support.
