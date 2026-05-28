"""Base extractor protocol + registry of installed sources."""

from __future__ import annotations

from collections.abc import Iterable
from typing import ClassVar, Protocol

from crawler.models import RawExhibition, SourceName


class SourceExtractor(Protocol):
    name: SourceName
    country: ClassVar[str]  # ISO 3166-1 alpha-2; defaults to "KR" via pipeline fallback

    def crawl(self) -> Iterable[RawExhibition]: ...


_REGISTRY: dict[SourceName, type[SourceExtractor]] = {}


def register_source(name: SourceName, cls: type[SourceExtractor]) -> None:
    _REGISTRY[name] = cls


def get_source(name: SourceName) -> type[SourceExtractor]:
    if name not in _REGISTRY:
        raise KeyError(f"source not registered: {name.value}")
    return _REGISTRY[name]


def all_sources() -> dict[SourceName, type[SourceExtractor]]:
    return dict(_REGISTRY)
