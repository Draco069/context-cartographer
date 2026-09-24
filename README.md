# Context Cartographer

Context Cartographer is a zero-dependency Python CLI that statically maps a project's files, structure, likely entry points, tests, configuration, documentation, and TODO/FIXME markers.

## Features

- Produces deterministic Markdown or JSON project maps.
- Shows a file tree, extension counts, likely entry points, tests, configuration, documentation, and TODO/FIXME locations.
- Supports custom glob exclusions and a maximum traversal depth.
- Skips common generated and dependency directories by default.
- Rejects scan roots whose path contains a symbolic link or Windows reparse point, and skips discovered link/reparse entries with warnings.
- Uses only the Python standard library and never executes discovered project code.

## Installation

Python 3.10 or newer is required. From the repository root, install the project in editable mode:

```bash
python -m pip install --no-deps -e .
```

This provides both the `cartographer` command and the equivalent module entry point:

```bash
cartographer --help
python -m context_cartographer --help
```

## Quick start

Run these commands from the repository root:

```bash
python -m pip install --no-deps -e .
cartographer .
cartographer examples/demo-project --format json
python -m context_cartographer examples/demo-project --output examples/demo-project/MAP.md
```

The last command writes a Markdown report to `examples/demo-project/MAP.md`. That generated file will be included in a later scan of `examples/demo-project` unless it is excluded with `--exclude` or removed. Without `--output`, Context Cartographer writes the report to standard output. Markdown keeps the documented Unicode tree in the report; if the console encoding cannot represent it, standard output uses an ASCII-safe backslash-escaped fallback and the command still exits successfully.

## Command options

```text
cartographer [PATH] [--format {markdown,json}] [--output PATH]
              [--exclude GLOB] [--max-depth N] [--no-todos]
              [--version] [--help]
```

| Option | Description |
| --- | --- |
| `PATH` | Project directory to scan. The default is the current directory (`.`). |
| `-h`, `--help` | Show the command help and exit. |
| `--format {markdown,json}` | Select the report format. The default is `markdown`. |
| `--output PATH` | Write the report to `PATH` instead of standard output. |
| `--exclude GLOB` | Exclude matching relative paths or entry names. Repeat the option to add multiple glob patterns. |
| `--max-depth N` | Limit directory recursion. `0` scans only files directly inside `PATH`; the default is unlimited depth. Values below zero are rejected. |
| `--no-todos` | Omit TODO/FIXME locations from the report. |
| `--version` | Show the package version (`0.1.0`) and exit. |

### Discovery behavior

Directory traversal is sorted and case-insensitive at each level, with the original name used as a deterministic tie-breaker. These directory names are ignored by default, matched case-insensitively: `.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `dist`, and `build`.

If any component of the supplied `PATH` is a symbolic link or Windows reparse point (including a junction), Context Cartographer rejects the scan root and exits with code `1`. Link/reparse files or directories discovered below an accepted root are not followed; each is skipped and a relative warning is written to standard error and included in the report. Resolved entry paths are checked to ensure they remain under the accepted root.

### Report behavior

Markdown reports contain these sections in order: `Summary`, `Project tree`, `Files by extension`, `Likely entry points`, `Tests`, `Configuration`, `Documentation`, `TODO/FIXME`, and `Warnings`. The report and tree title use only the resolved directory basename, not the absolute target path. JSON reports contain the same information in a key-sorted object, including summary counts, tree lines, categorized paths, per-file metadata, TODO/FIXME records, and warnings.

File records contain relative paths, extensions, classification flags, and TODO/FIXME path, line, and marker records. Reports do not contain complete source-file contents. Standard output is flushed before scan and read warnings are printed to standard error, keeping the rendered report ordered when streams are combined.

The command uses these exit codes:

| Code | Meaning |
| ---: | --- |
| `0` | The report was generated successfully. |
| `1` | Arguments, the target path, or another input check was invalid. |
| `2` | Scanning, rendering, or output writing failed. |

## Report examples

Generate Markdown directly in the terminal:

```bash
cartographer examples/demo-project --format markdown
```

A report includes output like:

```text
# Project map: demo-project

## Summary

- Files: 4
- Warnings: 0
...
## Tests

- tests/test_demo_app.py

## Configuration

- pyproject.toml

## TODO/FIXME

- src/demo_app.py:9 (TODO)
```

Generate indented, key-sorted JSON:

```bash
cartographer examples/demo-project --format json
```

The shown JSON `todos` section has this shape:

```json
{
  "todos": [
    {
      "line": 9,
      "marker": "TODO",
      "path": "src/demo_app.py"
    }
  ]
}
```

Write Markdown to a file:

```bash
cartographer examples/demo-project --output examples/demo-project/MAP.md
```

## Privacy and safety

Context Cartographer performs static filesystem inspection only. It does **not** execute discovered code, import scanned modules, or make network requests. Reports include file metadata, classifications, and TODO/FIXME locations (path, line, and marker), not complete source files. Warnings can contain file paths and operating-system error text.

The tool has no upload functionality, and generated report files are not uploaded. Review reports before sharing them because paths and TODO/FIXME marker tokens can reveal project-specific information.

## Development

Set the source directory on `PYTHONPATH`, then run the standard-library test suite and syntax compilation:

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

Run the CLI directly without installing the console script:

```powershell
$env:PYTHONPATH = 'src'
python -m context_cartographer examples/demo-project --format markdown
```

## Project layout

```text
.github/
  workflows/
    ci.yml
examples/
  demo-project/
    README.md
    pyproject.toml
    src/
      demo_app.py
    tests/
      test_demo_app.py
src/
  context_cartographer/
    __init__.py
    __main__.py
    analyzers.py
    cli.py
    errors.py
    models.py
    reporters.py
    scanner.py
tests/
  test_analyzers.py
  test_cli.py
  test_models.py
  test_package.py
  test_reporters.py
  test_scanner.py
```

## Contributing

1. Create a focused branch for the change.
2. Add or update tests that demonstrate the intended behavior.
3. Run the full test and compilation commands from [Development](#development).
4. Review generated report files and keep them out of the change unless the project explicitly requires an example.
5. Commit the focused change with a descriptive message and open a pull request describing the motivation and verification.

## License

Context Cartographer is available under the MIT License. See [LICENSE](LICENSE) for details.
