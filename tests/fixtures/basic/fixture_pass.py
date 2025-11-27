import unittest


class MathTests(unittest.TestCase):
    """Simple passing tests to validate pyjest happy path."""

    def test_addition(self) -> None:
        self.assertEqual(1 + 1, 2)

    def test_truthy(self) -> None:
        self.assertTrue("pyjest")
