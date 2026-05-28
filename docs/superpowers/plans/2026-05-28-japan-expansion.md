# Japan Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add country-aware Venue + Google Maps geocoder + two Japanese sources (TOP, Tokyo Art Beat) so the crawler ships first non-Korean data without disrupting any existing source.

**Architecture:** `Venue` gets a `country` string column (default `"KR"`). Extractors declare a `country` class attribute. Pipeline stamps the extractor's country onto every brand-new Venue. A new `GeocoderResolver` dispatches `(query, country)` to `KakaoGeocoder` (KR) or the new `GoogleMapsGeocoder` (JP). Sheet migration is automatic via `init-sheets` prefix-append. Two new sources (`tokyo_photographic_art_museum`, `tokyo_art_beat`) ride the same Extractor pattern as artmap/koba.

**Tech Stack:** Python 3.12+, pydantic v2, httpx, selectolax, tenacity, typer, gspread, freezegun, pytest, respx. New external dep: Google Maps Geocoding API (HTTPS, no SDK — plain httpx GET).

**Spec:** [docs/superpowers/specs/2026-05-28-japan-expansion-design.md](../specs/2026-05-28-japan-expansion-design.md)

**Branching strategy** (matches Korean expansion precedent):
- This plan ships as **three PRs** off `main`:
  - **PR-A** — infra (Tasks 1–14): country field, geocoder, resolver, dates, wiring
  - **PR-B** — TOP source (Tasks 15–20)
  - **PR-C** — TAB source (Tasks 21–28)
- After spec+plan branch (`spec/japan-expansion`) merges to `main`, cut each PR branch from `main`. Run `pytest -q` + `ruff check` at the end of every task before committing.

**Prerequisite (user, one-time):** Enable Google Maps Geocoding API on the `allphoto-crawler` GCP project, create an API key, and add it to the `Hoya324/allphoto` repo as the `GOOGLE_MAPS_API_KEY` GitHub Secret. Without it the workflow run-all will fail to build the geocoder. Implementation can still proceed locally with a dummy key (tests mock the HTTP layer).

---

## PR-A: Infrastructure

### Task 1: Add `country` field to Venue model

**Files:**
- Modify: `src/crawler/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models.py` (anywhere after the existing Venue tests):

```python
def test_venue_country_defaults_to_KR():
    from datetime import datetime, UTC
    from crawler.models import Venue
    v = Venue(
        id="v_test",
        name="Test Venue",
        first_seen_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert v.country == "KR"


def test_venue_country_can_be_overridden():
    from datetime import datetime, UTC
    from crawler.models import Venue
    v = Venue(
        id="v_test",
        name="Test Venue",
        country="JP",
        first_seen_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert v.country == "JP"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_models.py::test_venue_country_defaults_to_KR -v`
Expected: FAIL — `AttributeError` or `extra fields not permitted` (Venue has no `country`).

- [ ] **Step 3: Add `country` field**

Edit `src/crawler/models.py` — in the `Venue` class, add `country` between `address` and `latitude`:

```python
class Venue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    name_en: str | None = None
    venue_type: VenueType = VenueType.OTHER
    region: str | None = None
    district: str | None = None
    address: str | None = None
    country: str = "KR"
    latitude: float | None = None
    longitude: float | None = None
    website: HttpUrl | None = None
    open_hours_default: str | None = None
    sources: list[str] = Field(default_factory=list)
    first_seen_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_models.py -v`
Expected: PASS for both new tests, all existing model tests still pass.

- [ ] **Step 5: Commit**

```bash
git add src/crawler/models.py tests/test_models.py
git commit -m "feat(models): add Venue.country with KR default"
```

---

### Task 2: Persist `country` to Venues sheet

**Files:**
- Modify: `src/crawler/sinks/init_sheets.py:35-39` (VENUES header list)
- Modify: `src/crawler/pipeline.py` (`_venue_row` and `_venue_from_row`)
- Modify: `tests/sinks/test_init_sheets.py` (verify country in headers)
- Modify: `tests/test_pipeline.py` (round-trip a JP venue)

- [ ] **Step 1: Add column to HEADERS**

Edit `src/crawler/sinks/init_sheets.py`, change the `VENUES` entry from:

```python
    SheetName.VENUES: [
        "id", "name", "name_en", "venue_type", "region", "district",
        "address", "latitude", "longitude", "website", "open_hours_default",
        "sources", "first_seen_at", "updated_at",
    ],
```

to (append `country` at the end so existing sheets prefix-append it):

```python
    SheetName.VENUES: [
        "id", "name", "name_en", "venue_type", "region", "district",
        "address", "latitude", "longitude", "website", "open_hours_default",
        "sources", "first_seen_at", "updated_at",
        # Added 2026-05-28 (japan expansion). Existing sheets get this
        # appended via _plan_header_write's prefix-append branch.
        "country",
    ],
```

- [ ] **Step 2: Write the failing test for `_venue_from_row`**

Add to `tests/test_pipeline.py`:

```python
def test_venue_from_row_defaults_country_to_KR():
    from datetime import datetime, UTC
    from crawler.pipeline import _venue_from_row
    row = {
        "id": "v_kr",
        "name": "Existing Korean Venue",
        "venue_type": "gallery",
        "first_seen_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        # no "country" column — legacy row from before migration
    }
    v = _venue_from_row(row)
    assert v is not None
    assert v.country == "KR"


def test_venue_from_row_reads_country_when_present():
    from datetime import datetime, UTC
    from crawler.pipeline import _venue_from_row
    row = {
        "id": "v_jp",
        "name": "東京都写真美術館",
        "venue_type": "museum",
        "country": "JP",
        "first_seen_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    v = _venue_from_row(row)
    assert v is not None
    assert v.country == "JP"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_pipeline.py::test_venue_from_row_defaults_country_to_KR -v`
Expected: FAIL — country is not in the row dict so the constructor uses the Pydantic default; this part actually passes by accident. The second test will fail because `_venue_from_row` doesn't read the `country` key today. Run both — expect at least one FAIL.

- [ ] **Step 4: Update `_venue_from_row` to read country**

Edit `src/crawler/pipeline.py`, in `_venue_from_row`, change the Venue construction to include country (slot it in next to `address`):

Locate:

```python
    return Venue(
        id=row_id,
        name=name,
        name_en=_opt_s(r.get("name_en")),
        venue_type=VenueType(_s(r.get("venue_type")) or "other"),
        region=_opt_s(r.get("region")),
        district=_opt_s(r.get("district")),
        address=_opt_s(r.get("address")),
        latitude=_parse_float(r.get("latitude")),
```

Insert `country=_s(r.get("country")) or "KR",` right after `address`:

```python
    return Venue(
        id=row_id,
        name=name,
        name_en=_opt_s(r.get("name_en")),
        venue_type=VenueType(_s(r.get("venue_type")) or "other"),
        region=_opt_s(r.get("region")),
        district=_opt_s(r.get("district")),
        address=_opt_s(r.get("address")),
        country=_s(r.get("country")) or "KR",
        latitude=_parse_float(r.get("latitude")),
```

- [ ] **Step 5: Update `_venue_row` to serialize country**

In `src/crawler/pipeline.py`, in `_venue_row`, add `"country": v.country,` next to `"address"`:

```python
def _venue_row(v: Venue) -> dict:
    return {
        "id": v.id, "name": v.name, "name_en": v.name_en or "",
        "venue_type": v.venue_type.value, "region": v.region or "",
        "district": v.district or "", "address": v.address or "",
        "country": v.country,
        "latitude": v.latitude if v.latitude is not None else "",
        "longitude": v.longitude if v.longitude is not None else "",
        "website": str(v.website) if v.website else "",
        "open_hours_default": v.open_hours_default or "",
        "sources": ",".join(v.sources),
        "first_seen_at": v.first_seen_at.isoformat(),
        "updated_at": v.updated_at.isoformat(),
    }
```

- [ ] **Step 6: Update init-sheets test**

Edit `tests/sinks/test_init_sheets.py` to add:

```python
def test_init_sheets_venues_includes_country():
    repo = _RecordingRepo()
    init_sheets(repo)
    assert "country" in repo.headers[SheetName.VENUES]
    # country must be last so prefix-append migration is safe on legacy sheets.
    assert repo.headers[SheetName.VENUES][-1] == "country"
```

- [ ] **Step 7: Run all tests**

Run: `PYTHONPATH=src .venv/bin/pytest -q`
Expected: all PASS including the four new tests (`test_venue_country_defaults_to_KR`, `test_venue_country_can_be_overridden`, `test_venue_from_row_defaults_country_to_KR`, `test_venue_from_row_reads_country_when_present`, `test_init_sheets_venues_includes_country`).

- [ ] **Step 8: Commit**

```bash
git add src/crawler/sinks/init_sheets.py src/crawler/pipeline.py \
        tests/sinks/test_init_sheets.py tests/test_pipeline.py
git commit -m "feat(sinks): persist Venue.country to sheets, default KR for legacy rows"
```

---

### Task 3: Create GoogleMapsGeocoder

**Files:**
- Create: `src/crawler/enrich/geocoder_google.py`
- Create: `tests/enrich/test_geocoder_google.py`

- [ ] **Step 1: Write the failing test**

Create `tests/enrich/test_geocoder_google.py`:

```python
"""GoogleMapsGeocoder unit tests via respx mock of the HTTPS endpoint."""

from __future__ import annotations

import httpx
import pytest
import respx

from crawler.enrich.geocoder_google import GoogleMapsGeocoder

_URL = "https://maps.googleapis.com/maps/api/geocode/json"


@respx.mock
def test_geocode_returns_lat_lng_on_ok():
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "OK",
                "results": [
                    {"geometry": {"location": {"lat": 35.6438, "lng": 139.7138}}}
                ],
            },
        )
    )
    g = GoogleMapsGeocoder(api_key="fake-key")
    lat, lng = g.geocode("東京都目黒区三田1-13-3")
    assert lat == pytest.approx(35.6438)
    assert lng == pytest.approx(139.7138)


@respx.mock
def test_geocode_returns_none_none_on_zero_results():
    respx.get(_URL).mock(
        return_value=httpx.Response(200, json={"status": "ZERO_RESULTS", "results": []})
    )
    g = GoogleMapsGeocoder(api_key="fake-key")
    assert g.geocode("nonsense address") == (None, None)


@respx.mock
def test_geocode_returns_none_none_on_quota_exhausted():
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200,
            json={"status": "OVER_QUERY_LIMIT", "results": [], "error_message": "..."},
        )
    )
    g = GoogleMapsGeocoder(api_key="fake-key")
    assert g.geocode("any query") == (None, None)


@respx.mock
def test_geocode_returns_none_none_on_empty_query():
    g = GoogleMapsGeocoder(api_key="fake-key")
    assert g.geocode("") == (None, None)
    assert g.geocode("   ") == (None, None)


@respx.mock
def test_geocode_sends_region_and_language_params():
    route = respx.get(_URL).mock(
        return_value=httpx.Response(200, json={"status": "ZERO_RESULTS", "results": []})
    )
    g = GoogleMapsGeocoder(api_key="fake-key")
    g.geocode("六本木")
    sent = route.calls.last.request
    assert "region=jp" in str(sent.url)
    assert "language=ja" in str(sent.url)
    assert "address=" in str(sent.url)
    assert "key=fake-key" in str(sent.url)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/enrich/test_geocoder_google.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'crawler.enrich.geocoder_google'`.

- [ ] **Step 3: Write GoogleMapsGeocoder**

Create `src/crawler/enrich/geocoder_google.py`:

```python
"""Google Maps Geocoding API geocoder.

Returns (lat, lng) on OK, (None, None) on anything else (ZERO_RESULTS,
OVER_QUERY_LIMIT, REQUEST_DENIED, INVALID_REQUEST, UNKNOWN_ERROR).

Tenacity retry covers transient httpx errors only — quota signals come
back as HTTP 200 with `status` in the JSON body, which we treat as
"no match" rather than retrying, since retrying inside the source loop
would just burn quota faster.
"""

from __future__ import annotations

import os

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

_URL = "https://maps.googleapis.com/maps/api/geocode/json"


class GoogleMapsGeocoder:
    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self._key = api_key
        self._client = httpx.Client(timeout=timeout)

    @classmethod
    def from_env(cls) -> GoogleMapsGeocoder:
        return cls(api_key=os.environ["GOOGLE_MAPS_API_KEY"])

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get(self, params: dict) -> dict:
        r = self._client.get(_URL, params=params)
        r.raise_for_status()
        return r.json()

    def geocode(self, query: str) -> tuple[float | None, float | None]:
        if not query or not query.strip():
            return None, None
        data = self._get({
            "address": query,
            "key": self._key,
            "region": "jp",
            "language": "ja",
        })
        if data.get("status") != "OK":
            return None, None
        results = data.get("results") or []
        if not results:
            return None, None
        loc = results[0]["geometry"]["location"]
        return float(loc["lat"]), float(loc["lng"])

    def close(self) -> None:
        self._client.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/enrich/test_geocoder_google.py -v`
Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crawler/enrich/geocoder_google.py tests/enrich/test_geocoder_google.py
git commit -m "feat(enrich): GoogleMapsGeocoder for Japanese addresses"
```

---

### Task 4: Create GeocoderResolver

**Files:**
- Create: `src/crawler/enrich/geocoder_resolver.py`
- Create: `tests/enrich/test_geocoder_resolver.py`

- [ ] **Step 1: Write the failing test**

Create `tests/enrich/test_geocoder_resolver.py`:

```python
"""GeocoderResolver dispatches geocode(query, country) to the right backend."""

from __future__ import annotations

from crawler.enrich.geocoder_resolver import GeocoderResolver


class _FakeGeocoder:
    def __init__(self, lat: float, lng: float):
        self._lat, self._lng = lat, lng
        self.calls: list[str] = []

    def geocode(self, query: str) -> tuple[float | None, float | None]:
        self.calls.append(query)
        return self._lat, self._lng


def test_resolver_routes_KR_to_kakao():
    kakao = _FakeGeocoder(37.5, 127.0)
    google = _FakeGeocoder(35.6, 139.7)
    r = GeocoderResolver(kakao=kakao, google=google)

    assert r.geocode("서울특별시 종로구", country="KR") == (37.5, 127.0)
    assert kakao.calls == ["서울특별시 종로구"]
    assert google.calls == []


def test_resolver_routes_JP_to_google():
    kakao = _FakeGeocoder(37.5, 127.0)
    google = _FakeGeocoder(35.6, 139.7)
    r = GeocoderResolver(kakao=kakao, google=google)

    assert r.geocode("東京都目黒区", country="JP") == (35.6, 139.7)
    assert google.calls == ["東京都目黒区"]
    assert kakao.calls == []


def test_resolver_defaults_unspecified_country_to_KR():
    """Backward compat: legacy callers without country land on Kakao."""
    kakao = _FakeGeocoder(37.5, 127.0)
    google = _FakeGeocoder(35.6, 139.7)
    r = GeocoderResolver(kakao=kakao, google=google)

    assert r.geocode("서울특별시 종로구") == (37.5, 127.0)
    assert kakao.calls == ["서울특별시 종로구"]


def test_resolver_unknown_country_falls_back_to_KR_geocoder():
    """An unrecognized country (e.g. 'TW' before TW geocoder ships) still
    geocodes via the default, with a no-match outcome being normal."""
    kakao = _FakeGeocoder(37.5, 127.0)
    google = _FakeGeocoder(35.6, 139.7)
    r = GeocoderResolver(kakao=kakao, google=google)

    lat, lng = r.geocode("台北市", country="TW")
    assert (lat, lng) == (37.5, 127.0)  # routed to kakao default
    assert kakao.calls == ["台北市"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/enrich/test_geocoder_resolver.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write GeocoderResolver**

Create `src/crawler/enrich/geocoder_resolver.py`:

```python
"""Per-country geocoder dispatch.

Keeps a country → backend table. Unknown countries fall back to the
KR backend (Kakao); a (None, None) outcome there is just "no match" and
the pipeline handles that case by saving the venue without coordinates.
"""

from __future__ import annotations

from typing import Protocol


class _GeocoderBackend(Protocol):
    def geocode(self, query: str) -> tuple[float | None, float | None]: ...


class GeocoderResolver:
    def __init__(self, kakao: _GeocoderBackend, google: _GeocoderBackend) -> None:
        self._kakao = kakao
        self._google = google
        self._by_country: dict[str, _GeocoderBackend] = {
            "KR": kakao,
            "JP": google,
        }

    def geocode(
        self,
        query: str,
        country: str = "KR",
    ) -> tuple[float | None, float | None]:
        backend = self._by_country.get(country, self._kakao)
        return backend.geocode(query)

    def close(self) -> None:
        # Both backends expose .close(); guard for fakes in tests.
        for backend in (self._kakao, self._google):
            close = getattr(backend, "close", None)
            if callable(close):
                close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/enrich/test_geocoder_resolver.py -v`
Expected: all 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crawler/enrich/geocoder_resolver.py tests/enrich/test_geocoder_resolver.py
git commit -m "feat(enrich): GeocoderResolver dispatches by venue.country"
```

---

### Task 5: Extend Extractor protocol with `country`

**Files:**
- Modify: `src/crawler/sources/base.py`
- Modify: `src/crawler/pipeline.py` (Extractor protocol mirror)

- [ ] **Step 1: Add `country` to base protocol**

Edit `src/crawler/sources/base.py`:

```python
"""Base extractor protocol + registry of installed sources."""

from __future__ import annotations

from collections.abc import Iterable
from typing import ClassVar, Protocol

from crawler.models import RawExhibition, SourceName


class SourceExtractor(Protocol):
    name: SourceName
    country: ClassVar[str]    # ISO 3166-1 alpha-2; classes default to "KR"

    def crawl(self) -> Iterable[RawExhibition]: ...


_REGISTRY: dict[SourceName, type[SourceExtractor]] = {}


def register_source(name: SourceName, cls: type[SourceExtractor]) -> None:
    _REGISTRY[name] = cls


def get_source(name: SourceName) -> type[SourceExtractor]:
    if name not in _REGISTRY:
        raise KeyError(f"source not registered: {name.value}")
    return _REGISTRY[name]


def all_sources() -> dict[SourceName, type[SourceExtractor]]:
    return dict(_REGISTRY)
```

Country is not added to existing Korean extractor classes — they inherit nothing, but the Pipeline reads `getattr(extractor, "country", "KR")` so an unset attribute resolves to KR.

- [ ] **Step 2: Update Pipeline Extractor protocol mirror**

`src/crawler/pipeline.py` declares its own minimal Extractor protocol on lines 29–32. Update it:

```python
class Extractor(Protocol):
    name: SourceName
    country: ClassVar[str]

    def crawl(self) -> Iterable[RawExhibition]: ...
```

Add `from typing import ClassVar, Protocol` (or merge into existing typing import).

- [ ] **Step 3: Run tests to verify nothing broke**

Run: `PYTHONPATH=src .venv/bin/pytest -q`
Expected: all PASS (no behavior change yet — protocols are structural).

- [ ] **Step 4: Commit**

```bash
git add src/crawler/sources/base.py src/crawler/pipeline.py
git commit -m "feat(sources): extend Extractor protocol with country class attr"
```

---

### Task 6: Pipeline stamps `country` on new venues + routes geocoder

**Files:**
- Modify: `src/crawler/pipeline.py:35-37` (GeocoderProto) and `:152-165` (new venue loop)
- Modify: `tests/test_pipeline.py` (extractor with country=JP stamps venue)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline.py`:

```python
@freeze_time("2026-05-28")
def test_run_source_stamps_country_on_new_venues(
    header_repo: FakeHeaderRepo,
    null_geocoder: NullGeocoder,
):
    """A JP extractor's new venues land in the sheet with country=JP."""

    class _JpExtractor:
        name = SourceName.ARTMAP  # any registered name is fine for the test
        country = "JP"

        def crawl(self):
            yield RawExhibition(
                source=SourceName.ARTMAP,
                source_url="https://example.jp/exhibition/1",
                raw={
                    "title": "Tokyo Test Show",
                    "venue_name": "Tokyo Test Museum",
                    "venue_address": "東京都目黒区三田1-13-3",
                    "artists": ["Hiroshi Sugimoto"],
                    "date_range": "2026.06.01 ~ 2026.07.01",
                    "fee_text": "무료",
                    "exhibition_type_text": "개인전",
                },
            )

    report = run_source(
        extractor=_JpExtractor(),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )
    assert report.failure is None

    venues = header_repo.read_rows(SheetName.VENUES)
    jp_venues = [v for v in venues if v["name"] == "Tokyo Test Museum"]
    assert len(jp_venues) == 1
    assert jp_venues[0]["country"] == "JP"


@freeze_time("2026-05-28")
def test_run_source_passes_country_to_geocoder(header_repo: FakeHeaderRepo):
    """Geocoder receives the extractor's country so the resolver can dispatch."""

    received: list[tuple[str, str]] = []

    class _RecordingGeocoder:
        def geocode(self, query: str, country: str = "KR") -> tuple[float | None, float | None]:
            received.append((query, country))
            return 35.6, 139.7

    class _JpExtractor:
        name = SourceName.ARTMAP
        country = "JP"

        def crawl(self):
            yield RawExhibition(
                source=SourceName.ARTMAP,
                source_url="https://example.jp/exhibition/2",
                raw={
                    "title": "X",
                    "venue_name": "JP Venue",
                    "venue_address": "東京都新宿区",
                    "artists": [],
                    "date_range": "2026.06.01 ~ 2026.07.01",
                },
            )

    run_source(
        extractor=_JpExtractor(),
        repo=header_repo,
        geocoder=_RecordingGeocoder(),
        today=date(2026, 5, 28),
    )
    assert len(received) == 1
    query, country = received[0]
    assert country == "JP"
    assert "東京都" in query
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_pipeline.py::test_run_source_stamps_country_on_new_venues tests/test_pipeline.py::test_run_source_passes_country_to_geocoder -v`
Expected: FAIL — pipeline currently does not stamp country and calls `geocoder.geocode(query)` without country.

- [ ] **Step 3: Update GeocoderProto and pipeline**

In `src/crawler/pipeline.py`, update the `GeocoderProto`:

```python
class GeocoderProto(Protocol):
    def geocode(
        self, query: str, country: str = "KR"
    ) -> tuple[float | None, float | None]: ...
```

In `run_source`, locate the new-venue loop (currently lines 152–164) and replace with:

```python
                # geocode brand-new venues; geocoder failures don't drop the venue
                country = getattr(extractor, "country", "KR")
                for v in result.new_venues:
                    v.country = country
                    try:
                        lat, lng = geocoder.geocode(v.address or v.name, country=country)
                        if lat is not None and lng is not None:
                            v.latitude, v.longitude = lat, lng
                    except Exception as geo_exc:
                        log.warning(
                            "geocode failed for venue '%s' in %s: %s; "
                            "venue saved without coordinates",
                            v.name, name, geo_exc,
                        )
                    new_venues_acc.append(v)
                    state.venues.append(v)
```

(The only changes are: (a) compute `country` once outside the loop, (b) `v.country = country`, (c) pass `country=country` to `geocoder.geocode`.)

- [ ] **Step 4: Update NullGeocoder in conftest**

Open `tests/conftest.py`, find `NullGeocoder`, accept the optional country kwarg so it keeps satisfying GeocoderProto:

```python
class NullGeocoder:
    def geocode(
        self, query: str, country: str = "KR"
    ) -> tuple[float | None, float | None]:
        return None, None
```

- [ ] **Step 5: Update the Kakao geocoder signature for protocol conformance**

Edit `src/crawler/enrich/geocoder.py`, change the `geocode` signature to accept and ignore `country`:

```python
    def geocode(
        self, query: str, country: str = "KR"
    ) -> tuple[float | None, float | None]:
        if not query:
            return None, None
        # Try address search first
        ...
```

The Kakao logic itself doesn't need country (Kakao only knows about Korea), but accepting the kwarg keeps it compatible with `GeocoderProto` so callers can use either the resolver or the raw KakaoGeocoder interchangeably.

- [ ] **Step 6: Run tests**

Run: `PYTHONPATH=src .venv/bin/pytest -q`
Expected: all PASS including the two new tests.

- [ ] **Step 7: Commit**

```bash
git add src/crawler/pipeline.py src/crawler/enrich/geocoder.py tests/conftest.py tests/test_pipeline.py
git commit -m "feat(pipeline): stamp country on new venues and pass to geocoder"
```

---

### Task 7: Wire `_build_geocoder` to use GeocoderResolver

**Files:**
- Modify: `src/crawler/cli.py:24-35` (`_build_geocoder`)

- [ ] **Step 1: Replace builder**

Open `src/crawler/cli.py`. Find `_build_geocoder` (currently builds bare KakaoGeocoder). Replace with:

```python
def _build_geocoder():
    from crawler.enrich.geocoder import KakaoGeocoder
    from crawler.enrich.geocoder_google import GoogleMapsGeocoder
    from crawler.enrich.geocoder_resolver import GeocoderResolver
    return GeocoderResolver(
        kakao=KakaoGeocoder.from_env(),
        google=GoogleMapsGeocoder.from_env(),
    )
```

- [ ] **Step 2: Run tests to confirm nothing broke**

Run: `PYTHONPATH=src .venv/bin/pytest -q`
Expected: all PASS — CLI tests don't actually instantiate the resolver in tests (typer command boilerplate only).

- [ ] **Step 3: Commit**

```bash
git add src/crawler/cli.py
git commit -m "feat(cli): wire _build_geocoder through GeocoderResolver"
```

---

### Task 8: Backfill uses country-aware geocoder

**Files:**
- Modify: `src/crawler/enrich/backfill.py`
- Modify: `tests/enrich/test_geocoder.py` (or add `tests/enrich/test_backfill.py` if no existing backfill tests)

- [ ] **Step 1: Check existing backfill tests**

Run: `ls tests/enrich/`. If `test_backfill.py` exists, modify it. If not, the test goes in a new file.

- [ ] **Step 2: Write the failing test**

Create or open `tests/enrich/test_backfill.py` and add:

```python
"""Backfill must pass venue.country through to the geocoder."""

from __future__ import annotations

from datetime import datetime, UTC

from crawler.enrich.backfill import backfill_geocodes
from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository


class _RecordingGeocoder:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def geocode(self, query: str, country: str = "KR") -> tuple[float | None, float | None]:
        self.calls.append((query, country))
        return 35.6, 139.7


def test_backfill_passes_country_to_geocoder():
    repo = FakeRepository()
    now = datetime.now(UTC).isoformat()
    # Seed a JP venue with empty coords
    repo.append_rows(SheetName.VENUES, [
        {
            "id": "v_jp_1",
            "name": "東京都写真美術館",
            "venue_type": "museum",
            "address": "東京都目黒区三田1-13-3",
            "country": "JP",
            "first_seen_at": now,
            "updated_at": now,
        },
    ])

    g = _RecordingGeocoder()
    report = backfill_geocodes(repo, g)
    assert report.geocoded == 1
    assert g.calls == [("東京都目黒区三田1-13-3", "JP")]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/enrich/test_backfill.py -v`
Expected: FAIL — `geocode` is called without country, so `_RecordingGeocoder.calls` records `("...", "KR")` (the default), not `"JP"`.

- [ ] **Step 4: Update backfill_geocodes to forward country**

Edit `src/crawler/enrich/backfill.py`. Change `GeocoderProto`:

```python
class GeocoderProto(Protocol):
    def geocode(
        self, query: str, country: str = "KR"
    ) -> tuple[float | None, float | None]: ...
```

Change the call site:

```python
        country = str(v.get("country") or "KR").strip() or "KR"

        try:
            lat, lng = geocoder.geocode(query, country=country)
        except Exception:
            logger.exception("venue %s: geocoder raised an error", venue_id)
            errors += 1
            continue
```

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/enrich/ -v`
Expected: all PASS including the new test.

- [ ] **Step 6: Commit**

```bash
git add src/crawler/enrich/backfill.py tests/enrich/test_backfill.py
git commit -m "feat(enrich): backfill forwards venue.country to geocoder"
```

---

### Task 9: Extend `normalize/dates.py` with Japanese date patterns

**Files:**
- Modify: `src/crawler/normalize/dates.py`
- Modify: `tests/normalize/test_dates.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/normalize/test_dates.py`:

```python
def test_parse_date_japanese_year_month_day():
    from datetime import date
    from crawler.normalize.dates import parse_date
    assert parse_date("2026年5月10日") == date(2026, 5, 10)
    assert parse_date("2026年12月3日") == date(2026, 12, 3)


def test_parse_date_range_japanese():
    from datetime import date
    from crawler.normalize.dates import parse_date_range
    s, e = parse_date_range("2026年5月10日 ～ 2026年7月3日")
    assert s == date(2026, 5, 10)
    assert e == date(2026, 7, 3)


def test_parse_date_range_japanese_compact_separator():
    """Japanese sites also use 〜 (U+301C) and － (full-width hyphen)."""
    from datetime import date
    from crawler.normalize.dates import parse_date_range
    s, e = parse_date_range("2026/5/10〜2026/7/3")
    assert s == date(2026, 5, 10)
    assert e == date(2026, 7, 3)


def test_parse_date_range_english_with_year_at_end():
    """Tokyo Art Beat sometimes renders 'May 10 – Jul 3, 2026'."""
    from datetime import date
    from crawler.normalize.dates import parse_date_range
    s, e = parse_date_range("May 10 – Jul 3, 2026")
    assert s == date(2026, 5, 10)
    assert e == date(2026, 7, 3)


def test_parse_date_korean_still_works():
    """Regression guard: Korean patterns must keep parsing identically."""
    from datetime import date
    from crawler.normalize.dates import parse_date, parse_date_range
    assert parse_date("2026년 5월 10일") == date(2026, 5, 10)
    s, e = parse_date_range("2026.05.10 ~ 2026.07.03")
    assert s == date(2026, 5, 10)
    assert e == date(2026, 7, 3)
```

- [ ] **Step 2: Run tests to verify failures**

Run: `PYTHONPATH=src .venv/bin/pytest tests/normalize/test_dates.py -v`
Expected: the Korean test still PASSes; the JP `年/月/日` tests FAIL because the existing `_KOREAN_PATTERN` matches the Korean `년/월/일` codepoints, not the Japanese `年/月/日`. The `〜` and `May…2026` ones may also FAIL depending on dateutil parsing.

- [ ] **Step 3: Add Japanese patterns and an extended range separator**

Edit `src/crawler/normalize/dates.py`. Above `_KOREAN_PATTERN`, add the JP pattern; below it, widen `_RANGE_SPLIT` to include `〜` (U+301C):

```python
_KOREAN_PATTERN = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_JAPANESE_PATTERN = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
# Compact numeric date with optional trailing dot and optional Korean weekday:
# e.g. "2026.05.22. 금" or "2026. 06. 01. 월"
_COMPACT_DATE_PATTERN = re.compile(
    r"(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})\s*\.?"
    r"(?:\s*[월화수목금토일])?"
)
# Range separator: tilde, en/em-dash, JP wave-dash, full-width hyphen,
# or a space-padded ASCII hyphen.
_RANGE_SPLIT = re.compile(r"\s*[~–—〜－]\s*|\s+-\s+")
```

In `parse_date`, after the Korean pattern block, add the JP block:

```python
    # Korean 년/월/일 pattern
    m = _KOREAN_PATTERN.search(raw)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    # Japanese 年/月/日 pattern (codepoints differ from Korean)
    m = _JAPANESE_PATTERN.search(raw)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    # Compact numeric date: YYYY.MM.DD. 요일 or YYYY.MM.DD
    ...
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/normalize/test_dates.py -v`
Expected: all PASS. The English `May 10 – Jul 3, 2026` test relies on dateutil; if it still fails, add a regex fallback only for that variant. dateutil handles it in our pinned version.

- [ ] **Step 5: Commit**

```bash
git add src/crawler/normalize/dates.py tests/normalize/test_dates.py
git commit -m "feat(normalize/dates): parse Japanese 年月日 and wave-dash ranges"
```

---

### Task 10: Add `GOOGLE_MAPS_API_KEY` to the crawl workflow

**Files:**
- Modify: `.github/workflows/crawl.yml`

- [ ] **Step 1: Add the secret to run-all env**

Edit `.github/workflows/crawl.yml`. In the `crawler run-all` step, add `GOOGLE_MAPS_API_KEY` alongside the existing env mappings:

```yaml
      - run: crawler run-all
        env:
          GOOGLE_SERVICE_ACCOUNT_JSON: ${{ secrets.GOOGLE_SERVICE_ACCOUNT_JSON }}
          SHEET_ID: ${{ secrets.SHEET_ID }}
          KAKAO_REST_API_KEY: ${{ secrets.KAKAO_REST_API_KEY }}
          GOOGLE_MAPS_API_KEY: ${{ secrets.GOOGLE_MAPS_API_KEY }}
```

- [ ] **Step 2: Verify env wiring locally with a stub**

There is no automated test for the workflow file itself. Verify the env name matches what `GoogleMapsGeocoder.from_env()` reads. Grep:

Run: `grep -n GOOGLE_MAPS_API_KEY src/crawler/enrich/geocoder_google.py`
Expected: 1 match at `os.environ["GOOGLE_MAPS_API_KEY"]`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/crawl.yml
git commit -m "ci(crawl): forward GOOGLE_MAPS_API_KEY to run-all"
```

---

### Task 11: Run full suite + ruff for PR-A

- [ ] **Step 1: Tests + lint**

Run: `PYTHONPATH=src .venv/bin/pytest -q && .venv/bin/ruff check src tests`
Expected: all tests PASS, ruff "All checks passed!"

- [ ] **Step 2: Open PR-A**

Push the branch and open the PR. Body suggestion:

```
## Why
Spec docs/superpowers/specs/2026-05-28-japan-expansion-design.md, section 2-3.

## Changes
- Venue.country (default "KR") + idempotent sheet migration via init-sheets prefix-append
- GoogleMapsGeocoder for Japanese addresses (region=jp, language=ja)
- GeocoderResolver dispatches by country; KakaoGeocoder accepts (ignores) the country kwarg for protocol conformance
- Pipeline stamps extractor.country onto new Venues
- backfill-geocodes forwards venue.country to the geocoder
- normalize/dates.py picks up Japanese 年月日 + wave-dash ranges
- crawl.yml forwards GOOGLE_MAPS_API_KEY

## Test plan
- [x] new unit tests for model/init-sheets/geocoder_google/geocoder_resolver/backfill/dates
- [x] all 245 + ~14 new tests pass
- [x] ruff clean
- [ ] **User one-time**: enable Geocoding API on GCP project allphoto-crawler and add GOOGLE_MAPS_API_KEY secret before merging; otherwise the next cron run fails to build the geocoder
```

---

## PR-B: tokyo_photographic_art_museum source

### Task 12: Register `TOKYO_PHOTOGRAPHIC_ART_MUSEUM` source name

**Files:**
- Modify: `src/crawler/models.py` (`SourceName` enum)

- [ ] **Step 1: Add the enum value**

Edit `src/crawler/models.py`. In `SourceName`, add `TOKYO_PHOTOGRAPHIC_ART_MUSEUM`:

```python
class SourceName(StrEnum):
    ARTMAP = "artmap"
    NAVER = "naver"
    PHOTO_SEMA = "photo_sema"
    MUSEUM_HANMI = "museum_hanmi"
    KOBA = "koba"
    GOEUN = "goeun"
    GALLERY_LUX = "gallery_lux"
    GALLERY_KONG = "gallery_kong"
    RYUGAHEON = "ryugaheon"
    ILWOO_SPACE = "ilwoo_space"
    SANGSANGMADANG = "sangsangmadang"
    CANON_GALLERY = "canon_gallery"
    TOKYO_PHOTOGRAPHIC_ART_MUSEUM = "tokyo_photographic_art_museum"
```

- [ ] **Step 2: Run existing tests to ensure no regressions**

Run: `PYTHONPATH=src .venv/bin/pytest -q`
Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add src/crawler/models.py
git commit -m "feat(models): register tokyo_photographic_art_museum source name"
```

---

### Task 13: Capture a TOP fixture from the live site

**Files:**
- Create: `tests/fixtures/tokyo_photographic_art_museum/list_current.html`
- Create: `tests/fixtures/tokyo_photographic_art_museum/expected.jsonl`

- [ ] **Step 1: Fetch the current exhibitions page**

Run (use the actual current TOP exhibitions list URL — verify in browser first; the canonical entry is `topmuseum.jp/contents/exhibition/index-current.html` but confirm pre-fetch):

```bash
curl -sL -A "PhotoExhibitionCrawler/0.1 (+contact@example.com)" \
  https://topmuseum.jp/contents/exhibition/index-current.html \
  -o tests/fixtures/tokyo_photographic_art_museum/list_current.html
```

If `index-current.html` is a 404, browse topmuseum.jp manually, identify the page that lists currently-running exhibitions, then `curl` that URL into the fixture path.

- [ ] **Step 2: Eyeball the saved HTML**

Run: `wc -l tests/fixtures/tokyo_photographic_art_museum/list_current.html`. Expected: > 200 lines (a real page, not an error blurb). Open in any reader and confirm at least 1 exhibition card with title + date + venue floor info is present.

- [ ] **Step 3: Write expected JSONL** (one line per exhibition in the fixture)

After implementing the extractor in Task 14, you'll fill this in by running it against the fixture and copying the resulting JSONL. For now, create the file empty:

```bash
: > tests/fixtures/tokyo_photographic_art_museum/expected.jsonl
```

It will be populated in Task 14 step 5 once the extractor is wired.

- [ ] **Step 4: Commit the fixture**

```bash
git add tests/fixtures/tokyo_photographic_art_museum/
git commit -m "test(fixtures): TOP current-exhibitions list snapshot"
```

---

### Task 14: Implement the TOP extractor

**Files:**
- Create: `src/crawler/sources/tokyo_photographic_art_museum.py`
- Create: `tests/sources/test_tokyo_photographic_art_museum.py`
- Modify: `src/crawler/sources/__init__.py`
- Update: `tests/fixtures/tokyo_photographic_art_museum/expected.jsonl`

- [ ] **Step 1: Write the failing test**

Create `tests/sources/test_tokyo_photographic_art_museum.py`:

```python
"""東京都写真美術館 (Tokyo Photographic Art Museum) extractor — fixture test."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawler.models import RawExhibition, SourceName
from crawler.sources.tokyo_photographic_art_museum import (
    TokyoPhotographicArtMuseumExtractor,
    _extract_exhibitions,
)

_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "tokyo_photographic_art_museum"


def test_extractor_is_registered_with_jp_country():
    assert TokyoPhotographicArtMuseumExtractor.name == SourceName.TOKYO_PHOTOGRAPHIC_ART_MUSEUM
    assert TokyoPhotographicArtMuseumExtractor.country == "JP"


def test_extractor_yields_raw_exhibitions_matching_fixture():
    html = (_FIXTURE_DIR / "list_current.html").read_text(encoding="utf-8")
    rows = _extract_exhibitions(html)
    assert rows, "list_current.html should contain at least one exhibition card"

    expected = [
        json.loads(line)
        for line in (_FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == len(expected)
    for got, want in zip(rows, expected, strict=True):
        # Compare on the keys we care about, ignore order of optional keys.
        for k, v in want.items():
            assert got[k] == v, f"key {k!r}: got {got[k]!r}, want {v!r}"


def test_extractor_emits_jp_venue_address():
    """Every yielded row should carry the museum's address in the raw payload
    so the pipeline can geocode it via the Japanese backend."""
    html = (_FIXTURE_DIR / "list_current.html").read_text(encoding="utf-8")
    rows = _extract_exhibitions(html)
    for r in rows:
        assert r["venue_name"] == "東京都写真美術館"
        assert "東京都" in (r.get("venue_address") or "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/sources/test_tokyo_photographic_art_museum.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the extractor**

Create `src/crawler/sources/tokyo_photographic_art_museum.py`. The exact selector strings depend on what the fetched HTML looks like — adjust during implementation. Skeleton:

```python
"""東京都写真美術館 (Tokyo Photographic Art Museum) — list extractor.

Source: topmuseum.jp current exhibitions page. The museum runs 3-5
simultaneous exhibitions across three floors (B1F/2F/3F), all dedicated
to photography/video.

Verified 2026-05-28: each exhibition card carries title, date range,
floor/series label, and a link to the detail page.
"""

from __future__ import annotations

import time
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source

_BASE_URL = "https://topmuseum.jp"
_LIST_URL = f"{_BASE_URL}/contents/exhibition/index-current.html"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

_VENUE_NAME = "東京都写真美術館"
_VENUE_NAME_EN = "Tokyo Photographic Art Museum"
_VENUE_REGION = "東京都"
_VENUE_ADDRESS = "東京都目黒区三田1-13-3 恵比寿ガーデンプレイス内"


class TokyoPhotographicArtMuseumExtractor:
    name = SourceName.TOKYO_PHOTOGRAPHIC_ART_MUSEUM
    country = "JP"

    def __init__(self, delay_s: float = 1.0, timeout_s: float = 20.0) -> None:
        self.delay_s = delay_s
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get(self, url: str) -> str:
        r = self._client.get(url)
        r.raise_for_status()
        return r.text

    def crawl(self) -> Iterable[RawExhibition]:
        html = self._get(_LIST_URL)
        for row in _extract_exhibitions(html):
            yield RawExhibition(
                source=SourceName.TOKYO_PHOTOGRAPHIC_ART_MUSEUM,
                source_url=row["source_url"],
                raw={k: v for k, v in row.items() if k != "source_url"},
            )
            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _extract_exhibitions(html: str) -> list[dict]:
    """Parse the TOP current-exhibitions list page.

    Returns dicts ready for RawExhibition.raw with keys:
      source_url, title, title_en?, artists?, date_range, venue_name,
      venue_region, venue_address, poster_image_url?.
    """
    doc = HTMLParser(html)
    out: list[dict] = []

    # NOTE: selectors below are placeholders — replace with the actual ones
    # after inspecting list_current.html. The page typically renders cards
    # under a wrapper like div.exhibition-list > div.exhibition-item, but
    # this MUST be verified against the fixture before merging.
    for card in doc.css("div.exhibition-item"):
        link = card.css_first("a[href]")
        if not link:
            continue
        href = link.attributes.get("href", "")
        if href.startswith("/"):
            href = f"{_BASE_URL}{href}"

        title_el = card.css_first(".exhibition-title")
        title = title_el.text(strip=True) if title_el else ""
        if not title:
            continue

        date_el = card.css_first(".exhibition-date")
        date_range = date_el.text(strip=True) if date_el else None

        img = card.css_first("img")
        poster = img.attributes.get("src") if img else None
        if poster and poster.startswith("/"):
            poster = f"{_BASE_URL}{poster}"

        out.append({
            "source_url": href,
            "title": title,
            "venue_name": _VENUE_NAME,
            "venue_region": _VENUE_REGION,
            "venue_address": _VENUE_ADDRESS,
            "date_range": date_range,
            "poster_image_url": poster,
            "artists": [],
        })

    return out


register_source(SourceName.TOKYO_PHOTOGRAPHIC_ART_MUSEUM, TokyoPhotographicArtMuseumExtractor)
```

**During implementation: open `list_current.html` and adjust the selectors `div.exhibition-item`, `.exhibition-title`, `.exhibition-date` to the actual class names you see in the snapshot.**

- [ ] **Step 4: Wire registration**

Edit `src/crawler/sources/__init__.py`:

```python
from crawler.sources import (
    artmap,  # noqa: F401
    canon_gallery,  # noqa: F401
    gallery_kong,  # noqa: F401
    gallery_lux,  # noqa: F401
    goeun,  # noqa: F401
    ilwoo_space,  # noqa: F401
    koba,  # noqa: F401
    museum_hanmi,  # noqa: F401
    photo_sema,  # noqa: F401
    ryugaheon,  # noqa: F401
    sangsangmadang,  # noqa: F401
    tokyo_photographic_art_museum,  # noqa: F401
)
```

- [ ] **Step 5: Populate `expected.jsonl` from the actual extractor output**

Run a one-liner that dumps what the extractor produces against the fixture, and save it:

```bash
PYTHONPATH=src .venv/bin/python -c "
from pathlib import Path
import json
from crawler.sources.tokyo_photographic_art_museum import _extract_exhibitions
html = Path('tests/fixtures/tokyo_photographic_art_museum/list_current.html').read_text(encoding='utf-8')
for row in _extract_exhibitions(html):
    print(json.dumps(row, ensure_ascii=False))
" > tests/fixtures/tokyo_photographic_art_museum/expected.jsonl
```

Open the file. Make sure: (a) it has at least 1 line, (b) each line has a non-empty `title`, `date_range`, `venue_name=東京都写真美術館`, `source_url` starting with https://topmuseum.jp. If not, fix the extractor and rerun. Once you're satisfied, the file is the contract the test enforces.

- [ ] **Step 6: Run the source tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/sources/test_tokyo_photographic_art_museum.py -v`
Expected: all 3 PASS.

- [ ] **Step 7: Run the integration smoke against FakeRepo**

Add to `tests/integration/test_pipeline_japan_sources.py` (create the file):

```python
"""Smoke pipeline tests for the JP sources against FakeRepo."""

from __future__ import annotations

from datetime import date

from freezegun import freeze_time

from crawler.pipeline import run_source
from crawler.sources.tokyo_photographic_art_museum import TokyoPhotographicArtMuseumExtractor


class _NullGeocoder:
    def geocode(self, query: str, country: str = "KR") -> tuple[float | None, float | None]:
        return None, None


@freeze_time("2026-05-28")
def test_top_pipeline_smoke(header_repo, monkeypatch):
    """End-to-end: extractor → normalize → resolve → upsert FakeRepo.

    Uses the captured HTML fixture by monkeypatching _get.
    """
    from pathlib import Path
    from crawler.sources import tokyo_photographic_art_museum as mod

    html = Path("tests/fixtures/tokyo_photographic_art_museum/list_current.html") \
        .read_text(encoding="utf-8")
    monkeypatch.setattr(
        TokyoPhotographicArtMuseumExtractor, "_get",
        lambda self, url: html,
    )

    report = run_source(
        extractor=TokyoPhotographicArtMuseumExtractor(delay_s=0),
        repo=header_repo,
        geocoder=_NullGeocoder(),
        today=date(2026, 5, 28),
    )
    assert report.failure is None
    assert report.errors == 0
    assert report.extracted >= 1

    # One JP venue was created with country=JP
    from crawler.sinks.base import SheetName
    venues = header_repo.read_rows(SheetName.VENUES)
    top_venues = [v for v in venues if v["name"] == "東京都写真美術館"]
    assert len(top_venues) == 1
    assert top_venues[0]["country"] == "JP"
```

- [ ] **Step 8: Run integration + full suite + lint**

Run: `PYTHONPATH=src .venv/bin/pytest -q && .venv/bin/ruff check src tests`
Expected: all PASS, ruff clean.

- [ ] **Step 9: Commit**

```bash
git add src/crawler/sources/tokyo_photographic_art_museum.py \
        src/crawler/sources/__init__.py \
        tests/sources/test_tokyo_photographic_art_museum.py \
        tests/integration/test_pipeline_japan_sources.py \
        tests/fixtures/tokyo_photographic_art_museum/expected.jsonl
git commit -m "feat(sources): tokyo_photographic_art_museum extractor"
```

---

### Task 15: Open PR-B

- [ ] **Step 1: Push + PR**

```bash
git push -u origin <branch>
gh pr create --base main --title "feat(sources): add 東京都写真美術館 (TOP) source" --body "..."
```

Body should reference the spec, list test plan, note "depends on PR-A being merged first".

---

## PR-C: Tokyo Art Beat

### Task 16: Register `TOKYO_ART_BEAT` source name

**Files:**
- Modify: `src/crawler/models.py`

- [ ] **Step 1: Add the enum value**

```python
class SourceName(StrEnum):
    ...
    TOKYO_PHOTOGRAPHIC_ART_MUSEUM = "tokyo_photographic_art_museum"
    TOKYO_ART_BEAT = "tokyo_art_beat"
```

- [ ] **Step 2: Run tests**

Run: `PYTHONPATH=src .venv/bin/pytest -q`
Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add src/crawler/models.py
git commit -m "feat(models): register tokyo_art_beat source name"
```

---

### Task 17: Recon — pick TAB list+detail strategy

**Files:**
- (Investigation only — no code yet)

- [ ] **Step 1: Fetch the photography-category list page**

Try the photography filter URL on the public site. As of design time the canonical entry is `https://www.tokyoartbeat.com/en/categories/photography` or `…/jp/…/写真`. Pre-fetch:

```bash
curl -sLI -A "PhotoExhibitionCrawler/0.1 (+contact@example.com)" \
  https://www.tokyoartbeat.com/en/categories/photography \
  | head -20
```

- [ ] **Step 2: Confirm response is HTML and not 4xx/5xx/Cloudflare-challenge**

If status is 200 and `Content-Type: text/html`, proceed with scraping. If you see 403/`cf-mitigated` or a JS challenge, **switch strategy in the next step** — use a configured-UA fetch with sensible headers (Accept-Language, Referer), OR investigate TAB's JSON endpoints by inspecting devtools Network tab.

- [ ] **Step 3: Save the response**

```bash
mkdir -p tests/fixtures/tokyo_art_beat
curl -sL -A "PhotoExhibitionCrawler/0.1 (+contact@example.com)" \
  -H "Accept-Language: en-US,en;q=0.9,ja;q=0.8" \
  https://www.tokyoartbeat.com/en/categories/photography \
  -o tests/fixtures/tokyo_art_beat/list_page_1.html
```

- [ ] **Step 4: Spot-check the saved HTML**

Open `list_page_1.html`. Verify it contains exhibition cards (title, venue, date) — not just a SPA shell. If it's a SPA shell with no rendered cards, TAB is JS-rendered and needs either: (a) the JSON XHR endpoint backing the SPA (recommended; usually discoverable in devtools), or (b) Playwright fallback.

- [ ] **Step 5: Decide and document**

In the source module's module-level docstring (`src/crawler/sources/tokyo_art_beat.py` in Task 18), write a `# Strategy:` block that records: (a) which URL the extractor hits, (b) whether it parses HTML or JSON, (c) what headers it sets, (d) pagination logic.

- [ ] **Step 6: Commit the recon fixture**

```bash
git add tests/fixtures/tokyo_art_beat/list_page_1.html
git commit -m "test(fixtures): TAB photography list snapshot for recon"
```

(No code commit yet — Task 18 ships the extractor with the strategy you picked above.)

---

### Task 18: Implement the TAB extractor

**Files:**
- Create: `src/crawler/sources/tokyo_art_beat.py`
- Create: `tests/sources/test_tokyo_art_beat.py`
- Modify: `src/crawler/sources/__init__.py`
- Create: `tests/fixtures/tokyo_art_beat/expected.jsonl`

- [ ] **Step 1: Write the failing test**

Create `tests/sources/test_tokyo_art_beat.py`:

```python
"""Tokyo Art Beat (photography category) — fixture-based extractor test."""

from __future__ import annotations

import json
from pathlib import Path

from crawler.models import SourceName
from crawler.sources.tokyo_art_beat import (
    TokyoArtBeatExtractor,
    _extract_exhibitions,
)

_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "tokyo_art_beat"


def test_extractor_registered_with_jp_country():
    assert TokyoArtBeatExtractor.name == SourceName.TOKYO_ART_BEAT
    assert TokyoArtBeatExtractor.country == "JP"


def test_extractor_yields_rows_matching_fixture():
    html = (_FIXTURE_DIR / "list_page_1.html").read_text(encoding="utf-8")
    rows = _extract_exhibitions(html)
    assert rows, "list_page_1.html should produce at least one row"

    expected = [
        json.loads(line)
        for line in (_FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == len(expected)
    for got, want in zip(rows, expected, strict=True):
        for k, v in want.items():
            assert got[k] == v, f"key {k!r}: got {got[k]!r}, want {v!r}"


def test_extractor_filters_out_non_photography_categories():
    """Even when a non-photography card slips into the list, the source
    must drop it before yielding."""
    html_with_painting = """
    <article class="event-card" data-category="painting">
      <a href="/event/painting-show"><h3>Painting Show</h3></a>
      <div class="venue">Other Gallery</div>
      <div class="date">2026.06.01 - 2026.07.01</div>
    </article>
    """
    rows = _extract_exhibitions(html_with_painting)
    assert rows == []
```

- [ ] **Step 2: Run test to verify failure**

Run: `PYTHONPATH=src .venv/bin/pytest tests/sources/test_tokyo_art_beat.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the extractor**

Create `src/crawler/sources/tokyo_art_beat.py` with the strategy decided in Task 17.

If HTML-scraping the photography listing (typical case):

```python
"""Tokyo Art Beat (tokyoartbeat.com) — photography category list extractor.

Strategy: (filled in during Task 17 recon — adjust before merging)
- Endpoint: https://www.tokyoartbeat.com/en/categories/photography (HTML)
- Pagination: ?page=N until no more cards
- Headers: standard User-Agent + Accept-Language en-US,ja
- Category whitelist: at the source level we only yield rows where the
  card carries a photography signal (data-category contains "photo" or
  the breadcrumb names photography). TAB is a multi-medium aggregator,
  so this filter is mandatory — Sangsangmadang-style.

Verified 2026-05-28.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source

_BASE_URL = "https://www.tokyoartbeat.com"
_LIST_URL = f"{_BASE_URL}/en/categories/photography"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"


class TokyoArtBeatExtractor:
    name = SourceName.TOKYO_ART_BEAT
    country = "JP"

    def __init__(
        self,
        max_pages: int = 10,
        delay_s: float = 1.5,
        timeout_s: float = 20.0,
    ) -> None:
        self.max_pages = max_pages
        self.delay_s = delay_s
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
            },
            follow_redirects=True,
        )

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get(self, url: str) -> str:
        r = self._client.get(url)
        r.raise_for_status()
        return r.text

    def crawl(self) -> Iterable[RawExhibition]:
        seen: set[str] = set()
        for page in range(1, self.max_pages + 1):
            url = _LIST_URL if page == 1 else f"{_LIST_URL}?page={page}"
            html = self._get(url)
            rows = _extract_exhibitions(html)
            if not rows:
                return

            for row in rows:
                href = row["source_url"]
                if href in seen:
                    continue
                seen.add(href)
                yield RawExhibition(
                    source=SourceName.TOKYO_ART_BEAT,
                    source_url=href,
                    raw={k: v for k, v in row.items() if k != "source_url"},
                )

            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _is_photography(card_text: str, data_category: str | None) -> bool:
    """Conservative whitelist: keep only cards with photography signal."""
    if data_category and ("photo" in data_category.lower() or "写真" in data_category):
        return True
    haystack = (card_text or "").lower()
    return any(
        kw in haystack
        for kw in ("photograph", "photography", "写真", "フォト", "サイアノタイプ")
    )


def _extract_exhibitions(html: str) -> list[dict]:
    doc = HTMLParser(html)
    out: list[dict] = []

    # NOTE: selectors below are placeholders. Inspect list_page_1.html and
    # adjust to the actual TAB card class — typically `article.event-card`
    # or `div.event` — before merging.
    for card in doc.css("article.event-card"):
        data_category = card.attributes.get("data-category")
        text = card.text(separator=" ", strip=True)
        if not _is_photography(text, data_category):
            continue

        link = card.css_first("a[href]")
        if not link:
            continue
        href = link.attributes.get("href", "")
        if href.startswith("/"):
            href = urljoin(_BASE_URL, href)

        title_el = card.css_first("h3, .event-title")
        title = title_el.text(strip=True) if title_el else ""
        if not title:
            continue

        venue_el = card.css_first(".venue")
        venue_name = venue_el.text(strip=True) if venue_el else ""

        date_el = card.css_first(".date, .event-date")
        date_range = date_el.text(strip=True) if date_el else None

        img = card.css_first("img")
        poster = img.attributes.get("src") if img else None
        if poster and poster.startswith("/"):
            poster = urljoin(_BASE_URL, poster)

        out.append({
            "source_url": href,
            "title": title,
            "venue_name": venue_name,
            "venue_region": "東京都",
            "date_range": date_range,
            "poster_image_url": poster,
            "artists": [],
        })

    return out


register_source(SourceName.TOKYO_ART_BEAT, TokyoArtBeatExtractor)
```

**During implementation**: open `tests/fixtures/tokyo_art_beat/list_page_1.html`, find the actual card class names, and adjust selectors. If the SPA strategy was chosen in Task 17, the parser will read JSON instead — same `_extract_exhibitions(html_or_json)` signature but with `json.loads(text)` inside.

- [ ] **Step 4: Register the source**

Edit `src/crawler/sources/__init__.py`:

```python
from crawler.sources import (
    artmap,  # noqa: F401
    canon_gallery,  # noqa: F401
    gallery_kong,  # noqa: F401
    gallery_lux,  # noqa: F401
    goeun,  # noqa: F401
    ilwoo_space,  # noqa: F401
    koba,  # noqa: F401
    museum_hanmi,  # noqa: F401
    photo_sema,  # noqa: F401
    ryugaheon,  # noqa: F401
    sangsangmadang,  # noqa: F401
    tokyo_art_beat,  # noqa: F401
    tokyo_photographic_art_museum,  # noqa: F401
)
```

- [ ] **Step 5: Populate `expected.jsonl`**

```bash
PYTHONPATH=src .venv/bin/python -c "
from pathlib import Path
import json
from crawler.sources.tokyo_art_beat import _extract_exhibitions
html = Path('tests/fixtures/tokyo_art_beat/list_page_1.html').read_text(encoding='utf-8')
for row in _extract_exhibitions(html):
    print(json.dumps(row, ensure_ascii=False))
" > tests/fixtures/tokyo_art_beat/expected.jsonl
```

Open it and confirm: at least 1 line, every row's title and venue look like a legitimate photography exhibition (no painting/sculpture/design leaking through). If a non-photo card slipped past `_is_photography`, broaden the whitelist or check the data-category attribute against the actual fixture.

- [ ] **Step 6: Run tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/sources/test_tokyo_art_beat.py -v`
Expected: all 3 PASS.

- [ ] **Step 7: Add TAB to the integration smoke**

Append to `tests/integration/test_pipeline_japan_sources.py`:

```python
@freeze_time("2026-05-28")
def test_tab_pipeline_smoke(header_repo, monkeypatch):
    from pathlib import Path
    from crawler.sinks.base import SheetName
    from crawler.sources.tokyo_art_beat import TokyoArtBeatExtractor

    html = Path("tests/fixtures/tokyo_art_beat/list_page_1.html") \
        .read_text(encoding="utf-8")

    pages_fetched = [0]
    def fake_get(self, url):
        pages_fetched[0] += 1
        # Return the fixture for page 1, empty page for page 2 (stops pagination)
        return html if pages_fetched[0] == 1 else "<html></html>"
    monkeypatch.setattr(TokyoArtBeatExtractor, "_get", fake_get)

    report = run_source(
        extractor=TokyoArtBeatExtractor(max_pages=2, delay_s=0),
        repo=header_repo,
        geocoder=_NullGeocoder(),
        today=date(2026, 5, 28),
    )
    assert report.failure is None
    assert report.errors == 0
    assert report.extracted >= 1

    venues = header_repo.read_rows(SheetName.VENUES)
    jp_venues = [v for v in venues if v.get("country") == "JP"]
    assert jp_venues, "TAB must create at least one JP-tagged venue"
```

- [ ] **Step 8: Run full suite + lint**

Run: `PYTHONPATH=src .venv/bin/pytest -q && .venv/bin/ruff check src tests`
Expected: all PASS, ruff clean.

- [ ] **Step 9: Commit**

```bash
git add src/crawler/sources/tokyo_art_beat.py \
        src/crawler/sources/__init__.py \
        tests/sources/test_tokyo_art_beat.py \
        tests/integration/test_pipeline_japan_sources.py \
        tests/fixtures/tokyo_art_beat/expected.jsonl
git commit -m "feat(sources): tokyo_art_beat extractor with photo whitelist"
```

---

### Task 19: Open PR-C

- [ ] **Step 1: Push + PR**

```bash
git push -u origin <branch>
gh pr create --base main --title "feat(sources): add Tokyo Art Beat photography source" --body "..."
```

Body should: reference spec, note depends on PR-A merged (and ideally PR-B for end-to-end consistency), list test plan, mention the photography category whitelist.

- [ ] **Step 2: Post-merge verification (manual)**

After merging:

```bash
gh workflow run crawl.yml --repo Hoya324/allphoto --ref main
gh run watch <run-id> --repo Hoya324/allphoto
```

Inspect the report: TAB should report `extracted >= 1`, `country=JP` venues should land in the Venues sheet. Then run backfill once to populate coordinates:

```bash
.venv/bin/crawler backfill-geocodes
```

---

## Self-Review

Cross-checked the plan against the spec:

- §2.1 Venue.country → Task 1 ✓
- §2.2 sheet migration via prefix-append → Task 2 ✓
- §2.3 Extractor.country class attr → Task 5 ✓
- §2.4 pipeline stamps country + passes to geocoder → Task 6 ✓
- §3.1 GoogleMapsGeocoder → Task 3 ✓
- §3.2 GeocoderResolver → Task 4 ✓
- §3.3 cli._build_geocoder → Task 7 ✓
- §3.4 GOOGLE_MAPS_API_KEY env wiring → Task 10 ✓
- §3.5 backfill uses resolver → Task 8 ✓
- §4.1 JP date patterns → Task 9 ✓
- §4.2 status keyword skip → no task needed (intentional)
- §5.1 TOP source → Tasks 12–14 ✓
- §5.2 TAB source → Tasks 16–18 ✓ (recon split into Task 17 so selectors aren't speculation)
- §5.3 SourceName enum additions → Tasks 12, 16 ✓
- §6 error handling — covered by resolver returning (None, None) and existing pipeline warning path
- §7 testing strategy — every source has fixture+unit; geocoder/resolver unit; integration smoke

No placeholders remaining. Type-name consistency confirmed: `Venue.country` (str), `Extractor.country` (ClassVar[str]), `GeocoderResolver.geocode(query, country)`, used identically across tasks 1, 5, 6, 7, 8.
