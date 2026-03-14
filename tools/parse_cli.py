"""
tools/parse_cli.py

Parser debug CLI — parse signal text from command line or file.
For manual testing during development.

Usage:
    python tools/parse_cli.py --text "GOLD BUY @ 2030 SL 2020 TP 2040"
    python tools/parse_cli.py --file samples.txt
    echo "EURUSD SELL 1.0800 SL 1.0850 TP 1.0750" | python tools/parse_cli.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.models import ParsedSignal, ParseFailure
from core.signal_parser.parser import SignalParser
from core.signal_validator import SignalValidator
from utils.symbol_mapper import SymbolMapper


def _format_result(result: ParsedSignal | ParseFailure, index: int = 0) -> str:
    """Format a parse result for display."""
    lines: list[str] = []

    if index > 0:
        lines.append(f"\n{'─' * 50}")

    if isinstance(result, ParseFailure):
        lines.append(f"  ❌ PARSE FAILED")
        lines.append(f"  Reason : {result.reason}")
        if result.raw_text:
            preview = result.raw_text[:80].replace("\n", "\\n")
            lines.append(f"  Input  : {preview}")
        return "\n".join(lines)

    lines.append(f"  ✅ PARSE SUCCESS")
    lines.append(f"  Symbol      : {result.symbol}")
    lines.append(f"  Side        : {result.side.value}")
    lines.append(
        f"  Entry       : {result.entry if result.entry else 'MARKET'}"
    )
    lines.append(
        f"  SL          : {result.sl if result.sl else 'not set'}"
    )
    if result.tp:
        for i, tp in enumerate(result.tp):
            lines.append(f"  TP{i + 1}         : {tp}")
    else:
        lines.append(f"  TP          : not set")
    lines.append(f"  Fingerprint : {result.fingerprint}")

    return "\n".join(lines)


def _parse_and_print(
    parser: SignalParser,
    validator: SignalValidator,
    text: str,
    index: int = 0,
    validate: bool = True,
) -> None:
    """Parse a signal text and print formatted result."""
    result = parser.parse(text)
    print(_format_result(result, index))

    # Optionally validate
    if validate and isinstance(result, ParsedSignal):
        vr = validator.validate(result)
        if vr.valid:
            print(f"  Validation  : ✅ PASSED")
        else:
            print(f"  Validation  : ❌ REJECTED — {vr.reason}")


def main() -> None:
    arg_parser = argparse.ArgumentParser(
        description="Parse trading signal text for testing.",
    )
    arg_parser.add_argument(
        "--text", "-t",
        help="Signal text to parse (enclose in quotes).",
    )
    arg_parser.add_argument(
        "--file", "-f",
        help="File containing signal messages (one per block, "
             "separated by blank lines).",
    )
    arg_parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip validation step.",
    )

    args = arg_parser.parse_args()

    mapper = SymbolMapper()
    parser = SignalParser(symbol_mapper=mapper)
    validator = SignalValidator()

    validate = not args.no_validate

    if args.text:
        print(f"\n{'=' * 50}")
        print(f"  SIGNAL PARSER DEBUG")
        print(f"{'=' * 50}")
        _parse_and_print(parser, validator, args.text, validate=validate)
        print()
        return

    if args.file:
        filepath = Path(args.file)
        if not filepath.exists():
            print(f"ERROR: file not found: {args.file}")
            sys.exit(1)

        content = filepath.read_text(encoding="utf-8")
        # Split by double newline into blocks
        blocks = [b.strip() for b in content.split("\n\n") if b.strip()]

        print(f"\n{'=' * 50}")
        print(f"  SIGNAL PARSER DEBUG — {len(blocks)} signals")
        print(f"{'=' * 50}")

        for i, block in enumerate(blocks):
            _parse_and_print(parser, validator, block, i, validate=validate)

        print(f"\n{'=' * 50}")
        print(f"  Processed {len(blocks)} signal(s)")
        print(f"{'=' * 50}\n")
        return

    # Read from stdin
    if not sys.stdin.isatty():
        text = sys.stdin.read().strip()
        if text:
            print(f"\n{'=' * 50}")
            print(f"  SIGNAL PARSER DEBUG")
            print(f"{'=' * 50}")
            _parse_and_print(parser, validator, text, validate=validate)
            print()
            return

    arg_parser.print_help()


if __name__ == "__main__":
    main()
