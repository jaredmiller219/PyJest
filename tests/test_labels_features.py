import unittest

from pyjest import autolabel, describe, test
from pyjest.discovery import _apply_only_filter, _iter_tests


@describe("Skip and todo decorators")
class SkipAndTodoDecoratorTests(unittest.TestCase):
    @test("marks skip flags with default reason")
    def test_skip_sets_unittest_flags(self) -> None:
        @test.skip("skip this one")
        def fn():
            pass

        self.assertEqual(getattr(fn, "__pyjest_test__", None), "skip this one")
        self.assertTrue(getattr(fn, "__unittest_skip__", False))
        self.assertEqual(getattr(fn, "__unittest_skip_why__", None), "skip this one")

    @test("respects custom skip reason when provided")
    def test_skip_with_custom_reason(self) -> None:
        @test.skip("skip this one", "custom reason")
        def fn():
            pass

        self.assertEqual(getattr(fn, "__pyjest_test__", None), "skip this one")
        self.assertTrue(getattr(fn, "__unittest_skip__", False))
        self.assertEqual(getattr(fn, "__unittest_skip_why__", None), "custom reason")

    @test("falsy skip reason falls back to label")
    def test_skip_with_empty_reason(self) -> None:
        @test.skip("skip this one", "")
        def fn():
            pass

        self.assertEqual(getattr(fn, "__pyjest_test__", None), "skip this one")
        self.assertTrue(getattr(fn, "__unittest_skip__", False))
        # Empty reason falls back to label because decorators treat falsy reason as missing.
        self.assertEqual(getattr(fn, "__unittest_skip_why__", None), "skip this one")

    @test("only sets focus flag without skipping")
    def test_only_sets_only_flag(self) -> None:
        @test.only("focus this")
        def fn():
            pass

        self.assertEqual(getattr(fn, "__pyjest_test__", None), "focus this")
        self.assertTrue(getattr(fn, "__pyjest_only__", False))
        self.assertFalse(getattr(fn, "__unittest_skip__", False))

    @test("todo marks skip with TODO reason")
    def test_todo_sets_marker_and_reason(self) -> None:
        @test.todo("pending work")
        def fn():
            pass

        self.assertEqual(getattr(fn, "__pyjest_test__", None), "pending work")
        self.assertTrue(getattr(fn, "__unittest_skip__", False))
        self.assertEqual(getattr(fn, "__pyjest_todo__", False), True)
        self.assertEqual(getattr(fn, "__unittest_skip_why__", None), "TODO: pending work")


@describe("Describe decorators")
class DescribeSkipTests(unittest.TestCase):
    @test("class skip sets unittest flags")
    def test_class_skip_sets_unittest_flags(self) -> None:
        @describe.skip("skip the whole suite")
        class cls(unittest.TestCase):
            pass

        self.assertEqual(getattr(cls, "__pyjest_describe__", None), "skip the whole suite")
        self.assertTrue(getattr(cls, "__unittest_skip__", False))
        self.assertEqual(getattr(cls, "__unittest_skip_why__", None), "skip the whole suite")

    @test("class skip honors custom reason")
    def test_class_skip_with_custom_reason(self) -> None:
        @describe.skip("skip the whole suite", "custom class reason")
        class cls(unittest.TestCase):
            pass

        self.assertEqual(getattr(cls, "__pyjest_describe__", None), "skip the whole suite")
        self.assertTrue(getattr(cls, "__unittest_skip__", False))
        self.assertEqual(getattr(cls, "__unittest_skip_why__", None), "custom class reason")

    @test("class only sets focus flag")
    def test_class_only_sets_flag(self) -> None:
        @describe.only("focused suite")
        class cls(unittest.TestCase):
            pass

        self.assertEqual(getattr(cls, "__pyjest_describe__", None), "focused suite")
        self.assertTrue(getattr(cls, "__pyjest_only__", False))
        self.assertFalse(getattr(cls, "__unittest_skip__", False))

    @test("class skip default reason matches label")
    def test_class_skip_default_reason_uses_label(self) -> None:
        @describe.skip("label only")
        class cls(unittest.TestCase):
            pass

        self.assertEqual(getattr(cls, "__unittest_skip__", False), True)
        self.assertEqual(getattr(cls, "__unittest_skip_why__", None), "label only")


@describe("Only filter handling")
class OnlyDecoratorsFilterTests(unittest.TestCase):
    @test("filters in only-labeled tests and classes")
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


@describe("Autolabel options")
class AutolabelOptionsTests(unittest.TestCase):
    @autolabel(strip_prefix="test_")
    class StripPrefix(unittest.TestCase):
        def test_with_prefix(self) -> None:
            pass

    @autolabel(title_case=True)
    class TitleCase(unittest.TestCase):
        def test_title_case_example(self) -> None:
            pass

    @test("strip_prefix trims test_ prefix")
    def test_strip_prefix_option(self) -> None:
        label = getattr(self.StripPrefix.test_with_prefix, "__pyjest_test__", None)
        self.assertEqual(label, "with prefix")

    @test("title_case turns underscores into title case")
    def test_title_case_option(self) -> None:
        label = getattr(self.TitleCase.test_title_case_example, "__pyjest_test__", None)
        self.assertEqual(label, "Test Title Case Example")

    @test("title_case and strip_prefix combine")
    def test_autolabel_title_case_with_prefix(self) -> None:
        @autolabel(strip_prefix="test_", title_case=True)
        class TitleAndStrip(unittest.TestCase):
            def test_title_me(self) -> None:
                pass

        self.assertEqual(getattr(TitleAndStrip.test_title_me, "__pyjest_test__", None), "Title Me")

    @test("non-test attributes remain untouched")
    def test_autolabel_leaves_non_tests_untouched(self) -> None:
        @autolabel()
        class NonTests(unittest.TestCase):
            helper_value = 1

            def not_a_test(self) -> None:
                pass

        self.assertEqual(NonTests.helper_value, 1)
        self.assertIsNone(getattr(NonTests, "__pyjest_test__", None))
        self.assertIsNone(getattr(NonTests.not_a_test, "__pyjest_test__", None))

    @test("non-callable test_* attributes stay unchanged")
    def test_autolabel_leaves_non_callable_test_prefix_attrs(self) -> None:
        @autolabel()
        class HasData(unittest.TestCase):
            test_value = 7

        self.assertEqual(getattr(HasData, "test_value", None), 7)
        self.assertFalse(hasattr(HasData, "test_value__pyjest_test__"))

    @test("existing labels are preserved")
    def test_autolabel_preserves_existing_label(self) -> None:
        class AlreadyLabeled(unittest.TestCase):
            @test("custom label")
            def test_already(self) -> None:
                pass

        decorated = autolabel()(AlreadyLabeled)
        self.assertEqual(getattr(decorated.test_already, "__pyjest_test__", None), "custom label")

    @test("custom transform is applied")
    def test_autolabel_uses_custom_transform(self) -> None:
        def transform(name: str) -> str:
            return f"X-{name}"

        @autolabel(transform)
        class CustomTransform(unittest.TestCase):
            def test_special_case(self) -> None:
                pass

        self.assertEqual(getattr(CustomTransform.test_special_case, "__pyjest_test__", None), "X-test_special_case")

    @test("multiple prefixes strip in order")
    def test_autolabel_multiple_prefixes(self) -> None:
        @autolabel(strip_prefix=("test_it_", "test_"))
        class MultiPrefix(unittest.TestCase):
            def test_first_prefix(self) -> None:
                pass

            def test_it_second_prefix(self) -> None:
                pass

        self.assertEqual(getattr(MultiPrefix.test_first_prefix, "__pyjest_test__", None), "first prefix")
        self.assertEqual(getattr(MultiPrefix.test_it_second_prefix, "__pyjest_test__", None), "second prefix")

    @test("no prefix match leaves original name minus underscores")
    def test_autolabel_no_prefix_match_keeps_name(self) -> None:
        @autolabel(strip_prefix="does_not_match")
        class NoStrip(unittest.TestCase):
            def test_keep_prefix(self) -> None:
                pass

        self.assertEqual(getattr(NoStrip.test_keep_prefix, "__pyjest_test__", None), "test keep prefix")


if __name__ == "__main__":
    unittest.main()
