"""Base extractor protocol + registry of installed sources."""

from __future__ import annotations

from typing import Iterable, Protocol, Type

from crawler.models import RawExhibition, SourceName


class SourceExtractor(Protocol):
    name: SourceName

    def crawl(self) -> Iterable[RawExhibition]: ...


_REGISTRY: dict[SourceName, Type[SourceExtractor]] = {}


def register_source(name: SourceName, cls: Type[SourceExtractor]) -> None:
    _REGISTRY[name] = cls


def get_source(name: SourceName) -> Type[SourceExtractor]:
    if name not in _REGISTRY:
        raise KeyError(f"source not registered: {name.value}")
    return _REGISTRY[name]


def all_sources() -> dict[SourceName, Type[SourceExtractor]]:
    return dict(_REGISTRY)
