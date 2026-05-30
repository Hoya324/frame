from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository
from crawler.sinks.upsert import UpsertEngine, UpsertReport


def test_upsert_inserts_new_rows():
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    report = engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "류가헌"}])
    assert report == UpsertReport(new=1, updated=0, unchanged=0)
    assert repo.read_rows(SheetName.VENUES) == [{"id": "v1", "name": "류가헌"}]


def test_upsert_updates_changed_rows_only():
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "류가헌"}])
    report = engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "사진위주 류가헌"}])
    assert report == UpsertReport(new=0, updated=1, unchanged=0)


def test_upsert_skips_unchanged_rows():
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "류가헌"}])
    report = engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "류가헌"}])
    assert report == UpsertReport(new=0, updated=0, unchanged=1)


def test_upsert_mixed_batch():
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    engine.upsert(SheetName.VENUES, [
        {"id": "v1", "name": "A"},
        {"id": "v2", "name": "B"},
    ])
    report = engine.upsert(SheetName.VENUES, [
        {"id": "v1", "name": "A"},       # unchanged
        {"id": "v2", "name": "B prime"}, # updated
        {"id": "v3", "name": "C"},       # new
    ])
    assert report == UpsertReport(new=1, updated=1, unchanged=1)


def test_upsert_collapses_duplicate_ids_within_batch():
    """A source can emit the same exhibition multiple times in one crawl
    (e.g. goeun's board paginates the same row). Those collapse to a single
    stored row instead of being appended N times."""
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    report = engine.upsert(SheetName.EXHIBITIONS, [
        {"id": "e1", "title": "부산 이바구"},
        {"id": "e1", "title": "부산 이바구"},
        {"id": "e1", "title": "부산 이바구"},
    ])
    assert report == UpsertReport(new=1, updated=0, unchanged=0)
    assert repo.read_rows(SheetName.EXHIBITIONS) == [{"id": "e1", "title": "부산 이바구"}]


def test_upsert_duplicate_ids_within_batch_last_wins():
    """When the same id appears twice in a batch with differing fields, the
    later occurrence wins (sources list freshest data last)."""
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    engine.upsert(SheetName.EXHIBITIONS, [
        {"id": "e1", "title": "old"},
        {"id": "e1", "title": "new"},
    ])
    assert repo.read_rows(SheetName.EXHIBITIONS) == [{"id": "e1", "title": "new"}]


def test_upsert_preserves_existing_columns_not_in_patch():
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "A", "latitude": 37.5}])
    engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "A prime"}])
    # latitude was not in the patch — must survive
    assert repo.read_rows(SheetName.VENUES)[0]["latitude"] == 37.5


def test_upsert_treats_crawled_at_only_change_as_unchanged():
    """Re-fetching an exhibition gets a fresh crawled_at every time. That
    alone must not count as 'updated' — otherwise every row on every cron
    burns a batch_update for zero data change."""
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    engine.upsert(SheetName.EXHIBITIONS, [{
        "id": "e1",
        "title": "Show",
        "crawled_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }])
    report = engine.upsert(SheetName.EXHIBITIONS, [{
        "id": "e1",
        "title": "Show",
        "crawled_at": "2026-05-29T01:00:00+00:00",   # fresh fetch
        "updated_at": "2026-05-29T01:00:00+00:00",   # fresh fetch
    }])
    assert report == UpsertReport(new=0, updated=0, unchanged=1)
    # Sheet stays at original crawled_at (no patch happened)
    stored = repo.read_rows(SheetName.EXHIBITIONS)[0]
    assert stored["crawled_at"] == "2026-01-01T00:00:00+00:00"


def test_upsert_real_change_preserves_original_crawled_at():
    """When facts actually changed and we patch, crawled_at must NOT
    jump forward — it records when we first saw this exhibition, and
    that doesn't change just because the title got tweaked."""
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    engine.upsert(SheetName.EXHIBITIONS, [{
        "id": "e1",
        "title": "Show",
        "crawled_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }])
    report = engine.upsert(SheetName.EXHIBITIONS, [{
        "id": "e1",
        "title": "Show (revised title)",                # real change
        "crawled_at": "2026-05-29T01:00:00+00:00",
        "updated_at": "2026-05-29T01:00:00+00:00",
    }])
    assert report == UpsertReport(new=0, updated=1, unchanged=0)
    stored = repo.read_rows(SheetName.EXHIBITIONS)[0]
    assert stored["title"] == "Show (revised title)"
    # crawled_at frozen at first observation
    assert stored["crawled_at"] == "2026-01-01T00:00:00+00:00"
    # updated_at moved forward to reflect when this change landed
    assert stored["updated_at"] == "2026-05-29T01:00:00+00:00"


def test_upsert_real_change_preserves_first_seen_at_for_venues():
    """Same principle for the Venues sheet: first_seen_at is sticky."""
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    engine.upsert(SheetName.VENUES, [{
        "id": "v1",
        "name": "Gallery",
        "first_seen_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }])
    engine.upsert(SheetName.VENUES, [{
        "id": "v1",
        "name": "Gallery (renamed)",
        "first_seen_at": "2026-05-29T01:00:00+00:00",   # don't trust this
        "updated_at": "2026-05-29T01:00:00+00:00",
    }])
    stored = repo.read_rows(SheetName.VENUES)[0]
    assert stored["first_seen_at"] == "2026-01-01T00:00:00+00:00"
    assert stored["updated_at"] == "2026-05-29T01:00:00+00:00"


def test_upsert_warnings_only_change_is_unchanged():
    """The _warnings bag is volatile diagnostic noise — its drift alone
    should not trigger a patch."""
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    engine.upsert(SheetName.EXHIBITIONS, [{
        "id": "e1", "title": "T", "_warnings": "",
        "crawled_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }])
    report = engine.upsert(SheetName.EXHIBITIONS, [{
        "id": "e1", "title": "T", "_warnings": "date parse fallback,fee tier missing",
        "crawled_at": "2026-05-29T01:00:00+00:00",
        "updated_at": "2026-05-29T01:00:00+00:00",
    }])
    assert report == UpsertReport(new=0, updated=0, unchanged=1)
