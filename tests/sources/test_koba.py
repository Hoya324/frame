import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.koba import KobaExtractor

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "koba"
_INFO_URL = "https://conference.kobashow.com/kor/about/info.asp"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@respx.mock
def test_koba_extractor_parses_current_edition():
    info_html = _load_fixture("list_page_1.html")
    respx.get(_INFO_URL).mock(return_value=httpx.Response(200, text=info_html))

    extractor = KobaExtractor(delay_s=0.0)
    raws = list(extractor.crawl())

    # KOBA produces 1 row per edition — tolerance assertion as per plan
    assert len(raws) >= 1, f"expected at least 1 row, got {len(raws)}"
    assert all(r.source is SourceName.KOBA for r in raws)

    expected = _load_expected()
    by_url = {str(r.source_url): r for r in raws}
    for exp in expected:
        actual = by_url[exp["source_url"]]
        for k, v in exp["raw"].items():
            assert actual.raw.get(k) == v, (
                f"mismatch on {exp['source_url']} field {k!r}: "
                f"got {actual.raw.get(k)!r}, expected {v!r}"
            )

    # Description is pulled from the info page's intro paragraphs.
    desc = raws[0].raw.get("description", "")
    assert "KOBA 전시회" in desc
    assert len(desc) > 200


@respx.mock
def test_koba_extractor_handles_empty_page():
    """If the info page returns no parseable exhibition data, crawl yields nothing."""
    respx.get(_INFO_URL).mock(
        return_value=httpx.Response(200, text="<html><body><p>준비중</p></body></html>")
    )

    extractor = KobaExtractor(delay_s=0.0)
    raws = list(extractor.crawl())
    assert raws == []
