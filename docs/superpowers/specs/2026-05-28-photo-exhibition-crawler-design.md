# 한국 사진/영상/카메라 전시 크롤러 — 설계 (v1)

- **상태**: Draft, 사용자 리뷰 대기
- **작성일**: 2026-05-28
- **범위**: v1 크롤러 + 데이터 정제 파이프라인 + Google Sheets 적재까지. 웹사이트(프론트)는 별도 프로젝트.

## 1. 배경 & 목표

한국에는 사진·영상·카메라 관련 전시·박람회 정보를 한곳에 모아주는 통합 서비스가 없다. 미술관·갤러리 개별 사이트, 통합 전시 사이트, 박람회 공식 사이트가 흩어져 있어 사용자가 매번 N곳을 돌아야 한다.

이 프로젝트의 v1은 **여러 소스에서 사진·영상·카메라 관련 전시 정보를 수집하고, 카테고리·좌표·인기 시그널을 정제해서 Google Sheets에 축적하는 파이프라인**을 만든다. 시트는 이후 별도 웹사이트의 데이터 소스가 된다.

### 성공 기준 (v1)

- P0 소스 5곳에서 매일 자동으로 데이터 수집·갱신
- 4개 메인 시트(Exhibitions/Artists/Venues/Organizers) + 1개 보조 시트(`_overrides`)로 정규화된 데이터 적재
- 새 venue는 자동 지오코딩되어 좌표 포함
- 한 사이트 실패가 다른 사이트 진행을 막지 않음
- 사이트 구조 변경 시 자동 감지 알림

### v1 비범위

- 웹 프론트엔드, 사용자 인증, 가격 결제, 알림 구독 — 별도 프로젝트
- 인기도 점수 산출 (`popularity_score`) — v1.5로 연기, 컬럼만 둠
- LLM 기반 런타임 추출 — 개발 시점에만 AI 사용

---

## 2. 1차 소스 우선순위

레퍼런스(관객 규모, 사진계 영향력, 커버리지 효율) 기반.

| 등급 | 사이트 | 근거 | 역할 |
|---|---|---|---|
| **P0** | 아트맵 (art-map.co.kr) | 데이터 기반 큐레이션, 다수 갤러리 통합 | 양 확보 |
| **P0** | 네이버 전시 검색 | 가장 광범위, 지역/장르 필터 | 양 보완 |
| **P0** | 서울시립 사진미술관 (Photo SeMA) | 한국 유일 공립 사진미술관, 서울사진축제 주관 | 사진 품질 코어 |
| **P0** | 뮤지엄한미 (한미사진미술관) | 2002년 개관 국내 최초 사진 전문 미술관 | 사진 품질 코어 |
| **P0** | KOBA (kobashow.com) | 2026년 4만+ 관객, 220개 업체, 1,000부스 | 박람회/장비 시드 |
| **P1** | P&I 사진영상기자재전 (photoshow.co.kr) | 한국 유일 사진영상 박람회 | 박람회 보완 |
| **P1** | 고은사진미술관 | 부산 권역 사진 미술관 | 지역 확장 |
| **P1** | 공근혜갤러리 (K.O.N.G) | 2005~ 국제 사진작가 소개로 사진계 영향력 | 갤러리 시드 |
| **P1** | 사진위주 류가헌 | 사진계 사랑방 (책방 병행) | 갤러리 시드 |
| **P2** | 보스토크 매거진 | 사진 전문 매거진, 큐레이션 시그널 | 인기 가중치 산출용 |
| **P2** | 99티켓 | 유료 사진전 큐레이션 + 가격 | 가격 보완 |

v1은 P0 5곳부터 시작 → 안정화 후 P1 → 마지막에 P2.

---

## 3. 아키텍처

### 3.1 흐름

```
GitHub Actions cron (매일 03:00 KST)
        │
        ▼
   Orchestrator (CLI)
        │  사이트별
        ▼
   Source Extractor    ─→ RawExhibition (사이트당 1개 모듈)
        │
        ▼
   Normalizer          ─→ NormalizedExhibition
        │
        ▼
   Entity Resolver     ─→ FK 해소 + 신규 Artist/Venue/Organizer
        │
        ▼
   Geocoder            ─→ 신규 Venue 좌표 보강 (카카오 API)
        │
        ▼
   Sheets Writer       ─→ 4시트 upsert (gspread)
```

### 3.2 디렉토리 구조

```
photo-exhibition-crawler/
├── pyproject.toml
├── README.md
├── .github/workflows/
│   ├── test.yml             # push/PR마다
│   ├── crawl.yml            # 매일 cron
│   └── external.yml         # 주 1회 healthcheck
├── src/crawler/
│   ├── cli.py
│   ├── models.py            # pydantic 모델
│   ├── sources/             # 사이트별 추출기 (1파일 1사이트)
│   │   ├── base.py
│   │   ├── artmap.py
│   │   ├── naver_exhibition.py
│   │   ├── photo_sema.py
│   │   ├── museum_hanmi.py
│   │   └── koba.py
│   ├── normalize/
│   │   ├── dates.py
│   │   ├── categories.py
│   │   ├── text.py
│   │   └── dedup.py
│   ├── resolver/
│   │   └── entities.py      # Artist/Venue/Organizer 매칭·생성
│   ├── enrich/
│   │   └── geocoder.py
│   ├── sinks/
│   │   └── sheets.py
│   └── pipeline.py
├── tests/
│   ├── fixtures/<source>/   # HTML 스냅샷 + expected.jsonl
│   ├── sources/
│   ├── normalize/
│   ├── resolver/
│   ├── sinks/
│   └── integration/
└── docs/
    ├── sources/<name>.md    # 사이트별 best practice 노트 (AI assisted)
    └── superpowers/specs/
```

### 3.3 의존성 그래프

```
cli
 └─ pipeline
     ├─ sources/*        ← 다른 컴포넌트 모름
     ├─ normalize/*      ← 순수 함수
     ├─ resolver         ← sinks/sheets만 의존
     ├─ enrich/geocoder  ← 외부 API
     └─ sinks/sheets     ← gspread
```

단방향. 순환 의존 금지. 정제·resolver는 sources를 모른다.

---

## 4. 데이터 모델

메인 4개 시트 + 수동 보정용 보조 시트 1개로 정규화:

```
Exhibitions ──N:1──▶ Venues       (장소: 좌표 캐싱)
     ├────N:M──▶ Artists           (작가/사진가)
     └────N:1──▶ Organizers        (주최: 페스티벌/박람회 분리)
```

**왜 Venues와 Organizers를 분리하나?** 미술관 자체 전시는 같지만 페스티벌·박람회는 다르다:

- KOBA → 주최: 한국전파진흥협회 / 장소: COEX
- 서울사진축제 → 주최: 서울시 / 장소: Photo SeMA

같을 땐 두 컬럼에 같은 ID를 넣어도 된다.

### 4.1 시트 1: `Exhibitions`

| 열 | 컬럼 | 타입 | 비고 |
|---|---|---|---|
| A | id | string | sha1(source\|title\|start_date)[:12] |
| B | source | enum | |
| C | status | enum | upcoming/ongoing/past/unknown (date로 파생). **페이징 정렬 1순위라 C에 배치** |
| D | source_url | url | |
| E | title | string | |
| F | title_en | string | |
| G | description | string | ~200자 요약 |
| H | poster_image_url | url | |
| I | medium | enum | photo/video/gear/mixed |
| J | exhibition_type | enum | solo/group/curated/festival/expo/permanent |
| K | genre_tags | csv | "documentary,landscape" |
| L | fee_type | enum | free/paid/partial |
| M | price_min | int | KRW |
| N | price_max | int | KRW |
| O | activities | csv | 도슨트/워크숍/시연/체험존/컨퍼런스 |
| P | start_date | date | |
| Q | end_date | date | |
| R | open_hours | string | 휴관일 포함 원문 |
| S | artist_ids | csv | → Artists.id |
| T | venue_id | fk | → Venues.id |
| U | organizer_id | fk | → Organizers.id (없으면 venue_id와 동일) |
| V | popularity_score | float | v1은 비움 (v1.5) |
| W | featured | bool | 매거진/언론 노출 시그널 |
| X | crawled_at | iso8601 | |
| Y | updated_at | iso8601 | |
| Z | _warnings | csv | 정제 실패 필드명 (있으면) |

### 4.2 시트 2: `Artists`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | string | sha1(normalized_name)[:12] |
| name | string | 원문 한글 |
| name_en | string | |
| name_normalized | string | 매칭용 (공백/구두점/대소문자 정규화) |
| bio | string | 발견된 한 줄 약력 |
| instagram | url | |
| website | url | |
| sources | csv | 발견된 출처 (artmap,photo_sema...) |
| first_seen_at | iso8601 | |
| updated_at | iso8601 | |

### 4.3 시트 3: `Venues`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | string | sha1(normalized_address or name)[:12] |
| name | string | |
| name_en | string | |
| venue_type | enum | museum/gallery/cafe/alt_space/convention/other |
| region | string | 광역 (서울/경기/부산/...) |
| district | string | 종로구 등 |
| address | string | |
| latitude | float | 지오코딩 1회 캐싱 |
| longitude | float | |
| website | url | |
| open_hours_default | string | 장소 기본 운영시간 |
| sources | csv | |
| first_seen_at | iso8601 | |
| updated_at | iso8601 | |

### 4.4 시트 4: `Organizers`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | string | sha1(normalized_name)[:12] |
| name | string | |
| name_en | string | |
| organizer_type | enum | museum/gallery/foundation/association/corporate/public/other |
| website | url | |
| sources | csv | |
| first_seen_at | iso8601 | |
| updated_at | iso8601 | |

### 4.5 시트 5: `_overrides` (수동 보정)

빈 시트로 시드. 표기 흔들림으로 자동 매칭이 실패한 엔티티의 정답을 수동 입력하면 정제 단계가 우선 적용. 컬럼:

| 컬럼 | 타입 | 비고 |
|---|---|---|
| entity_type | enum | artist/venue/organizer |
| match_pattern | string | 원본 텍스트 패턴 |
| canonical_id | string | 합칠 대상의 id |
| note | string | |

### 4.6 자연키 & 매칭 정책

- **Exhibition.id**: `sha1(source|venue_name|title|start_date)[:12]` — 같은 전시가 여러 소스에 있으면 분리 행
- **Artist.id**: `sha1(name_normalized)[:12]` — `name_normalized`가 같으면 동일 작가로 자동 병합 (한국어/영어 따로 정규화)
- **Venue.id**: `sha1(normalized_address)[:12]` — 주소 없으면 `sha1(normalized_name)[:12]` fallback
- **Organizer.id**: `sha1(name_normalized)[:12]`

100% 자동 매칭은 불가능하므로 `_overrides` 시트로 수동 보정.

---

## 5. 컴포넌트 책임

### 5.1 Source Extractor (`sources/<name>.py`)

- 책임: 사이트 HTML/JSON에서 `RawExhibition` dict만 뽑기 (필드 옵셔널, 원문 보존)
- 의존: httpx 또는 playwright. 다른 컴포넌트 의존 없음.
- 테스트: `tests/fixtures/<source>/*.html` 스냅샷 + `expected.jsonl`

### 5.2 Normalizer (`normalize/`)

- 책임: `RawExhibition` → `NormalizedExhibition`. 날짜/통화/카테고리/한글 정제, enum 매핑
- 서브모듈: `dates.py` (다국어 날짜), `categories.py` (장르·매체 enum), `text.py` (한글 정제), `dedup.py` (자연키 해시)
- 테스트: 입출력 표 기반 파라미터라이즈드

### 5.3 Entity Resolver (`resolver/entities.py`)

- 책임: 작가/장소/주최 이름을 ID로 해소. `_overrides` 우선 적용
- 입력: `NormalizedExhibition` + 현재 엔티티 상태
- 출력: `(exhibition_with_fk, new_artists, new_venues, new_organizers)`

### 5.4 Geocoder (`enrich/geocoder.py`)

- 책임: 신규 Venue의 address → (lat, lng). 기존 좌표 있으면 skip
- 의존: 카카오 로컬 API (`KAKAO_REST_API_KEY`)
- 테스트: API client 모킹, 429/빈 결과 분기

### 5.5 Sheets Writer (`sinks/sheets.py`)

- 책임: 4시트 read/upsert. ID 기준 행 매칭, 변경분만 patch
- 의존: gspread + 서비스 계정
- 테스트: dict 백엔드 Fake로 단위 테스트, 실 API는 통합 1-2개만

### 5.6 Orchestrator (`pipeline.py`)

- 책임: 한 사이트 end-to-end + 부분 실패 격리
- 에러 정책: 행 단위 실패는 skip, 사이트 전체 실패해도 다른 사이트는 계속

### 5.7 CLI (`cli.py`)

```
python -m crawler init-sheets             # 시트 4개 + 헤더 시드 (멱등)
python -m crawler run <source>            # 한 소스만
python -m crawler run-all                 # P0 전체
python -m crawler dry-run <source>        # 시트 쓰지 않고 결과만
python -m crawler reconcile               # 시트 정합성 검사
python -m crawler healthcheck <source>    # 셀렉터 살아있는지
```

---

## 6. 데이터 흐름 & Upsert

### 6.1 한 소스 1회 실행 시퀀스

1. `Sheets Writer.read_all()` → 5시트 전체 메모리 로드 (4 메인 + `_overrides`. v1 행수 1만 이하 가정)
2. `Extractor.crawl()` → `RawExhibition` 스트림
3. for each raw:
   - `Normalizer.normalize(raw)` → `NormalizedExhibition`
   - `Resolver.resolve(normalized, current_state)` → FK 해소 + 신규 엔티티 누적
4. `Geocoder.enrich(new_venues)` → 신규 장소만 카카오 호출
5. diff 계산 (신규 / 변경 / unchanged)
6. `Sheets Writer.upsert(diff)` → gspread batch_update
7. `status` 자동 재계산 (모든 행, 단일 컬럼 patch)
8. 리포트 출력

### 6.2 Upsert 규칙

| 케이스 | 처리 |
|---|---|
| id 같고 모든 컬럼 동일 | 무시 (updated_at 안 건드림) |
| id 같고 일부 컬럼 변경 | 변경 셀만 patch + updated_at 갱신 |
| id 신규 | append |
| 이전엔 있었는데 이번 크롤에서 안 나옴 | soft skip (행 유지) — `reconcile` 커맨드 책임 |

### 6.3 status 자동 계산

```
오늘 < start_date           → upcoming
start_date ≤ 오늘 ≤ end_date → ongoing
end_date < 오늘             → past
날짜 비어있음                 → unknown
```

매 실행 끝에 모든 행 재계산.

### 6.4 엔티티 시트 업데이트 정책

- 자동 삭제 X (추가 only 기본)
- **기존 값은 절대 덮어쓰지 않음**, 빈 값에만 채움 (수동 보정 보호)
- `updated_at`, `sources`는 항상 갱신

### 6.5 동시 실행 안전성

GitHub Actions concurrency group(`crawl`)으로 직렬화. 같은 source 두 번 동시 실행 금지, 다른 source 병렬은 OK (row-level은 Google이 처리).

---

## 7. 에러 처리 · 재시도 · 관측성

### 7.1 에러 분류

| 종류 | 처리 |
|---|---|
| 일시적 네트워크 (timeout, 5xx) | 1s/4s/16s exponential backoff 3회. 최종 실패 시 항목 skip + WARN |
| Rate limit (429) | Retry-After 존중. 없으면 60s 대기 1회 재시도. 두번째 실패 시 사이트 중단 |
| HTML 구조 변경 (셀렉터 실패) | 항목 skip + ERROR. 사이트 내 임계치(20건 또는 50%) 초과 시 사이트 실패 처리 |
| 정제 실패 (날짜/enum) | 해당 필드만 null + `_warnings`에 사유. drop하지 않음 |
| 시트 쓰기 실패 | 5회 재시도. 최종 실패 시 `out/failed-<source>-<ts>.jsonl` dump + 사이트 실패 |
| 시트 인증/권한 오류 (401/403) | 즉시 전체 중단 |
| 개발자 버그 (KeyError 등) | 사이트 단위 격리 |

### 7.2 격리

- 사이트 단위 try/except: 한 사이트 실패가 다른 사이트를 막지 않음
- 항목 단위 try/except: 한 항목 실패가 사이트를 막지 않음 (단, 실패율 임계치 초과 시 사이트 실패로 승격)

### 7.3 구조화 로그

JSON Lines stdout. 필드: `ts/level/source/stage/msg` + 컨텍스트 (`item_url`, `field` 등).

### 7.4 실행 리포트

마크다운 1장으로 `out/report.md` 생성, GitHub Step Summary에 노출.

```
## Crawl Report — YYYY-MM-DD HH:MM KST

| source | extracted | new | updated | skipped | errors | duration |
| ...    | ...       | ... | ...     | ...     | ...    | ...      |

### Failures
- ...
```

### 7.5 조기 감지

각 extractor가 `title` 등 필수 필드 추출률 측정. 평소 대비 크게 떨어지면(< 80%) WARN, 0%면 ERROR + 자동 이슈 생성.

### 7.6 경보

v1은 GitHub 워크플로 실패 알림만. v1.5에서 Discord/Slack webhook.

---

## 8. 테스트 전략

| 카테고리 | 도구 | 네트워크 | CI 기본 실행 |
|---|---|---|---|
| 단위 (normalize/resolver/sinks 등) | pytest, 파라미터라이즈드 | X | ✅ |
| Source extractor (fixture HTML) | pytest-httpx 또는 respx | X | ✅ |
| 통합 (한 사이트 end-to-end, fake sink) | pytest | X | ✅ |
| 외부 통합 (실 사이트/시트) | `-m external` | O | ❌ (주 1회 별도 워크플로) |
| Healthcheck (운영용) | CLI 명령 | O | ❌ (일일 cron) |

### 8.1 Fixture 정책

```
tests/fixtures/<source>/
├── list_page_1.html
├── detail_<id>.html
└── expected.jsonl
```

사이트 구조 변경 시 fixture 재생성 + expected 갱신 → PR diff로 의도 명시.

### 8.2 회귀 방지

- 새 사이트 추가 = fixture + expected + 단위 테스트 필수
- 버그 수정 = 그 케이스 fixture 추가
- 정제 함수 변경 = expected 갱신을 PR에서 명시

### 8.3 커버리지 가이드

- `normalize/`, `resolver/`, `sinks/`: 80%+
- `sources/`: fixture 케이스 커버리지 우선
- `cli.py`: smoke 1개

---

## 9. 운영

### 9.1 GitHub Actions 3개

- `test.yml` — push/PR마다 unit + integration (~1-2분)
- `crawl.yml` — 매일 03:00 KST + 수동 trigger
- `external.yml` — 주 1회 실 사이트 healthcheck

`crawl.yml` 핵심:

```yaml
name: crawl
on:
  schedule:
    - cron: '0 18 * * *'  # 03:00 KST = 18:00 UTC 전일
  workflow_dispatch:
concurrency:
  group: crawl
  cancel-in-progress: false
jobs:
  crawl:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -e .
      - run: playwright install --with-deps chromium
      - run: python -m crawler run-all
        env:
          GOOGLE_SERVICE_ACCOUNT_JSON: ${{ secrets.GOOGLE_SERVICE_ACCOUNT_JSON }}
          SHEET_ID: ${{ secrets.SHEET_ID }}
          KAKAO_REST_API_KEY: ${{ secrets.KAKAO_REST_API_KEY }}
      - if: always()
        uses: actions/upload-artifact@v4
        with: { name: report, path: out/ }
      - if: always()
        run: cat out/report.md >> $GITHUB_STEP_SUMMARY
```

### 9.2 시크릿

| 이름 | 발급 | 권한 |
|---|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | GCP 콘솔 서비스 계정 키. **시트에 서비스 이메일 편집자 공유** | 시트 1개에만 |
| `SHEET_ID` | 시드 시트 ID: `1KjhDcaWVQizAcltjp4HHoWhMonztAeADAMMaaRtKRXI` | n/a |
| `KAKAO_REST_API_KEY` | 카카오 개발자 콘솔 → 앱 → REST API 키 | 로컬 API만 |

### 9.3 시드 (`python -m crawler init-sheets`)

시트가 비어있으면 5개 워크시트(`Exhibitions`/`Artists`/`Venues`/`Organizers`/`_overrides`) 생성 + 헤더 작성. 이미 있으면 헤더만 검증. 멱등.

### 9.4 비용 (월)

| 항목 | 추정 |
|---|---|
| GitHub Actions | ₩0 (free tier 충분) |
| Sheets API | ₩0 |
| 카카오 로컬 API | ₩0 (일 10만건 한도, 실제 일 100건 미만 예상) |

### 9.5 백업 & 롤백

- Google Sheets 자체 90일 버전 히스토리로 충분 (v1)
- 망가졌을 때: 시트 복원 → `crawl.yml` 비활성화 → fixture 갱신 → 재활성화

### 9.6 새 사이트 추가 절차

1. `docs/sources/<name>.md` 작성 (URL, 페이지네이션, 셀렉터, 특이사항 — AI assisted)
2. `tests/fixtures/<name>/*.html` 캡처 + `expected.jsonl` 작성
3. `src/crawler/sources/<name>.py` 구현
4. `tests/sources/test_<name>.py` 통과
5. `normalize/categories.py` enum 매핑 추가, CLI 레지스트리 등록

### 9.7 보안 체크리스트

- [ ] 서비스 계정 JSON git 커밋 금지 (`.gitignore`)
- [ ] 시트 공유는 서비스 계정 + 본인만 (시드 끝나면 사용자가 view-only 전환 결정)
- [ ] User-Agent 정직(`PhotoExhibitionCrawler/0.1 (+<contact>)`), robots.txt 준수
- [ ] 사이트별 robots.txt 확인을 PR 체크리스트에 포함
- [ ] 요청 간 최소 간격 1초

---

## 10. 기술 스택

- **Python 3.12** — 단일 언어 (Scrapy/Playwright/pandas/한글 처리 라이브러리 모두 강세)
- **추출**: httpx + selectolax 또는 scrapy-playwright (사이트 특성에 따라 base.py에서 선택)
- **데이터 모델**: pydantic v2
- **HTTP 재시도**: tenacity
- **시트**: gspread + google-auth
- **지오코딩**: 카카오 로컬 REST API (httpx로 직접 호출)
- **테스트**: pytest, pytest-httpx, freezegun
- **린트/타입**: ruff, mypy
- **CI**: GitHub Actions

---

## 11. 마일스톤

| 마일스톤 | 범위 |
|---|---|
| **M1: 골격** | 모델, CLI, init-sheets, normalize 코어, fake sink로 dry-run 통과 |
| **M2: 첫 사이트** | 아트맵 1개로 end-to-end (extractor → 시트 적재 성공) |
| **M3: P0 5사이트** | 네이버/Photo SeMA/뮤지엄한미/KOBA 추가, GitHub Actions 매일 실행 |
| **M4: 운영 안정화** | healthcheck, external 워크플로, 리포트·알림 |
| **v1 완료 기준** | P0 5곳이 7일 연속 무사고 cron 통과 |

P1·P2는 v1 끝난 뒤 별도 사이클.

---

## 12. 열린 질문 / 추후 결정

- **사이트 변경 알림 채널**: v1.5 도입 시 Discord vs Slack vs 이메일
- **인기도 점수 산출 알고리즘**: v1.5에서 보스토크 매칭 + 사이트별 가중치 정의
- **v2 DB 마이그레이션 시점**: 시트 행 1만 초과하거나 웹사이트 트래픽 발생 시
- **다국어 지원**: 영문 메타 채울지 (`title_en`, `name_en`) — 현재는 발견 시에만 채움, 의도적 번역은 v2
