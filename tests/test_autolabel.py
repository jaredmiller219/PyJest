import unittest

from pyjest import autolabel, describe, test


@autolabel()
@describe("Mixing explicit labels with autolabel")
class AutolabelIntegrationTests(unittest.TestCase):
    @test("keeps the explicit label on decorated methods")
    def test_explicit_label_is_preserved(self) -> None:
        label = getattr(self.__class__.test_explicit_label_is_preserved, "__pyjest_test__", None)
        self.assertEqual(label, "keeps the explicit label on decorated methods")
        self.assertEqual(getattr(self.__class__, "__pyjest_describe__", None), "Mixing explicit labels with autolabel")

    def test_autolabeled_method(self) -> None:
        label = getattr(self.__class__.test_autolabeled_method, "__pyjest_test__", None)
        self.assertEqual(label, "test autolabeled method")

    def test_another_autolabeled_method(self) -> None:
        label = getattr(self.__class__.test_another_autolabeled_method, "__pyjest_test__", None)
        self.assertEqual(label, "test another autolabeled method")


if __name__ == "__main__":
    unittest.main()
