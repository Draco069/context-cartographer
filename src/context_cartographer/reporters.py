"""Render project reports as Markdown or JSON."""

from __future__ import annotations

import json

from context_cartographer.models import ProjectReport


__all__ = ["render_json", "render_markdown", "render_report"]


_EMPTY_SECTION = "*None found.*"


def _escape_table_cell(value: object) -> str:
    """Escape a value for use in a Markdown table cell."""
    return str(value).replace("|", "\\|")


def _append_path_section(
    lines: list[str], heading: str, paths: tuple[str, ...]
) -> None:
    """Append a section containing a list of paths."""
    lines.extend((heading, ""))
    if paths:
        lines.extend(f"- {path}" for path in paths)
    else:
        lines.append(_EMPTY_SECTION)
    lines.append("")


def render_markdown(report: ProjectReport) -> str:
    """Render a complete, deterministic Markdown project report."""
    lines: list[str] = [f"# Project map: {report.root}", "", "## Summary", ""]
    lines.extend((f"- Files: {len(report.files)}", f"- Warnings: {len(report.warnings)}"))
    lines.append("")

    lines.extend(("## Project tree", ""))
    if report.tree:
        lines.extend(("```text", *report.tree, "```"))
    else:
        lines.append(_EMPTY_SECTION)
    lines.append("")

    lines.extend(("## Files by extension", ""))
    if report.extension_counts:
        lines.extend((
            "| Extension | Files |",
            "| --- | ---: |",
        ))
        lines.extend(
            f"| {_escape_table_cell(extension)} | {_escape_table_cell(count)} |"
            for extension, count in report.extension_counts.items()
        )
    else:
        lines.append(_EMPTY_SECTION)
    lines.append("")

    _append_path_section(lines, "## Likely entry points", report.entry_points)
    _append_path_section(lines, "## Tests", report.test_files)
    _append_path_section(lines, "## Configuration", report.config_files)
    _append_path_section(lines, "## Documentation", report.documentation_files)

    lines.extend(("## TODO/FIXME", ""))
    todos = [todo for record in report.files for todo in record.todos]
    if todos:
        lines.extend(
            f"- {todo.path}:{todo.line} ({todo.marker})" for todo in todos
        )
    else:
        lines.append(_EMPTY_SECTION)
    lines.append("")

    lines.extend(("## Warnings", ""))
    if report.warnings:
        lines.extend(f"- {warning}" for warning in report.warnings)
    else:
        lines.append(_EMPTY_SECTION)

    return "\n".join(lines).rstrip("\n") + "\n"


def render_json(report: ProjectReport) -> str:
    """Render a key-sorted, indented JSON project report."""
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_report(report: ProjectReport, output_format: str) -> str:
    """Render ``report`` using the requested output format."""
    if output_format == "markdown":
        return render_markdown(report)
    elif output_format == "json":
        return render_json(report)
    raise ValueError(f"unsupported report format: {output_format}")
