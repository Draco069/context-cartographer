import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from context_cartographer.cli import build_parser, main
from context_cartographer.errors import (
    CartographerError,
    InputError,
    OutputError,
    UsageError,
)


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
            self.assertTrue(stdout.getvalue().endswith("\n"))

    def test_markdown_stdout_uses_ascii_fallback_for_cp1252_console(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_text("print('ok')\n", encoding="utf-8")
            raw = io.BytesIO()

            with io.TextIOWrapper(raw, encoding="cp1252") as stdout:
                with redirect_stdout(stdout):
                    exit_code = main([str(root)])
                output = raw.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertTrue(output.isascii())
            self.assertIn(b"\\u2514", output)

    def test_report_title_uses_resolved_basename_without_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            nested = project / "nested"
            nested.mkdir(parents=True)
            (project / "main.py").write_text("print('ok')\n", encoding="utf-8")
            requested_root = nested / ".."
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = main([str(requested_root)])

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertTrue(output.startswith("# Project map: project\n"))
            self.assertIn("\nproject\n", output)
            self.assertNotIn(str(Path(directory)), output)

    def test_json_output_file_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_text("print('ok')\n", encoding="utf-8")
            output = root / "map.json"
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                exit_code = main([str(root), "--format", "json", "--output", str(output)])

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8"))["summary"]["file_count"],
                1,
            )

    def test_invalid_target_returns_one_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "missing"
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                exit_code = main([str(target)])

            self.assertEqual(exit_code, 1)
            self.assertIn("cartographer: error:", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_unknown_format_returns_one(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = main(["--format", "html"])

        self.assertEqual(exit_code, 1)
        self.assertIn("invalid choice", stderr.getvalue())
        self.assertIn("cartographer: error:", stderr.getvalue())

    def test_parser_exposes_all_options_and_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "project",
                "--format",
                "json",
                "--output",
                "map.json",
                "--exclude",
                "*.log",
                "--exclude",
                "build/*",
                "--max-depth",
                "0",
                "--no-todos",
            ]
        )

        self.assertEqual(parser.prog, "cartographer")
        self.assertEqual(args.path, Path("project"))
        self.assertEqual(args.format, "json")
        self.assertEqual(args.output, "map.json")
        self.assertEqual(args.exclude, ["*.log", "build/*"])
        self.assertEqual(args.max_depth, 0)
        self.assertTrue(args.no_todos)

    def test_invalid_max_depth_returns_one(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = main(["--max-depth", "-1"])

        self.assertEqual(exit_code, 1)
        self.assertIn("zero or greater", stderr.getvalue())

    def test_options_are_forwarded_to_the_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text("TODO: later\n", encoding="utf-8")
            (root / "debug.log").write_text("TODO: hidden\n", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "module.py").write_text("FIXME: nested\n", encoding="utf-8")
            output = root / "report.json"
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        str(root),
                        "--format",
                        "json",
                        "--output",
                        str(output),
                        "--exclude",
                        "*.log",
                        "--max-depth",
                        "0",
                        "--no-todos",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["file_count"], 1)
            self.assertEqual(payload["files"][0]["path"], "app.py")
            self.assertEqual(payload["todos"], [])

    def test_warnings_are_preserved_on_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            (target / "file.txt").write_text("content\n", encoding="utf-8")
            link = root / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symbolic links are unavailable: {error}")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main([str(root)])

            self.assertEqual(exit_code, 0)
            self.assertIn("cartographer: warning:", stderr.getvalue())
            self.assertIn("link", stderr.getvalue())
            self.assertIn("# Project map:", stdout.getvalue())
            self.assertNotIn("cartographer: warning:", stdout.getvalue())

    def test_output_write_error_returns_two_and_names_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_text("print('ok')\n", encoding="utf-8")
            output = root / "map.md"
            stderr = io.StringIO()

            with patch.object(Path, "write_text", side_effect=OSError("disk full")):
                with redirect_stderr(stderr):
                    exit_code = main([str(root), "--output", str(output)])

            self.assertEqual(exit_code, 2)
            self.assertIn(str(output), stderr.getvalue())
            self.assertIn("disk full", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_symlink_target_is_rejected_before_directory_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            target = parent / "target"
            target.mkdir()
            (target / "file.txt").write_text("content\n", encoding="utf-8")
            link = parent / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symbolic links are unavailable: {error}")

            original_is_dir = Path.is_dir

            def fail_for_link(path: Path) -> bool:
                if path == link:
                    raise AssertionError("symlink root should not be checked as a directory")
                return original_is_dir(path)

            stderr = io.StringIO()
            with patch.object(Path, "is_dir", fail_for_link):
                with redirect_stderr(stderr):
                    exit_code = main([str(link)])

            self.assertEqual(exit_code, 1)
            self.assertIn("symlink", stderr.getvalue().lower())

    def test_error_types_have_documented_exit_codes(self) -> None:
        self.assertEqual(CartographerError("failure", 7).exit_code, 7)
        self.assertEqual(UsageError("usage").exit_code, 1)
        self.assertEqual(InputError("input").exit_code, 1)
        self.assertEqual(OutputError("output").exit_code, 2)


if __name__ == "__main__":
    unittest.main()
