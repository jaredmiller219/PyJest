import unittest


class OtherTests(unittest.TestCase):
    """Additional passing tests for parallel runs."""

    def test_truth(self) -> None:
        self.assertTrue(True)
