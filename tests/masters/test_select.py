from crawler.masters.models import MasterSeed, RawWork, SourceQuery
from crawler.masters.select import select_works


def _work(oid, source="the_met", pd=True, img="https://x/i.jpg", highlight=False, year="1900"):
    return RawWork(
        source=source, source_object_id=oid, title=f"t{oid}", year=year, medium="m",
        image_url=img, thumb_url=img, source_url=f"https://x/{oid}", credit="c",
        is_public_domain=pd, is_highlight=highlight,
    )


class FakeClient:
    def __init__(self, source, by_id=None, by_query=None):
        self.source = source
        self._by_id = by_id or {}
        self._by_query = by_query or []

    def fetch_by_ids(self, ids):
        return [self._by_id[i] for i in ids if i in self._by_id]

    def search_works(self, query, limit):
        return self._by_query[:limit]


def test_explicit_ids_preserved_in_order_and_filtered():
    seed = MasterSeed(
        id="m", name="M", region="foreign", nationality="US", birth_year=None,
        death_year=None, portrait_url=None,
        sources=[SourceQuery(source="the_met", object_ids=["2", "1", "bad"])],
    )
    client = FakeClient("the_met", by_id={
        "1": _work("1"), "2": _work("2"), "bad": _work("bad", pd=False),
    })
    works = select_works(seed, {"the_met": client}, cap=10)
    assert [w.source_object_id for w in works] == ["2", "1"]  # order kept, non-PD dropped


def test_query_results_ranked_highlight_first_and_capped():
    seed = MasterSeed(
        id="m", name="M", region="foreign", nationality="US", birth_year=None,
        death_year=None, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="M")],
    )
    client = FakeClient("the_met", by_query=[
        _work("a", highlight=False), _work("b", highlight=True), _work("c", highlight=False),
    ])
    works = select_works(seed, {"the_met": client}, cap=2)
    assert works[0].source_object_id == "b"  # highlight ranked first
    assert len(works) == 2


def test_dedupes_same_work_id_across_sources():
    seed = MasterSeed(
        id="m", name="M", region="foreign", nationality="US", birth_year=None,
        death_year=None, portrait_url=None,
        sources=[SourceQuery(source="the_met", object_ids=["1"]),
                 SourceQuery(source="the_met", query="M")],
    )
    client = FakeClient("the_met", by_id={"1": _work("1")}, by_query=[_work("1")])
    works = select_works(seed, {"the_met": client}, cap=10)
    assert len(works) == 1
