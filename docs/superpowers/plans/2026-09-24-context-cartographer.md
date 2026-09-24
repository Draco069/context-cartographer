# Context Cartographer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-dependency Python CLI that scans a project directory and emits a useful Markdown or JSON map of its files, structure, entry points, tests, configuration, documentation, and TODO/FIXME locations.

**Architecture:** Keep discovery, classification, rendering, and command-line orchestration in separate modules. The scanner returns discovered files and warnings; the analyzer converts files into serializable records; reporters render those records; the CLI validates arguments and coordinates the pipeline without executing project code or making network requests.

**Tech Stack:** Python 3.10+, standard library only at runtime, `unittest`, `argparse`, `pathlib`, `fnmatch`, `json`, and `re`; setuptools as the build backend; GitHub Actions for CI.

## Global Constraints

- Support Python 3.10 and newer.
- Use no third-party runtime dependencies.
- Do not execute project files or make network requests.
- Do not follow symlinked directories or files.
- Ignore `.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `dist`, and `build` by default.
- Report file paths relative to the scanned root wherever possible.
- Do not include complete file contents in reports.
- Use exit code `0` for success, `1` for invalid arguments or target paths, and `2` for scanning, rendering, or output failures.
- Keep the package importable as `context_cartographer` and expose the console command `cartographer`.
- Keep all user-facing errors concise and avoid tracebacks for expected failures.

---

## File Map

The implementation will create or modify these files:

- `pyproject.toml` — package metadata, build configuration, and `cartographer` entry point.
- `.gitignore` — Python, virtual-environment, build, and generated-report exclusions.
- `src/context_cartographer/__init__.py` — package version and public metadata.
- `src/context_cartographer/__main__.py` — `python -m context_cartographer` entry point.
- `src/context_cartographer/errors.py` — typed user-facing errors and exit codes.
- `src/context_cartographer/models.py` — immutable report data structures and JSON conversion.
- `src/context_cartographer/scanner.py` — directory traversal, exclusion rules, and tree construction.
- `src/context_cartographer/analyzers.py` — file classification and TODO/FIXME extraction.
- `src/context_cartographer/reporters.py` — Markdown and JSON rendering.
- `src/context_cartographer/cli.py` — argument parsing, pipeline coordination, warnings, and output.
- `tests/__init__.py` — makes the test directory importable for targeted unittest module runs.
- `tests/test_package.py` — package import and version smoke tests.
- `tests/test_models.py` — report serialization and extension aggregation tests.
- `tests/test_scanner.py` — traversal, exclusions, depth, symlink, and warning tests.
- `tests/test_analyzers.py` — classification, entry-point, and TODO/FIXME tests.
- `tests/test_reporters.py` — Markdown and JSON reporter tests.
- `tests/test_cli.py` — CLI output, output files, and exit-code tests.
- `examples/demo-project/` — small realistic project used by the README and smoke tests.
- `README.md` — installation, usage, output, privacy, development, and contribution documentation.
- `LICENSE` — MIT license.
- `.github/workflows/ci.yml` — Python-version test matrix.

---

### Task 1: Create package scaffolding and a passing import smoke test

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/context_cartographer/__init__.py`
- Create: `src/context_cartographer/__main__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_package.py`

**Interfaces:**
- Produces `context_cartographer.__version__ == "0.1.0"`.
- Produces an importable `context_cartographer` package and a `python -m context_cartographer` entry point.
- Registers `cartographer = "context_cartographer.cli:main"`; the CLI module will be implemented in Task 6.

- [ ] **Step 1: Write the failing package smoke test**

```python
# tests/test_package.py
import unittest

import context_cartographer


class PackageTests(unittest.TestCase):
    def test_package_exposes_version(self) -> None:
        self.assertEqual(context_cartographer.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the smoke test and verify it fails**

Run from the repository root with the source directory on `PYTHONPATH`:

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_package -v
```

Expected: FAIL because `context_cartographer` does not exist yet.

- [ ] **Step 3: Add package metadata and entry-point files**

`pyproject.toml` must contain:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "context-cartographer"
version = "0.1.0"
description = "Generate a concise map of a project directory"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [{name = "Draco", email = "frlexolexo@gmail.com"}]
dependencies = []

[project.scripts]
cartographer = "context_cartographer.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
```

`.gitignore` must contain:

```gitignore
__pycache__/
*.py[cod]
.venv/
venv/
.env
.env.*
.pytest_cache/
.mypy_cache/
.coverage
htmlcov/
build/
dist/
*.egg-info/
reports/
```

`src/context_cartographer/__init__.py` must contain:

```python
"""Generate concise maps of project directories."""

__version__ = "0.1.0"

__all__ = ["__version__"]
```

`src/context_cartographer/__main__.py` must contain:

```python
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

`tests/__init__.py` is an empty file so targeted commands such as `python -m unittest tests.test_package -v` resolve the repository's test package rather than an unrelated installed package.

- [ ] **Step 4: Run the smoke test and verify it passes**

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_package -v
```

Expected: PASS with one test.

- [ ] **Step 5: Commit the scaffolding**

```powershell
git add pyproject.toml .gitignore src/context_cartographer/__init__.py src/context_cartographer/__main__.py tests/__init__.py tests/test_package.py
git commit -m "chore: scaffold context cartographer package"
```

---

### Task 2: Define immutable report models and serialization

**Files:**
- Create: `src/context_cartographer/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- `Todo(path: str, line: int, marker: str)` serializes to `{"path": str, "line": int, "marker": str}`.
- `FileRecord(path: str, extension: str, is_source: bool, is_test: bool, is_config: bool, is_documentation: bool, is_entry_point: bool, todos: tuple[Todo, ...] = ())` serializes all classification flags and its TODO records.
- `AnalysisResult(files: tuple[FileRecord, ...], warnings: tuple[str, ...])` carries analyzer output.
- `ProjectReport(root: str, files: tuple[FileRecord, ...], tree: tuple[str, ...], warnings: tuple[str, ...])` exposes `extension_counts`, `entry_points`, `test_files`, `config_files`, `documentation_files`, and `to_dict()`.
- All collections in report models are immutable tuples, and JSON conversion returns ordinary lists and dictionaries.

- [ ] **Step 1: Write failing serialization tests**

```python
# tests/test_models.py
import unittest

from context_cartographer.models import FileRecord, ProjectReport, Todo


class ModelTests(unittest.TestCase):
    def test_report_serializes_sections_deterministically(self) -> None:
        todo = Todo(path="src/app.py", line=4, marker="TODO")
        record = FileRecord(
            path="src/app.py",
            extension=".py",
            is_source=True,
            is_test=False,
            is_config=False,
            is_documentation=False,
            is_entry_point=True,
            todos=(todo,),
        )
        report = ProjectReport(
            root="demo",
            files=(record,),
            tree=(".", "└── src", "    └── app.py"),
            warnings=("one warning",),
        )

        self.assertEqual(report.extension_counts, {".py": 1})
        self.assertEqual(report.entry_points, ("src/app.py",))
        self.assertEqual(report.to_dict()["summary"], {"file_count": 1, "warning_count": 1})
        self.assertEqual(report.to_dict()["todos"][0]["line"], 4)
        self.assertEqual(report.to_dict()["files"][0]["is_entry_point"], True)

    def test_empty_report_is_serializable(self) -> None:
        report = ProjectReport(root="empty", files=(), tree=(".",), warnings=())
        payload = report.to_dict()

        self.assertEqual(payload["extension_counts"], {})
        self.assertEqual(payload["entry_points"], [])
        self.assertEqual(payload["tree"], ["."])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify they fail**

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_models -v
```

Expected: FAIL because `context_cartographer.models` does not exist.

- [ ] **Step 3: Implement the models**

Use `@dataclass(frozen=True)` for `Todo`, `FileRecord`, `AnalysisResult`, and `ProjectReport`. Implement each `to_dict()` without private state or custom serialization dependencies. `ProjectReport.extension_counts` must count records by `extension`, sort keys alphabetically, and treat the empty extension as `"(none)"`. The report dictionary must use this exact top-level shape:

```python
{
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
```

The category properties must filter `self.files` in their stored order and return tuples of paths. `Todo.to_dict()` and `FileRecord.to_dict()` must return only JSON-compatible primitives, lists, and dictionaries.

- [ ] **Step 4: Run the model tests and verify they pass**

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_models -v
```

Expected: PASS with two tests.

- [ ] **Step 5: Commit the models**

```powershell
git add src/context_cartographer/models.py tests/test_models.py
git commit -m "feat: add report data models"
```

---

### Task 3: Implement safe recursive scanning and tree construction

**Files:**
- Create: `src/context_cartographer/scanner.py`
- Create: `tests/test_scanner.py`

**Interfaces:**
- `DEFAULT_EXCLUDED_DIRECTORIES: frozenset[str]` contains `.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `dist`, and `build`.
- `ScanResult(root: Path, files: tuple[Path, ...], tree: tuple[str, ...], warnings: tuple[str, ...])` is the scanner result.
- `scan_project(root: Path, *, exclude_patterns: Sequence[str] = (), max_depth: int | None = None) -> ScanResult` scans a directory recursively.
- `build_tree(root: Path, files: Sequence[Path]) -> tuple[str, ...]` renders a sorted, human-readable tree from relative file paths.
- A `max_depth` of `0` includes only files directly below the root; `None` means unlimited depth.

- [ ] **Step 1: Write failing scanner tests**

```python
# tests/test_scanner.py
import tempfile
import unittest
from pathlib import Path

from context_cartographer.scanner import scan_project


class ScannerTests(unittest.TestCase):
    def test_scanner_skips_default_directories_and_sorts_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "node_modules" / "package").mkdir(parents=True)
            (root / "node_modules" / "package" / "index.js").write_text("x\n", encoding="utf-8")

            result = scan_project(root)

            self.assertEqual(
                [path.relative_to(root).as_posix() for path in result.files],
                ["README.md", "src/app.py"],
            )
            self.assertEqual(result.warnings, ())
            self.assertIn("src", "\n".join(result.tree))

    def test_max_depth_zero_reads_only_direct_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "top.txt").write_text("top\n", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "deep.txt").write_text("deep\n", encoding="utf-8")

            result = scan_project(root, max_depth=0)

            self.assertEqual([path.name for path in result.files], ["top.txt"])

    def test_custom_exclusion_applies_to_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "keep.py").write_text("keep\n", encoding="utf-8")
            (root / "debug.log").write_text("noise\n", encoding="utf-8")

            result = scan_project(root, exclude_patterns=("*.log",))

            self.assertEqual([path.name for path in result.files], ["keep.py"])

    def test_nonexistent_root_raises_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            scan_project(Path("does-not-exist"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the scanner tests and verify they fail**

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_scanner -v
```

Expected: FAIL because `context_cartographer.scanner` does not exist.

- [ ] **Step 3: Implement the scanner**

Implement `scan_project` with a recursive, sorted traversal rather than `os.walk` so depth and symlink policy are explicit:

```python
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
    root: Path
    files: tuple[Path, ...]
    tree: tuple[str, ...]
    warnings: tuple[str, ...]


def _matches(relative_path: str, name: str, patterns: Sequence[str]) -> bool:
    return any(
        fnmatch.fnmatch(relative_path, pattern) or fnmatch.fnmatch(name, pattern)
        for pattern in patterns
    )
```

The recursive helper must sort entries by `entry.name.casefold(), entry.name`, collect regular files, skip symlinks with a warning, prune directories whose name is in `DEFAULT_EXCLUDED_DIRECTORIES` or matches a user pattern, and recurse only when `max_depth is None or current_depth < max_depth`. Wrap `Path.iterdir()` in `try/except OSError`; append a warning containing the relative path and continue. Re-raise a missing root as `FileNotFoundError` and reject a non-directory root with `NotADirectoryError`.

`build_tree` must create one root line containing the directory name, sort paths lexicographically by POSIX-style relative paths, and use two spaces per depth level. It must use `├── ` and `└── ` for the final sibling at each level. A directory-only branch must not be emitted unless it contains a discovered file. Keep the implementation deterministic so the same filesystem produces the same report.

- [ ] **Step 4: Run the scanner tests and verify they pass**

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_scanner -v
```

Expected: PASS with four tests.

- [ ] **Step 5: Commit the scanner**

```powershell
git add src/context_cartographer/scanner.py tests/test_scanner.py
git commit -m "feat: add safe project scanner"
```

---

### Task 4: Implement file classification and TODO/FIXME extraction

**Files:**
- Create: `src/context_cartographer/analyzers.py`
- Create: `tests/test_analyzers.py`

**Interfaces:**
- `analyze_files(root: Path, files: Sequence[Path], *, include_todos: bool = True) -> AnalysisResult` classifies every supplied file and returns sorted `FileRecord` values plus analyzer warnings.
- `is_test_path(relative_path: PurePosixPath) -> bool` recognizes conservative `test`, `tests`, `spec`, and `specs` path components.
- `extract_todos(path: Path, relative_path: str, *, include_todos: bool) -> tuple[Todo, ...]` reads text files line-by-line and returns markers with line numbers.
- Classification uses extension, basename, and path components; it never executes a file.

- [ ] **Step 1: Write failing analyzer tests**

```python
# tests/test_analyzers.py
import tempfile
import unittest
from pathlib import Path

from context_cartographer.analyzers import analyze_files


class AnalyzerTests(unittest.TestCase):
    def test_classifies_source_tests_config_docs_and_entry_points(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for relative, content in {
                "src/main.py": "# TODO: wire input\nprint('ok')\n",
                "tests/test_main.py": "def test_main():\n    pass\n",
                "pyproject.toml": "[project]\nname = 'demo'\n",
                "README.md": "# Demo\n",
            }.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                paths.append(path)

            result = analyze_files(root, paths)
            records = {record.path: record for record in result.files}

            self.assertTrue(records["src/main.py"].is_source)
            self.assertTrue(records["src/main.py"].is_entry_point)
            self.assertEqual(records["src/main.py"].todos[0].line, 1)
            self.assertTrue(records["tests/test_main.py"].is_test)
            self.assertTrue(records["pyproject.toml"].is_config)
            self.assertTrue(records["README.md"].is_documentation)

    def test_skips_todos_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "app.py"
            path.write_text("# FIXME: later\n", encoding="utf-8")

            result = analyze_files(root, [path], include_todos=False)

            self.assertEqual(result.files[0].todos, ())

    def test_binary_file_is_classified_without_decode_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "logo.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n")

            result = analyze_files(root, [path])

            self.assertEqual(result.warnings, ())
            self.assertEqual(result.files[0].extension, ".png")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the analyzer tests and verify they fail**

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_analyzers -v
```

Expected: FAIL because `context_cartographer.analyzers` does not exist.

- [ ] **Step 3: Implement classification constants and analyzer functions**

Use these exact data sets:

```python
SOURCE_EXTENSIONS = frozenset(
    {
        ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs",
        ".rb", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".swift", ".kt",
        ".sh", ".bash", ".ps1",
    }
)
DOCUMENTATION_EXTENSIONS = frozenset({".md", ".mdx", ".rst", ".txt", ".adoc"})
CONFIG_FILENAMES = frozenset(
    {
        "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
        "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "Cargo.toml", "go.mod", "Makefile", "Dockerfile", ".editorconfig",
        ".gitignore", ".gitattributes", "tox.ini", "noxfile.py",
    }
)
ENTRY_POINT_FILENAMES = frozenset(
    {
        "main.py", "app.py", "index.js", "index.ts", "server.js", "server.ts", "__main__.py",
        "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
    }
)
TODO_PATTERN = re.compile(r"\b(TODO|FIXME)\b")
TEXT_EXTENSIONS = SOURCE_EXTENSIONS | DOCUMENTATION_EXTENSIONS | frozenset({".toml", ".yaml", ".yml", ".ini", ".cfg", ".json"})
```

`is_test_path` must return true when any lower-cased POSIX path component is exactly `test`, `tests`, `spec`, or `specs`, or when a source filename stem starts with `test_` or ends with `_test`; it must not classify a path merely because it contains those letters inside another word. `analyze_files` must sort input paths by their relative POSIX strings, use lowercase suffixes for extension matching, mark config filenames case-sensitively against the exact known names, and mark documentation by extension. `extract_todos` must open files with `encoding="utf-8", errors="replace"`, scan only text-capable extensions, cap each file at 200,000 lines to bound memory/time, and append a warning for `OSError` or other read failures while returning an empty tuple for that file.

- [ ] **Step 4: Run the analyzer tests and verify they pass**

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_analyzers -v
```

Expected: PASS with three tests.

- [ ] **Step 5: Commit the analyzer**

```powershell
git add src/context_cartographer/analyzers.py tests/test_analyzers.py
git commit -m "feat: classify project files and find todos"
```

---

### Task 5: Render Markdown and JSON reports

**Files:**
- Create: `src/context_cartographer/reporters.py`
- Create: `tests/test_reporters.py`

**Interfaces:**
- `render_markdown(report: ProjectReport) -> str` returns a complete Markdown document ending in one newline.
- `render_json(report: ProjectReport) -> str` returns indented, key-sorted JSON ending in one newline.
- `render_report(report: ProjectReport, output_format: str) -> str` dispatches only on `markdown` and `json` and raises `ValueError` for another format.

- [ ] **Step 1: Write failing reporter tests**

```python
# tests/test_reporters.py
import json
import unittest

from context_cartographer.models import FileRecord, ProjectReport, Todo
from context_cartographer.reporters import render_json, render_markdown, render_report


class ReporterTests(unittest.TestCase):
    def setUp(self) -> None:
        record = FileRecord(
            path="src/main.py",
            extension=".py",
            is_source=True,
            is_test=False,
            is_config=False,
            is_documentation=False,
            is_entry_point=True,
            todos=(Todo(path="src/main.py", line=2, marker="TODO"),),
        )
        self.report = ProjectReport(
            root="demo",
            files=(record,),
            tree=("demo", "└── src", "    └── main.py"),
            warnings=("could not read cache",),
        )

    def test_markdown_contains_summary_sections_and_warning(self) -> None:
        output = render_markdown(self.report)

        self.assertTrue(output.startswith("# Project map: demo\n"))
        self.assertIn("## Summary", output)
        self.assertIn("src/main.py", output)
        self.assertIn("could not read cache", output)
        self.assertTrue(output.endswith("\n"))

    def test_json_is_valid_and_contains_todos(self) -> None:
        payload = json.loads(render_json(self.report))

        self.assertEqual(payload["entry_points"], ["src/main.py"])
        self.assertEqual(payload["todos"][0]["marker"], "TODO")

    def test_dispatch_rejects_unknown_format(self) -> None:
        with self.assertRaises(ValueError):
            render_report(self.report, "html")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the reporter tests and verify they fail**

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_reporters -v
```

Expected: FAIL because `context_cartographer.reporters` does not exist.

- [ ] **Step 3: Implement the reporters**

`render_markdown` must use these headings in this order: `# Project map: <root>`, `## Summary`, `## Project tree`, `## Files by extension`, `## Likely entry points`, `## Tests`, `## Configuration`, `## Documentation`, `## TODO/FIXME`, and `## Warnings`. For empty sections, print a single italic line such as `*None found.*`; never omit a section. Escape Markdown table cells by replacing `|` with `\\|`. Render the tree inside a fenced `text` block and render extension counts as a two-column table with `Extension` and `Files` headers.

`render_json` must call `json.dumps(report.to_dict(), indent=2, sort_keys=True)` and append exactly one newline. `render_report` must use an explicit `if output_format == "markdown"` / `elif output_format == "json"` dispatch and raise `ValueError("unsupported report format: ...")` otherwise.

- [ ] **Step 4: Run the reporter tests and verify they pass**

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_reporters -v
```

Expected: PASS with three tests.

- [ ] **Step 5: Commit the reporters**

```powershell
git add src/context_cartographer/reporters.py tests/test_reporters.py
git commit -m "feat: add markdown and json reporters"
```

---

### Task 6: Add typed errors and the command-line interface

**Files:**
- Create: `src/context_cartographer/errors.py`
- Create: `src/context_cartographer/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- `CartographerError` stores a message and an integer exit code.
- `UsageError`, `InputError`, and `OutputError` specialize `CartographerError` with codes `1`, `1`, and `2`.
- `build_parser() -> argparse.ArgumentParser` defines `PATH`, `--format`, `--output`, repeatable `--exclude`, `--max-depth`, `--no-todos`, and `--version`.
- `main(argv: Sequence[str] | None = None) -> int` returns the process exit code without calling `sys.exit` for normal execution.

- [ ] **Step 1: Write failing CLI tests**

```python
# tests/test_cli.py
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from context_cartographer.cli import main


class CliTests(unittest.TestCase):
    def test_markdown_report_is_written_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_text("print('ok')\n", encoding="utf-8")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = main([str(root)])

            self.assertEqual(exit_code, 0)
            self.assertIn("# Project map:", stdout.getvalue())

    def test_json_output_file_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_text("print('ok')\n", encoding="utf-8")
            output = root / "map.json"
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                exit_code = main([str(root), "--format", "json", "--output", str(output)])

            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["summary"]["file_count"], 1)

    def test_invalid_target_returns_one(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = main(["path-that-does-not-exist"])
        self.assertEqual(exit_code, 1)
        self.assertIn("cartographer: error:", stderr.getvalue())

    def test_unknown_format_returns_one(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = main(["--format", "html"])
        self.assertEqual(exit_code, 1)
        self.assertIn("invalid choice", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the CLI tests and verify they fail**

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_cli -v
```

Expected: FAIL because `context_cartographer.cli` does not exist.

- [ ] **Step 3: Implement typed errors**

`errors.py` must define:

```python
class CartographerError(Exception):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class UsageError(CartographerError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 1)


class InputError(CartographerError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 1)


class OutputError(CartographerError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 2)
```

- [ ] **Step 4: Implement argument parsing and orchestration**

`build_parser` must use a parser subclass whose `error()` raises `UsageError` instead of writing directly to stderr. The parser must set `prog="cartographer"`, use `Path` as the positional type only for storing text, choose `markdown` as the default format, use `action="append"` with `default=[]` for `--exclude`, and validate `--max-depth` with this helper:

```python
def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed
```

`--version` must use `version=__version__`.

`main` must perform this sequence:

```python
parser = build_parser()
try:
    args = parser.parse_args(argv)
    root = Path(args.path).expanduser()
    if not root.exists():
        raise InputError(f"target path does not exist: {root}")
    if not root.is_dir():
        raise InputError(f"target path is not a directory: {root}")
    scan = scan_project(
        root,
        exclude_patterns=args.exclude,
        max_depth=args.max_depth,
    )
    analysis = analyze_files(root, scan.files, include_todos=not args.no_todos)
    report = ProjectReport(
        root=root.name or str(root),
        files=analysis.files,
        tree=scan.tree,
        warnings=scan.warnings + analysis.warnings,
    )
    rendered = render_report(report, args.format)
    if args.output:
        output = Path(args.output).expanduser()
        try:
            output.write_text(rendered, encoding="utf-8")
        except OSError as error:
            raise OutputError(f"could not write output file {output}: {error}") from error
    else:
        sys.stdout.write(rendered)
    for warning in report.warnings:
        print(f"cartographer: warning: {warning}", file=sys.stderr)
    return 0
except CartographerError as error:
    print(f"cartographer: error: {error}", file=sys.stderr)
    return error.exit_code
except OSError as error:
    print(f"cartographer: error: {error}", file=sys.stderr)
    return 2
```

The output block above catches `OSError` from `write_text` and raises `OutputError` with the destination path. Do not catch `KeyboardInterrupt`. Keep report output exactly one rendered document with no progress messages on standard output.

- [ ] **Step 5: Run the CLI tests and verify they pass**

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_cli -v
```

Expected: PASS with four tests.

- [ ] **Step 6: Run the complete test suite**

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
```

Expected: all package, model, scanner, analyzer, reporter, and CLI tests PASS.

- [ ] **Step 7: Commit the CLI**

```powershell
git add src/context_cartographer/errors.py src/context_cartographer/cli.py tests/test_cli.py
git commit -m "feat: add cartographer command line interface"
```

---

### Task 7: Add the demo project, README, license, and CI

**Files:**
- Create: `examples/demo-project/README.md`
- Create: `examples/demo-project/pyproject.toml`
- Create: `examples/demo-project/src/demo_app.py`
- Create: `examples/demo-project/tests/test_demo_app.py`
- Create: `README.md`
- Create: `LICENSE`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- The example project must produce a report containing `src/demo_app.py`, `tests/test_demo_app.py`, `pyproject.toml`, and at least one TODO marker.
- The README must document installation, all CLI options, report behavior, privacy guarantees, development commands, and contribution workflow.
- CI must run the standard-library test suite on Python 3.10, 3.11, 3.12, and 3.13.

- [ ] **Step 1: Add the example project files**

`examples/demo-project/src/demo_app.py`:

```python
"""Small example application used by Context Cartographer."""


def greet(name: str) -> str:
    """Return a friendly greeting."""
    return f"Hello, {name}!"

# TODO: Add a command-line interface to this example.
```

`examples/demo-project/tests/test_demo_app.py`:

```python
import unittest

from src.demo_app import greet


class GreetTests(unittest.TestCase):
    def test_greet(self) -> None:
        self.assertEqual(greet("world"), "Hello, world!")


if __name__ == "__main__":
    unittest.main()
```

`examples/demo-project/pyproject.toml`:

```toml
[project]
name = "demo-project"
version = "0.1.0"
requires-python = ">=3.10"
```

`examples/demo-project/README.md`:

```markdown
# Demo project

A tiny project used to demonstrate Context Cartographer.
```

- [ ] **Step 2: Add the README**

The README must use these sections: title and one-sentence description, Features, Installation, Quick start, Command options, Report examples, Privacy and safety, Development, Project layout, Contributing, and License. The quick-start commands must be:

```bash
python -m pip install --no-deps -e .
cartographer .
cartographer examples/demo-project --format json
python -m context_cartographer examples/demo-project --output examples/demo-project/MAP.md
```

Document that reports contain metadata and TODO/FIXME locations, not complete source files; that generated files are not uploaded; and that the tool does not execute discovered code. Document the exact test and compile commands:

```bash
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

- [ ] **Step 3: Add the MIT license and CI workflow**

Use the MIT license with copyright year `2026` and copyright holder `Draco`.

`.github/workflows/ci.yml` must contain:

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: python -m pip install --upgrade pip
      - run: python -m pip install --no-deps -e .
      - run: python -m unittest discover -s tests -v
```

- [ ] **Step 4: Run a smoke report against the example project**

```powershell
$env:PYTHONPATH = 'src'
python -m context_cartographer examples/demo-project --format markdown
python -m context_cartographer examples/demo-project --format json | python -m json.tool
```

Expected: the first command exits `0` and includes `src/demo_app.py`; the second command prints valid JSON containing the example's TODO marker.

- [ ] **Step 5: Commit the documentation and example project**

```powershell
git add examples README.md LICENSE .github/workflows/ci.yml
git commit -m "docs: add project documentation and demo"
```

---

### Task 8: Perform final verification and prepare the repository for publication

**Files:**
- Modify: `README.md` only if verification reveals inaccurate commands.
- Modify: implementation files only when a verified failure requires a focused fix.

**Interfaces:**
- The final working tree must contain a passing standard-library test suite, a working console entry point when installed, and a clean Git history.
- The repository must be ready to add a public GitHub remote and push the default branch.

- [ ] **Step 1: Run the full test suite from a clean environment**

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
```

Expected: every test passes with exit code `0`.

- [ ] **Step 2: Run syntax compilation**

```powershell
python -m compileall -q src tests examples
```

Expected: exit code `0` and no output.

- [ ] **Step 3: Verify package installation and the console command**

```powershell
python -m pip install --no-deps -e .
cartographer --version
cartographer examples/demo-project --format markdown
```

Expected: version `0.1.0`, followed by a successful Markdown report.

- [ ] **Step 4: Inspect the diff and repository state**

```powershell
git diff --check
git status --short
git log --oneline --decorate -10
```

Expected: no whitespace errors, no unintended files, and a clear sequence of focused commits.

- [ ] **Step 5: Commit any verification-only corrections**

If Step 1–4 changes a file, stage only the affected file and create a focused commit such as:

```powershell
git add README.md
git commit -m "docs: clarify verified usage"
```

If no files changed, do not create an empty commit.

- [ ] **Step 6: Publish the repository after the user confirms the GitHub account and repository visibility**

Create a public repository named `context-cartographer` in the user's authenticated GitHub account, add it as `origin`, and push the default branch. The remote URL and pushed branch must be reported back to the user. If GitHub CLI authentication is unavailable, use the authenticated GitHub browser session instead of embedding credentials in commands.

---

## Plan Self-Review

- **Spec coverage:** The plan covers package scaffolding, Python version support, zero runtime dependencies, scanner exclusions, symlink policy, depth and custom patterns, classification rules, TODO/FIXME extraction, Markdown and JSON output, privacy constraints, warnings, all specified exit codes, tests, demo project, README, MIT license, CI, and GitHub publication readiness.
- **Placeholder scan:** The plan contains no `TBD`, deferred implementation, or unspecified error-handling steps. References to TODO/FIXME describe the feature itself, not unfinished plan work.
- **Type consistency:** `ScanResult`, `FileRecord`, `AnalysisResult`, `ProjectReport`, `analyze_files`, `render_report`, and `main` are introduced before their consumers. CLI construction uses the exact field names produced by the scanner and analyzer.
- **Scope check:** The repository is one cohesive CLI project. Publishing is a final operational step rather than a second software subsystem.
