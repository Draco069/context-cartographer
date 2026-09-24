import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from context_cartographer import analyzers
from context_cartographer.analyzers import (
    CONFIG_FILENAMES,
    DOCUMENTATION_EXTENSIONS,
    ENTRY_POINT_FILENAMES,
    SOURCE_EXTENSIONS,
    TEXT_EXTENSIONS,
    analyze_files,
    extract_todos,
    is_test_path,
)


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

    def test_classifications_use_lowercase_suffixes_and_exact_config_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for relative, content in {
                "src/APP.PY": "print('ok')\n",
                "PYPROJECT.TOML": "[project]\n",
                "requirements.txt": "TODO: replace dependency\n",
                "guide.MD": "TODO: expand guide\n",
            }.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                paths.append(path)

            records = {record.path: record for record in analyze_files(root, paths).files}

            self.assertTrue(records["src/APP.PY"].is_source)
            self.assertFalse(records["PYPROJECT.TOML"].is_config)
            self.assertTrue(records["requirements.txt"].is_config)
            self.assertTrue(records["requirements.txt"].is_documentation)
            self.assertTrue(records["guide.MD"].is_documentation)
            self.assertEqual(records["guide.MD"].extension, ".md")

    def test_entry_point_names_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for relative in ("app.py", "Main.py", "server.js", "index.tsx"):
                path = root / relative
                path.write_text("", encoding="utf-8")
                paths.append(path)

            records = {record.path: record for record in analyze_files(root, paths).files}

            self.assertTrue(records["app.py"].is_entry_point)
            self.assertTrue(records["server.js"].is_entry_point)
            self.assertFalse(records["Main.py"].is_entry_point)
            self.assertFalse(records["index.tsx"].is_entry_point)

    def test_test_path_matching_is_conservative(self) -> None:
        test_paths = {
            "test/module.py": True,
            "tests/module.py": True,
            "src/spec/module.py": True,
            "src/specs/module.py": True,
            "src/test_module.py": True,
            "src/module_test.py": True,
            "src/TEST_MODULE.PY": True,
            "src/contest/module.py": False,
            "src/latest/module.py": False,
            "src/test-file/module.py": False,
            "src/test_module.txt": False,
            "src/module.py": False,
        }
        for relative_path, expected in test_paths.items():
            with self.subTest(relative_path=relative_path):
                self.assertIs(
                    is_test_path(PurePosixPath(relative_path)),
                    expected,
                )

    def test_files_are_returned_in_relative_posix_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for relative in ("z.py", "src/a.py", "README.md", "src/../a.py"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
                paths.append(path)

            result = analyze_files(root, paths)

            self.assertEqual(
                [record.path for record in result.files],
                ["README.md", "src/../a.py", "src/a.py", "z.py"],
            )

    def test_extracts_all_markers_and_ignores_non_word_matches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.py"
            path.write_text(
                "# TODO first FIXME second\n"
                "method TODO_VALUE and XTODO are ignored\n"
                "TODO\n",
                encoding="utf-8",
            )

            todos = extract_todos(path, "app.py", include_todos=True)

            self.assertEqual(
                [(todo.line, todo.marker) for todo in todos],
                [(1, "TODO"), (1, "FIXME"), (3, "TODO")],
            )

    def test_invalid_utf8_is_replaced_while_reading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.txt"
            path.write_bytes(b"# TODO: caf\xe9\n")

            todos = extract_todos(path, "notes.txt", include_todos=True)

            self.assertEqual(todos[0].marker, "TODO")
            self.assertEqual(todos[0].line, 1)

    def test_todo_scan_is_capped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.py"
            path.write_text(
                "one\ntwo\nTODO: included\nfour\n", encoding="utf-8"
            )

            with patch.object(analyzers, "MAX_TODO_LINES", 3):
                todos = extract_todos(path, "app.py", include_todos=True)

            self.assertEqual([(todo.line, todo.marker) for todo in todos], [(3, "TODO")])
            self.assertEqual(analyzers.MAX_TODO_LINES, 200_000)

    def test_non_text_files_are_not_opened_for_todo_scan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "image.png"
            path.write_bytes(b"not a text file TODO: hidden\n")

            def fail_open(*args, **kwargs):
                raise AssertionError("binary file should not be opened")

            with patch.object(Path, "open", fail_open):
                result = analyze_files(root, [path])

            self.assertEqual(result.warnings, ())
            self.assertEqual(result.files[0].todos, ())

    def test_unreadable_text_file_produces_a_warning_and_no_partial_todos(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "broken.py"
            path.write_text("TODO: before\n", encoding="utf-8")
            original_open = Path.open

            def fail_for_file(self, *args, **kwargs):
                if self == path:
                    raise OSError("read failed")
                return original_open(self, *args, **kwargs)

            with patch.object(Path, "open", fail_for_file):
                result = analyze_files(root, [path])

            self.assertEqual(result.files[0].todos, ())
            self.assertEqual(len(result.warnings), 1)
            self.assertIn("broken.py", result.warnings[0])
            self.assertIn("read failed", result.warnings[0])

    def test_classification_constants_have_the_planned_values(self) -> None:
        self.assertIn(".py", SOURCE_EXTENSIONS)
        self.assertIn(".md", DOCUMENTATION_EXTENSIONS)
        self.assertIn("pyproject.toml", CONFIG_FILENAMES)
        self.assertIn("main.py", ENTRY_POINT_FILENAMES)
        self.assertIn(".json", TEXT_EXTENSIONS)
        self.assertEqual(analyzers.TODO_PATTERN.pattern, r"\b(TODO|FIXME)\b")


if __name__ == "__main__":
    unittest.main()
