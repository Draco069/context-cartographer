"""Immutable data models used by the project report pipeline."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


__all__ = ["AnalysisResult", "FileRecord", "ProjectReport", "Todo"]


@dataclass(frozen=True)
class Todo:
    """A TODO or FIXME marker found in a project file."""

    path: str
    line: int
    marker: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation of the marker."""
        return {
            "path": self.path,
            "line": self.line,
            "marker": self.marker,
        }


@dataclass(frozen=True)
class FileRecord:
    """Metadata and classification results for one project file."""

    path: str
    extension: str
    is_source: bool
    is_test: bool
    is_config: bool
    is_documentation: bool
    is_entry_point: bool
    todos: tuple[Todo, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation of the file record."""
        return {
            "path": self.path,
            "extension": self.extension,
            "is_source": self.is_source,
            "is_test": self.is_test,
            "is_config": self.is_config,
            "is_documentation": self.is_documentation,
            "is_entry_point": self.is_entry_point,
            "todos": [todo.to_dict() for todo in self.todos],
        }


@dataclass(frozen=True)
class AnalysisResult:
    """The files and warnings produced by static analysis."""

    files: tuple[FileRecord, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation of the analysis result."""
        return {
            "files": [record.to_dict() for record in self.files],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ProjectReport:
    """The complete report model consumed by output renderers."""

    root: str
    files: tuple[FileRecord, ...]
    tree: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def extension_counts(self) -> dict[str, int]:
        """Count files by extension, using ``(none)`` for empty suffixes."""
        counts = Counter(record.extension or "(none)" for record in self.files)
        return dict(sorted(counts.items()))

    @property
    def entry_points(self) -> tuple[str, ...]:
        """Return paths classified as likely entry points in stored order."""
        return tuple(record.path for record in self.files if record.is_entry_point)

    @property
    def test_files(self) -> tuple[str, ...]:
        """Return paths classified as tests in stored order."""
        return tuple(record.path for record in self.files if record.is_test)

    @property
    def config_files(self) -> tuple[str, ...]:
        """Return paths classified as configuration files in stored order."""
        return tuple(record.path for record in self.files if record.is_config)

    @property
    def documentation_files(self) -> tuple[str, ...]:
        """Return paths classified as documentation in stored order."""
        return tuple(record.path for record in self.files if record.is_documentation)

    def to_dict(self) -> dict[str, object]:
        """Return the complete report as JSON-compatible data."""
        return {
            "root": self.root,
            "summary": {
                "file_count": len(self.files),
                "warning_count": len(self.warnings),
            },
            "tree": list(self.tree),
            "extension_counts": dict(sorted(self.extension_counts.items())),
            "entry_points": list(self.entry_points),
            "test_files": list(self.test_files),
            "config_files": list(self.config_files),
            "documentation_files": list(self.documentation_files),
            "todos": [todo.to_dict() for record in self.files for todo in record.todos],
            "files": [record.to_dict() for record in self.files],
            "warnings": list(self.warnings),
        }
