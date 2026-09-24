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
