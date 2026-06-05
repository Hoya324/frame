from datetime import UTC, datetime

from crawler.masters.cache import LocalizedText
from crawler.masters.models import MasterSeed, RawWork, SourceQuery


class FakeWriter:
    def master_text(self, seed):
        return LocalizedText(
            ko=f"{seed.name} 소개", en=f"about {seed.name}", ja=f"{seed.name} 紹介",
            ko_tagline=f"{seed.name} 태그",
            en_tagline=f"{seed.name} tag",
            ja_tagline=f"{seed.name} タグ",
        )

    def work_text(self, work, master_name):
        return LocalizedText(
            ko=f"{work.title} 해설",
            en=f"about {work.title}",
            ja=f"{work.title} 解説",
        )


class FakeClient:
    source = "the_met"

    def fetch_by_ids(self, ids):
        return [RawWork(source="the_met", source_object_id=i, title=f"W{i}", year="1900",
                        medium="Albumen", image_url=f"https://x/{i}.jpg",
                        thumb_url=f"https://x/{i}_t.jpg", source_url=f"https://x/{i}",
                        credit="Met · CC0", is_public_domain=True) for i in ids]

    def search_works(self, query, limit):
        return []


def _roster():
    return [MasterSeed(id="atget", name="Eugène Atget", region="foreign", nationality="FR",
                       birth_year=1857, death_year=1927, portrait_url="https://x/a.jpg",
                       sources=[SourceQuery(source="the_met", object_ids=["1"])])]


def test_build_masters_shape():
    from crawler.masters.build import build_masters

    cat = build_masters(
        roster=_roster(), clients={"the_met": FakeClient()}, writer=FakeWriter(),
        generated_at=datetime(2026, 6, 5, tzinfo=UTC), cap=10,
    )
    assert cat["generated_at"].startswith("2026-06-05")
    m = cat["masters"][0]
    assert m["id"] == "atget"
    assert m["name"] == "Eugène Atget"
    assert m["lang"] == "ko"
    assert m["region"] == "foreign"
    assert m["bio"] == "Eugène Atget 소개"  # ko flat
    assert m["tr"]["en"]["bio"] == "about Eugène Atget"
    assert m["tr"]["ja"]["bio"] == "Eugène Atget 紹介"
    assert m["portraitUrl"] == "https://x/a.jpg"

    w = m["works"][0]
    assert w["id"] == "the_met-1"
    assert w["imageUrl"] == "https://x/1.jpg"
    assert w["commentary"] == "W1 해설"  # ko flat
    assert w["tr"]["en"]["commentary"] == "about W1"
    assert w["credit"] == "Met · CC0"


def test_build_masters_drops_master_with_no_works():
    from crawler.masters.build import build_masters

    class Empty(FakeClient):
        def fetch_by_ids(self, ids):
            return []

    cat = build_masters(roster=_roster(), clients={"the_met": Empty()},
                        writer=FakeWriter(), generated_at=datetime(2026, 6, 5, tzinfo=UTC))
    assert cat["masters"] == []  # a master with zero usable works is omitted
