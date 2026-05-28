from crawler.models import SourceName
from crawler.sources.base import all_sources

# Naver is BLOCKED in M3 (see docs/sources/naver.md), so it is intentionally
# absent from the registered set. Add it back when M3.5/v1.5 ships Naver.
_EXPECTED_REGISTERED_P0 = {
    SourceName.ARTMAP,
    SourceName.PHOTO_SEMA,
    SourceName.MUSEUM_HANMI,
    SourceName.KOBA,
}


def test_all_completed_p0_sources_registered():
    registered = set(all_sources().keys())
    missing = _EXPECTED_REGISTERED_P0 - registered
    assert not missing, f"missing registrations: {missing}"


def test_all_extractors_have_required_interface():
    for source_name, cls in all_sources().items():
        assert hasattr(cls, "name"), f"{cls.__name__} missing 'name'"
        assert cls.name == source_name, f"{cls.__name__} name mismatch"
        instance = cls()
        assert callable(getattr(instance, "crawl", None)), \
            f"{cls.__name__} missing crawl()"


def test_naver_explicitly_not_registered_in_m3():
    """Documents the M3 BLOCKED decision. Remove this test when Naver ships."""
    assert SourceName.NAVER not in all_sources(), \
        "Naver should be BLOCKED until v1.5 Open API integration"
