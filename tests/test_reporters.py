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
