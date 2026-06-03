# 온보딩 워크스루 + 로그아웃 게이팅 설계

날짜: 2026-06-03

## 배경 / 목표

FRAME 웹앱(`web/`, Next.js 16, Supabase 인증)에 **1회성 온보딩 워크스루**를 추가한다.
검정 반투명 화면 위에 단계별 설명 카드를 띄워 핵심 기능을 안내한다. 안내는 실제
탭을 이동하며 진행한다.

안내 흐름:
1. 둘러보기 타임라인 설명
2. 스와이프로 스크랩(오른쪽)/넘기기(왼쪽) 해보기
3. 스크랩 탭 이동 안내
4. 마이페이지: 로그인 후 구독 설정 가능 설명
5. 버그·피드백 제보 설명

이를 위해 **로그아웃 상태에서도 구독·제보 UI가 보이되, 조작하면 로그인을 유도**하도록
바꾼다(현재는 로그아웃 시 아예 렌더되지 않음). 스크랩도 로그인이 필요함을 안내한다.

## 현재 상태 (확인 완료)

- `app/page.tsx`(둘러보기): `mode: "time" | "swipe"` 내부 상태로 타임/스와이프 전환.
- `components/SwipeDeck.tsx`: 좌우 스와이프 = 넘기기/스크랩, 하단 X·하트·공유 버튼.
- `app/scrap/page.tsx`: 로그아웃 시 로그인 안내 화면만 렌더.
- `app/me/page.tsx`: 로그아웃 시 조기 반환(로그인 안내만). 로그인 시 계정 +
  `SubscriptionSettings` + `FeedbackForm` + 로그아웃 버튼.
- `components/SubscriptionSettings.tsx`, `components/FeedbackForm.tsx`: 둘 다
  `if (!user) return null` — 로그아웃 시 보이지 않음.
- `components/AuthProvider.tsx`: `toggle()`(스크랩)는 로그아웃 시 `signIn()` 호출. `signIn`/`signOut` 제공.
- `components/LanguageProvider.tsx` + `lib/i18n.ts`: `t(key)` i18n. ko/en/ja 사전.
- `components/InstallPrompt.tsx` + `lib/pwa.ts`, `lib/localeStore.ts`: localStorage 기반
  1회성/외부스토어 패턴의 선례.
- `app/layout.tsx`: `LanguageProvider > AuthProvider > (LocaleSync, Nav, …, children)`.

## A. 온보딩 워크스루

### A1. `lib/onboarding.ts` (순수 모듈 — 테스트 대상)
- `ONBOARDING_KEY = "frame.onboarding.v1"` (버전 포함 → 향후 변경 시 재노출 가능).
- `hasSeenOnboarding(): boolean` / `markOnboardingSeen(): void` / `resetOnboarding(): void`
  — `typeof localStorage === "undefined"` 가드 (localeStore와 동일 패턴).
- `OnboardingStep` 타입: `{ id: string; route: string; titleKey: string; bodyKey: string; kind?: "swipe" }`.
- `ONBOARDING_STEPS: OnboardingStep[]`:
  1. `{ id:"welcome",   route:"/",      titleKey:"onb.welcome.title",   bodyKey:"onb.welcome.body" }`
  2. `{ id:"timeline",  route:"/",      titleKey:"onb.timeline.title",  bodyKey:"onb.timeline.body" }`
  3. `{ id:"swipe",     route:"/",      titleKey:"onb.swipe.title",     bodyKey:"onb.swipe.body", kind:"swipe" }`
  4. `{ id:"scrap",     route:"/scrap", titleKey:"onb.scrap.title",     bodyKey:"onb.scrap.body" }`
  5. `{ id:"subscribe", route:"/me",    titleKey:"onb.subscribe.title", bodyKey:"onb.subscribe.body" }`
  6. `{ id:"feedback",  route:"/me",    titleKey:"onb.feedback.title",  bodyKey:"onb.feedback.body" }`

### A2. `components/OnboardingProvider.tsx` (client)
- Context 값: `{ active: boolean; step: OnboardingStep | null; stepIndex: number; total: number;
  start(): void; next(): void; prev(): void; skip(): void; isSwipeStep: boolean }`.
- 상태: `active`, `stepIndex`. `next`가 마지막 단계를 넘기면 `finish()`(= `markOnboardingSeen()` + `active=false`).
  `skip()`도 동일하게 종료.
- 라우팅: `next`/`prev`/`start`로 단계가 바뀌면 그 단계의 `route`가 현재 `usePathname()`과 다를 때
  `useRouter().push(route)`로 실제 탭 이동.
- 자동 시작: 마운트 후 `pathname === "/"` 이고 `!hasSeenOnboarding()`이면 한 번 `start()`.
  (set-state-in-effect는 InstallPrompt 선례대로 eslint-disable 주석 사용.)
- `useOnboarding()` 훅 export. Provider 밖 사용 대비 안전 기본값(컨텍스트 null → no-op) 허용.

### A3. `components/OnboardingOverlay.tsx` (client)
- `active`가 false면 `null`.
- `fixed inset-0 z-50` 검정 반투명 배경(`bg-black/80 backdrop-blur-sm`).
- 하단(모바일 탭 위, `bottom-[88px] md:bottom-8`) 또는 중앙에 설명 카드:
  아이콘/일러스트 + 제목(`t(step.titleKey)`) + 본문(`t(step.bodyKey)`) + 단계 점 표시(`stepIndex/total`)
  + 버튼: `건너뛰기`(skip) / `이전`(prev, 첫 단계 숨김) / `다음`·마지막은 `시작하기`(next).
- `kind === "swipe"` 단계: 좌우 화살표 제스처 애니메이션 힌트(오른쪽=스크랩, 왼쪽=넘기기)를 카드에 포함.
- 디자인 톤: 기존 다크 UI(`border-line2`, `bg-panel2`, 흰 버튼=주요 액션)와 일치.

### A4. 배선 — `app/layout.tsx`
- `AuthProvider` 내부를 `OnboardingProvider`로 감싸고, children 뒤에 `<OnboardingOverlay />` 렌더.

### A5. 스와이프 모드 연동 — `app/page.tsx`
- `useOnboarding()`의 `isSwipeStep`을 읽어, true이고 경로가 `/`면 `mode`를 `"swipe"`로 동기화하는
  `useEffect` 추가. (온보딩이 swipe 단계에 들어오면 사용자가 실제 스와이프 화면을 보게 됨.)

### A6. 재생 — `app/me/page.tsx`
- "안내 다시 보기" 버튼 추가: `resetOnboarding()` 후 `start()` 호출(→ `/`로 이동하며 1단계부터).
  로그인/로그아웃 무관하게 노출.

## B. 로그아웃 게이팅 (방식: 섹션 상단 로그인 배너 + 조작 시 로그인)

### B1. `app/me/page.tsx`
- 로그아웃 조기 반환 제거. 항상 렌더:
  - 헤더(마이) + 계정 카드: 로그인 시 이메일·스크랩 수, 로그아웃 시 로그인 배너 카드(설명 + Google 로그인 버튼).
  - `SubscriptionSettings`, `FeedbackForm` 항상 렌더.
  - 로그아웃 버튼은 로그인 시에만.
  - "안내 다시 보기" 버튼(A6).

### B2. `components/SubscriptionSettings.tsx`
- `if (!user) return null` 제거. `useAuth()`에서 `signIn`도 가져옴.
- 섹션 상단에 로그아웃일 때만 보이는 로그인 안내 배너(`t("sub.loginBanner")`) + 인라인 로그인 버튼.
- `setEnabled`/`setFilters`: `!user`면 `void signIn(); return;`(스크랩 토글과 동일 패턴).
- 로그아웃 시 토글은 기본 off 상태로 보임(조작하면 로그인으로 유도).

### B3. `components/FeedbackForm.tsx`
- `if (!user) return null` 제거. `useAuth()`에서 `signIn` 사용.
- 섹션 상단 로그인 안내 배너(`t("feedback.loginBanner")`, 로그아웃 시만).
- `onSubmit`: `!user`면 `void signIn(); return;` (제보 Edge Function은 인증 필요).
  OAuth 리디렉트로 입력이 사라지는 건 로그인 전이므로 감수.

### B4. `app/scrap/page.tsx`
- 기존 로그인 안내 화면 유지(스크랩 토글은 이미 로그인 유도). 온보딩 `scrap` 단계 문구로 "로그인 필요" 보강.
  추가 코드 변경 없음(문구는 i18n).

## i18n (lib/i18n.ts, ko/en/ja 모두)
- `onb.welcome.title/body`, `onb.timeline.title/body`, `onb.swipe.title/body`,
  `onb.scrap.title/body`, `onb.subscribe.title/body`, `onb.feedback.title/body`
- `onb.skip`(건너뛰기), `onb.prev`(이전), `onb.next`(다음), `onb.start`(시작하기), `onb.replay`(안내 다시 보기)
- `sub.loginBanner`, `feedback.loginBanner`, `sub.signIn`/재사용 `common.signIn`.

## 테스트
- `lib/onboarding.test.ts`: localStorage 게이팅(hasSeen/mark/reset), 단계 배열 불변식(route/key 존재).
- `OnboardingProvider` 로직: start/next/prev/skip의 stepIndex·active 전이(라우터는 모킹).
- `SubscriptionSettings`/`FeedbackForm`: 로그아웃 시 렌더되고 조작 시 `signIn` 호출되는지(기존 테스트 보강).
- 모든 `npm test`, `npm run lint`, `npm run build` 통과.

## 비목표 (YAGNI)
- 실제 DOM 요소 정밀 스포트라이트 추적(요소 위치 측정) — 하지 않음.
- 스와이프 실제 수행 강제 검출 — 하지 않음(제스처 일러스트로 안내).
- 온보딩 단계별 분석/트래킹 이벤트 — 하지 않음.
