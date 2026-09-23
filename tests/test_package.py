import unittest

import context_cartographer


class PackageTests(unittest.TestCase):
    def test_package_exposes_version(self) -> None:
        self.assertEqual(context_cartographer.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
