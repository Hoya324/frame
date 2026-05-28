from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository


def test_fake_starts_empty():
    repo = FakeRepository()
    assert repo.read_rows(SheetName.EXHIBITIONS) == []


def test_fake_append_and_read():
    repo = FakeRepository()
    repo.append_rows(SheetName.ARTISTS, [{"id": "a1", "name": "김작가"}])
    rows = repo.read_rows(SheetName.ARTISTS)
    assert rows == [{"id": "a1", "name": "김작가"}]


def test_fake_patch_by_id():
    repo = FakeRepository()
    repo.append_rows(SheetName.VENUES, [{"id": "v1", "name": "류가헌"}])
    repo.patch_rows(SheetName.VENUES, [{"id": "v1", "name": "사진위주 류가헌"}])
    rows = repo.read_rows(SheetName.VENUES)
    assert rows == [{"id": "v1", "name": "사진위주 류가헌"}]


def test_fake_patch_unknown_id_raises():
    import pytest

    repo = FakeRepository()
    with pytest.raises(KeyError):
        repo.patch_rows(SheetName.VENUES, [{"id": "missing", "name": "x"}])


def test_fake_patch_preserves_unmentioned_fields():
    """Regression: a partial patch must NOT wipe unmentioned columns.

    Earlier the gspread implementation reused `_serialize_row(headers, r)`,
    which filled missing keys with "", so backfill-geocodes sending
    `{id, latitude, longitude}` blew away `name`/`first_seen_at` on every
    geocoded venue. Both implementations now share true partial-patch
    semantics — this test pins the contract for both.
    """
    repo = FakeRepository()
    repo.append_rows(SheetName.VENUES, [{
        "id": "v1",
        "name": "류가헌",
        "first_seen_at": "2026-05-01T00:00:00+00:00",
        "updated_at": "2026-05-01T00:00:00+00:00",
    }])
    repo.patch_rows(SheetName.VENUES, [{
        "id": "v1",
        "latitude": 37.5,
        "longitude": 127.0,
    }])
    rows = repo.read_rows(SheetName.VENUES)
    assert rows == [{
        "id": "v1",
        "name": "류가헌",
        "first_seen_at": "2026-05-01T00:00:00+00:00",
        "updated_at": "2026-05-01T00:00:00+00:00",
        "latitude": 37.5,
        "longitude": 127.0,
    }]
