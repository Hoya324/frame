# 한국 사진 갤러리 7곳 소스 추가 — 설계

- **상태**: Draft, 사용자 리뷰 대기
- **작성일**: 2026-05-28
- **선행 spec**: [2026-05-28-photo-exhibition-crawler-design.md](2026-05-28-photo-exhibition-crawler-design.md)
- **후속 작업(분리)**: 일본 확장 plan — Tokyo Art Beat + 東京都写真美術館, country 필드 / 일본용 geocoder 인프라 변경 포함

## 1. 배경 & 목적

v1 spec의 P0 5개 소스(artmap / koba / museum_hanmi / photo_sema / Naver 미구현)는 적재되어 현재 Exhibitions 85건 수준. 사용자 관점에서 데이터가 부족함.

artmap이 한국 갤러리 통합 큐레이션이라 80건으로 압도적이고, 나머지 사진 전문관은 동시기 전시 2~3건씩. spec의 P1 후보(고은/공근혜/류가헌) + 그 외 인지도 높은 사진 전문 갤러리/공모전 갤러리를 한 번에 묶어 추가한다.

### 성공 기준

- 7개 새 source 모듈 등록, `run-all` 1회 실행 시 7개 모두 사이트별 fail 격리하며 정상 종료
- Exhibitions 행 추가 ≥ 15건 (`run-all` 1회 기준, 시즌 변동 고려 보수 추정)
- 신규 venue 7개는 `backfill-geocodes` 1회로 좌표 채움 가능
- 상상마당 갤러리의 사진 외 전시(회화/일러스트 등)는 source 단계에서 제외
- 기존 테스트 217 그대로 통과 + 신규 ~35 테스트 추가
- ruff clean

### 비범위 (이번 spec 아님)

- 일본 확장 (별도 spec)
- `Venue.country` 필드 추가, 일본용 geocoder 변경 (일본 spec)
- 사이트 셀렉터 healthcheck workflow (Task 후보 F)
- 추상화된 공통 scraper / selector YAML 외부화 — 7곳 안정화 후 진짜 공통점이 보이면 그때 별도 리팩토링
- `normalize/categories.py` 전반의 reject 정책 재설계 (3절 참조: source-level 해결만)

---

## 2. 대상 사이트 7곳

| # | name (slug) | 사이트 | URL | 사진 비중 | 페이지 패턴 | 주의 |
|---|---|---|---|---|---|---|
| 1 | `goeun` | 고은사진미술관 (부산) | https://www.goeunmuseum.org | 100% | 분리형 (진행/예정/종료) | 영문/국문 페이지 존재, 진행+예정만 수집 |
| 2 | `gallery_lux` | 갤러리 룩스 | https://www.gallerylux.net | 100% | 단순형 (전시 페이지 1개) | 정적 HTML 추정 |
| 3 | `gallery_kong` | 공근혜갤러리 (K.O.N.G) | https://www.gallerykong.com | 100% | 단순형 | 영문 위주, 작가 이름 EN 다수 |
| 4 | `ryugaheon` | 류가헌 (사진위주) | https://www.ryugaheon.com | 100% | 단순형 | 책방 메뉴와 전시 메뉴 분리 — 전시 페이지만 수집 |
| 5 | `ilwoo_space` | 일우스페이스 (한진그룹) | https://www.ilwoospace.org | 80%+ | 단순형 | 일우사진상 수상자 전시 비중 큼, 가끔 사진 외 |
| 6 | `sangsangmadang` | KT&G 상상마당 갤러리 | https://www.sangsangmadang.com | 50% | 분리형 (진행/예정) | **사진 외 전시 섞임 — source-level 화이트리스트 필터 필요** (3절) |
| 7 | `canon_gallery` | 캐논 갤러리 (한국) | https://www.canon-ci.co.kr (gallery section) | 100% | 단순형 | 정기 공모전 수상작 전시 중심 |

URL이 plan 시점에 변동되어 있을 가능성 있음 — plan의 첫 task에서 각 사이트 URL 재확인 후 confirm.

### Plan 시점 검증 항목 (각 사이트당)

- 실제 도메인 / 메뉴 경로
- 정적 HTML 여부 (JS 렌더링이면 Playwright fallback)
- 사진 전시 식별 신호 (카테고리 태그 / URL path / 키워드)
- 동시기 진행 전시 1개 이상 존재 (없으면 fixture 만들기 어려움)

---

## 3. Source-level 화이트리스트 — 상상마당

### 문제

상상마당 갤러리는 사진/회화/일러스트/미디어아트 전시가 섞여 있음. 현재 `normalize/categories.py`는 키워드 기반 medium 분류이지만, "사진" 키워드 없는 회화 전시도 medium=mixed/unknown으로 분류되어 통과한다.

### 결정: Source-level 화이트리스트 (A안)

상상마당 source 모듈 내부에서 fetch 단계에 사진 카테고리 페이지/태그만 수집. 다른 6개 source는 영향 없음. `normalize/categories.py`는 손대지 않음.

기각된 B안 (normalize-level reject 강화): 모든 source에 영향. 기존 적재 데이터 잘못 reject 위험. 글로벌 정책으로 키울 일이 아님.

### 구현 위치

`src/crawler/sources/sangsangmadang.py` 안에:

- 사진 카테고리 페이지/태그 URL 패턴을 모듈 상수로 둠
- `fetch()`에서 그 패턴에 해당하는 항목만 yield
- 단위 테스트: 회화 전시 fixture를 넣고 결과에 없는지 확인

---

## 4. 사이트 모듈 패턴

기존 `artmap` / `photo_sema` / `museum_hanmi` 모듈과 동일 구조. 새 추상화 도입하지 않음.

### 4.1 인터페이스

```python
class BaseSource:
    name: str
    def fetch(self) -> Iterable[RawExhibition]: ...
```

### 4.2 모듈 내부 구조

```python
# src/crawler/sources/<site>.py
_BASE = "https://..."
_LIST_URL = "..."
_VENUE = {  # 사이트 고정 venue
    "name": "...",
    "raw_address": "...",
    "raw_region": "...",
    "website": "...",
}
_LIST_SELECTORS = {"item": "...", "title": "...", "url": "..."}
_DETAIL_SELECTORS = {"description": "...", "artists": "...", "open_hours": "..."}
```

### 4.3 페이지 패턴 두 가지

- **단순형** (룩스/공근혜/류가헌/캐논/일우): 전시 페이지 1개 → 진행/예정 모두 노출됨. 1 HTTP fetch.
- **분리형** (고은/상상마당): 진행/예정 페이지 분리. 진행 + 예정 두 페이지 fetch, 종료 페이지 무시.

### 4.4 상세 페이지 enrichment

artmap detail enrichment 패턴(`251b425`) 따름. 목록에서 `title` / `source_url` / `poster_image_url` / `start_date` / `end_date` 만 잡고, 상세 페이지에서 `description` / `artists` / `open_hours` / `price` 추가. 추가 HTTP 요청은 사이트별 robots.txt + rate limit 존중.

### 4.5 venue 정보

각 사이트는 통상 venue 1개로 고정 (모듈 상수 `_VENUE` = `name` / `raw_address` / `raw_region` / `website`). 캐논/상상마당처럼 분점이 여러 곳이면 plan 시점에 결정 — 사이트가 노출하는 venue만 수집(보통 본관 1곳), 또는 전시별로 venue 필드를 상세에서 파싱. normalize 단계에서 `venue_raw_*` 필드 채움, resolver가 기존 venue 매칭 또는 신규 생성. 좌표는 `backfill-geocodes`가 카카오 API로 채움.

### 4.6 등록

`src/crawler/sources/__init__.py`에 import 7줄 추가. CLI/`run-all`은 변경 불필요 (등록된 source 자동 순회).

### 4.7 에러 정책

기존 pipeline.py가 source 단위 try/except로 격리. 한 사이트 fail → 다른 사이트 진행. 그대로 유지, 변경 없음.

---

## 5. 테스트

### 5.1 Fixture

각 사이트마다 오프라인 HTML 캐시 2~3개:

```
tests/sources/fixtures/<site>/
  list.html
  detail.html
  empty.html      # 진행 전시 0건일 때
```

상상마당은 사진 카테고리 fixture + 회화 카테고리 fixture 둘 다.

### 5.2 Unit test (사이트당 ~5건)

- 목록 페이지 파싱: title / url / 기간 추출 정확성
- 상세 페이지 파싱: description / artists / open_hours
- venue 상수: name / raw_address 매칭
- 빈 페이지 처리: 0건 정상 종료
- 깨진 HTML: warning 발생, 빈 결과

상상마당 추가 테스트:
- 사진 카테고리 fixture: 결과에 포함
- 회화 카테고리 fixture: 결과에서 제외

### 5.3 Integration test

artmap 패턴(`tests/integration/test_pipeline_artmap.py`) 따라 사이트당 1개. 또는 7개 site 묶음 단일 통합 테스트 (`test_pipeline_korea_galleries.py`) 한 개로 통합 — plan 시점에 결정.

### 5.4 신규 테스트 수 추정

7 sites × ~5 unit + 7~8 integration ≈ **35건 추가**. 217 → ~252.

### 5.5 Normalize / resolver / sinks 테스트

변경 없음. 기존 테스트 그대로 통과해야 함.

---

## 6. 운영 / 배포

### 6.1 PR 단위

**단일 PR**. 7개 source는 서로 독립 (다른 파일, 공유 상태 없음)이라 conflict 거의 없음. spec 1개 + plan 1개 + subagent 7개 parallel dispatch로 한 번에 진행. review 1회.

### 6.2 Workflow 변경

`crawl.yml` 변경 없음. `run-all`이 등록된 source 자동 순회.

### 6.3 시트 영향

- **Exhibitions**: ~+15~30건. 컬럼 변경 없음.
- **Venues**: +7개 신규 venue. **머지 후 `crawler backfill-geocodes` 1회 수동 실행**으로 좌표 채움. 다음 cron부턴 자동 (artmap 패턴과 동일).
- **Artists**: 신규 작가 자동 추가 (resolver가 처리).
- **컬럼 변경 없음** — init-sheets 마이그레이션 무관.

### 6.4 Rollback

사이트 1개 selector 깨지면 그 source만 fail → pipeline 전체는 진행. 기존 격리 패턴 그대로. 사이트 1개를 영구 제거하려면 `__init__.py`에서 import 1줄 빼면 끝.

### 6.5 사이트 변경 감시

이번 plan 범위 아님. 후속 Task F (healthcheck workflow — 주 1회 셀렉터 살아있는지)에서 다룸. 다만 신규 7개 source도 healthcheck 대상에 포함되도록 plan F에서 고려.

---

## 7. 작업 분해 (plan 입력용)

writing-plans 단계에서 다음 task로 분해 예상:

1. 각 사이트 URL/페이지 패턴 확인 (manual 1 round)
2. 사이트 7개 모듈 작성 — subagent 7개 parallel dispatch
3. 상상마당 사진 화이트리스트 unit test
4. integration test 7개 (또는 묶음 1개)
5. `__init__.py` 등록 7줄 추가
6. 로컬 `pytest` + `dry-run <site>` 7회 확인
7. PR 생성 / 머지 후 `backfill-geocodes` 1회

---

## 8. 일본 확장 후속 정보 (참고)

이번 spec에는 포함되지 않지만, 별도 spec(Task #5)에서 다룰 영역:

- `Venue.country` 필드 추가 (KR / JP), region 의미 재정의 (KR=시도, JP=도도부현)
- 일본 venue용 geocoder 선택 (Yahoo! Japan API / Nominatim / Google Maps 중)
- Tokyo Art Beat (통합) + 東京都写真美術館 (TOP) 두 사이트 우선
- 일본어 normalize (날짜 표기 / 카테고리 키워드 / 주소 파싱)

데이터 모델/geocoder 변경은 일본 spec 첫 task로. 한국 7곳과는 분리.
