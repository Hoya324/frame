# 필터·정렬 컨벤션 통일 디자인

날짜: 2026-06-02
대상: 웹앱 전 목록 페이지(둘러보기·검색·스크랩·지도) + 공간시트의 필터/정렬 UI 통일

## 배경 / 문제

페이지마다 필터·정렬 UI가 제각각이다.

| 페이지 | 상태 필터 | 정렬 | 비고 |
|---|---|---|---|
| 둘러보기(`page.tsx`) | 진행중·곧 종료·예정 | 없음 | + 무료·사진·개인전 |
| 검색(`search/page.tsx`) | 진행중·예정·종료 | 없음 | + 영상·장비·단체전·지역 |
| 스크랩(`scrap/page.tsx`) | 없음 | 마감순(하드코딩) | 컨트롤 없음 |
| 지도(`map/page.tsx`) | 없음(지역만) | 근처순(위치 시 자동) | |
| 공간시트(`VenueSheet.tsx`) | 진행중·예정 | 마감임박·최신순 | 가장 최근 컨벤션 |

문제:
- 같은 "곧 종료" 개념을 `filter.closing`("곧 종료")과 `venue.sortClosing`("마감임박") 두 키/라벨로 다르게 표기.
- 상태 필터 세트가 페이지마다 다름(진행중/곧 종료/예정 vs 진행중/예정/종료).
- 정렬 UI가 공간시트에만 존재.
- 칩 스타일 불일치: `FilterChips`(px-3.5 py-1.5 text-[13px]) vs 공간시트 칩(px-3 py-1 text-xs).

## 목표

전 페이지에 **하나의 필터/정렬 컨벤션**을 적용해 사용자가 어디서나 같은 방식으로 거르고 정렬할 수 있게 한다.

## 결정된 방향 (사용자 확정)

- **상태 필터(다중 선택, 비우면 전체)**: `진행중` · `예정` · `종료` — "마감임박"은 필터가 아니라 정렬로만.
- **정렬(단일 선택)**: `추천순`(기본) · `마감임박` · `최신순` — 모든 목록 페이지에 추가. 지도는 추가로 `가까운 순`(위치 켜졌을 때).

## 디자인

### 1. 공통 정렬 로직 — `lib/sort.ts` (신규)

```ts
export type SortKey = "recommended" | "closing" | "recent" | "nearby";

export interface SortContext { today?: Date; userLoc?: [number, number] | null; }

export function sortExhibitions(items: Exhibition[], key: SortKey, ctx?: SortContext): Exhibition[];
```

정렬 규칙:
- **recommended(추천순)**: featured 우선 → popularityScore 내림차순(null 마지막) → 상태 랭크(진행중<예정<정보없음<종료) → startDate 내림차순.
- **closing(마감임박)**: 진행중 먼저, endDate 오름차순(가까운 마감 먼저), 그 외는 뒤. (기존 공간시트 closing 로직과 동일)
- **recent(최신순)**: startDate 내림차순.
- **nearby(가까운 순)**: `ctx.userLoc` 기준 venue 좌표 거리 오름차순. userLoc 없으면 recommended로 폴백. (Haversine은 기존 `map/page.tsx`의 `distanceKm`를 `lib/geo.ts`로 추출해 공유)

항상 비파괴(`[...items]`). 안정 정렬 가정.

`lib/venueSheet.ts`의 `sortForSheet`는 `sortExhibitions`에 위임하는 얇은 래퍼로 바꿔 중복 제거(공간시트 동작·테스트 유지).

### 2. 공통 필터 로직 — `lib/filters.ts` 재사용

기존 `applyFilters(list, FilterState)`(statuses/mediums/types/freeOnly/regions)를 그대로 사용. 상태 필터는 `FilterState.statuses`(`Status[]`)로 전달.

### 3. 공통 UI 컴포넌트 (신규, `components/controls/`)

- **`FilterGroup.tsx`**: `{ label, children }` → 좌측에 muted 라벨(`text-[11px] text-tx3`) + `flex flex-wrap gap-2` 칩 줄. 라벨 없으면 칩만.
- **`SortChips.tsx`**: 단일 선택 정렬 칩. props `{ value: SortKey, options: SortKey[], onChange, disabled? }`. 라벨은 i18n `sort.*`.
- **`FilterChips.tsx`**(기존, 다중): 유지하되 스타일을 공통 칩 스타일로 통일(아래).

**공통 칩 스타일** (모든 칩 동일):
- 베이스: `rounded-full px-3.5 py-1.5 text-[13px] font-medium transition`
- 활성: `border border-white bg-white font-semibold text-black`
- 비활성: `border border-line text-tx2 hover:text-tx`

공간시트의 상태/정렬 칩도 이 스타일로 교체(현재 `px-3 py-1 text-xs` → 통일).

각 페이지는 이 조각들을 조합해 일관된 컨트롤 바를 구성한다:
```
[상태] 진행중 예정 종료   · (구분선) ·   [그 외] 사진 무료 …   ·   [정렬] 추천순 마감임박 최신순
```
구분선: `mx-1 h-4 w-px bg-line2`. 좁은 화면에서는 자연스럽게 줄바꿈(`flex-wrap`).

### 4. i18n 키 (신규/정리)

신규 canonical 키 추가(ko/en/ja):
- `controls.status` = 상태 / Status / 状態 (기존 `venue.statusLabel` 대체용 — 공간시트도 이 키로 통일)
- `controls.sort` = 정렬 / Sort / 並び替え (기존 `venue.sortLabel` 대체)
- `controls.more` = 그 외 / More / その他
- `sort.recommended` = 추천순 / Recommended / おすすめ順
- `sort.closing` = 마감임박 / Closing soon / 終了間近 (기존 `venue.sortClosing` 값 재사용)
- `sort.recent` = 최신순 / Newest / 新着順
- `sort.nearby` = 가까운 순 / Nearest / 近い順

상태 필터 라벨은 기존 `filter.ongoing`(진행중)·`filter.upcoming`(예정)·`filter.past`(종료) 재사용.
정리: 더 이상 안 쓰는 `venue.statusLabel`/`venue.sortLabel`/`venue.sortClosing`/`venue.sortRecent`는 `controls.*`/`sort.*`로 마이그레이션 후 제거. 둘러보기에서만 쓰던 `filter.closing`("곧 종료")은 상태 필터에서 빠지므로 사용처 제거(정렬 마감임박으로 대체).

### 5. 페이지별 적용

공통: 상태 필터(진행중·예정·종료) + 정렬(추천·마감·최신) + 페이지 고유 그룹은 `그 외`/지역 라벨로 유지.

- **둘러보기(`page.tsx`)**
  - 상태: 진행중·예정·종료 (기존 진행중·곧 종료·예정 → 통일)
  - 그 외: 무료·사진·개인전 (유지, 공통 스타일)
  - 정렬 추가: 추천순(기본)·마감임박·최신순
  - "곧 종료" 필터 제거(마감임박 정렬로 대체)
  - 기존 time/swipe 모드 토글은 유지
- **검색(`search/page.tsx`)**
  - 상태: 진행중·예정·종료 (유지)
  - 그 외: 사진·영상·장비·개인전·단체전·무료 (유지)
  - 지역: 한국/일본 도시 그룹 (유지, 공통 스타일)
  - 정렬 추가: 추천순(기본)·마감임박·최신순
  - 텍스트 검색과 정렬 공존(검색 결과를 정렬)
- **스크랩(`scrap/page.tsx`)**
  - 상태 필터 추가: 진행중·예정·종료
  - 정렬 추가: 추천순·마감임박(기본, 기존 동작 유지)·최신순
  - 빈 상태/0건 처리 유지
- **지도(`map/page.tsx`)**
  - 상태 필터 추가: 진행중·예정·종료 — 마커/클러스터(`items`)와 사이드바 목록 모두에 반영
  - 정렬 추가: 추천순(기본)·마감임박·최신순·가까운 순(위치 켜졌을 때 활성). "내 근처 전시 보기"로 위치를 켜면 정렬을 `가까운 순`으로 전환
  - 지역 칩(유지) + 상태/정렬 한 바에 배치
- **공간시트(`VenueSheet.tsx`)**
  - 칩 스타일을 공통 스타일로 교체, 라벨 키를 `controls.*`/`sort.*`로 통일
  - 기능(진행중·예정 필터 / 마감임박·최신순 정렬)은 유지

## 컴포넌트 경계

- `lib/sort.ts` — 정렬 순수 로직(컴포넌트/페이지 모름).
- `lib/geo.ts` — `distanceKm`(map에서 추출, 지도/정렬 공유).
- `lib/filters.ts` — 기존 필터 로직 재사용.
- `components/controls/FilterGroup.tsx`, `SortChips.tsx` — 표시만 담당, 상태는 부모가 소유.
- 각 페이지 — 자신의 필터/정렬 상태(useState)를 소유하고 lib 로직으로 목록 산출.

## 바꾸는 파일

- 신규: `lib/sort.ts`(+test), `lib/geo.ts`(+test), `components/controls/FilterGroup.tsx`, `components/controls/SortChips.tsx`(+test)
- 수정: `lib/i18n.ts`, `lib/venueSheet.ts`(+test), `components/FilterChips.tsx`, `components/VenueSheet.tsx`(+test), `app/page.tsx`, `app/search/page.tsx`, `app/scrap/page.tsx`, `app/map/page.tsx`

## 테스트 / 검증

- `sortExhibitions` 4종 순서(추천/마감/최신/근처) 단위 테스트
- `distanceKm` 단위 테스트(기존 로직 동등)
- `SortChips` 단일 선택 토글 테스트
- 각 페이지: 상태 필터 적용 시 목록 변화, 정렬 전환 시 순서 변화(통합/수동)
- 지도: 상태 필터가 마커·사이드바 동시 반영, 위치 켜면 가까운 순
- 공간시트: 기존 동작 유지(회귀 없음), 칩 스타일 통일
- 실제 앱 시각 확인(스크린샷)

## 범위 밖 (YAGNI)

- 필터/정렬 상태의 URL 동기화(딥링크) — 이번엔 페이지 내 상태만
- 새 정렬 기준(가격순 등) — 추천·마감·최신·근처만
- 필터 프리셋 저장
