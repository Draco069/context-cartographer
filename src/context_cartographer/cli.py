"""Command-line orchestration for Context Cartographer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from context_cartographer import __version__
from context_cartographer.analyzers import analyze_files
from context_cartographer.errors import CartographerError, InputError, OutputError, UsageError
from context_cartographer.models import ProjectReport
from context_cartographer.reporters import render_report
from context_cartographer.scanner import scan_project


__all__ = ["build_parser", "main"]


class _CartographerArgumentParser(argparse.ArgumentParser):
    """Argument parser that maps argparse errors to the CLI error contract."""

    def error(self, message: str) -> None:
        raise UsageError(message)


def _non_negative_int(value: str) -> int:
    """Parse an integer option that cannot be negative."""
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser used by :func:`main`."""
    parser = _CartographerArgumentParser(
        prog="cartographer",
        description="Generate a concise map of a project directory.",
    )
    parser.add_argument(
        "path",
        metavar="PATH",
        nargs="?",
        default=Path("."),
        type=Path,
        help="project directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="report format (default: markdown)",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="write the report to PATH instead of standard output",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="exclude paths matching GLOB (repeatable)",
    )
    parser.add_argument(
        "--max-depth",
        type=_non_negative_int,
        metavar="N",
        help="limit traversal depth (zero scans direct files only)",
    )
    parser.add_argument(
        "--no-todos",
        action="store_true",
        help="omit TODO/FIXME locations from the report",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
        help="show the package version and exit",
    )
    return parser


def _write_stdout(text: str) -> None:
    """Write text, falling back to ASCII escapes for narrow consoles."""
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        ascii_text = text.encode("ascii", errors="backslashreplace").decode("ascii")
        sys.stdout.write(ascii_text)


def _write_stderr(text: str) -> None:
    """Write stderr text with the same narrow-console fallback as stdout."""
    try:
        sys.stderr.write(text)
    except UnicodeEncodeError:
        ascii_text = text.encode("ascii", errors="backslashreplace").decode("ascii")
        sys.stderr.write(ascii_text)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the scanner, analyzer, renderer, and output pipeline."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        try:
            root = Path(args.path).expanduser()
        except (OSError, RuntimeError, ValueError) as error:
            raise InputError(
                f"could not expand target path {args.path}: {error}"
            ) from error

        try:
            scan = scan_project(
                root,
                exclude_patterns=args.exclude,
                max_depth=args.max_depth,
            )
        except (FileNotFoundError, NotADirectoryError) as error:
            raise InputError(str(error)) from error

        analysis = analyze_files(
            root,
            scan.files,
            include_todos=not args.no_todos,
        )
        report = ProjectReport(
            root=scan.tree[0],
            files=analysis.files,
            tree=scan.tree,
            warnings=scan.warnings + analysis.warnings,
        )
        rendered = render_report(report, args.format)

        if args.output:
            output_argument = args.output
            try:
                output = Path(output_argument).expanduser()
                output.write_text(rendered, encoding="utf-8")
            except (OSError, RuntimeError, ValueError) as error:
                raise OutputError(
                    f"could not write output file {output_argument}: {error}"
                ) from error
        else:
            _write_stdout(rendered)
            sys.stdout.flush()

        for warning in report.warnings:
            _write_stderr(f"cartographer: warning: {warning}\n")
        return 0
    except CartographerError as error:
        _write_stderr(f"cartographer: error: {error}\n")
        return error.exit_code
    except (OSError, ValueError) as error:
        _write_stderr(f"cartographer: error: {error}\n")
        return 2
