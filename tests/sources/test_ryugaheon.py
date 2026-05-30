import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.ryugaheon import _LIST_URL, RyugaheonExtractor, _extract_cards

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "ryugaheon"

_EMPTY_RSS = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel></channel></rss>'


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@respx.mock
def test_ryugaheon_extractor_parses_cards():
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text=_load_fixture("list_page_1.html"))
    )

    raws = list(RyugaheonExtractor(delay_s=0.0).crawl())
    assert len(raws) >= 1, f"expected at least 1 exhibition, got {len(raws)}"
    assert all(r.source is SourceName.RYUGAHEON for r in raws)

    by_url = {str(r.source_url): r for r in raws}
    for exp in _load_expected():
        actual = by_url.get(exp["source_url"])
        assert actual is not None, f"missing card for {exp['source_url']!r}"
        for k, v in exp["raw"].items():
            assert actual.raw.get(k) == v, (
                f"mismatch on {exp['source_url']} field {k!r}: "
                f"got {actual.raw.get(k)!r}, expected {v!r}"
            )


def _rss_with_img(img_src: str) -> str:
    desc = f'<![CDATA[<img src="{img_src}" />]]>'
    return (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
        "<item><title>테스트 전시</title>"
        "<link>https://blog.naver.com/noongamgo/123?fromRss=true</link>"
        f"<description>{desc}</description></item>"
        "</channel></rss>"
    )


def test_ryugaheon_promotes_protocol_relative_poster():
    cards = _extract_cards(_rss_with_img("//blogthumb.pstatic.net/x.jpg?type=s3"))
    assert cards[0]["poster_image_url"] == "https://blogthumb.pstatic.net/x.jpg?type=s3"


def test_ryugaheon_promotes_site_relative_poster():
    cards = _extract_cards(_rss_with_img("/img/x.jpg"))
    assert cards[0]["poster_image_url"] == "https://blog.naver.com/img/x.jpg"


def test_ryugaheon_keeps_absolute_poster():
    cards = _extract_cards(_rss_with_img("https://blogthumb.pstatic.net/x.jpg"))
    assert cards[0]["poster_image_url"] == "https://blogthumb.pstatic.net/x.jpg"


@respx.mock
def test_ryugaheon_extractor_empty_feed_yields_nothing():
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text=_EMPTY_RSS)
    )
    raws = list(RyugaheonExtractor(delay_s=0.0).crawl())
    assert raws == []
