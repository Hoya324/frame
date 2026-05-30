import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.photo_sema import PhotoSemaExtractor, _parse_detail

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "photo_sema"

_LIST_URL = (
    "https://sema.seoul.go.kr/kr/whatson/landing"
    "?whatsonMenuDivList=EX&exPlace=ORG51"
    "&whatChoice2=N&whatChoice3=N&whatChoice4=N&whatChoice5=N"
    "&whenType=FROM_TODAY"
)


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@respx.mock
def test_photo_sema_extractor_parses_photo_sema_cards():
    """Extractor parses Photo SeMA branch cards from the filtered landing page."""
    list_html = _load_fixture("list_page_1.html")
    respx.get(url__startswith="https://sema.seoul.go.kr/kr/whatson/landing").mock(
        return_value=httpx.Response(200, text=list_html)
    )

    extractor = PhotoSemaExtractor(max_pages=1, delay_s=0.0, with_details=False)
    raws = list(extractor.crawl())

    assert len(raws) >= 2, f"expected at least 2 Photo SeMA cards, got {len(raws)}"
    assert all(r.source is SourceName.PHOTO_SEMA for r in raws)

    expected = _load_expected()
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
def test_photo_sema_extractor_stops_when_page_empty():
    """Extractor stops after encountering an empty page (no cards)."""
    list_html = _load_fixture("list_page_1.html")
    call_count = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, text=list_html)
        # Subsequent pages return empty body
        return httpx.Response(200, text="<html><body></body></html>")

    # Match any GET to the landing URL (with or without currentPage param)
    respx.get(url__startswith="https://sema.seoul.go.kr/kr/whatson/landing").mock(
        side_effect=side_effect
    )

    extractor = PhotoSemaExtractor(max_pages=5, delay_s=0.0, with_details=False)
    raws = list(extractor.crawl())

    # Should stop after page 2 (empty) rather than continuing to page 5
    assert len(raws) >= 2
    assert call_count == 2, f"expected 2 GET calls, got {call_count}"


def test_photo_sema_parse_detail_extracts_description():
    html = _load_fixture("detail_1515171.html")
    desc = _parse_detail(html).get("description", "")
    assert "서울시립 사진미술관은 2026서울사진축제 《컴백홈》을 개최합니다" in desc
    assert len(desc) > 200
