"""Safe recursive project scanning and tree construction."""

from __future__ import annotations

import fnmatch
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterator, Sequence


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
_DEFAULT_EXCLUDED_DIRECTORIES_CASEFOLD = frozenset(
    name.casefold() for name in DEFAULT_EXCLUDED_DIRECTORIES
)
_WINDOWS_REPARSE_POINT_ATTRIBUTE = getattr(
    stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400
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


def _link_kind(path: Path) -> str | None:
    """Return the link kind detected without following ``path``.

    ``Path.is_symlink`` does not identify Windows junctions and other reparse
    points on all supported Python versions.  ``os.lstat`` exposes the link
    mode on POSIX and the reparse attributes on Windows.  The final
    ``is_symlink`` check is a portable fallback for platforms that do not
    expose either piece of link metadata.
    """
    try:
        metadata = os.lstat(path)
    except (AttributeError, NotImplementedError):
        try:
            return "symlink" if path.is_symlink() else None
        except OSError:
            return None

    if stat.S_ISLNK(metadata.st_mode):
        return "symlink"

    attributes = getattr(metadata, "st_file_attributes", None)
    if attributes is not None and attributes & _WINDOWS_REPARSE_POINT_ATTRIBUTE:
        return "reparse point"

    reparse_tag = getattr(metadata, "st_reparse_tag", None)
    if reparse_tag:
        return "reparse point"

    try:
        return "symlink" if path.is_symlink() else None
    except OSError:
        return None


def _absolute_components(path: Path) -> Iterator[Path]:
    """Yield lexical path components without resolving filesystem links."""
    if path.is_absolute():
        base = Path(path.anchor)
        user_components = path.parts[1:]
    elif path.drive:
        # ``os.path.abspath`` on the full path would normalize ``..`` before
        # the link checks.  Resolve only the drive-specific lexical base.
        base = Path(os.path.abspath(f"{path.drive}."))
        user_components = path.parts[1:]
    elif path.root:
        base = Path(os.path.abspath(path.anchor))
        user_components = path.parts[1:]
    else:
        base = Path.cwd()
        user_components = path.parts

    current = Path(base.anchor)
    yield current

    # Walk the base's ancestors and the user's components in their original
    # order.  In particular, inspect a component before applying a following
    # ``..`` so a link/reparse point cannot be hidden by normalization.
    for component in (*base.parts[1:], *user_components):
        if component in ("", "."):
            continue
        if component == "..":
            current = current.parent
            continue
        current /= component
        yield current


def _find_link_component(path: Path) -> tuple[Path, str] | None:
    """Find a symlink or reparse point in ``path``'s lexical ancestry."""
    for component in _absolute_components(path):
        try:
            link_kind = _link_kind(component)
        except FileNotFoundError:
            # Let the normal root validation below produce the public error.
            return None
        if link_kind is not None:
            return component, link_kind
    return None


def _is_contained(path: Path, root: Path) -> bool:
    """Return whether resolved ``path`` is at or below resolved ``root``."""
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _display_root_name(root: Path) -> str:
    """Return a resolved directory basename without exposing its full path."""
    try:
        resolved_root = root.resolve(strict=False)
    except (OSError, RuntimeError):
        resolved_root = root
    return resolved_root.name or "."


def _scan_directory(
    directory: Path,
    root: Path,
    resolved_root: Path,
    files: list[Path],
    warnings: list[str],
    exclude_patterns: Sequence[str],
    max_depth: int | None,
    current_depth: int,
) -> None:
    """Collect files below ``directory`` using deterministic depth-first order."""
    try:
        resolved_directory = directory.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        warnings.append(
            f"could not resolve {_relative_name(root, directory)}: {error}"
        )
        return

    if not _is_contained(resolved_directory, resolved_root):
        warnings.append(
            f"skipped directory outside scan root: {_relative_name(root, directory)}"
        )
        return

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
            link_kind = _link_kind(entry)
        except OSError as error:
            warnings.append(f"could not inspect {relative_name}: {error}")
            continue

        if link_kind is not None:
            warnings.append(f"skipped {link_kind}: {relative_name}")
            continue

        try:
            resolved_entry = entry.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            warnings.append(f"could not resolve {relative_name}: {error}")
            continue

        if not _is_contained(resolved_entry, resolved_root):
            warnings.append(f"skipped path outside scan root: {relative_name}")
            continue

        try:
            is_directory = resolved_entry.is_dir()
            is_file = resolved_entry.is_file()
        except OSError as error:
            warnings.append(f"could not inspect {relative_name}: {error}")
            continue

        if is_directory:
            if (
                entry.name.casefold() in _DEFAULT_EXCLUDED_DIRECTORIES_CASEFOLD
                or _matches(relative_name, entry.name, exclude_patterns)
            ):
                continue
            if max_depth is None or current_depth < max_depth:
                _scan_directory(
                    entry,
                    root,
                    resolved_root,
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
    """Scan ``root`` without following links or leaving its resolved tree."""
    root = Path(root)
    if max_depth is not None and max_depth < 0:
        raise ValueError("max_depth must be zero or greater")

    link_component = _find_link_component(root)
    if link_component is not None:
        component, link_kind = link_component
        description = "symbolic link" if link_kind == "symlink" else link_kind
        raise NotADirectoryError(
            f"scan root contains a {description}: {component}"
        )

    try:
        root_metadata = os.lstat(root)
    except FileNotFoundError:
        raise FileNotFoundError(f"scan root does not exist: {root}") from None
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise NotADirectoryError(f"scan root is not a directory: {root}")

    try:
        resolved_root = root.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise OSError(f"could not resolve scan root: {error}") from error

    files: list[Path] = []
    warnings: list[str] = []
    _scan_directory(
        root,
        root,
        resolved_root,
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

    lines = [_display_root_name(root)]

    def render(node: _TreeNode, depth: int) -> None:
        children = list(node.children.items())
        for index, (name, child) in enumerate(children):
            connector = "└── " if index == len(children) - 1 else "├── "
            lines.append(f"{'  ' * depth}{connector}{name}")
            render(child, depth + 1)

    render(tree_root, 0)
    return tuple(lines)
