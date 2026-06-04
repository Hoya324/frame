from crawler.masters.cache import CommentaryCache, LocalizedText


def test_put_get_roundtrip(tmp_path):
    path = tmp_path / "c.json"
    cache = CommentaryCache(path)
    val = LocalizedText(ko="가", en="a", ja="あ")
    cache.put("the_met-1", "hash1", val)
    cache.save()

    reloaded = CommentaryCache(path)
    assert reloaded.get("the_met-1", "hash1") == val


def test_get_miss_on_changed_facts_hash(tmp_path):
    cache = CommentaryCache(tmp_path / "c.json")
    cache.put("k", "hashA", LocalizedText(ko="x", en="x", ja="x"))
    assert cache.get("k", "hashB") is None  # facts changed → regenerate


def test_clear_empties_cache(tmp_path):
    path = tmp_path / "c.json"
    cache = CommentaryCache(path)
    cache.put("k", "h", LocalizedText(ko="x", en="x", ja="x"))
    cache.clear()
    assert cache.get("k", "h") is None
