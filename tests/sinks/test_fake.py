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
