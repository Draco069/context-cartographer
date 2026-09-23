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
