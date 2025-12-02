import unittest

from pyjest import autolabel, describe, test
from pyjest.discovery import _apply_only_filter, _iter_tests


class SkipAndTodoDecoratorTests(unittest.TestCase):
    @test.skip("skip this one")
    def test_skip_sets_unittest_flags(self) -> None:
        fn = getattr(self.__class__, "test_skip_sets_unittest_flags")
        self.assertTrue(getattr(fn, "__unittest_skip__", False))
        self.assertEqual(getattr(fn, "__unittest_skip_why__", None), "skip this one")

    @test.todo("pending work")
    def test_todo_sets_marker_and_reason(self) -> None:
        fn = getattr(self.__class__, "test_todo_sets_marker_and_reason")
        self.assertTrue(getattr(fn, "__unittest_skip__", False))
        self.assertEqual(getattr(fn, "__pyjest_todo__", False), True)
        self.assertEqual(getattr(fn, "__unittest_skip_why__", None), "TODO: pending work")


@describe.skip("skip the whole suite")
class DescribeSkipTests(unittest.TestCase):
    def test_class_skip_sets_unittest_flags(self) -> None:
        cls = self.__class__
        self.assertTrue(getattr(cls, "__unittest_skip__", False))
        self.assertEqual(getattr(cls, "__unittest_skip_why__", None), "skip the whole suite")


class OnlyDecoratorsFilterTests(unittest.TestCase):
    def test_only_filters_classes_and_methods(self) -> None:
        class Regular(unittest.TestCase):
            def test_regular(self) -> None:
                pass

        @describe.only("focused class")
        class Focused(unittest.TestCase):
            def test_focus_one(self) -> None:
                pass

        class Mixed(unittest.TestCase):
            @test.only("focused method")
            def test_focus(self) -> None:
                pass

            def test_other(self) -> None:
                pass

        suite = unittest.TestSuite(
            [
                unittest.defaultTestLoader.loadTestsFromTestCase(Regular),
                unittest.defaultTestLoader.loadTestsFromTestCase(Focused),
                unittest.defaultTestLoader.loadTestsFromTestCase(Mixed),
            ]
        )

        filtered = _apply_only_filter(suite)
        ids = {test.id() for test in _iter_tests(filtered)}

        self.assertTrue(any(identifier.endswith("Focused.test_focus_one") for identifier in ids))
        self.assertTrue(any(identifier.endswith("Mixed.test_focus") for identifier in ids))
        self.assertFalse(any(identifier.endswith("Mixed.test_other") for identifier in ids))
        self.assertFalse(any(identifier.endswith("Regular.test_regular") for identifier in ids))


class AutolabelOptionsTests(unittest.TestCase):
    @autolabel(strip_prefix="test_")
    class StripPrefix(unittest.TestCase):
        def test_with_prefix(self) -> None:
            pass

    @autolabel(title_case=True)
    class TitleCase(unittest.TestCase):
        def test_title_case_example(self) -> None:
            pass

    def test_strip_prefix_option(self) -> None:
        label = getattr(self.StripPrefix.test_with_prefix, "__pyjest_test__", None)
        self.assertEqual(label, "with prefix")

    def test_title_case_option(self) -> None:
        label = getattr(self.TitleCase.test_title_case_example, "__pyjest_test__", None)
        self.assertEqual(label, "Test Title Case Example")


if __name__ == "__main__":
    unittest.main()
