"""
codedrill.extractors.base — the extractor registry.

A language extractor is any object with:
    lang: str
    extract(self, graph, *, code, module_name, source_title) -> Optional[str]   # module node id

Extractors register themselves with the `@register("lang")` class decorator. The
registry stores an *instance* (not the class) so `for_language(...)` hands the compiler
something it can call directly — `extract(...)` receives a real `self`.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

_REGISTRY: dict[str, Any] = {}


def register(lang: str) -> Callable[[type], type]:
    """Class decorator: instantiate and register an extractor under `lang`."""
    def deco(cls: type) -> type:
        _REGISTRY[lang] = cls()          # store an instance, not the class
        return cls
    return deco


def for_language(lang: str) -> Optional[Any]:
    return _REGISTRY.get(lang)


def languages() -> list[str]:
    return sorted(_REGISTRY)
