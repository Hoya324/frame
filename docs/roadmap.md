# 로드맵 & 다음 작업 (2026-05-28 기준)

다음 세션 시작 시 이 문서 먼저 읽고 작업 결정.

## 현재 상태 스냅샷

| 항목 | 상태 |
|---|---|
| GitHub | https://github.com/Hoya324/allphoto (main) |
| 시트 | https://docs.google.com/spreadsheets/d/1KjhDcaWVQizAcltjp4HHoWhMonztAeADAMMaaRtKRXI |
| Service account | `allphoto-crawler-sa@allphoto-crawler.iam.gserviceaccount.com` (시트 편집자) |
| Sheets API | ✅ 활성화 |
| Kakao Local API | ✅ 활성화 |
| 적재된 데이터 | Exhibitions 84 / Venues 67 (좌표 59) / Artists ~0 / Organizers 일부 |
| 등록된 sources | `artmap`, `koba`, `museum_hanmi`, `photo_sema` (Naver 제외) |
| 테스트 | 200/200 pass, ruff clean |

## 로컬 환경 사용법 (다음 세션 reminder)

```bash
cd /Users/hoyana/Desktop/01_sideproject/photo-exhibition-crawler

# .venv가 .pth 신뢰 못하는 이슈가 있어 매번 reinstall이 가장 안전
.venv/bin/pip install -e . --quiet

# 또는 PYTHONPATH 우회
export PYTHONPATH=src

# 시크릿 (매 shell마다 export)
export SHEET_ID="1KjhDcaWVQizAcltjp4HHoWhMonztAeADAMMaaRtKRXI"
export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat /Users/hoyana/Downloads/allphoto-crawler-7857be59dae5.json)"
export KAKAO_REST_API_KEY="58b99f1ce43d7d02e84693af4964e603"

# 명령
.venv/bin/crawler init-sheets
.venv/bin/crawler dry-run artmap
.venv/bin/crawler run artmap
.venv/bin/crawler run-all
.venv/bin/crawler backfill-geocodes
```

⚠️ **보안 권장**: 위 카카오 키 + GCP 서비스 계정 키는 이전 대화에 노출됐음. 다음 세션 시작 전 회전 권장.

---

## 즉시 가능한 작업 (우선순위순)

### 🔥 1. M4 — GitHub Actions cron 자동화 (가장 임팩트 큼)

**왜 먼저인가**: 지금은 수동 실행. cron 걸면 매일 신선한 데이터 들어옴. 사람 손 안 가도 시트 누적.

**범위**:
- `.github/workflows/crawl.yml` 만들기 (매일 03:00 KST = cron `0 18 * * *` UTC)
- GitHub Repository Settings → Secrets에 `SHEET_ID` / `GOOGLE_SERVICE_ACCOUNT_JSON` / `KAKAO_REST_API_KEY` 등록
- `workflow_dispatch` 트리거도 추가 (수동 실행 가능)
- 실행 후 `out/report.md`를 GitHub Step Summary에 노출
- 실패 시 워크플로 fail → GitHub 알림

**시작점**: spec §9 (운영), plan M1+M2 Task 20 (test.yml 작성 패턴).

**예상 작업량**: subagent 1번 dispatch면 끝 (1 task plan, ~30분).

---

### 🟢 2. `_overrides` 보조 시트로 no_match 8개 보정

**왜**: backfill에서 매칭 안 된 venue 8개 (예: "삼청", "스페이스 톤" 등)를 수동으로 좌표 또는 정식 주소로 보정. 새 사이트 추가할 때마다 이런 케이스 또 생길 거라 워크플로 굳히기.

**범위**:
- `_overrides` 시트는 이미 존재. 컬럼: `entity_type`, `match_pattern`, `canonical_id`, `note`.
- 현재 resolver는 `_overrides`를 읽지만 venue alias로만 사용. **좌표 직접 입력은 미지원**.
- 새 entity_type "venue_geocode"를 추가하거나, 별도 시트 `_venue_coords` 추가.
- backfill 명령이 `_overrides`/`_venue_coords` 도 읽어서 수동 좌표 적용하게.

**예상 작업량**: 작은 plan + 1 task. ~1시간.

---

### 🟡 3. v1.5 큰 plan 작성 — 프론트엔드 + Naver + popularity

**왜**: 사용자의 원래 목표는 "시트 → 웹사이트". 백엔드 데이터는 준비됨. 이제 사용자가 볼 UI.

**3개 별도 plan으로 분리**:

#### 3-A. 프론트엔드 (Next.js or 단순 React + 지도)

- 시트를 source-of-truth로 두고 client에서 직접 fetch (Sheets API public read) 또는 별도 백엔드 API
- 페이지: 전시 목록 (페이징/필터링) + 지도 (네이버 maps 또는 카카오 maps) + 디테일
- 검색·필터: medium / region / status / 기간 / 무료여부
- 인기 가중치 정렬 (popularity_score 비어있어도 status + start_date 정렬로 임시)
- **시작점**: 새 repo (`allphoto-web`) 또는 같은 repo 안 `web/` 디렉토리

#### 3-B. Naver source 추가 (Open API 경로)

- developers.naver.com에 앱 등록 → `client_id`/`client_secret`
- `openapi.naver.com/v1/search/exhibition.json` 호출
- `src/crawler/sources/naver.py` 작성 (httpx + OAuth 헤더)
- `docs/sources/naver.md` 업데이트 (BLOCKED → 해결 방법)
- **시작점**: 현 `docs/sources/naver.md` 참고

#### 3-C. Popularity scoring

- 보스토크 매거진 (vostokpress.com) crawl → "추천" 카테고리에 등장한 전시 매칭
- 매칭된 전시는 `featured=TRUE` + `popularity_score` 가산
- title 또는 venue+date 부분 매칭 알고리즘 필요
- **시작점**: spec §1 (popularity_score 의도), v1.5 임팩트 평가 후 결정

---

### 🔵 4. 작은 보강 (틈틈이)

- **Artmap detail page 보강**: 현재 list page만 → artist/description/관람료 등 detail page에서 더 가져오기 (v1.5에서 1-2시간)
- **medium 분류 정확도**: `mixed`가 너무 많음. title + venue 종류 + organizer 조합으로 더 정확하게.
- **Healthcheck workflow** (`external.yml`): 주 1회 실 사이트 셀렉터 살아있는지 확인 → 사이트 구조 변경 조기 감지. spec §8.5에 명시됨.
- **`.venv` .pth 이슈 해결**: 매번 `pip install -e .` 안 해도 되게 — `pyproject.toml`의 hatchling 설정 조정 또는 `[tool.pytest.ini_options] pythonpath` 보강. 5분 작업.

---

## 큰 사이클 (장기)

| 단계 | 내용 |
|---|---|
| **v1 완성** | M4 (cron) + 프론트엔드 (3-A) + Naver (3-B) — 약 1-2주 |
| **v1.5** | popularity + 매거진 추가 + 인기도 정렬 | 
| **v2** | Sheets → PostgreSQL 마이그레이션 (행 1만 초과 시) + 사용자 인증 + 알림 구독 |

---

## 다음 세션 시작 체크리스트

다음 세션 켰을 때 이 순서로:

1. `git pull` (origin/main 동기화)
2. `.venv/bin/pip install -e . --quiet` (.pth 이슈 우회)
3. `.venv/bin/pytest -q` (200 pass 확인)
4. **이 문서 다시 읽기** — 우선순위 결정
5. 작업 시작 — 일반적으로 가장 임팩트 큰 1번 (M4 cron) 권장

만약 사용자가 "지난번 어디까지 했지?"라고 묻거든, 답:
- "v1 골격 + 4 source 적재 + 좌표 backfill까지 완료. M4 GitHub Actions cron 자동화가 다음 임팩트 가장 큼."

---

## 참고 문서

- 스펙: `docs/superpowers/specs/2026-05-28-photo-exhibition-crawler-design.md`
- 완료된 plans:
  - `docs/superpowers/plans/2026-05-28-m1-m2-foundation-and-first-source.md`
  - `docs/superpowers/plans/2026-05-28-m3-additional-p0-sources.md`
- 사이트별 노트: `docs/sources/{artmap,naver,photo_sema,museum_hanmi,koba}.md`
- README (운영 가이드): `README.md`
