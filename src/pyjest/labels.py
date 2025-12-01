"""Lightweight helpers to label tests with Jest-style describe/test strings."""

from __future__ import annotations

from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable[..., object])
T = TypeVar("T", bound=type)


def describe(label: str) -> Callable[[T], T]:
    def decorator(cls: T) -> T:
        setattr(cls, "__pyjest_describe__", label)
        return cls

    return decorator


def test(label: str) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        setattr(fn, "__pyjest_test__", label)
        return fn

    return decorator


def autolabel(transform: Callable[[str], str] | None = None) -> Callable[[T], T]:
    """Decorator to ensure all test_* methods have a display label.

    If a method already has @test, it is left untouched. Otherwise, we assign
    __pyjest_test__ using the provided transform (default: replace '_' with ' ').
    """

    def decorator(cls: T) -> T:
        fn_transform = transform or (lambda name: name.replace("_", " "))
        for attr in dir(cls):
            if not attr.startswith("test"):
                continue
            fn = getattr(cls, attr, None)
            if not callable(fn):
                continue
            if getattr(fn, "__pyjest_test__", None):
                continue
            setattr(fn, "__pyjest_test__", fn_transform(attr))
        return cls

    return decorator
