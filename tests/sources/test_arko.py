import json
from datetime import date
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.arko import ArkoExtractor, _extract_cards, _is_current_or_upcoming

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "arko"

_LIST_URL = "https://www.arko.or.kr/artcenter/board/list/506?bid=266"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _mock_site(detail_status: int = 200) -> None:
    respx.get(url__startswith=_LIST_URL).mock(
        return_value=httpx.Response(200, text=_load_fixture("list_page_1.html"))
    )
    respx.get(url__regex=r".*board/view/506.*cid=717239.*").mock(
        return_value=httpx.Response(detail_status, text=_load_fixture("detail_717239.html"))
    )
    # Every other (past) show's detail is irrelevant — the date filter drops
    # those cards before any detail fetch.
    respx.get(url__regex=r".*board/view/506.*").mock(return_value=httpx.Response(404))


def test_extract_cards_parses_board_fields():
    cards = _extract_cards(_load_fixture("list_page_1.html"))

    assert len(cards) == 6
    first = cards[0]
    assert first["title"] == "《어긋난 파동, 흔들리는 시간: 오민, 카밀 노먼트》"
    assert first["date_range"] == "2026-05-22 ~ 2026-07-19"
    assert first["fee_text"] == "무료"
    assert first["artists"] == ["오민", "카밀 노먼트"]
    # Canonical detail URL rebuilt from the numeric cid.
    assert first["source_url"] == (
        "https://www.arko.or.kr/artcenter/board/view/506?bid=266&cid=717239"
    )
    assert first["venue_name"] == "아르코미술관"


def test_date_filter_current_vs_past():
    rng = "2026-05-22 ~ 2026-07-19"
    assert _is_current_or_upcoming(rng, date(2026, 7, 1)) is True  # still on
    assert _is_current_or_upcoming(rng, date(2026, 7, 19)) is True  # last day
    assert _is_current_or_upcoming(rng, date(2026, 7, 20)) is False  # ended
    assert _is_current_or_upcoming("2026-08-01 ~ 2026-09-01", date(2026, 7, 1)) is True
    assert _is_current_or_upcoming(None, date(2026, 7, 1)) is False
    assert _is_current_or_upcoming("일정 미정", date(2026, 7, 1)) is False


@respx.mock
def test_crawl_current_video_show_passes_media_gate():
    # With the 오민/카밀 노먼트 show still running, it is the only current card
    # and its detail prose carries video compounds → one 영상 yield.
    _mock_site()

    raws = list(ArkoExtractor(delay_s=0.0, today=date(2026, 7, 1)).crawl())

    assert len(raws) == 1
    (item,) = raws
    assert item.source is SourceName.ARKO
    assert item.raw["title"] == "《어긋난 파동, 흔들리는 시간: 오민, 카밀 노먼트》"
    assert item.raw["category"] == "영상"
    assert item.raw["description"]


@respx.mock
def test_crawl_matches_expected_on_recon_date():
    # expected.jsonl was generated at recon (2026-07-20): the last show ended
    # 07-19 and nothing else is current → zero yields, by the date filter.
    _mock_site()

    raws = list(ArkoExtractor(delay_s=0.0, today=date(2026, 7, 20)).crawl())

    assert [json.loads(json.dumps({"source": r.source.value})) for r in raws] == [
        {"source": e["source"]} for e in _load_expected()
    ]
    assert raws == []


@respx.mock
def test_crawl_survives_detail_failure():
    # Detail 404 → no description; the title alone has no media keyword, so
    # the show is gated out rather than crashing the crawl.
    _mock_site(detail_status=404)

    raws = list(ArkoExtractor(delay_s=0.0, today=date(2026, 7, 1)).crawl())

    assert raws == []
