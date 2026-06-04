"""Enum mapping for medium, exhibition type, venue type, fee type."""

from __future__ import annotations

from crawler.models import ExhibitionType, FeeType, Medium, OrganizerType, VenueType


def _has(haystack: str, *needles: str) -> bool:
    return any(n in haystack for n in needles)


def map_medium(text: str) -> Medium:
    t = (text or "").lower()
    photo = _has(t, "사진", "photo", "写真", "フォト")
    video = _has(t, "영상", "video", "film", "movie", "미디어", "映像", "動画")
    gear = _has(t, "카메라", "camera", "장비", "기자재", "imaging", "カメラ", "機材")
    if photo and video:
        return Medium.MIXED
    if gear and not (photo or video):
        return Medium.GEAR
    if video and not photo:
        return Medium.VIDEO
    if photo:
        return Medium.PHOTO
    return Medium.MIXED


# High-precision solo/group phrases that are safe to detect inside a free-form
# exhibition *title* (unlike the broad "show"/"fair"/"solo" substrings below,
# which would false-positive on artwork titles). 個展 = JP solo show; 2인전/3인전
# = KR two-/three-person shows.
_SOLO_TITLE = ("개인전", "個展", "solo exhibition", "solo show")
_GROUP_TITLE = (
    "단체전",
    "그룹전",
    "2인전",
    "3인전",
    "group exhibition",
    "group show",
)


def map_exhibition_type(
    text: str,
    *,
    title: str | None = None,
    artist_count: int | None = None,
) -> ExhibitionType:
    """Classify an exhibition's type.

    Precedence: (1) the controlled ``exhibition_type_text`` field, where broad
    keywords like "show"/"fair" are unambiguous; (2) high-precision phrases in
    the free-form ``title`` (개인전/個展 → solo, 단체전 → group); (3) the artist
    count as a fallback (1 → solo, ≥2 → group). Defaults to curated.
    """
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

    # The type-text field carried no signal; fall back to the title's
    # high-precision phrases, then to the artist count.
    tt = (title or "").lower()
    if _has(tt, *_SOLO_TITLE):
        return ExhibitionType.SOLO
    if _has(tt, *_GROUP_TITLE):
        return ExhibitionType.GROUP
    if artist_count == 1:
        return ExhibitionType.SOLO
    if artist_count is not None and artist_count >= 2:
        return ExhibitionType.GROUP
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
