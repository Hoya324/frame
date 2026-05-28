"""Enum mapping for medium, exhibition type, venue type, fee type."""

from __future__ import annotations

from crawler.models import ExhibitionType, FeeType, Medium, OrganizerType, VenueType


def _has(haystack: str, *needles: str) -> bool:
    return any(n in haystack for n in needles)


def map_medium(text: str) -> Medium:
    t = (text or "").lower()
    photo = _has(t, "사진", "photo")
    video = _has(t, "영상", "video", "film", "movie", "미디어")
    gear = _has(t, "카메라", "camera", "장비", "기자재", "imaging")
    if photo and video:
        return Medium.MIXED
    if gear and not (photo or video):
        return Medium.GEAR
    if video and not photo:
        return Medium.VIDEO
    if photo:
        return Medium.PHOTO
    return Medium.MIXED


def map_exhibition_type(text: str) -> ExhibitionType:
    t = (text or "").lower()
    if _has(t, "개인전", "solo"):
        return ExhibitionType.SOLO
    if _has(t, "단체전", "group"):
        return ExhibitionType.GROUP
    if _has(t, "페스티벌", "festival"):
        return ExhibitionType.FESTIVAL
    if _has(t, "박람회", "expo", "fair", "show"):
        return ExhibitionType.EXPO
    if _has(t, "상설", "permanent"):
        return ExhibitionType.PERMANENT
    if _has(t, "기획", "curated"):
        return ExhibitionType.CURATED
    return ExhibitionType.CURATED


def map_venue_type(text: str) -> VenueType:
    t = (text or "").lower()
    if _has(t, "미술관", "museum"):
        return VenueType.MUSEUM
    if _has(t, "갤러리", "gallery"):
        return VenueType.GALLERY
    if _has(t, "coex", "kintex", "컨벤션", "convention", "센터"):
        return VenueType.CONVENTION
    if _has(t, "카페", "cafe"):
        return VenueType.CAFE
    if _has(t, "대안공간", "alt space", "스페이스"):
        return VenueType.ALT_SPACE
    return VenueType.OTHER


def map_organizer_type(text: str) -> OrganizerType:
    t = (text or "").lower()
    if _has(t, "미술관"):
        return OrganizerType.MUSEUM
    if _has(t, "갤러리"):
        return OrganizerType.GALLERY
    if _has(t, "재단", "foundation"):
        return OrganizerType.FOUNDATION
    if _has(t, "협회", "association"):
        return OrganizerType.ASSOCIATION
    if _has(t, "주식회사", "corp", "inc", "ltd"):
        return OrganizerType.CORPORATE
    if _has(t, "시청", "공사", "공단", "정부", "구청"):
        return OrganizerType.PUBLIC
    return OrganizerType.OTHER


def map_fee_type(
    text: str | None,
    price_min: int | None,
    price_max: int | None,
) -> FeeType:
    t = (text or "").lower()
    if _has(t, "일부 유료", "partial"):
        return FeeType.PARTIAL
    if _has(t, "무료", "free"):
        return FeeType.FREE
    if price_min is not None and price_max is not None:
        if price_min == 0 and price_max > 0:
            return FeeType.PARTIAL
        if price_min > 0:
            return FeeType.PAID
        return FeeType.FREE
    return FeeType.FREE
