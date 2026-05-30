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
