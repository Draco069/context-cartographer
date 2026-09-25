# Context Cartographer Design

**Date:** 2026-09-24  
**Status:** Approved for implementation  
**Project:** `context-cartographer`

## Purpose

Context Cartographer is a zero-dependency Python command-line tool that turns a project directory into a concise, human-readable map. It helps contributors quickly understand a codebase without opening every file.

The first release focuses on static, local analysis. It does not execute project code, call external services, or upload source data.

## Goals

- Generate a useful project map from a single command.
- Support both Markdown and JSON output.
- Avoid third-party runtime dependencies.
- Work on Windows, macOS, and Linux.
- Be easy to install and contribute to.
- Handle imperfect or partially unreadable projects gracefully.

## Non-goals

- Building a full static-analysis engine.
- Parsing every programming language.
- Reading or summarizing file contents beyond lightweight TODO/FIXME detection.
- Watching files or generating live reports.
- Calling GitHub or other network APIs.

## User Interface

The installed console command is:

```text
cartographer [PATH] [OPTIONS]
```

Examples:

```bash
cartographer .
cartographer ./my-project --format json
cartographer . --output PROJECT_MAP.md
```

### Options

- `PATH` defaults to the current directory.
- `--format {markdown,json}` defaults to `markdown`.
- `--output PATH` writes to a file instead of standard output.
- `--exclude GLOB` adds an exclusion pattern; the option may be repeated.
- `--max-depth N` limits directory traversal depth; zero means the target directory only.
- `--no-todos` omits TODO/FIXME locations from the report.
- `--version` prints the package version.

## Architecture

The project will be a small Python package with separated discovery, analysis, rendering, and CLI concerns.

### Modules

- `context_cartographer.models` contains serializable report models.
- `context_cartographer.scanner` discovers files and applies default and user-provided exclusions.
- `context_cartographer.analyzers` classifies files and extracts lightweight metadata.
- `context_cartographer.reporters` renders reports as Markdown or JSON.
- `context_cartographer.cli` parses arguments, coordinates the pipeline, and maps failures to exit codes.
- `context_cartographer.__main__` enables `python -m context_cartographer`.

The modules will communicate through explicit data structures rather than sharing mutable scanner state.

## Data Flow

1. Parse and validate the requested path and options.
2. Walk the target directory recursively.
3. Skip ignored directories and files.
4. Classify each file by extension, basename, and location.
5. Collect file counts, likely entry points, tests, configuration/documentation files, and TODO/FIXME locations.
6. Construct a report model.
7. Render it as Markdown or JSON.
8. Write to the selected output destination or standard output.

The default report will include a project tree, file counts by extension, likely source/test/config files, likely entry points, and TODO/FIXME locations. File contents will not be included by default.

## Classification Rules

The initial classifier will use conservative, language-agnostic rules:

- Source extensions include common Python, JavaScript, TypeScript, Java, Go, Rust, Ruby, C/C++, and shell extensions.
- Test paths include names or directories containing `test` or `spec`, subject to conservative matching rules.
- Documentation includes Markdown, reStructuredText, and text documentation files.
- Configuration includes known names such as `pyproject.toml`, `package.json`, `Cargo.toml`, `Makefile`, and `.editorconfig`.
- Likely entry points include common filenames such as `main.py`, `app.py`, `index.js`, `index.ts`, and `server.js`, plus project manifests.
- TODO/FIXME detection will be line-based and limited to source/text files. The report will include file path, line number, and matched marker, not surrounding content.

The rules will be data-driven where practical so they can be expanded without rewriting the scanner.

## Error Handling and Exit Codes

- `0`: report generated successfully.
- `1`: invalid arguments or target path.
- `2`: unexpected scanning, rendering, or output error.

An unreadable individual file will produce a warning on standard error; its file metadata is retained while content analysis is skipped. An unreadable directory will produce a warning and be skipped. A completely inaccessible target will fail with a concise error. Output errors will include the destination path. The CLI will not print a traceback for expected user errors.

## Security and Privacy

- The tool will not execute discovered files.
- It will not make network requests.
- It will not include full file contents in reports.
- It will inspect lexical scan-root components before applying user-supplied `..`, continue past missing intermediate components to find later links, reject any symbolic link or Windows reparse point, and will not follow discovered link/reparse entries by default; resolved paths are kept under the accepted root.
- Link/reparse detection and resolved containment are point-in-time checks, not race-free guarantees against a concurrent process replacing a path during a scan. Untrusted, concurrently modified trees should be copied to a stable location before scanning.
- Paths in reports will be relative to the target where possible.

## Testing Strategy

The automated test suite will use Python's standard `unittest` framework and temporary directories. Coverage will include:

- empty and nested directories;
- default ignored directories;
- custom exclusions and maximum depth;
- extension classification;
- source, test, configuration, and documentation detection;
- likely entry-point detection;
- TODO/FIXME extraction;
- Markdown and JSON rendering;
- output-file handling;
- invalid paths and argument validation;
- unreadable-file behavior where the platform permits it;
- command-line exit codes.

A small example project will be included under `examples/` and used in documentation examples and possibly an integration test.

## Repository Deliverables

- Python package source under `src/context_cartographer/`
- Test suite under `tests/`
- Example project under `examples/`
- `pyproject.toml` with console-script entry point
- README with installation, usage, output examples, and contribution guidance
- MIT `LICENSE`
- `.gitignore`
- GitHub Actions workflow running tests on supported Python versions
- Design specification and implementation documentation

## Success Criteria

A new user can install the package, run `cartographer .`, and receive a useful Markdown report without installing project-specific dependencies. A contributor can run the test suite with one standard command, understand the module boundaries, and extend the classifier or add a reporter safely. A maintainer can publish the project as a public GitHub repository with clear documentation and automated checks.

## Future Extensions

Possible later additions include HTML output, richer language statistics, configurable ignore files, `.gitignore` parsing, JSON-schema validation, and optional integrations with repository metadata. These are intentionally outside the first release.
