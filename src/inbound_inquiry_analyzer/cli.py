"""CLI entry point for the inbound inquiry analyzer.

Wires together: parser -> normalizer -> orchestrator -> xlsx_writer

Usage:
    python -m inbound_inquiry_analyzer [file1.json ...] [-o output.xlsx] [-c config.yaml]
    python -m inbound_inquiry_analyzer --keyword-only [file1.json ...]
    cat data.json | python -m inbound_inquiry_analyzer
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from inbound_inquiry_analyzer.api_client import get_client
from inbound_inquiry_analyzer.config import load_config
from inbound_inquiry_analyzer.normalizer import normalize
from inbound_inquiry_analyzer.orchestrator import (
    METHOD_KEYWORD,
    classify_all,
)
from inbound_inquiry_analyzer.parser import parse_input
from inbound_inquiry_analyzer.xlsx_writer import generate_workbook


def _load_dotenv() -> None:
    """Load .env file if python-dotenv is available."""
    try:
        from dotenv import load_dotenv  # type: ignore[import-untyped]
        load_dotenv()
    except ImportError:
        pass  # python-dotenv not installed; environment variables must be set manually


def main(argv: list[str] | None = None) -> int:
    """Main entry point. Returns exit code (0=success, 1=error)."""
    _load_dotenv()

    parser = argparse.ArgumentParser(
        prog="inbound-inquiry-analyzer",
        description="Classify inbound inquiries and generate a formatted XLSX workbook.",
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        metavar="FILE",
        help="Input file(s) (JSON or CSV). Reads from stdin if not provided.",
    )
    parser.add_argument(
        "-o", "--output",
        default="inquiries_categorized.xlsx",
        metavar="OUTPUT",
        help="Output XLSX file path (default: inquiries_categorized.xlsx).",
    )
    parser.add_argument(
        "-c", "--config",
        default=None,
        metavar="CONFIG",
        help="Path to categories YAML config (default: config/categories.yaml).",
    )
    parser.add_argument(
        "--keyword-only",
        action="store_true",
        default=False,
        help=(
            "Force keyword-based classification regardless of whether an "
            "ANTHROPIC_API_KEY is set. Useful for offline use or reproducible runs."
        ),
    )

    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ValueError as exc:
        print(f"Error loading config: {exc}", file=sys.stderr)
        return 1

    # Resolve API client (None when key absent or --keyword-only)
    if args.keyword_only:
        client = None
    else:
        try:
            client = get_client(require=False)
        except Exception as exc:  # pragma: no cover
            print(f"Warning: could not initialize Anthropic client: {exc}", file=sys.stderr)
            client = None

    # Collect raw records from all inputs
    all_raw: list[dict] = []

    if args.inputs:
        for file_path in args.inputs:
            try:
                raw = parse_input(file_path)
                all_raw.extend(raw)
            except (ValueError, OSError) as exc:
                print(f"Error reading {file_path}: {exc}", file=sys.stderr)
                return 1
    elif not sys.stdin.isatty():
        # Read from stdin
        try:
            stdin_data = sys.stdin.read()
            raw = parse_input(stdin_data)
            all_raw.extend(raw)
        except ValueError as exc:
            print(f"Error parsing stdin: {exc}", file=sys.stderr)
            return 1
    else:
        print(
            "No input provided. Pass file paths as arguments or pipe JSON via stdin.",
            file=sys.stderr,
        )
        parser.print_usage(sys.stderr)
        return 1

    if not all_raw:
        print("Warning: no records found in input.", file=sys.stderr)

    # Normalize
    try:
        records = [normalize(r) for r in all_raw]
    except ValueError as exc:
        print(f"Error normalizing records: {exc}", file=sys.stderr)
        return 1

    # Classify (Claude with keyword fallback, or keyword-only)
    category_names = config.category_names
    predicted, method = classify_all(
        records,
        category_names,
        client=client,
        keyword_only=args.keyword_only,
    )

    # Register any new categories that Claude returned
    for cat in predicted:
        if cat not in config.color_map:
            config.add_category(cat)

    # Generate XLSX
    try:
        output_path = generate_workbook(records, predicted, config, args.output)
    except OSError as exc:
        print(f"Error writing output file: {exc}", file=sys.stderr)
        return 1

    method_label = {
        "claude": "Claude API",
        "keyword": "keyword classifier",
        "mixed": "mixed (Claude + keyword fallback)",
    }.get(method, method)

    print(
        f"Processed {len(records)} inquiries -> {output_path} "
        f"[classification: {method_label}]",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
