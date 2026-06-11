"""Data shapes for the masters pipeline: a candidate work from a museum API,
and a curated roster seed describing where to pull a master's works from."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RawWork:
    """One candidate work returned by a museum client, pre-selection."""

    source: str  # museum source key, e.g. "the_met"
    source_object_id: str  # the museum's own object id
    title: str
    year: str | None
    medium: str | None
    image_url: str | None  # full/large hosted image (CC0)
    thumb_url: str | None  # smaller variant for grids/carousels
    source_url: str  # museum object page
    credit: str  # attribution / license line
    is_public_domain: bool
    is_highlight: bool = False

    @property
    def has_image(self) -> bool:
        return bool(self.image_url)

    @property
    def work_id(self) -> str:
        return f"{self.source}-{self.source_object_id}"


@dataclass(frozen=True)
class SourceQuery:
    """Where to pull one master's works from a single museum. Provide
    ``object_ids`` to hand-pick exact iconic works (preferred), OR ``query`` to
    auto-pull by artist search. Exactly one of the two should be set.

    ``artist`` overrides the artist-match needle for query searches; without it
    clients fall back to the query's last token, which breaks for queries like
    "Percival Lowell Korea" (needle would be "Korea")."""

    source: str
    query: str | None = None
    object_ids: list[str] | None = None
    artist: str | None = None


@dataclass(frozen=True)
class MasterSeed:
    """A curated master and the museum sources for their works."""

    id: str  # stable kebab-case slug
    name: str  # original-language display name
    region: str  # "kr" | "jp" | "modern" | "foreign"
    nationality: str  # ISO 3166-1 alpha-2
    birth_year: int | None
    death_year: int | None
    portrait_url: str | None  # PD portrait (Wikimedia), curated here
    sources: list[SourceQuery] = field(default_factory=list)
    # Case-insensitive title substrings to drop at select time — for works
    # whose subject or period caption doesn't fit the app's tone.
    exclude_titles: list[str] = field(default_factory=list)
