# 개인전 소스 확장 (Round: 작가운영·소형 사진 갤러리) — 설계

작성일: 2026-06-04
범위: KR + JP, 이번 라운드 **4개 소스** 추가

## 배경 / 목표

기존 크롤러는 대형 사진관·미술관·카메라사 중심이라, **독립 작가의 개인전**(소규모/작가운영 갤러리에서 열리고 주로 인스타로 홍보되는 전시)이 잘 잡히지 않는다. 인스타 직접 크롤링은 비공식 API·차단·메타데이터 부정확으로 제외하고, 대신 **개인 작가 개인전이 실제로 열리는 소형/작가운영 사진 전문 갤러리 사이트**를 기존 모듈 패턴으로 추가한다.

2026-06-04 recon으로 plain-HTTP SSR 크롤이 가능하고 사진 100%인 4곳을 확정했다. 혼합 장르(The Reference 등)·Wix/JS 렌더(김영섭사진화랑, 윌링앤딜링, Gallery Index)·폐업(Guardian Garden, 트렁크갤러리)·JS(Nikon Salon)는 이번 범위에서 제외.

## 추가 대상 (4)

| SourceName | 사이트 | 국가 | 비고 |
|---|---|---|---|
| `place_m` | placem.com | JP | 작가운영, 100% 사진 |
| `totem_pole` | tppg.jp | JP | artist-run photography gallery, WordPress |
| `gallery_tosei` | tosei-sha.jp | JP | 사진 전문(冬青社), http-only + Shift_JIS |
| `art_space_j` | artspacej.com | KR | "SPACE FOR PHOTO", 개인전 위주 |

## 공통 패턴 (기존 소스와 동일)

- 사이트당 `src/crawler/sources/<name>.py` 한 파일, 하단 `register_source(SourceName.X, XExtractor)`.
- `sources/__init__.py`에 import 추가, `models.py` `SourceName` enum에 멤버 추가.
- Extractor: `name`, `country`(ClassVar), httpx.Client(브라우저 UA, follow_redirects), `_get`에 tenacity retry, `crawl()`이 `RawExhibition` yield, `self.delay_s` 사이 sleep.
- 4곳 모두 **사진 전용** → `raw["category"]`에 사진 키워드 시드(JP=`"写真"`, KR=`"사진"`)해 `map_medium`이 photo로 분류하게 함. 장르 화이트리스트 불필요.
- 날짜: 점·물결 형식은 공유 `crawler.sources._detail.extract_date_range` 사용. JP `年月日` 형식은 zen_foto식 **source-local** `_extract_jp_date_range`(dotted extractor를 본문에 돌리면 작가 생년 등을 오인하므로 금지).
- 포스터: og:image 있으면 사용, 없으면 본문 첫 `<img src>` 추출(상대경로는 `_BASE_URL`로 절대화).
- `artists`: 안전하게 파싱 가능하면 채우고, 모호하면 `[]`(기존 관례).
- TDD: 실제 페이지를 저장한 HTML 픽스처를 `tests/fixtures/<name>/`에 두고, `tests/sources/test_<name>.py`에서 respx로 `_get`을 목킹 + `_parse_list`/`_parse_detail` 순수함수 단위 테스트.

## 소스별 설계

### 1. `place_m` — Place M / プレイスM (JP)

- `_BASE_URL = "https://www.placem.com"` (apex는 403/redirect → www 필수)
- 목록: `GET /schedule/schedule.php`. 각 항목 = `작가명「제목」` + 날짜 `2026.06.01 - 2026.06.07` + 상대 href `../schedule/2026/main/20260601/exhibition.php`.
- 파싱: 스케줄 행에서 (a) href → `_HREF_RE`로 매칭 후 절대화, (b) 날짜는 `extract_date_range`(점+ASCII 하이픈, 양끝 연도 존재 → OK), (c) 제목 텍스트에서 날짜 토큰 제거 후 `「」` 안쪽=title, `「` 앞=artist 추출.
- 상세: og:image 없음 → 본문 첫 콘텐츠 `<img src>`를 절대화해 poster. description은 본문 prose(`paragraphs_text`/`meta_description` 폴백).
- venue: `Place M`, region `東京`(신주쿠).

### 2. `totem_pole` — Totem Pole Photo Gallery / TPPG (JP)

- `_BASE_URL = "https://tppg.jp"`. WordPress. robots는 `/wp/wp-admin/`만 Disallow → 목록/상세 허용.
- 목록 진입점: **홈페이지**(`/`)가 current + upcoming를 inline SSR로 노출. 항목 = `작가명(JP / EN) "제목"` + 날짜 `2026.5.26 (tue) – 6.7 (sun)` + 상세 slug 링크 `/<slug>/`.
  - 폴백/보강 옵션: WP REST(`/wp-json/wp/v2/posts?_embed`); pretty permalink 404 시 gallery_bresson처럼 `index.php?rest_route=/wp/v2/posts&_embed=1`. **1차 구현은 홈페이지 HTML 파싱**으로 단순화, REST는 필요 시 후속.
- 날짜: 점+`(요일)`+en-dash → `extract_date_range`(weekday-paren strip 처리됨, 끝 연도 없으면 back-fill).
- 제목: `작가 / Artist "Title"` 형태 → 따옴표(`"`/`「」`) 안쪽=title, 앞=artist(JP·EN 병기 가능 → artist는 보수적으로, 모호하면 `[]`).
- 상세: WordPress라 og:image 존재 가능성 높음 → og:image 우선, 없으면 본문 `<img>`. 상세는 slug 페이지.
- venue: `Totem Pole Photo Gallery`, region `東京`(신주쿠).

### 3. `gallery_tosei` — Gallery Tosei / ギャラリー冬青 (JP)

- `_BASE_URL = "http://www.tosei-sha.jp"` — **http only**(https 없음).
- **인코딩 주의: Shift_JIS.** `_get`에서 `httpx` 응답을 bytes로 받아 `decode("shift_jis", errors="replace")` 또는 selectolax에 bytes+encoding 지정. (다른 소스는 utf-8 `r.text` 사용 — 이 소스만 예외 처리.)
- 목록: `/TOSEI-NEW-HP/html/EXHIBITIONS/j_exhibitions.html` (current + next show). 항목 = 제목/작가 + 날짜 `2026年6月28日(日) - 7月12日(日)` + 이미지 `<img src="../../jpg/EXHIBITIONS/...jpg">` + 상세 href `../../html/EXHIBITIONS/j_<Name>.html`.
- 날짜: JP `年月日` 형식 → **source-local `_extract_jp_date_range`**(zen_foto 패턴 복제: 끝 연/월 없으면 start에서 back-fill).
- 포스터: og:image 없음 → 목록/상세의 `<img src>` 상대경로(`../../jpg/...`)를 `_BASE_URL` + 정규화 경로로 절대화.
- 상세 404 주의: 갓 공지된 upcoming 상세(`j_<Name>.html`)는 404 가능 → **목록 페이지만으로 title/date/image 확보**하고 상세는 try/except로 보강만.
- venue: `Gallery Tosei`, region `東京`.

### 4. `art_space_j` — Art Space J / 아트스페이스 J (KR)

- `_BASE_URL = "http://www.artspacej.com"` (https는 self-signed → http 경로 사용; 만약 https 필요 시 httpx `verify=False`). 기본 브라우저 UA 필수(루트 https는 406 WAF, http `/sub/*.php`는 200).
- 목록: current `/sub/sub03_01.php?boardid=exhib`, upcoming `/sub/sub03_03.php?boardid=exhib`, past `/sub/sub03_02.php?boardid=exhib`. 1차 구현은 **current + upcoming** 크롤(과거는 후속).
- 항목 = `[CUBE1]김영진 개인전_제목_2026.03.06-04.30` + 별도 날짜 필드 `2026.03.06 ~ 2026.04.30` + 상세 href `?mode=view&idx=<n>`.
- 파싱: 날짜는 별도 필드 우선 `extract_date_range`(점+`~`). 제목은 `[CUBE1]`/`[CUBE2]` 전시실 태그·말미 날짜 토큰 제거; `작가명 개인전_부제` 패턴에서 `개인전`/`_` 기준 artist 추출(모호하면 `[]`).
- 상세: og:image 없음 → 본문 첫 `/uploaded/board/exhib/l__*.jpg` 이미지 절대화. description은 본문 prose.
- venue: `Art Space J`, region `성남`(분당/판교).

## 데이터 흐름 / 정규화

각 Extractor → `RawExhibition(source, source_url, raw=dict)` → 기존 정규화 파이프라인(`map_medium`이 category 시드로 photo 분류, `parse_date_range`가 `YYYY.MM.DD~YYYY.MM.DD` 해석, venue/artist upsert). 새 정규화 로직 추가 없음 — 기존 경로 재사용.

## 에러 처리

- 상세 fetch 실패(404/timeout)는 per-item try/except로 흡수, poster/description만 None 폴백(기존 pgi 패턴).
- 날짜 미파싱 시 `date_range=None`(경고 없이 허용 — 일부 전시는 포스터에만 날짜).
- 네트워크 오류는 tenacity가 `httpx.TransportError`에 한해 3회 지수백오프 재시도.

## 테스트 전략 (TDD)

소스별로:
1. 실제 목록/상세 페이지를 `tests/fixtures/<name>/list.html`(+ `detail_*.html`)로 저장. Tosei는 Shift_JIS 원본 보존.
2. `test_parse_list_*`: 제목·날짜·URL 추출, 점/`年月日` 날짜 canonical 검증, 중복 제거, 제목 내 연도/전시실 태그 보존.
3. `test_parse_detail_*`: poster(og 또는 `<img>`), description 추출.
4. `test_crawl_*`: respx로 `_get` 목킹, `RawExhibition` 필드(`source`, `country`, `category` 시드) 검증.
5. 회귀: `register_source`로 레지스트리 등록·`all_sources()` 포함 확인.

CI 게이트: `ruff check src/ tests/` + `pytest -q`. (mypy는 CI 아님 — 기존 `register_source`/`source_url` 패턴 오류는 허용.)

## 범위에서 제외 (재조사 방지 기록)

- **The Reference** (the-ref.kr) — SSR 가능하나 사진+회화·영상 혼합 → 이번 사진전용 라운드에서 제외(원하면 후속 medium-분류 라운드).
- **김영섭사진화랑/gallerykim.com** — Wix 부분렌더, 목록 JS·데이터 신선도(2022) 의심. ⚠️ 보류.
- **윌링앤딜링** — Wix, 혼합장르. wix-warmup-data JSON 검증 필요. ⚠️ 보류.
- **집현전 배다리(uram54.com)** — imweb SSR로 쉽지만 사진 전용 아님(헌책방+종합 전시). "사진공간 배다리" 본체는 Facebook 전용.
- **Gallery Niépce** — 혼합장르 렌탈 + 목록 구조 불명. ⚠️.
- **Nikon Salon** — JS 렌더(2020 아카이브만 SSR). ❌ Playwright 필요.
- **Guardian Garden** — 2023 폐업(후속 BUG는 종합 아트센터). ❌
- **트렁크갤러리(서울)** — 자체 사이트 없음(.com 파킹), 인스타 전용. ❌
- **Gallery Index** — Creatorlink JS 렌더. ❌
