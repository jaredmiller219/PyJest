import unittest


class FailingTests(unittest.TestCase):
    """Failing test to assert pyjest returns non-zero."""

    def test_failure(self) -> None:
        self.assertEqual(1 + 1, 3)
