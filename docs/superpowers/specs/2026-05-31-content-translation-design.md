# 전시 콘텐츠 다국어 번역 설계

작성일: 2026-05-31

## 배경 / 문제

크롤러는 한국·일본 소스에서 사진 전시를 수집해 웹앱에 표시한다. UI 라벨은 이미 ko/en/ja i18n이 적용돼 있지만, **전시 콘텐츠 자체**(제목·설명·미술관명·작가명)는 원문 언어 그대로 저장·표시된다. 그 결과 한국어 모드에서 일본 전시를 보면 `戎康友 「A Whole California Anthology」`처럼 일본어가 그대로 노출되어 한국 사용자가 읽지 못한다. 모든 언어 조합에서 같은 문제가 발생한다.

데이터 현황(532건 기준):
- 제목 ~11k자, 설명 ~861k자(전체의 98%), 고유 미술관 134개/~1.7k자, 고유 작가 79개/~1.2k자
- 3개 로케일 풀 커버 시 번역 대상 ~175만 자 (원문 외 2개 로케일 ×)
- 530/532건이 한국어 소스(`title_en` 대부분 null), 일본어 콘텐츠는 JP 4개 소스에 집중

## 제약

- **무료 배포/운영**: 전 구간 무료 티어로 동작해야 함(개인·비상업). [[project_free_deployment]]
- 웹앱은 정적 호스팅 유지(빌드 타임 데이터 번들).
- 월 한도가 있는 클라우드 번역 무료 티어(DeepL/Google 50만 자/월)로는 175만 자 초기 백필을 한 번에 처리 불가.

## 핵심 결정

1. **번역 시점**: 크롤/수집 시점 사전번역. 결과를 store에 영속화하고 JSON으로 export. 조회 시 비용 0, 정적 호스팅 유지.
2. **번역 엔진**: **Argos Translate**(오프라인, 파이썬). 비용 0·한도 0·카드 불필요로 대량 백필 가능. 트레이드오프: 오프라인 NMT 품질이 DeepL보다 낮고, 백필이 CPU로 수십 분~수시간(1회성).
3. **표시 모델**: 기본은 **원문 그대로** 표시. 사용자가 탭하면 현재 UI 언어로 번역을 보여준다(원문은 보존). 기존 UI i18n과 별개의 추가 기능.
4. **인터랙션**: **하이브리드** — 짧은 항목(제목·장소·작가)은 인라인 토글, 긴 소개글은 팝오버.

## 1. 데이터 모델 & 스키마

엔티티별로 로케일 키 번역 맵을 추가한다. 원문은 절대 덮어쓰지 않는다.

```jsonc
// exhibition
{
  "title": "戎康友 「A Whole California Anthology」",   // 원문 유지
  "description": "カリフォルニアを…",                    // 원문 유지
  "lang": "ja",                                         // 원문 언어 (소스 country에서 도출)
  "tr": {                                               // 원문 외 로케일만 채움
    "ko": { "title": "에비스 야스토모 「…」", "description": "캘리포니아를…" },
    "en": { "title": "…", "description": "…" }
  }
}
// venue:  name + lang + tr.{locale}.name (region/district 포함)
// artist: name + tr.{locale}.name
```

- **번역 대상 필드**: 전시 `title`·`description`; 미술관 `name`·`region`·`district`; 작가 `name`. medium/type/fee 등은 기존 UI i18n 라벨로 처리하므로 제외.
- **원문 언어(`lang`) 도출**: 소스 country(KR→ko, JP→ja). 미술관은 자체 `country` 사용. 작가는 country가 없으므로 이를 참조하는 전시의 lang을 따르되 기본 ko로 폴백.
- **스키마 형태**: 평면 접미사(`title_ko`)가 아니라 `tr.{locale}` 중첩 맵. 로케일 추가에 강하고, 기존 `title_en`/`name_en`은 `tr.en.title`/`tr.en.name`으로 흡수.
- **기존 `title_en`/`name_en` 처리**: export에서 이 평면 필드 방출을 중단하고 `tr.en`으로 일원화한다. `catalog.ts`의 `titleEn`/`nameEn` 파싱·사용처(`ExhibitionCard`의 `bilingual(e.title, e.titleEn)` 등)는 `tr` 기반으로 대체한다. 단일 데이터 소스를 유지하기 위함(이중 표기 방지).
- **원문 보존 근거**: 기본 표시가 원문이라 정체성·검색성을 지키고, 기계번역 오류 위험을 "탭했을 때"로 격리.

## 2. 번역 파이프라인 (오프라인 Argos enrich 단계)

geocoder와 동일한 패턴의 enrich 스텝을 신설한다: `src/crawler/enrich/translate.py`.

- **엔진**: Argos Translate. 필요한 언어 페어 모델을 1회 다운로드 후 로컬 추론(ko↔ja, ko↔en, ja↔en 등).
- **멱등성**: 각 필드의 `tr.{locale}`가 비어 있을 때만 번역. 재크롤 시 신규/변경 전시만 처리되어 증분 비용이 작다. 초기 백필(~175만 자)은 1회성.
- **고유명사 처리**: Argos 음역 품질이 낮으므로 이름(`name`)은 번역을 *시도*하되, 원문이 항상 기본 노출이라 위험이 낮다. 번역 결과가 비거나 원문과 동일하면 `tr` 항목을 비워 둔다 → 웹은 힌트를 표시하지 않는다.
- **저장**: Exhibitions/Venues/Artists 시트에 번역 컬럼 추가. export(`json_export.py`)가 `tr` 맵과 `lang`으로 직렬화.
- **실패 격리**: 항목별 번역 실패는 경고 로그 후 건너뛴다(원문은 그대로 export). 파이프라인 전체를 중단시키지 않는다.

## 3. 웹 표시 & 인터랙션 (하이브리드)

- **기본 상태**: 원문 표시. `tr[현재언어]`가 존재하고 현재 UI 언어 ≠ 원문 언어일 때만 **점선 밑줄 힌트 + 작은 칩**을 노출(발견성).
- **짧은 항목(제목·장소·작가)**: 탭 → 인라인으로 번역↔원문 토글. 다시 탭하면 복귀.
- **긴 소개글**: 탭 → 팝오버로 번역 표시(원문은 자리 유지). 바깥 클릭 또는 ✕로 닫기. "기계번역" 라벨 표기.
- **입력 매핑**: 모바일/데스크톱 모두 탭(클릭). 길게누르기 대신 탭 토글로 확정 — 발견성·접근성 우위.
- **현재 언어 소스**: 기존 `LanguageProvider`의 locale을 "번역 대상 언어"로 사용.
- **신규/변경 컴포넌트**:
  - `TranslatableText` — 인라인 토글(짧은 항목용).
  - `TranslationPopover` — 소개글 팝오버.
  - `catalog.ts` — `tr`/`lang` 파싱 추가. `Exhibition`/`VenueEmbed`/artist 타입에 `tr`/`lang` 필드 추가. 기존 `bilingual()` 유지.
  - `ExhibitionCard.tsx`/`ExhibitionDetailView.tsx` — 원문 직접 출력을 `TranslatableText`/`TranslationPopover`로 교체.

## 4. 테스트 & 롤아웃

- **파이프라인 테스트**: `translate.py` 멱등성(빈 필드만 채움), 원문 미변경, 실패 시 graceful skip. Argos는 테스트에서 모킹.
- **export 테스트**: `tr`/`lang` 직렬화 스냅샷.
- **웹 테스트**: `TranslatableText`(토글), `TranslationPopover`(open/close), 힌트 노출 조건(현재 언어 ≠ 원문 언어 & 번역 존재).
- **롤아웃 순서**:
  1. 스키마 + export 직렬화
  2. enrich `translate.py` + 초기 백필 1회 실행(데이터 갱신)
  3. 웹 컴포넌트
  - 데이터는 점진 반영 가능. `tr`가 없으면 웹은 원문만 표시하므로 어느 시점에 배포해도 안전.

## 비범위 (YAGNI)

- 런타임/클라이언트 번역, 브라우저 내장 번역 위임 — 채택 안 함(이미 사전번역으로 결정).
- 사람 손번역·번역 검수 워크플로 — 현 단계 비범위.
- 고유명사 전용 음역 사전/룰 엔진 — 비범위(원문 기본 노출로 위험 완화).

## 참고

- [[project_source_expansion]] — 소스 확장 초기화(JP 소스 포함). 번역 대상 소스 범위에 영향.
- [[project_web_app_status]] — 웹앱 빌드 상태.
