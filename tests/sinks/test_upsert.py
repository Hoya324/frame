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


def test_upsert_preserves_existing_columns_not_in_patch():
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "A", "latitude": 37.5}])
    engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "A prime"}])
    # latitude was not in the patch — must survive
    assert repo.read_rows(SheetName.VENUES)[0]["latitude"] == 37.5
