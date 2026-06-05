from crawler.masters.models import MasterSeed, RawWork, SourceQuery


def test_rawwork_has_image_true_when_image_url_present():
    w = RawWork(
        source="the_met", source_object_id="269725", title="Le Pont Neuf",
        year="1900", medium="Albumen silver print", image_url="https://x/full.jpg",
        thumb_url="https://x/small.jpg", source_url="https://x/269725",
        credit="The Met · CC0", is_public_domain=True, is_highlight=True,
    )
    assert w.has_image is True
    assert w.work_id == "the_met-269725"


def test_rawwork_has_image_false_when_no_image():
    w = RawWork(
        source="aic", source_object_id="1", title="x", year=None, medium=None,
        image_url=None, thumb_url=None, source_url="https://x/1", credit="AIC",
        is_public_domain=True, is_highlight=False,
    )
    assert w.has_image is False


def test_masterseed_explicit_ids_and_query_sources():
    seed = MasterSeed(
        id="eugene-atget", name="Eugène Atget", region="foreign", nationality="FR",
        birth_year=1857, death_year=1927, portrait_url="https://x/atget.jpg",
        sources=[
            SourceQuery(source="the_met", object_ids=["269725", "283181"]),
            SourceQuery(source="aic", query="Eugène Atget"),
        ],
    )
    assert seed.sources[0].object_ids == ["269725", "283181"]
    assert seed.sources[0].query is None
    assert seed.sources[1].query == "Eugène Atget"
    assert seed.region == "foreign"
