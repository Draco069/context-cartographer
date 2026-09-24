"""Safe recursive project scanning and tree construction."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Sequence


__all__ = [
    "DEFAULT_EXCLUDED_DIRECTORIES",
    "ScanResult",
    "build_tree",
    "scan_project",
]


DEFAULT_EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "dist",
        "build",
    }
)


@dataclass(frozen=True)
class ScanResult:
    """Files and warnings discovered while scanning a project root."""

    root: Path
    files: tuple[Path, ...]
    tree: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass
class _TreeNode:
    """A node in the directory tree used to render discovered files."""

    children: dict[str, "_TreeNode"] = field(default_factory=dict)
    is_file: bool = False


def _matches(relative_path: str, name: str, patterns: Sequence[str]) -> bool:
    """Return whether a path or entry name matches a user exclusion pattern."""
    return any(
        fnmatch.fnmatch(relative_path, pattern) or fnmatch.fnmatch(name, pattern)
        for pattern in patterns
    )


def _relative_to(root: Path, path: Path) -> Path:
    """Return ``path`` relative to ``root`` across absolute/relative inputs."""
    try:
        return path.relative_to(root)
    except ValueError:
        return path.absolute().relative_to(root.absolute())


def _relative_name(root: Path, path: Path) -> str:
    """Return a stable POSIX-style path suitable for matching and warnings."""
    return _relative_to(root, path).as_posix()


def _scan_directory(
    directory: Path,
    root: Path,
    files: list[Path],
    warnings: list[str],
    exclude_patterns: Sequence[str],
    max_depth: int | None,
    current_depth: int,
) -> None:
    """Collect files below ``directory`` using deterministic depth-first order."""
    try:
        entries = sorted(
            directory.iterdir(),
            key=lambda entry: (entry.name.casefold(), entry.name),
        )
    except OSError as error:
        if current_depth == 0:
            raise
        warnings.append(
            f"could not read directory {_relative_name(root, directory)}: {error}"
        )
        return

    for entry in entries:
        relative_name = _relative_name(root, entry)

        try:
            if entry.is_symlink():
                warnings.append(f"skipped symlink: {relative_name}")
                continue
        except OSError as error:
            warnings.append(f"could not inspect {relative_name}: {error}")
            continue

        try:
            is_directory = entry.is_dir()
            is_file = entry.is_file()
        except OSError as error:
            warnings.append(f"could not inspect {relative_name}: {error}")
            continue

        if is_directory:
            if entry.name in DEFAULT_EXCLUDED_DIRECTORIES or _matches(
                relative_name, entry.name, exclude_patterns
            ):
                continue
            if max_depth is None or current_depth < max_depth:
                _scan_directory(
                    entry,
                    root,
                    files,
                    warnings,
                    exclude_patterns,
                    max_depth,
                    current_depth + 1,
                )
        elif is_file:
            if not _matches(relative_name, entry.name, exclude_patterns):
                files.append(entry)


def scan_project(
    root: Path,
    *,
    exclude_patterns: Sequence[str] = (),
    max_depth: int | None = None,
) -> ScanResult:
    """Scan ``root`` recursively without following symbolic links."""
    if root.is_symlink():
        raise NotADirectoryError(f"scan root is a symbolic link: {root}")
    if not root.exists():
        raise FileNotFoundError(f"scan root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"scan root is not a directory: {root}")

    files: list[Path] = []
    warnings: list[str] = []
    _scan_directory(
        root,
        root,
        files,
        warnings,
        exclude_patterns,
        max_depth,
        0,
    )

    return ScanResult(
        root=root,
        files=tuple(files),
        tree=build_tree(root, files),
        warnings=tuple(warnings),
    )


def build_tree(root: Path, files: Sequence[Path]) -> tuple[str, ...]:
    """Build a deterministic human-readable tree containing only discovered files."""
    relative_paths: list[str] = []
    for path in files:
        relative_name = _relative_to(root, path).as_posix()
        if relative_name != ".":
            relative_paths.append(relative_name)
    relative_paths.sort()

    tree_root = _TreeNode()
    for relative_path in relative_paths:
        parts = PurePosixPath(relative_path).parts
        node = tree_root
        for index, part in enumerate(parts):
            node = node.children.setdefault(part, _TreeNode())
            if index == len(parts) - 1:
                node.is_file = True

    lines = [root.name or str(root)]

    def render(node: _TreeNode, depth: int) -> None:
        children = list(node.children.items())
        for index, (name, child) in enumerate(children):
            connector = "└── " if index == len(children) - 1 else "├── "
            lines.append(f"{'  ' * depth}{connector}{name}")
            render(child, depth + 1)

    render(tree_root, 0)
    return tuple(lines)
