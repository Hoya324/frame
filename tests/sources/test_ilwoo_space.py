import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.ilwoo_space import _LIST_URL, IlwooSpaceExtractor, _parse_detail

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "ilwoo_space"

_EMPTY_HTML = "<html><body></body></html>"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@respx.mock
def test_ilwoo_space_extractor_parses_cards():
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text=_load_fixture("list_page_1.html"))
    )
    # Page 2 returns no cards — stops pagination
    respx.get(_LIST_URL, params={"com_board_page": "2", "com_board_id": "10"}).mock(
        return_value=httpx.Response(200, text=_EMPTY_HTML)
    )

    raws = list(IlwooSpaceExtractor(delay_s=0.0, with_details=False).crawl())
    assert len(raws) >= 1, f"expected at least 1 exhibition, got {len(raws)}"
    assert all(r.source is SourceName.ILWOO_SPACE for r in raws)

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
def test_ilwoo_space_decodes_euckr_despite_wrong_header():
    """The live site serves EUC-KR bytes but declares charset=utf-8 in the
    Content-Type header. Decoding by the declared charset produces U+FFFD
    mojibake, so the extractor must detect the real encoding from the bytes."""
    title = "일우사진상 수상자전 작품 모음"
    html = (
        "<html><body><table>"
        "<tr onclick=\"location.href='/default/m02/p03.php?com_board_basic="
        "read_form&com_board_idx=99&com_board_id=10'\">"
        "<td class='bbsno'>99</td>"
        "<td class='bbsnewf5'><a href=''>"
        "<a href='/default/m02/p03.php?com_board_basic=read_form"
        f"&com_board_idx=99&com_board_id=10'>{title}</a></a></td>"
        "<td class='bbsetc_add1'>2026.5. 1 ~ 2026.5.31</td>"
        "</tr></table></body></html>"
    )
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(
            200,
            content=html.encode("euc-kr"),
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
    )
    respx.get(_LIST_URL, params={"com_board_page": "2", "com_board_id": "10"}).mock(
        return_value=httpx.Response(200, text=_EMPTY_HTML)
    )

    raws = list(IlwooSpaceExtractor(delay_s=0.0, with_details=False).crawl())
    assert len(raws) == 1
    assert raws[0].raw["title"] == title
    assert "�" not in raws[0].raw["title"]


@respx.mock
def test_ilwoo_space_extractor_empty_page_yields_nothing():
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text="<html><body></body></html>")
    )
    raws = list(IlwooSpaceExtractor(delay_s=0.0, with_details=False).crawl())
    assert raws == []


def test_ilwoo_space_parse_detail_extracts_description_and_poster():
    html = _load_fixture("detail_93.html")
    info = _parse_detail(html)
    assert "일우재단" in info.get("description", "")
    assert len(info["description"]) > 200
    assert "/u_image/" in info.get("poster_image_url", "")
    assert info["poster_image_url"].startswith("https://www.ilwoo.org/")
