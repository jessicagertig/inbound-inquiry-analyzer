"""CLI entry point for the inbound inquiry analyzer.

Wires together: parser -> normalizer -> classifier/claude_classifier -> xlsx_writer

Usage:
    python -m inbound_inquiry_analyzer [file1.json ...] [-o output.xlsx] [-c config.yaml]
    cat data.json | python -m inbound_inquiry_analyzer
    python -m inbound_inquiry_analyzer --keyword-only [file1.json ...]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from inbound_inquiry_analyzer.classifier import classify
from inbound_inquiry_analyzer.claude_classifier import classify_with_claude
from inbound_inquiry_analyzer.config import load_config
from inbound_inquiry_analyzer.normalizer import normalize
from inbound_inquiry_analyzer.parser import parse_input
from inbound_inquiry_analyzer.xlsx_writer import generate_workbook


def _load_dotenv() -> None:
    """Load .env file if present. Silently skips if python-dotenv is unavailable."""
    try:
        from dotenv import load_dotenv  # noqa: PLC0415 — deferred on purpose
        load_dotenv()
    except ImportError:
        pass


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
            "Use keyword-based classification only (no Claude API calls). "
            "Useful when ANTHROPIC_API_KEY is not set or for offline use."
        ),
    )

    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ValueError as exc:
        print(f"Error loading config: {exc}", file=sys.stderr)
        return 1

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

    # Classify — Claude mode by default, keyword-only if requested or no API key
    category_names = config.category_names
    use_keyword_only = args.keyword_only

    if not use_keyword_only and not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "Warning: ANTHROPIC_API_KEY is not set. "
            "Falling back to keyword classification. "
            "Pass --keyword-only to suppress this warning.",
            file=sys.stderr,
        )
        use_keyword_only = True

    if use_keyword_only:
        predicted = [classify(r, category_names) for r in records]
        method_counts = {"keyword": len(predicted)}
    else:
        results = classify_with_claude(records, config)
        predicted = [cat for cat, _ in results]
        method_counts: dict[str, int] = {}
        for _, method in results:
            method_counts[method] = method_counts.get(method, 0) + 1

    # Log method summary to stderr
    if method_counts:
        summary_parts = [f"{count} via {method}" for method, count in sorted(method_counts.items())]
        print(f"Classification: {', '.join(summary_parts)}", file=sys.stderr)

    # Generate XLSX
    try:
        output_path = generate_workbook(records, predicted, config, args.output)
    except OSError as exc:
        print(f"Error writing output file: {exc}", file=sys.stderr)
        return 1

    print(
        f"Processed {len(records)} inquiries -> {output_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
