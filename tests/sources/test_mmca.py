import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.normalize.dates import parse_date_range
from crawler.sources.mmca import MmcaExtractor, _parse_artists, _parse_record

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "mmca"

_AJAX_URL = "https://www.mmca.go.kr/exhibitions/AjaxExhibitionList.do"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _mock_pages() -> None:
    """Route the AJAX endpoint to per-(flag, page) fixture files."""
    fixtures = {
        ("1", "1"): "list_flag1_page1.json",
        ("1", "2"): "list_flag1_page2.json",
        ("2", "1"): "list_flag2_page1.json",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.url.params["exhFlag"], request.url.params["pageIndex"])
        name = fixtures.get(key)
        if name is None:
            return httpx.Response(
                200,
                json={"exhibitionsList": [], "paginationInfo": {"totalPageCount": 1}},
            )
        return httpx.Response(200, text=_load_fixture(name))

    respx.get(url__startswith=_AJAX_URL).mock(side_effect=handler)


@respx.mock
def test_mmca_extractor_keeps_only_photo_media_shows():
    """20 fixture records (13 ongoing + 7 upcoming) → only the 2 media shows.

    MMCA is a general art museum; the shared photo/film/media gate must drop
    painting/sculpture shows and keep 필름앤비디오 + media-installation ones.
    """
    _mock_pages()

    extractor = MmcaExtractor(delay_s=0.0)
    raws = list(extractor.crawl())

    assert all(r.source is SourceName.MMCA for r in raws)

    titles = {r.raw["title"] for r in raws}
    # Painting-heavy shows must be filtered out.
    assert "이것은 개념미술이 (아니)다" not in titles
    assert "MMCA 과천 상설전 «한국근현대미술 I»" not in titles

    expected = _load_expected()
    assert len(raws) == len(expected)
    by_url = {str(r.source_url): r for r in raws}
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
def test_mmca_extractor_paginates_and_dedupes():
    """Flag 1 spans 2 pages (13 records) and flag 2 one page — all visited."""
    _mock_pages()

    extractor = MmcaExtractor(delay_s=0.0)
    list(extractor.crawl())

    visited = {
        (c.request.url.params["exhFlag"], c.request.url.params["pageIndex"])
        for c in respx.calls
    }
    assert visited == {("1", "1"), ("1", "2"), ("2", "1")}


@respx.mock
def test_mmca_date_range_parses_downstream():
    """The emitted ISO date_range must resolve via parse_date_range."""
    _mock_pages()

    extractor = MmcaExtractor(delay_s=0.0)
    for r in extractor.crawl():
        start, end = parse_date_range(r.raw["date_range"])
        assert start is not None and end is not None, r.raw["date_range"]
        assert start <= end


def test_mmca_parse_artists_headcounts_and_rosters():
    assert _parse_artists("-") == []
    assert _parse_artists("9인") == []
    assert _parse_artists("73명") == []
    assert _parse_artists("장 클로드 루소") == ["장 클로드 루소"]
    assert _parse_artists("김환기, 유영국 등 78여 명") == ["김환기", "유영국"]
    assert _parse_artists("곽인식, 남화연 등 40여 명") == ["곽인식", "남화연"]
    # 팀-counted tails are stripped too; names containing 등/명 survive.
    assert _parse_artists("김철수, 이영희 등 3팀") == ["김철수", "이영희"]
    assert _parse_artists("홍등명, 이외수") == ["홍등명", "이외수"]


def test_mmca_parse_record_admission_variants():
    base = {
        "exhTitle": "사진전 테스트",
        "exhCd": "전시",
        "exhTpCd": "기획전시",
        "exhThemewd": "",
        "exhContentsSumm": "",
        "exhContents": "",
        "exhStDt": "2026-01-01",
        "exhEdDt": "2026-02-01",
        "exhPlaNm": "서울",
        "exhThumbImg": "",
        "exhArtist": "-",
    }
    free = _parse_record({**base, "exhAdm": "0"})
    assert free is not None and free["fee_text"] == "무료"

    paid = _parse_record({**base, "exhAdm": "과천관통합권 3,000원"})
    assert paid is not None
    assert paid["price_min"] == 3000 and paid["price_max"] == 3000
    assert "fee_text" not in paid

    unspecified = _parse_record({**base, "exhAdm": "-"})
    assert unspecified is not None
    assert "fee_text" not in unspecified and "price_min" not in unspecified


def test_mmca_parse_record_drops_non_media():
    rec = {
        "exhTitle": "한국 근현대 회화전",
        "exhCd": "전시",
        "exhTpCd": "기획전시",
        "exhThemewd": "회화,근대",
        "exhContentsSumm": "근대 회화의 흐름을 조망하는 전시",
        "exhContents": "<p>회화 작품을 선보인다. 사진 촬영이 가능하다.</p>",
        "exhStDt": "2026-01-01",
        "exhEdDt": "2026-02-01",
        "exhPlaNm": "서울",
        "exhAdm": "0",
        "exhThumbImg": "",
        "exhArtist": "-",
    }
    # "사진 촬영" in the long body must NOT pass the strict tier.
    assert _parse_record(rec) is None
