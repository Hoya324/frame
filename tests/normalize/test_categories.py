import pytest

from crawler.models import ExhibitionType, FeeType, Medium, VenueType
from crawler.normalize.categories import (
    map_exhibition_type,
    map_fee_type,
    map_medium,
    map_venue_type,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("사진전", Medium.PHOTO),
        ("Photography", Medium.PHOTO),
        ("영상", Medium.VIDEO),
        ("video art", Medium.VIDEO),
        ("카메라 박람회", Medium.GEAR),
        ("camera show", Medium.GEAR),
        ("사진/영상", Medium.MIXED),
        ("写真展", Medium.PHOTO),
        ("フォトグラフ", Medium.PHOTO),
        ("映像作品", Medium.VIDEO),
        ("動画", Medium.VIDEO),
        ("写真と映像", Medium.MIXED),
        ("カメラ機材展", Medium.GEAR),
    ],
)
def test_map_medium(text: str, expected: Medium):
    assert map_medium(text) is expected


def test_map_medium_falls_back_to_mixed_on_unknown():
    assert map_medium("???") is Medium.MIXED


@pytest.mark.parametrize(
    "text, expected",
    [
        ("개인전", ExhibitionType.SOLO),
        ("Solo Exhibition", ExhibitionType.SOLO),
        ("단체전", ExhibitionType.GROUP),
        ("기획전", ExhibitionType.CURATED),
        ("페스티벌", ExhibitionType.FESTIVAL),
        ("박람회", ExhibitionType.EXPO),
        ("상설전", ExhibitionType.PERMANENT),
    ],
)
def test_map_exhibition_type(text: str, expected: ExhibitionType):
    assert map_exhibition_type(text) is expected


def test_map_exhibition_type_defaults_to_curated():
    assert map_exhibition_type("???") is ExhibitionType.CURATED


@pytest.mark.parametrize(
    "text, expected",
    [
        ("미술관", VenueType.MUSEUM),
        ("갤러리", VenueType.GALLERY),
        ("Gallery", VenueType.GALLERY),
        ("COEX", VenueType.CONVENTION),
        ("카페", VenueType.CAFE),
        ("대안공간", VenueType.ALT_SPACE),
    ],
)
def test_map_venue_type(text: str, expected: VenueType):
    assert map_venue_type(text) is expected


def test_map_venue_type_other_for_unknown():
    assert map_venue_type("호텔") is VenueType.OTHER


def test_map_fee_type_free():
    assert map_fee_type("무료", None, None) is FeeType.FREE


def test_map_fee_type_paid():
    assert map_fee_type(None, 5000, 5000) is FeeType.PAID


def test_map_fee_type_partial():
    assert map_fee_type("일부 유료", 0, 10000) is FeeType.PARTIAL


@pytest.mark.parametrize(
    "title, expected",
    [
        ("손모아 개인전 <단편의 조각들>", ExhibitionType.SOLO),  # KR solo in title
        ("原直久 個展「柘榴」", ExhibitionType.SOLO),  # JP 個展 = solo
        ("변웅필 개인전", ExhibitionType.SOLO),
        ("청춘 단체전", ExhibitionType.GROUP),
        # A free-form art title containing 'show' must NOT be read as an EXPO —
        # broad keywords apply only to the controlled type-text field.
        ("The Show Must Go On", ExhibitionType.CURATED),
        ("西成", ExhibitionType.CURATED),  # bare title, no signal
    ],
)
def test_map_exhibition_type_from_title(title: str, expected: ExhibitionType):
    assert map_exhibition_type("", title=title) is expected


@pytest.mark.parametrize(
    "artist_count, expected",
    [
        (1, ExhibitionType.SOLO),
        (2, ExhibitionType.GROUP),
        (5, ExhibitionType.GROUP),
        (0, ExhibitionType.CURATED),
        (None, ExhibitionType.CURATED),
    ],
)
def test_map_exhibition_type_artist_count_fallback(
    artist_count, expected: ExhibitionType
):
    assert map_exhibition_type("", artist_count=artist_count) is expected


def test_map_exhibition_type_text_keyword_beats_artist_count():
    # An explicit '단체전' in type-text wins even if only one artist is listed.
    assert (
        map_exhibition_type("단체전", artist_count=1) is ExhibitionType.GROUP
    )
