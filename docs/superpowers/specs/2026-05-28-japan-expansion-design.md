# 일본 확장 (Tokyo Art Beat + 東京都写真美術館) — 설계

- **상태**: Draft, 사용자 리뷰 대기
- **작성일**: 2026-05-28
- **선행 spec**:
  - [2026-05-28-photo-exhibition-crawler-design.md](2026-05-28-photo-exhibition-crawler-design.md) (v1 원본)
  - [2026-05-28-photo-sources-korea-expansion-design.md](2026-05-28-photo-sources-korea-expansion-design.md) (한국 7곳, 동일 패턴 검증됨)
- **후속 작업(분리)**:
  - 프론트엔드 country 필터 UI (v1.5)
  - Yahoo!Japan / OSM geocoder 추가 옵션 (필요 시)
  - 풀-스케일 일본어 normalize (전각/반각, 도도부현 파싱, 로마자 전사)

## 1. 배경 & 목적

크롤러는 v1+한국 7곳 추가로 11개 한국 소스를 운영 중이며, 데이터 적재가 안정화됨. 사용자 관점에서 다음 단계는 **국가 확장 — 일본**.

일본은 사진 예술 시장이 성숙해 있고 (TOP, Hara Museum, 21_21 DESIGN SIGHT 등), Tokyo Art Beat는 도쿄권 전 갤러리/미술관의 동시기 전시를 영/일/중 다국어로 큐레이팅하는 사실상 표준 애그리게이터. TAB만 잘 통합해도 일본 전시 수십~수백 건 확보 가능.

이번 이터레이션은 **인프라 변경 + 일본 첫 두 소스**를 한 스펙에서 다룬다. country-aware 인프라가 한 번 깔리면 향후 일본 추가 소스나 대만/미국 확장은 같은 패턴으로 깔끔하게 붙는다.

### 성공 기준

- `Venue.country` 필드 추가, 기존 KR 행 무손실 보존 (자동 default "KR")
- `GoogleMapsGeocoder` 추가, `GeocoderResolver`가 country별 디스패치
- 신규 소스 2개 등록: `tokyo_photographic_art_museum` (TOP), `tokyo_art_beat` (TAB)
- `run-all` 1회 실행 시 11+2=13개 소스가 사이트별 fail 격리하며 정상 종료
- Exhibitions 행 추가 ≥ 30건 (`run-all` 1회 기준, TAB 다수+TOP 동시기 2~5)
- 신규 일본 venue ≥ 1 (TOP) — TAB venue는 다수 자동 누적, `backfill-geocodes`로 일괄 좌표 채움
- 기존 테스트 245 그대로 통과 + 신규 ~30 테스트 추가
- ruff clean

### 비범위 (이번 spec 아님)

- 프론트엔드 country 필터 / 일본 전용 뷰
- 풀-스케일 일본어 처리 (전각/반각 정규화, 도도부현 분리, 로마자 전사) — 필요 시점에 별도 spec
- TAB 외 일본 소스 추가 (Hara/21_21/その他)
- Naver Open API
- Popularity scoring (보스토크 매거진 추천 매칭)

---

## 2. Country 필드 도입

### 2.1 모델 변경

`Venue` 모델에 한 줄 추가:

```python
class Venue(BaseModel):
    ...
    address: str | None = None
    country: str = "KR"        # ← NEW. ISO 3166-1 alpha-2.
    latitude: float | None = None
    ...
```

- str 타입 (Enum 아님) — 향후 TW/US/SG 등 추가가 빈번할 수 있고, 모델 변경 없이 string 비교로 충분.
- default `"KR"` — 기존 7곳 한국 소스가 country 미지정으로 venue를 만들어도 자동으로 KR.

### 2.2 시트 마이그레이션

`sinks/init_sheets.py`의 `HEADERS[SheetName.VENUES]`에 `"country"` 추가.

기존 시트의 Venues 헤더에는 country 컬럼이 없음. 다행히 [PR #5](https://github.com/Hoya324/allphoto/pull/5)에서 도입한 `_plan_header_write`가 "append" 액션을 지원함 — 헤더가 expected의 strict prefix인 경우 자동으로 새 컬럼을 오른쪽에 append. **추가 마이그레이션 코드 불필요**, `crawler init-sheets` 한 번 실행으로 끝.

기존 행의 country 칸은 비어있음. `pipeline._venue_from_row`에서:

```python
country = _s(r.get("country")) or "KR"
```

빈 칸 → "KR" default로 hydrate. 기존 모든 한국 venue는 별도 백필 없이 KR로 정상 해석됨.

### 2.3 Extractor에 country 선언

`sources/base.py`의 Extractor protocol에 class-level `country` 추가:

```python
class Extractor(Protocol):
    name: SourceName
    country: str        # 기본 "KR"; JP 소스는 override
    def crawl(self) -> Iterable[RawExhibition]: ...
```

각 Extractor 클래스에 한 줄:

```python
class TokyoPhotographicArtMuseumExtractor:
    name = SourceName.TOKYO_PHOTOGRAPHIC_ART_MUSEUM
    country = "JP"
    ...
```

기존 11개 한국 소스는 명시 안 함 — base default `"KR"`로 자동 fallback. YAGNI.

### 2.4 Pipeline 배선

`pipeline.run_source`의 새 venue 처리 (현 코드 line 153–164):

```python
for v in result.new_venues:
    v.country = extractor.country     # ← stamp country
    try:
        lat, lng = geocoder.geocode(v.address or v.name, country=v.country)
        ...
```

`resolver.entities`는 venue를 만들 때 country를 모르므로, pipeline이 사후 stamp. resolver 시그니처 보존 → 변경 최소.

---

## 3. Geocoder 인프라

### 3.1 GoogleMapsGeocoder

`enrich/geocoder_google.py` — 신규 모듈. Kakao와 동일한 패턴:

```python
class GoogleMapsGeocoder:
    BASE = "https://maps.googleapis.com/maps/api/geocode/json"
    def __init__(self, api_key, timeout=10.0): ...
    @classmethod
    def from_env(cls): return cls(os.environ["GOOGLE_MAPS_API_KEY"])
    @retry(retry=retry_if_exception_type(httpx.TransportError),
           wait=wait_exponential(...), stop=stop_after_attempt(3), reraise=True)
    def _get(self, params): ...
    def geocode(self, query: str) -> tuple[float|None, float|None]:
        data = self._get({"address": query, "key": self._key,
                          "region": "jp", "language": "ja"})
        if data.get("status") != "OK":
            return None, None
        loc = data["results"][0]["geometry"]["location"]
        return float(loc["lat"]), float(loc["lng"])
    def close(self): self._client.close()
```

- `region=jp` + `language=ja` 파라미터로 일본 결과 우선.
- 응답 `status`가 `ZERO_RESULTS`, `OVER_QUERY_LIMIT`, `REQUEST_DENIED` 등 다양 — `OK` 외엔 (None, None) 반환하고 호출자 (pipeline) 가 warning 처리, venue는 좌표 없이 저장 (기존 KakaoGeocoder 동작과 동일).

### 3.2 GeocoderResolver

`enrich/geocoder_resolver.py` — 신규 모듈:

```python
class GeocoderResolver:
    def __init__(self, kakao: KakaoGeocoder, google: GoogleMapsGeocoder):
        self._by_country = {"KR": kakao, "JP": google}
        self._default = kakao    # legacy callers w/o country
    def geocode(self, query: str, country: str = "KR") -> tuple[float|None, float|None]:
        g = self._by_country.get(country, self._default)
        return g.geocode(query)
    def close(self): kakao.close(); google.close()
```

- `GeocoderProto`만 country 시그니처로 확장:
  ```python
  class GeocoderProto(Protocol):
      def geocode(self, query: str, country: str = "KR") -> tuple[float|None, float|None]: ...
  ```
  Pipeline은 Resolver만 직접 호출하므로 KakaoGeocoder / GoogleMapsGeocoder의 시그니처는 country를 받지 않는 단일 인자 형태 그대로 둔다. Resolver가 country로 선택만 하고 query는 그대로 위임.

### 3.3 cli.\_build\_geocoder()

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

### 3.4 Env / Secret

- 추가: `GOOGLE_MAPS_API_KEY` (GitHub Secret + workflow env)
- 기존 GCP 프로젝트(`allphoto-crawler-*`)에서 Geocoding API 활성화 + API key 발급 (사용자 1회 작업)
- `.github/workflows/crawl.yml`에 env로 매핑

### 3.5 Backfill

`enrich/backfill.py`도 Resolver 통과. 각 venue의 `country`를 보고 적절한 geocoder 호출. 이 또한 기존 venue가 country 비어있으면 "KR" default로 흐름.

---

## 4. Japanese normalize (최소)

### 4.1 날짜 (`normalize/dates.py` 확장)

추가 패턴:

| 표현 | 예시 |
|------|------|
| `YYYY年M月D日` | `2026年5月10日` |
| `YYYY年M月D日 ～ YYYY年M月D日` | `2026年5月10日 ～ 2026年7月3日` |
| `YYYY/M/D` (구분자 차이) | `2026/5/10–2026/7/3` |
| `M月D日 – M月D日, YYYY` (TAB EN 변형) | `May 10 – Jul 3, 2026` |

기존 한국 패턴 (`2026.05.10 ~ 2026.07.03`)을 깨뜨리지 않도록 신규 regex만 append. 테스트 fixture 추가.

### 4.2 상태 키워드 (`normalize/status.py` 확장)

기존 `compute_status`는 날짜 기반이라 키워드 의존 거의 없음. 단 raw 단계에서 "현재 전시" / "종료" 등을 source가 노출할 때 status hint를 채워주면 분류 정확도가 오름.

이번 spec에선 **날짜 파싱이 우선** — 일본 status 키워드는 raw → normalize에서 직접 status로 매핑하지 말고 (date_range 추출이 신뢰성 있음), source 모듈에서 "현재 전시 섹션 / 종료 전시 섹션"으로 분리 수집만 한다.

### 4.3 주소

원문 그대로 (`venue_raw_address`) 저장. Google Maps Geocoding이 한자/가나/영문 혼합 주소를 깔끔하게 처리하므로 클라이언트 측 파싱 불필요.

### 4.4 텍스트 정규화 (skip)

전각/반각, kana/kanji 정규화, 로마자 전사는 **비범위**. TOP/TAB 데이터는 그대로 저장. 추후 검색/필터 요구가 생기면 별도 spec.

---

## 5. 신규 소스 모듈

### 5.1 `tokyo_photographic_art_museum` (TOP)

- 도메인: topmuseum.jp (또는 redirect)
- 패턴: 분리형 (개최중 / 予定 / 終了) — 진행+예정만 수집
- 정적 HTML 가능성 높음 (단순 미술관 사이트). JS 렌더이면 plan에서 Playwright fallback.
- venue 1개 고정: 東京都写真美術館 / 東京都目黒区三田1-13-3
- artists: 전시별로 detail 페이지에서 추출 (보통 1~3명 / 그룹전 다수)
- 사진 비중 100% (사진 전문 미술관). normalize whitelist 불필요.
- 동시기 전시 보통 3~5개 (1F~3F 각 다른 전시).

### 5.2 `tokyo_art_beat` (TAB)

- 도메인: tokyoartbeat.com
- 패턴: 애그리게이터. **API vs 스크래핑 plan 시점 검증 항목.** TAB는 과거 RSS와 API를 제공한 이력이 있으나 현재 상태는 plan에서 fetch 후 확인.
- 필터: photography / 写真 카테고리만 — TAB는 모든 미디어 (회화/조각/디자인/공연) 망라하므로 source-level filter 필수.
- 리스트 → 페이지네이션 → detail 페이지(전시별)
- venue: 매번 다름. detail 페이지의 venue 섹션에서 추출 → 새 venue면 Venues 시트 누적, `country = "JP"` stamp
- artists: detail 페이지에서 추출
- 동시기 ~수십~수백 (도쿄 전체 광범위)

**리스크**:
- 안티봇 / 페이지네이션 / Cloudflare 등. plan 첫 task에서 직접 fetch해서 차단 여부 확인 후 UA/headers 조정 (gallery_kong 403 같은 회귀 학습 적용).
- 데이터 볼륨이 큼 → 첫 run에서 backfill 폭주 시 Google Maps quota / Sheets 429 위험. PR #8에서 적용한 retry+backoff가 있어 안전망 있음.

### 5.3 SourceName enum 추가

```python
class SourceName(StrEnum):
    ...
    TOKYO_PHOTOGRAPHIC_ART_MUSEUM = "tokyo_photographic_art_museum"
    TOKYO_ART_BEAT = "tokyo_art_beat"
```

---

## 6. 에러 처리 & 회복

- **Google Maps quota / billing 차단**: Resolver가 None,None 반환 → pipeline이 warning + venue 좌표 없이 저장. Kakao 회로 영향 없음.
- **GeocoderResolver 자체 실패** (env 누락 등): cli 빌드 시 raise. crawl-all 시작 안 함 → secret 누락 알아채기 쉬움.
- **TAB 카테고리 필터 오인식**: source 단계 화이트리스트 — 사진 외 카테고리는 yield 안 함 (상상마당과 동일 패턴).
- **신규 country 충돌**: 동일 venue 이름이 KR과 JP 양쪽에 존재할 가능성 (예: "캐논 갤러리" KR vs "Canon Gallery Tokyo" JP) → entity resolver의 venue 매칭은 name+region+address 조합으로 id 생성하므로 country가 다르면 자연스럽게 다른 id로 분리됨. 추가 로직 불필요. (Plan에서 회귀 테스트 추가.)

---

## 7. 테스트 전략

- `tests/enrich/test_geocoder_google.py` — httpx mock, OK/ZERO_RESULTS/quota 응답별 동작 검증
- `tests/enrich/test_geocoder_resolver.py` — KR/JP 디스패치, 미지 country는 default 폴백
- `tests/normalize/test_dates.py` 확장 — 4.1의 일본 패턴 fixture 케이스 추가
- `tests/sources/test_tokyo_photographic_art_museum.py` — 고정 fixture HTML, 셀렉터 검증
- `tests/sources/test_tokyo_art_beat.py` — 동일
- `tests/integration/test_pipeline_japan_sources.py` — TOP+TAB을 FakeRepo로 end-to-end, country stamp 확인, 일본 venue 새로 생성
- `tests/test_models.py` 확장 — Venue.country default = "KR", 명시값 "JP" 통과

### Plan 시점 검증 항목 (각 소스당)

- 실제 도메인 / 메뉴 경로
- 정적 HTML 여부 (JS 렌더링이면 Playwright fallback)
- 카테고리 / 사진 식별 신호 — TAB는 필수
- 동시기 진행 전시 1개 이상 존재 (fixture 만들기 위해)
- UA / headers / anti-bot 차단 여부 (gallery_kong 403 사례 학습)

---

## 8. 배포 / 운영

- PR 슬라이싱 권장 (plan에서 확정):
  - **PR-A**: 인프라 (Venue.country, GoogleMapsGeocoder, GeocoderResolver, init-sheets 헤더, pipeline 배선, env wiring) — 기능 미노출
  - **PR-B**: TOP 소스 모듈 + 테스트 — 첫 일본 데이터
  - **PR-C**: TAB 소스 모듈 + 테스트 — 대량 데이터
- 각 PR 머지 후 crawl workflow 수동 트리거로 회귀 모니터링
- 사용자 1회 작업: GCP에서 Geocoding API 활성화 + key 발급 → GitHub Secret 등록

---

## 9. 변경되지 않는 것

- KakaoGeocoder 그대로 (KR 소스 동작 무영향)
- 기존 11개 한국 source 코드 무변경
- 기존 Exhibitions/Artists/Organizers 시트 스키마 무변경 (Venues에만 country 컬럼 append)
- crawl.yml 스케줄/구조 (env만 1개 추가)
- normalize 한국 동작 (regex 추가만, 기존 패턴 보존)
