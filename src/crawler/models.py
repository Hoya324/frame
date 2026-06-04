"""Pydantic models and enums shared across the pipeline."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SourceName(StrEnum):
    ARTMAP = "artmap"
    NAVER = "naver"
    PHOTO_SEMA = "photo_sema"
    MUSEUM_HANMI = "museum_hanmi"
    KOBA = "koba"
    GOEUN = "goeun"
    GALLERY_LUX = "gallery_lux"
    GALLERY_KONG = "gallery_kong"
    RYUGAHEON = "ryugaheon"
    ILWOO_SPACE = "ilwoo_space"
    SANGSANGMADANG = "sangsangmadang"
    CANON_GALLERY = "canon_gallery"
    TOKYO_PHOTOGRAPHIC_ART_MUSEUM = "tokyo_photographic_art_museum"
    TOKYO_ART_BEAT = "tokyo_art_beat"
    FUJIFILM_SQUARE = "fujifilm_square"
    GALLERY_BRESSON = "gallery_bresson"
    PGI = "pgi"
    ZEN_FOTO = "zen_foto"
    PLACE_M = "place_m"


class Medium(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"
    GEAR = "gear"
    MIXED = "mixed"


class ExhibitionType(StrEnum):
    SOLO = "solo"
    GROUP = "group"
    CURATED = "curated"
    FESTIVAL = "festival"
    EXPO = "expo"
    PERMANENT = "permanent"


class FeeType(StrEnum):
    FREE = "free"
    PAID = "paid"
    PARTIAL = "partial"


class VenueType(StrEnum):
    MUSEUM = "museum"
    GALLERY = "gallery"
    CAFE = "cafe"
    ALT_SPACE = "alt_space"
    CONVENTION = "convention"
    OTHER = "other"


class OrganizerType(StrEnum):
    MUSEUM = "museum"
    GALLERY = "gallery"
    FOUNDATION = "foundation"
    ASSOCIATION = "association"
    CORPORATE = "corporate"
    PUBLIC = "public"
    OTHER = "other"


class Status(StrEnum):
    UPCOMING = "upcoming"
    ONGOING = "ongoing"
    PAST = "past"
    UNKNOWN = "unknown"


class PriceTier(BaseModel):
    """One line of an exhibition's price table (e.g. `성인: 10,000원`)."""

    model_config = ConfigDict(extra="forbid")

    label: str
    amount: int


class RawExhibition(BaseModel):
    """Raw payload from a source extractor. All semantic fields are in `raw`."""

    model_config = ConfigDict(extra="forbid")

    source: SourceName
    source_url: HttpUrl
    raw: dict = Field(default_factory=dict)


class NormalizedExhibition(BaseModel):
    """Post-normalization, before/after entity resolution."""

    model_config = ConfigDict(extra="forbid")

    id: str
    source: SourceName
    source_url: HttpUrl

    title: str
    title_en: str | None = None
    description: str | None = None
    poster_image_url: HttpUrl | None = None

    medium: Medium
    exhibition_type: ExhibitionType
    genre_tags: list[str] = Field(default_factory=list)
    fee_type: FeeType = FeeType.FREE
    price_min: int | None = None
    price_max: int | None = None
    price_breakdown: list[PriceTier] = Field(default_factory=list)
    price_notes: str | None = None
    activities: list[str] = Field(default_factory=list)

    start_date: date | None = None
    end_date: date | None = None
    open_hours: str | None = None

    artist_raw_names: list[str] = Field(default_factory=list)
    venue_raw_name: str | None = None
    venue_raw_region: str | None = None
    venue_raw_address: str | None = None
    venue_raw_lat: float | None = None
    venue_raw_lng: float | None = None
    organizer_raw_name: str | None = None

    artist_ids: list[str] = Field(default_factory=list)
    venue_id: str = ""
    organizer_id: str = ""

    popularity_score: float | None = None
    featured: bool = False

    status: Status = Status.UNKNOWN
    crawled_at: datetime
    updated_at: datetime
    warnings: list[str] = Field(default_factory=list)


class Artist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    name_en: str | None = None
    name_normalized: str
    bio: str | None = None
    instagram: HttpUrl | None = None
    website: HttpUrl | None = None
    sources: list[str] = Field(default_factory=list)
    first_seen_at: datetime
    updated_at: datetime


class Venue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    name_en: str | None = None
    venue_type: VenueType = VenueType.OTHER
    region: str | None = None
    district: str | None = None
    address: str | None = None
    country: str = "KR"
    latitude: float | None = None
    longitude: float | None = None
    website: HttpUrl | None = None
    open_hours_default: str | None = None
    sources: list[str] = Field(default_factory=list)
    first_seen_at: datetime
    updated_at: datetime


class Organizer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    name_en: str | None = None
    name_normalized: str
    organizer_type: OrganizerType = OrganizerType.OTHER
    website: HttpUrl | None = None
    sources: list[str] = Field(default_factory=list)
    first_seen_at: datetime
    updated_at: datetime
