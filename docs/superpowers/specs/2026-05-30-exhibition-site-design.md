# 전시 디스커버리 사이트 — 설계 문서

작성일: 2026-05-30

## 1. 목적

크롤러가 모은 사진/영상/장비 전시 데이터를 일반 사용자가 탐색할 수 있는 웹 사이트(PWA). 핵심 잡(job)은 **"곧 볼 수 있는 전시를 찾고, 검색하고, 둘러보기"**. 부가로 마음에 드는 전시를 스크랩하고, 메일 구독으로 놓치지 않게 한다.

## 2. 사용자 & 핵심 잡

- 사진/예술 전시에 관심 있는 일반 관람객.
- 주된 행동: ① 지금/곧 열리는 전시 발견 ② 조건으로 검색·필터 ③ 가볍게 둘러보며 발견 ④ 스크랩 ⑤ 메일 알림 구독.
- 모바일·데스크탑 **동등하게** 1급 지원 (반응형 + PWA).

## 3. 디자인 방향

### 톤 (확정)
- **순흑백 (BeReal 톤)**: UI 크롬은 흑/백/회색만. 컬러 액센트 없음. 액센트는 **반전(흰 배경 + 검은 글씨)**으로 표현.
- **구조·완성도는 Linear/Vercel/Raycast 계열**: near-black 표면, 그림자 대신 1px 보더, 또렷한 타이포, 절제된 모션.
- 포스터 사진만 컬러 유지 (BeReal식: 흑백 프레임 + 컬러 콘텐츠).
- 큰/굵은 헤드라인 타이포(800 weight, tight tracking).

### 레퍼런스
- 전시 디스커버리: Ocula(지도↔리스트 동기화), 네오룩(마감일 정렬·아카이브), MMCA(진행/예정/종료 탭·상세 레이아웃).
- 시간·구독·알림: Resident Advisor(개인화 피드 + 알림), DICE(모바일 카드·PWA 감각).
- 포스터·스크랩: Letterboxd(포스터 위 스크랩 버튼·롱프레스 퀵액션), MUBI(시네마틱·"오늘의 전시").
- 미감 기준선: Awwwards/Godly/FWA의 2026 다크 미니멀 트렌드.

### 완성도 요구사항 (구현 단계 필수)
- **아이콘**: 현재 목업의 이모지는 전부 플레이스홀더. 통일된 아이콘 세트(예: Lucide)로 교체.
- **버튼·컴포넌트**: hover/active/focus/disabled 상태, 전환 애니메이션, 마이크로 디테일 완성도를 대폭 끌어올린다.

> 목업 파일(브레인스토밍 산출물): `.superpowers/brainstorm/.../content/` 의 `home-bw.html`, `mobile-bw.html` 참고. (gitignore 대상이라 git에는 미포함.)

## 4. 정보 구조 (IA) & 화면

내비게이션: 데스크탑 = 상단 내비 / 모바일 = 하단 탭.

- **둘러보기 (홈, 기본)** — "지금 볼 수 있는 전시"가 최상단. 상태 칩(진행중/곧 종료/예정/무료/매체/유형). **모드 토글: 타임(C) ↔ 스와이프(E)**. featured 1건 + "곧 종료"(D-day) + "진행 중" 그리드.
- **검색 / 필터** — 매체(사진/영상/장비)·유형(개인전/단체전/큐레이션/…)·요금·지역·기간·작가·장르. 클라이언트 사이드 검색.
- **지도 (D)** — MapLibre + OSM. 좌표 핀, 권역(삼청·을지로 등) 그룹, 현 위치 주변, 지도↔리스트 동기화.
- **전시 상세** — 포스터·기간·장소(미니지도)·작가·요금·설명. 스크랩 ♥, 공유, 길찾기, 작가/장소 링크.
- **스크랩 (로그인)** — 담은 전시 모음, 종료 임박 정렬, 메일 알림 연동.
- **마이 / 구독 (로그인)** — Google 로그인, 메일 구독 설정.

### 세 가지 발견 모드 (같은 데이터의 세 렌즈)
- **C 타임**: 진행중 / 곧 종료(D-day) / 예정. 시간 축 중심. 홈 기본.
- **D 지도**: 공간 축. 동네 단위 "전시 산책".
- **E 스와이프**: 우연 발견. 풀스크린 포스터 1장씩, ✕ 넘기기 / ♥ 스크랩 / ↗ 공유.

## 5. 아키텍처 — 두 개의 데이터 평면

### 5.1 카탈로그 (읽기 전용)
- 크롤러 → **정적 JSON 스냅샷** 생성 → 리포 커밋 → Vercel 자동 재배포.
- 프론트는 JSON을 받아 **검색·필터·정렬을 클라이언트에서** 처리 (데이터 ~100건 규모, 메모리 충분, 구글 시트 읽기 쿼터 문제 회피).

### 5.2 사용자 평면
- **Supabase** (Postgres + Auth). Google OAuth, 스크랩, 구독 저장. RLS로 본인 데이터만 접근.

### 5.3 지도
- MapLibre GL + OSM 타일 (무료, 국내·해외 좌표 모두 커버).

## 6. 리포 구조 & 데이터 흐름

- **모노레포**: 기존 `src/crawler`(Python) 유지 + 신규 `web/`(Next.js + Tailwind).
- 크롤러 파이프라인에 **JSON export sink** 추가 → `web/public/data/exhibitions.json` 생성 (프론트용으로 적당히 비정규화: 전시에 venue/artist 핵심 필드 인라인 + 별도 venues/artists 배열).
- 기존 GitHub Actions 크롤 워크플로우 주기 실행 → JSON 갱신 커밋 → Vercel 배포. **런타임 백엔드 없이 항상 최신.**

### 카탈로그 JSON 형태 (초안)
```json
{
  "generated_at": "2026-05-30T06:54:00Z",
  "exhibitions": [
    {
      "id": "…", "title": "…", "title_en": null,
      "poster_image_url": "…", "description": "…",
      "medium": "photo", "exhibition_type": "solo",
      "genre_tags": [], "fee_type": "free",
      "price_min": null, "price_max": null,
      "start_date": "2026-05-30", "end_date": "2026-07-20",
      "status": "ongoing", "open_hours": "…",
      "venue": { "id": "…", "name": "한미사진미술관", "region": "서울",
                 "district": "삼청", "lat": 37.5, "lng": 126.9 },
      "artists": [ { "id": "…", "name": "…" } ],
      "source_url": "…", "featured": false, "popularity_score": null
    }
  ],
  "venues": [ … ],
  "artists": [ … ]
}
```
(필드는 `src/crawler/models.py`의 `NormalizedExhibition`/`Venue`/`Artist`에서 파생.)

## 7. 사용자 DB 모델 (Supabase)

- `profiles` (id = auth uid, email, created_at)
- `bookmarks` (user_id, exhibition_id, created_at) — exhibition_id는 카탈로그 id(string) 참조
- `subscriptions` (user_id, type = `weekly_digest | closing_soon | custom`, enabled bool, filters jsonb)
  - custom filters: `{ artists:[], regions:[], genres:[], mediums:[] }`
- `email_log` (user_id, type, sent_at, ref) — 중복 발송 방지
- 모든 테이블 RLS: `auth.uid() = user_id` 인 행만 read/write.

## 8. 메일 시스템 — GitHub Actions cron + Resend

`web/`(또는 별도 `jobs/`)의 Node 스크립트가 카탈로그 스냅샷 + Supabase(service role key)를 읽어 Resend로 발송.

- **주간 다이제스트**: 주 1회. 신규/진행 전시 추려 구독자에게.
- **종료 임박**: 매일. 각 유저 스크랩 중 `end_date - today ∈ {3, 1}` 리마인드.
- **맞춤 알림**: 매일. 신규 전시를 유저 custom filters와 매칭.
- 발송 후 `email_log`에 기록해 중복 방지.

## 9. PWA

- `manifest.json` + 서비스워커(next-pwa). 설치형, 앱셸 + 카탈로그 JSON 오프라인 캐시.
- 푸시 알림은 v1 제외 (메일이 알림 역할). 필요 시 v2.

## 10. 기술 스택

- 프론트: **Next.js + Tailwind**, 정적 배포(Vercel).
- 지도: MapLibre GL + OSM.
- 인증·DB: Supabase (Google OAuth).
- 메일: Resend + GitHub Actions cron.
- 크롤러: 기존 Python 파이프라인 + JSON export sink 추가.

## 11. 단계 (권장 빌드 순서)

- **P1**: 카탈로그 JSON export + 둘러보기(타임)·스와이프 + 검색/필터 + 상세 + 지도 + 반응형 + PWA 셸 (로그인 없음).
- **P2**: Google 로그인 + 스크랩.
- **P3**: 구독 설정 UI + 메일 잡(주간/종료임박/맞춤).

## 12. 범위 밖 (YAGNI)

- 웹 푸시 알림 (v1 제외).
- 티켓 구매/예약, 결제.
- 소셜 기능(팔로우·댓글·리뷰).
- 다국어 UI (데이터의 영문 필드는 노출하되 UI는 한국어).
- 관리자 CMS (데이터는 크롤러가 소유).
