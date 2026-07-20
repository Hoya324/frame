"""Tests for the shared photo/film/media keyword gate."""

from crawler.sources._media import media_category


def test_broad_photo_keyword_in_short_text():
    assert media_category("한국 현대사진, 멈춤과 흐름") == "사진"
    assert media_category("포토 페스티벌 2026") == "사진"


def test_broad_video_keywords_in_short_text():
    assert media_category("2026 서울국제실험영화페스티벌") == "영상"
    assert media_category("필름앤비디오 기획전") == "영상"
    assert media_category("미디어 설치 작업을 선보이는 전시") == "영상"
    # Nam June Paik by name is video art, in either language.
    assert media_category("백남준과 TV 너머의 세계") == "영상"
    assert media_category("Nam June Paik: Megatron") == "영상"


def test_both_families_yield_mixed_seed():
    assert media_category("사진과 영상 사이") == "사진 영상"


def test_non_media_short_text_is_dropped():
    assert media_category("한국 근현대 회화의 흐름") is None
    assert media_category("도자기와 조각") is None


def test_latin_keywords_are_word_bounded():
    # Embedded substrings must not trigger the gate…
    assert media_category("Photosynthesis: Botanical Paintings") is None
    assert media_category("Immediate Presence") is None
    assert media_category("Confilmed") is None
    # …but real word forms still do.
    assert media_category("Contemporary Photography Now") == "사진"
    assert media_category("Video Art Now") == "영상"
    assert media_category("Moving Images from Asia") == "영상"


def test_strict_tier_promotes_from_long_prose():
    # Bare "사진" in prose is NOT enough ("사진 촬영 가능" is everywhere)…
    assert media_category("무제", "전시장 내 사진 촬영이 가능합니다.") is None
    # …but compound terms are.
    assert media_category("무제", "1세대 사진가의 연작을 조망한다.") == "사진"
    assert media_category("무제", "대형 영상 설치 작업이 중심이다.") == "영상"
    assert media_category("무제", "백남준의 비디오 아트 유산을 잇는다.") == "영상"


def test_long_prose_alone_never_uses_broad_tier():
    # A broad keyword that only appears in prose must not pass.
    assert media_category("무제", "행사 영상 스케치가 홈페이지에 게시됩니다.") is None


def test_empty_inputs():
    assert media_category("") is None
    assert media_category("", None) is None
