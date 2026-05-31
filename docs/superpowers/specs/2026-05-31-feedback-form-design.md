# 버그·피드백 제보 기능 설계

날짜: 2026-05-31

## 목적

마이페이지에서 사용자가 버그/피드백을 제보하면 `hoyana1225@gmail.com` 으로
이메일이 전송된다. 유형·내용·답장 이메일은 필수이고, 사진 첨부는 선택이다.

## 제약

- 웹은 GitHub Pages 정적 배포(무료) → 클라이언트에서 Resend API 키를 노출할 수 없다.
- 모든 인프라는 무료 티어 안에서 동작해야 한다 (개인·비상업).
- 이미 Supabase(인증·DB)와 Resend(이메일, `/jobs`)를 사용 중이다.

## 결정 사항 (사용자 확정)

- 접근 권한: **로그인 사용자만** 제보 가능.
- 필수 항목: **유형 선택 / 내용 / 답장받을 이메일**.
- 전송 방식: **Supabase Edge Function + Resend**.
- 사진: **메일 첨부파일로 직접 전송** (Supabase Storage 미사용).
- 저장: **메일만 전송, DB 기록 테이블 없음** (YAGNI).

## 아키텍처

```
마이페이지 (로그인 시)
  └─ FeedbackForm 컴포넌트 (마이페이지 카드)
       │ 유형 + 내용 + 답장 이메일(자동채움·수정가능) + 사진(선택)
       ▼ supabase.functions.invoke("feedback", { body })  ← 로그인 JWT 자동 첨부
  Edge Function "feedback" (Deno, verify_jwt=on)
       │ 입력 검증 → Resend REST API 호출
       ▼
  hoyana1225@gmail.com 수신 (사진은 메일 첨부, reply-to = 제보자 이메일)
```

## 컴포넌트

### 1. `web/src/components/FeedbackForm.tsx` (신규, client component)

- 마이페이지(`web/src/app/me/page.tsx`)의 `SubscriptionSettings` 아래 카드로 추가.
- 기존 카드 스타일 재사용: `rounded-lg border border-line p-5`.
- 필드:
  - **유형**: 버그 / 기능제안 / 기타 — 칩 버튼(단일 선택). 기존 `FilterChips`
    패턴을 단일 선택용으로 사용하거나 간단한 버튼 그룹으로 구현.
  - **내용**: `<textarea>`, 필수, 1~2000자.
  - **답장 이메일**: `<input type="email">`, `user.email`로 자동 채움, 수정 가능, 필수.
  - **사진(선택)**: `<input type="file" accept="image/jpeg,image/png,image/webp" multiple>`.
    최대 3장, 각 5MB 이하. 선택 즉시 검증하고 파일명/썸네일 목록 표시, 개별 제거 가능.
- 제출:
  1. 클라이언트 검증(유형 선택됨, 내용 길이, 이메일 형식, 이미지 개수·크기·MIME).
  2. 이미지를 base64로 변환.
  3. `getSupabase().functions.invoke("feedback", { body: { type, message, replyTo, images } })`.
  4. 성공 → 폼 초기화 + 성공 메시지(인라인). 실패 → 에러 메시지(인라인).
- 제출 중 버튼 disabled + 로딩 표시.
- i18n: ko/en/ja 3개 dict 모두에 `feedback.*` 키 추가
  (`web/src/lib/i18n.ts`). 제목·유형 라벨·placeholder·버튼·성공/에러 메시지.

### 2. `supabase/functions/feedback/index.ts` (신규, Deno Edge Function)

- `config.toml`(또는 함수 설정)에서 `verify_jwt = true` → 로그인 사용자만 호출 가능.
  인증 토큰이 없으면 Supabase 게이트웨이가 401 반환 → 함수 내 인증 코드 불필요.
- 의존성 없이 `fetch`로 Resend REST API(`POST https://api.resend.com/emails`) 호출.
- 입력 검증(서버 측, 신뢰 경계):
  - `type` ∈ {`bug`, `feature`, `other`} 화이트리스트.
  - `message` 1~2000자.
  - `replyTo` 이메일 형식.
  - `images` 0~3개, 각 디코딩 크기 5MB 이하, MIME image/jpeg|png|webp.
  - 위반 시 400 + 메시지.
- Resend payload:
  - `from`: `FEEDBACK_FROM` (기존 검증된 도메인 사용, 예: `FRAME <notify@frame-photo.cloud>`).
  - `to`: `FEEDBACK_TO` (`hoyana1225@gmail.com`).
  - `reply_to`: 사용자가 입력한 `replyTo`.
  - `subject`: `[FRAME 제보][유형] ...` 형태.
  - `html`: 유형, 내용, 제보자 이메일, 호출자 `user_id`(JWT의 sub) 포함.
  - `attachments`: `[{ filename, content(base64) }]`.
- CORS: 웹 오리진(`https://frame-photo.cloud`)에 대해 OPTIONS 프리플라이트 응답.
  (`supabase-js functions.invoke`는 브라우저에서 호출되므로 CORS 헤더 필요.)
- 성공 시 200 `{ ok: true }`, 실패 시 적절한 4xx/5xx + 메시지.

## 데이터 흐름

1. 사용자가 폼 작성 후 제출.
2. 클라이언트가 검증·base64 변환 후 `functions.invoke`로 전송 (JWT 자동 포함).
3. Edge Function이 JWT 검증(게이트웨이) 통과 후 입력 재검증.
4. Resend로 메일 전송 (첨부 포함).
5. 결과를 클라이언트에 반환 → 인라인 피드백 표시.

## 에러 처리

- 클라이언트: 필드별 인라인 검증 메시지. 네트워크/함수 실패 시 "전송 실패, 다시 시도" 메시지.
- Edge Function: 검증 실패 400, Resend 실패 502, 예외 500. 본문에 사용자에게 보여줄
  안전한 메시지만 포함(내부 오류 상세는 로깅만).
- Resend 키 미설정 등 구성 오류는 500으로 처리하고 함수 로그에 기록.

## 테스트

- **Edge Function 검증 로직**: 입력 검증 함수를 순수 함수로 분리해 단위 테스트.
  (유형 화이트리스트, 내용 길이, 이메일 형식, 이미지 개수·크기·MIME — 경계값.)
  Resend 호출은 fetch를 주입/모킹해 payload 구성만 검증.
- **FeedbackForm**: 기존 vitest + @testing-library/react 패턴 사용.
  - 필수 필드 미입력 시 제출 차단.
  - 이미지 개수/크기 초과 시 거부.
  - 제출 성공/실패 시 UI 상태(폼 초기화/에러 표시).
  - `functions.invoke`는 모킹.
- 수동 확인: 실제 제보 1건을 전송해 hoyana1225@gmail.com 수신 및 첨부·reply-to 확인.

## 배포 / 시크릿

- Edge Function 배포: `supabase functions deploy feedback` (Supabase 무료 티어).
- Supabase secrets 설정: `RESEND_API_KEY`, `FEEDBACK_TO=hoyana1225@gmail.com`,
  `FEEDBACK_FROM` (검증된 발신 도메인).
- 웹은 기존 GitHub Pages 워크플로 그대로 (정적). 새 NEXT_PUBLIC 환경변수 불필요
  (`functions.invoke`는 기존 `NEXT_PUBLIC_SUPABASE_URL`/`ANON_KEY`로 동작).
- README 또는 jobs/.env.example 인근에 시크릿 설정 절차 문서화.

## 범위 밖 (하지 않음)

- 비로그인 사용자 제보, 익명 제보.
- 제보 내역 DB 저장/조회 화면.
- 관리자 대시보드, 상태 관리(처리중/완료 등).
- Supabase Storage 업로드.
