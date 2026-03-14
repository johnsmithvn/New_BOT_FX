"""
tools/benchmark.py

Parser benchmark script — measure throughput and latency.

Usage:
    python tools/benchmark.py
    python tools/benchmark.py --iterations 500
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.signal_parser.parser import SignalParser
from utils.symbol_mapper import SymbolMapper


_SAMPLE_SIGNALS = [
    "GOLD BUY @ 2030 SL 2020 TP 2040 TP2 2050 TP3 2060",
    "XAUUSD SELL 2045 SL 2055 TP1 2035 TP2 2025",
    "EURUSD BUY 1.0850\nSL 1.0800\nTP1 1.0900\nTP2 1.0950",
    "GBPUSD SELL LIMIT 1.2700\nSL 1.2750\nTP 1.2650",
    "GOLD BUY NOW SL 2020 TP 2040",
    "XAUUSD BUY MARKET\nSL: 2015\nTP: 2045",
    "🚀🚀🚀 GOLD BUY 2030 🎯 SL 2020 💰 TP 2040 TP2 2050 🔥🔥",
    "hello world this is not a signal",
    "BITCOIN BUY 65000\nSL 64000\nTP 66000",
    "XAU/USD BUY 2030\nSL 2020\nTP 2040",
]


def run_benchmark(iterations: int = 100) -> None:
    mapper = SymbolMapper()
    parser = SignalParser(symbol_mapper=mapper)

    total_signals = iterations * len(_SAMPLE_SIGNALS)

    print(f"\n{'=' * 50}")
    print(f"  PARSER BENCHMARK")
    print(f"  Iterations : {iterations}")
    print(f"  Signals    : {total_signals}")
    print(f"{'=' * 50}\n")

    # Warm-up
    for sig in _SAMPLE_SIGNALS:
        parser.parse(sig)

    # Timed run
    start = time.perf_counter()
    for _ in range(iterations):
        for sig in _SAMPLE_SIGNALS:
            parser.parse(sig)
    elapsed = time.perf_counter() - start

    throughput = total_signals / elapsed
    avg_latency_us = (elapsed / total_signals) * 1_000_000

    print(f"  Total time      : {elapsed:.3f}s")
    print(f"  Throughput      : {throughput:,.0f} signals/sec")
    print(f"  Avg latency     : {avg_latency_us:.1f} µs/signal")
    print(f"\n{'=' * 50}\n")


def main() -> None:
    arg_parser = argparse.ArgumentParser(
        description="Benchmark the signal parser pipeline.",
    )
    arg_parser.add_argument(
        "--iterations", "-n",
        type=int,
        default=100,
        help="Number of benchmark iterations (default: 100).",
    )
    args = arg_parser.parse_args()
    run_benchmark(args.iterations)


if __name__ == "__main__":
    main()
