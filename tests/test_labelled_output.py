import unittest

from pyjest import describe, test


@describe("Labeled test group")
class LabeledTests(unittest.TestCase):
    @test("shows custom test label")
    def test_custom_label(self):
        """should still run normally"""
        self.assertTrue(True)

    @test("falls back to method name when no label provided")
    def test_falls_back_to_method_name(self):
        self.assertEqual(1 + 1, 2)


if __name__ == "__main__":
    unittest.main()
