import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.goeun import GoeunExtractor

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "goeun"

_CURRENT_URL = "https://www.goeunmuseum.kr/bbs/board.php?bo_table=exhibition&page=1"
_UPCOMING_URL = "https://www.goeunmuseum.kr/bbs/board.php?bo_table=exhibition&page=2"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@respx.mock
def test_goeun_extractor_parses_both_pages():
    respx.get(_CURRENT_URL).mock(
        return_value=httpx.Response(200, text=_load_fixture("list_current.html"))
    )
    respx.get(_UPCOMING_URL).mock(
        return_value=httpx.Response(200, text=_load_fixture("list_upcoming.html"))
    )

    raws = list(GoeunExtractor(delay_s=0.0, max_pages=2).crawl())
    assert len(raws) >= 1, f"expected at least 1 exhibition, got {len(raws)}"
    assert all(r.source is SourceName.GOEUN for r in raws)

    by_url = {str(r.source_url): r for r in raws}
    for exp in _load_expected():
        actual = by_url.get(exp["source_url"])
        assert actual is not None, f"missing card for {exp['source_url']!r}"
        for k, v in exp["raw"].items():
            assert actual.raw.get(k) == v, (
                f"mismatch on {exp['source_url']} field {k!r}: "
                f"got {actual.raw.get(k)!r}, expected {v!r}"
            )


@respx.mock
def test_goeun_extractor_empty_pages_yield_nothing():
    empty = "<html><body></body></html>"
    respx.get(_CURRENT_URL).mock(return_value=httpx.Response(200, text=empty))
    respx.get(_UPCOMING_URL).mock(return_value=httpx.Response(200, text=empty))
    raws = list(GoeunExtractor(delay_s=0.0, max_pages=2).crawl())
    assert raws == []
