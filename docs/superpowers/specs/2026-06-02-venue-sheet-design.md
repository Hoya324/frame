# 공간 시트(Venue Sheet) 디자인

날짜: 2026-06-02
대상: 웹앱 지도 페이지 — 같은 장소의 여러 전시 둘러보기 UI

## 배경 / 문제

지도에서 같은 venue(장소)의 전시들은 하나의 포스터 마커 + 개수 배지(예: `83`)로 묶여 표시된다. 마커를 누르면 사이드바가 해당 venue의 전시만 필터링해서 보여준다.

문제:
- "한 공간에 여러 전시가 있다"는 사실이 **개수 배지 숫자로만** 표현돼 직관적이지 않다.
- 둘러보기 경험이 평범한 사이드바 필터라 "이 공간 둘러보기"라는 맥락이 약하다.

목표: **"하나의 공간 = 여러 전시"**를 한눈에 알 수 있고, 그 공간의 전시들을 기분 좋게 둘러볼 수 있는 UI를 만든다.

## 현재 구조 (참고)

- 프레임워크: Next.js 16 / Tailwind v4 / MapLibre GL (CARTO Dark Matter 베이스맵)
- `web/src/components/MapView.tsx`
  - `toFeatureCollection()` (L30-63): 전시들을 venue 단위로 집계 → venue당 GeoJSON feature 1개 (count, poster, venueName, firstId)
  - `posterMarkerEl()` (L67-86): 포스터 썸네일 마커 + 개수 배지 생성
  - 마커 클릭 (L138-143): `count > 1`이면 `onVenueSelect(venueId, venueName)`, 아니면 `onSelect(firstId)`
  - 클러스터 레이어 (L166-199): MapLibre 네이티브 클러스터(저줌에서 원 + 숫자)
- `web/src/app/map/page.tsx` (L75-87): 멀티 전시 venue 클릭 시 사이드바를 해당 venue 전시로 필터
- `web/src/components/ExhibitionCard.tsx`: 포스터·상태배지·제목·날짜·스크랩 버튼이 있는 카드 (재사용)
- 데이터: `web/src/lib/catalog.ts` — `Exhibition`(status, startDate, endDate, venue 등), `VenueEmbed`(id, name, region, district, lat, lng, tr)

## 디자인

### 1. 공간 시트(Venue Sheet) — 반응형 컴포넌트

멀티 전시 venue 마커를 누르면 전용 시트가 열린다. 하나의 컴포넌트를 반응형으로 처리한다.

- **모바일**: 하단에서 올라오는 **바텀시트**
  - 드래그 핸들
  - 스냅 2단계: peek(절반, 약 50vh) → full(약 90vh)
  - 배경 딤(backdrop), 아래로 스와이프 또는 딤 탭 시 닫힘
- **데스크탑**: 우측에서 슬라이드되는 **사이드 패널** (~380px 폭)
  - 지도는 좌측에서 계속 조작 가능
  - 닫기(X) 버튼

기존 "사이드바 필터" 방식은 이 시트로 대체한다.

### 2. 시트 헤더 (sticky)

- 공간 이름 (크게) — 예: `캐논갤러리 호텔점`
- 위치: `부산 · 해운대구` (region · district)
- 상태 요약: `전시 83 · 진행중 12 · 예정 5`
  - venue의 전시 목록에서 `status`로 집계 (ongoing/upcoming)
- 정렬 칩(단일 선택): `진행중 먼저`(기본) · `마감임박` · `최신순`
  - 진행중 먼저: status 우선순위(ongoing > upcoming > past) 정렬
  - 마감임박: ongoing 중 `endDate` 오름차순
  - 최신순: `startDate` 내림차순
- 닫기(X) / 모바일 드래그 핸들

### 3. 시트 본문

- 포스터 **2열 그리드** — `ExhibitionCard` 재사용
- 시트 내부 스크롤
- 카드 클릭 → 기존 전시 상세 `/exhibitions/[id]` 이동

### 4. 지도 마커 stacked 디자인

시트를 열기 전에도 "여러 전시"임이 보이도록, `count > 1` 마커는 **포스터가 살짝 겹쳐 쌓인 모양(stacked)** + 기존 개수 배지를 함께 표시한다.

- 단일 전시(count=1): 기존처럼 포스터 한 장
- 멀티 전시(count>1): 뒤쪽에 1~2장의 카드가 살짝 겹쳐진 stacked 룩 + 개수 배지
- 순수 CSS(가상 요소 또는 추가 레이어 div)로 구현해 마커 DOM/이미지 추가 로드 없음

### 5. 동작 디테일

- 시트가 열리면 선택된 마커를 지도에서 **강조**(살짝 확대 / 하이라이트 보더)
- 시트가 닫히면 강조 해제
- 단일 전시 venue는 지금처럼 **바로 상세로** 이동 (시트 없음)

## 컴포넌트 경계

- `VenueSheet.tsx` (신규): props로 `venueId`, `venueName`, `venue` 메타, `exhibitions`(해당 venue 전시 배열), `isOpen`, `onClose`를 받는다. 내부에서 정렬 상태와 반응형 레이아웃(바텀시트/사이드패널)만 책임진다. 데이터 패칭/마커는 모른다.
- `MapView.tsx`: 마커 stacked 스타일 + 선택 강조 + 멀티 전시 클릭 시 `onVenueSelect` 콜백(기존 시그니처 유지). 시트 자체는 모른다.
- `map/page.tsx`: 선택된 venue 상태를 들고 `VenueSheet`에 전시 목록을 넘긴다. 기존 사이드바 필터 로직을 시트 연결로 대체.

## 바꾸는 파일

- `web/src/components/VenueSheet.tsx` — **신규**
- `web/src/components/MapView.tsx` — stacked 마커, 선택 강조
- `web/src/app/globals.css` — stacked 마커 스타일, 시트/패널 트랜지션
- `web/src/app/map/page.tsx` — 사이드바 필터 → 시트 상태 연결

## 테스트 / 검증

- 단일/멀티 전시 venue 클릭 동작 분기
- 정렬 칩 3종이 올바른 순서를 만드는지
- 모바일(바텀시트 스냅/스와이프 닫기)·데스크탑(사이드 패널) 반응형 전환
- 상태 요약 집계 숫자 정확성
- MapLibre 마커 강조/해제 토글

## 범위 밖 (YAGNI)

- 시트 내 추가 필터(무료/사진만 등) — 정렬만 제공
- 공간 운영시간/주소 등 풀 venue 정보 — 이름/위치/개수까지만
- 마커 스파이더화(지도 위 펼침) — 시트 방식으로 대체
