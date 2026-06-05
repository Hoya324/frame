from crawler.masters.cache import CommentaryCache
from crawler.masters.commentary import CommentaryWriter
from crawler.masters.models import MasterSeed, RawWork


class FakeGemini:
    def __init__(self):
        self.generate_calls = 0

    def generate(self, prompt, *, temperature=0.4):
        self.generate_calls += 1
        return "한국어 본문"

    def translate_batch(self, jobs):
        # jobs: list[(text, src, tgt)] -> echo with a target marker
        return [f"{tgt}:{text}" for (text, _src, tgt) in jobs]


def _seed():
    return MasterSeed(id="atget", name="Eugène Atget", region="foreign",
                      nationality="FR", birth_year=1857, death_year=1927,
                      portrait_url=None, sources=[])


def _work():
    return RawWork(source="the_met", source_object_id="1", title="Le Pont Neuf",
                   year="1900", medium="Albumen", image_url="https://x/i.jpg",
                   thumb_url="https://x/t.jpg", source_url="https://x/1",
                   credit="Met", is_public_domain=True)


def test_master_text_generates_ko_then_translates(tmp_path):
    g = FakeGemini()
    w = CommentaryWriter(g, CommentaryCache(tmp_path / "c.json"))
    out = w.master_text(_seed())
    assert g.generate_calls == 2  # bio + tagline
    assert out.ko == "한국어 본문"
    assert out.ko_tagline == "한국어 본문"
    assert out.en == "en:한국어 본문"


def test_master_text_cached_second_call_skips_generation(tmp_path):
    g = FakeGemini()
    cache = CommentaryCache(tmp_path / "c.json")
    w = CommentaryWriter(g, cache)
    w.master_text(_seed())
    first = g.generate_calls
    w.master_text(_seed())  # same facts → cache hit
    assert g.generate_calls == first  # no extra generation


def test_work_text_generates_and_translates(tmp_path):
    g = FakeGemini()
    w = CommentaryWriter(g, CommentaryCache(tmp_path / "c.json"))
    out = w.work_text(_work(), master_name="Eugène Atget")
    assert out.ko == "한국어 본문"
    assert out.en.startswith("en:")


class FailingGemini:
    def generate(self, prompt, *, temperature=0.4):
        raise RuntimeError("429 Too Many Requests")

    def translate_batch(self, jobs):
        raise RuntimeError("429 Too Many Requests")


def test_generation_failure_returns_empty_not_cached(tmp_path):
    # A quota/network failure on one item must not crash the build: the item
    # comes back empty and is NOT cached, so a recovered run retries it.
    cache = CommentaryCache(tmp_path / "c.json")
    w = CommentaryWriter(FailingGemini(), cache)

    out = w.work_text(_work(), master_name="Eugène Atget")
    assert out.ko == "" and out.en == "" and out.ja == ""
    assert cache.get(f"work:{_work().work_id}", "any") is None  # not cached

    mt = w.master_text(_seed())
    assert mt.ko == "" and mt.ko_tagline == ""

    # A subsequent successful engine fills it in (proves the empty wasn't cached).
    g = FakeGemini()
    w2 = CommentaryWriter(g, cache)
    out2 = w2.work_text(_work(), master_name="Eugène Atget")
    assert out2.ko == "한국어 본문"
