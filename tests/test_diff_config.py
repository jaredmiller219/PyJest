import unittest

from pyjest import describe, test
from pyjest.assertions import DIFF_CONFIG, configure_diffs, expect


@describe("Diff configuration")
class DiffConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        # Reset diff settings after each test to avoid bleeding into others.
        configure_diffs(200, True)

    @test("max diff lines of zero disables truncation")
    def test_configure_diffs_zero_unlimited(self) -> None:
        configure_diffs(0, True)
        self.assertIsNone(DIFF_CONFIG.max_lines)
        self.assertTrue(DIFF_CONFIG.color)

    @test("diffs truncate and drop color when configured")
    def test_diff_truncates_and_disables_color(self) -> None:
        configure_diffs(1, False)
        with self.assertRaises(AssertionError) as ctx:
            expect({"a": 1, "b": 2}).to_equal({"a": 1, "b": 3})

        message = str(ctx.exception)
        self.assertIn("... (", message)  # truncated marker
        self.assertNotIn("\033", message)  # no ANSI color codes when disabled


if __name__ == "__main__":
    unittest.main()
