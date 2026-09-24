"""Static file classification and lightweight TODO/FIXME extraction."""

from __future__ import annotations

import os
import re
from itertools import islice
from pathlib import Path, PurePosixPath
from typing import Sequence

from context_cartographer.models import AnalysisResult, FileRecord, Todo


SOURCE_EXTENSIONS = frozenset(
    {
        ".py",
        ".pyi",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".java",
        ".go",
        ".rs",
        ".rb",
        ".c",
        ".h",
        ".cc",
        ".cpp",
        ".hpp",
        ".cs",
        ".swift",
        ".kt",
        ".sh",
        ".bash",
        ".ps1",
    }
)
DOCUMENTATION_EXTENSIONS = frozenset({".md", ".mdx", ".rst", ".txt", ".adoc"})
CONFIG_FILENAMES = frozenset(
    {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Cargo.toml",
        "go.mod",
        "Makefile",
        "Dockerfile",
        ".editorconfig",
        ".gitignore",
        ".gitattributes",
        "tox.ini",
        "noxfile.py",
    }
)
ENTRY_POINT_FILENAMES = frozenset(
    {
        "main.py",
        "app.py",
        "index.js",
        "index.ts",
        "server.js",
        "server.ts",
        "__main__.py",
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
    }
)
TODO_PATTERN = re.compile(r"\b(TODO|FIXME)\b")
TEXT_EXTENSIONS = SOURCE_EXTENSIONS | DOCUMENTATION_EXTENSIONS | frozenset(
    {".toml", ".yaml", ".yml", ".ini", ".cfg", ".json"}
)

MAX_TODO_LINES = 200_000

__all__ = [
    "CONFIG_FILENAMES",
    "DOCUMENTATION_EXTENSIONS",
    "ENTRY_POINT_FILENAMES",
    "MAX_TODO_LINES",
    "SOURCE_EXTENSIONS",
    "TEXT_EXTENSIONS",
    "TODO_PATTERN",
    "analyze_files",
    "extract_todos",
    "is_test_path",
]


_TEST_PATH_COMPONENTS = frozenset({"test", "tests", "spec", "specs"})


def _relative_name(root: Path, path: Path) -> str:
    """Return a path relative to ``root`` using POSIX separators when possible."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        pass

    try:
        return path.absolute().relative_to(root.absolute()).as_posix()
    except ValueError:
        pass

    try:
        relative = os.path.relpath(path.absolute(), root.absolute())
    except ValueError:
        return path.as_posix()
    return Path(relative).as_posix()


def is_test_path(relative_path: PurePosixPath) -> bool:
    """Return whether a path is conservatively identifiable as a test file.

    Directory and path components must be an exact test/spec name.  Source
    files may additionally use the conventional ``test_`` prefix or ``_test``
    suffix naming pattern.
    """
    path = PurePosixPath(relative_path)
    if any(part.casefold() in _TEST_PATH_COMPONENTS for part in path.parts):
        return True

    if path.suffix.casefold() not in SOURCE_EXTENSIONS:
        return False

    stem = path.stem.casefold()
    return stem.startswith("test_") or stem.endswith("_test")


def _read_todos(
    path: Path,
    relative_path: str,
    *,
    include_todos: bool,
    warnings: list[str],
) -> tuple[Todo, ...]:
    """Read markers while recording failures in ``warnings``."""
    if not include_todos or path.suffix.casefold() not in TEXT_EXTENSIONS:
        return ()

    todos: list[Todo] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as source:
            for line_number, line in enumerate(
                islice(source, MAX_TODO_LINES), start=1
            ):
                for match in TODO_PATTERN.finditer(line):
                    todos.append(
                        Todo(
                            path=relative_path,
                            line=line_number,
                            marker=match.group(1),
                        )
                    )
    except Exception as error:
        warnings.append(f"could not read {relative_path}: {error}")
        return ()

    return tuple(todos)


def extract_todos(
    path: Path, relative_path: str, *, include_todos: bool
) -> tuple[Todo, ...]:
    """Extract up to ``MAX_TODO_LINES`` TODO/FIXME markers from a text file.

    Read failures are intentionally represented by an empty tuple because the
    public interface has no warning collection parameter.  ``analyze_files``
    uses the internal implementation to preserve those failures in its result.
    """
    return _read_todos(
        path,
        str(relative_path),
        include_todos=include_todos,
        warnings=[],
    )


def _classify_file(
    path: Path,
    relative_path: str,
    *,
    include_todos: bool,
    warnings: list[str],
) -> FileRecord:
    """Classify one file and extract its optional TODO markers."""
    relative = PurePosixPath(relative_path)
    extension = path.suffix.casefold()
    basename = path.name

    return FileRecord(
        path=relative_path,
        extension=extension,
        is_source=extension in SOURCE_EXTENSIONS,
        is_test=is_test_path(relative),
        is_config=basename in CONFIG_FILENAMES,
        is_documentation=extension in DOCUMENTATION_EXTENSIONS,
        is_entry_point=basename in ENTRY_POINT_FILENAMES,
        todos=_read_todos(
            path,
            relative_path,
            include_todos=include_todos,
            warnings=warnings,
        ),
    )


def analyze_files(
    root: Path,
    files: Sequence[Path],
    *,
    include_todos: bool = True,
) -> AnalysisResult:
    """Classify supplied files and return records in relative-path order."""
    root = Path(root)
    ordered_paths = sorted(
        ((_relative_name(root, Path(path)), Path(path)) for path in files),
        key=lambda item: item[0],
    )

    warnings: list[str] = []
    records: list[FileRecord] = []
    for relative_path, path in ordered_paths:
        try:
            is_symlink = path.is_symlink()
        except OSError as error:
            warnings.append(f"could not inspect {relative_path}: {error}")
            continue

        if is_symlink:
            warnings.append(f"skipped symlink: {relative_path}")
            continue

        records.append(
            _classify_file(
                path,
                relative_path,
                include_todos=include_todos,
                warnings=warnings,
            )
        )
    return AnalysisResult(files=tuple(records), warnings=tuple(warnings))
