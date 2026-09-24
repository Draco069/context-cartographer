import unittest

from src.demo_app import greet


class GreetTests(unittest.TestCase):
    def test_greet(self) -> None:
        self.assertEqual(greet("world"), "Hello, world!")


if __name__ == "__main__":
    unittest.main()
