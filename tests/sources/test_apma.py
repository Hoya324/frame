import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources._media import media_category
from crawler.sources.apma import ApmaExtractor, _extract_cards, _parse_detail

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "apma"

_LIST_URL = "https://apma.amorepacific.com/contents/exhibition/index.do"
_DETAIL_URL_TMPL = "https://apma.amorepacific.com/contents/exhibition/{}/view.do"

# Detail fixtures captured 2026-07-20. All other cards' detail URLs are
# mocked as 404 in the crawl tests (→ title-only media gate).
_FIXTURE_IDS = ("4055621", "3951792", "3971237", "3925724")


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _mock_site() -> None:
    """Register respx routes for the list page + the three detail fixtures."""
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_load_fixture("list.html")))
    for fid in _FIXTURE_IDS:
        respx.get(_DETAIL_URL_TMPL.format(fid)).mock(
            return_value=httpx.Response(200, text=_load_fixture(f"detail_{fid}.html"))
        )
    # Every other card's detail 404s → per-item fallback (title-only gate).
    respx.route(
        method="GET",
        url__regex=r"apma\.amorepacific\.com/contents/exhibition/\d+/view\.do",
    ).mock(return_value=httpx.Response(404))


def test_extract_cards_skips_decorative_items():
    cards = _extract_cards(_load_fixture("list.html"))

    # 2026-07-20 snapshot: 10 exhibition cards; the interleaved decorative
    # li.photoLst (fixedBox badges without an <a>) must be skipped.
    assert len(cards) == 10
    first = cards[0]
    assert first["source_url"] == _DETAIL_URL_TMPL.format("4055621")
    assert first["title"] == (
        "[APMA, CHAPTER FIVE: FROM THE APMA COLLECTION] 육명심, 예술가의 초상"
    )
    # Thumbnail is lazy-loaded: URL lives in data-src, already absolute.
    assert first["poster_image_url"].startswith("https://image-apma.amorepacific.com/")


def test_parse_detail_headline_show():
    detail = _parse_detail(_load_fixture("detail_4055621.html"))
    assert detail["title"] == (
        "[APMA, CHAPTER FIVE: FROM THE APMA COLLECTION] 육명심, 예술가의 초상"
    )
    # li.place: "2026.04.01(수) – 2026.08.02(일) | 미술관 1F로비, …"
    assert detail["date_range"] == "2026.04.01~2026.08.02"
    # Prose comes from the inline `let content` JSON blob, not server HTML.
    assert "육명심" in detail["description"]
    assert len(detail["description"]) > 200


def test_media_gate_passes_via_description_strict_compound():
    # "육명심, 예술가의 초상" has no photo keyword in the title — it passes
    # only via strict compounds (사진가/사진작가) in the blob prose.
    detail = _parse_detail(_load_fixture("detail_4055621.html"))
    assert media_category(detail["title"]) is None
    assert media_category(detail["title"], detail["description"]) == "사진"


def test_media_gate_passes_via_title_broad_keyword():
    # "한국 현대사진, 멈춤과 흐름" carries the broad 사진 in the title itself.
    detail = _parse_detail(_load_fixture("detail_3951792.html"))
    assert media_category(detail["title"]) == "사진"
    assert media_category(detail["title"], detail["description"]) == "사진"


def test_media_gate_passes_video_via_paik_name_and_description():
    # "백남준과 TV 너머의 세계" — 백남준 by name is a broad video keyword, so
    # the title alone passes; the blob prose (비디오 아트/미디어 아트 strict
    # compounds) independently agrees → 영상 either way.
    detail = _parse_detail(_load_fixture("detail_3925724.html"))
    assert media_category(detail["title"]) == "영상"
    assert media_category(detail["title"], detail["description"]) == "영상"


def test_media_gate_excludes_painting_subpage():
    # "회화 속 세계들" is a painting section — no broad/strict match anywhere.
    detail = _parse_detail(_load_fixture("detail_3971237.html"))
    assert media_category(detail["title"], detail["description"]) is None


@respx.mock
def test_crawl_matches_expected():
    _mock_site()

    raws = list(ApmaExtractor(delay_s=0.0).crawl())

    assert all(r.source is SourceName.APMA for r in raws)
    by_url = {str(r.source_url): r for r in raws}
    # The painting sub-page parsed fine but must be gated out.
    assert _DETAIL_URL_TMPL.format("3971237") not in by_url

    expected = _load_expected()
    assert len(expected) >= 1  # at least one known photo show passes
    assert len(raws) == len(expected)
    for exp in expected:
        assert exp["source_url"] in by_url, (
            f"Expected URL not found: {exp['source_url']}\n"
            f"Available URLs: {list(by_url.keys())}"
        )
        actual = by_url[exp["source_url"]]
        for k, v in exp["raw"].items():
            assert actual.raw.get(k) == v, (
                f"mismatch on {exp['source_url']} field {k!r}: "
                f"got {actual.raw.get(k)!r}, expected {v!r}"
            )


@respx.mock
def test_crawl_detail_failure_falls_back_to_title_gate():
    # When every detail page fails, the crawl must still finish: cards whose
    # TITLE alone passes the gate are yielded without date/description.
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_load_fixture("list.html")))
    respx.route(
        method="GET",
        url__regex=r"apma\.amorepacific\.com/contents/exhibition/\d+/view\.do",
    ).mock(return_value=httpx.Response(404))

    raws = list(ApmaExtractor(delay_s=0.0).crawl())

    # Two titles pass on their own: 사진 (broad keyword) and 백남준 (by name).
    assert [str(r.source_url) for r in raws] == [
        _DETAIL_URL_TMPL.format("3951792"),
        _DETAIL_URL_TMPL.format("3925724"),
    ]
    by_id = {str(r.source_url): r for r in raws}
    photo = by_id[_DETAIL_URL_TMPL.format("3951792")]
    assert photo.raw["category"] == "사진"
    assert photo.raw["date_range"] is None
    assert photo.raw["description"] is None
    paik = by_id[_DETAIL_URL_TMPL.format("3925724")]
    assert paik.raw["category"] == "영상"
