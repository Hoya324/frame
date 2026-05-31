# photo-exhibition-crawler

Crawler for Korean photography/video/camera exhibitions. Writes normalized data into Google Sheets across 5 worksheets: `Exhibitions`, `Artists`, `Venues`, `Organizers`, `_overrides`.

## Setup (one-time)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run tests

```bash
pytest -q              # unit + integration (no network)
ruff check src/ tests/
```

## Configure secrets for live crawling

Create a Google Cloud service account, download its JSON key, and share the target sheet with the service-account email as an Editor.

```bash
export SHEET_ID="1KjhDcaWVQizAcltjp4HHoWhMonztAeADAMMaaRtKRXI"
export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat service-account.json)"
export KAKAO_REST_API_KEY="..."
```

## CLI

```bash
crawler init-sheets       # create 5 worksheets with headers (idempotent)
crawler dry-run artmap    # crawl and print normalized JSON, no writes
crawler run artmap        # crawl one source and upsert
crawler run-all           # crawl every registered source
crawler export-json       # write web/public/data/exhibitions.json snapshot
```

## Adding a new source

1. Write `docs/sources/<name>.md` — list URL, pagination, selectors, quirks.
2. Capture HTML snapshot to `tests/fixtures/<name>/list_page_1.html` and author `expected.jsonl` for the first 3 cards.
3. Implement `src/crawler/sources/<name>.py` with `crawl()` returning `RawExhibition`s and call `register_source(...)` at module bottom.
4. Add `tests/sources/test_<name>.py` mirroring `test_artmap.py`.
5. Add the source value to `SourceName` enum in `models.py` if it's new.

## Currently supported sources

| Name | Type | Status |
|---|---|---|
| `artmap` | aggregator | ✅ |
| `naver` | aggregator | ⚠️ BLOCKED (M3 recon: SPA + IP gating, OAuth route deferred to v1.5) |
| `photo_sema` | museum (Photo SeMA branch only) | ✅ |
| `museum_hanmi` | museum (삼청 + 삼청별관 branches) | ✅ |
| `koba` | expo (annual edition) | ✅ |

## Architecture (one paragraph)

CLI → pipeline → (source extractor → normalizer → entity resolver → geocoder → sheets writer). Each stage is independently testable; sources only know HTTP/HTML, normalizers are pure functions, the resolver only talks to the sink via the Repository protocol, and the gspread implementation is one of two repositories (the other is in-memory for tests).

See `docs/superpowers/specs/2026-05-28-photo-exhibition-crawler-design.md` for full design.

## 피드백 제보 (Supabase Edge Function)

마이페이지의 버그·피드백 폼은 `supabase/functions/feedback` Edge Function을 통해
Resend로 메일을 보낸다. 클라이언트는 로그인 JWT로만 호출할 수 있다(verify_jwt 기본 활성).

### 시크릿 설정 (한 번)

    supabase secrets set RESEND_API_KEY=re_xxx
    supabase secrets set FEEDBACK_TO=hoyana1225@gmail.com
    supabase secrets set FEEDBACK_FROM="FRAME <notify@frame-photo.cloud>"
    # 선택: 허용 오리진 (기본 https://frame-photo.cloud,http://localhost:3000)
    supabase secrets set FEEDBACK_ALLOWED_ORIGINS="https://frame-photo.cloud"

`FEEDBACK_FROM`의 도메인은 Resend에서 검증된 발신 도메인이어야 한다.

### 배포

    supabase functions deploy feedback

JWT 검증은 `supabase/config.toml`의 `[functions.feedback] verify_jwt = true`로
고정되어 있다. 배포 기본값에 의존하지 않으며 `--no-verify-jwt`는 금지.

### 로컬 테스트

    cd supabase/functions/feedback && deno test
