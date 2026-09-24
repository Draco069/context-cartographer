import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_symlink_root_is_rejected_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            (target / "inside.txt").write_text("inside\n", encoding="utf-8")
            link = root / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symbolic links are unavailable: {error}")

            with self.assertRaises(NotADirectoryError) as context:
                scan_project(link)

            self.assertIn("symbolic link", str(context.exception).lower())

    def test_nested_symlinks_are_skipped_with_warnings_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            target_file = target / "inside.txt"
            target_file.write_text("inside\n", encoding="utf-8")
            file_link = root / "linked-file.txt"
            directory_link = root / "linked-directory"
            try:
                file_link.symlink_to(target_file)
                directory_link.symlink_to(target, target_is_directory=True)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symbolic links are unavailable: {error}")

            result = scan_project(root)
            relative_files = {
                path.relative_to(root).as_posix() for path in result.files
            }
            warning_text = "\n".join(result.warnings).lower()

            self.assertEqual(relative_files, {"target/inside.txt"})
            self.assertIn("symlink", warning_text)
            self.assertIn("linked-file.txt", warning_text)
            self.assertIn("linked-directory", warning_text)

    def test_root_listing_failure_propagates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "file.txt").write_text("file\n", encoding="utf-8")
            original_iterdir = Path.iterdir

            def fail_root_iterdir(path: Path):
                if path == root:
                    raise OSError("root listing failed")
                return original_iterdir(path)

            with patch.object(Path, "iterdir", fail_root_iterdir):
                with self.assertRaises(OSError) as context:
                    scan_project(root)

            self.assertIn("root listing failed", str(context.exception))

    def test_nested_listing_failure_becomes_warning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()
            (root / "file.txt").write_text("file\n", encoding="utf-8")
            original_iterdir = Path.iterdir

            def fail_nested_iterdir(path: Path):
                if path == nested:
                    raise OSError("nested listing failed")
                return original_iterdir(path)

            with patch.object(Path, "iterdir", fail_nested_iterdir):
                result = scan_project(root)

            self.assertEqual([path.name for path in result.files], ["file.txt"])
            self.assertIn("nested", "\n".join(result.warnings))
            self.assertIn("nested listing failed", "\n".join(result.warnings))


if __name__ == "__main__":
    unittest.main()
