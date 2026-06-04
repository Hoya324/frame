# 번역 처리량 개선 + README 단장 + public 전환 보안 점검

날짜: 2026-06-04
상태: 설계 승인됨 (범위 A+B+C)

## 배경

- 전시 546개 중 258개만 완전 번역(약 47%), 288개 미번역(`lang` 미감지).
- 번역은 GitHub Actions(`backfill-translations` 수동 + 일일 `crawl`)에서 무료 Gemini로 채워짐.
- 사용자 관찰: "토큰(쿼터)이 남았는데도 안 도는 경우가 있다."
- 결정: 저장소를 **public**으로 전환(Actions 무제한), **Gemini 키 10개** 보유.

## 워크스트림 A — 번역 처리량

### A-1. 멈춤 버그 수정 (핵심)

`src/crawler/enrich/translate.py`의 서킷 브레이커가 **모든 429**를 쿼터 소진으로
카운트한다 (`is_quota = status_code == 429`). per-minute(RPM) 429는 1분이면 풀리는
일시적 차단인데도 5회 누적되면 런 전체가 `circuit_open`으로 죽는다 → 일일 쿼터가
멀쩡한데도 멈추는 원인.

수정:
- per-day 429에서만 브레이커 카운트. `translator._gemini_is_daily_429`를 재사용
  (이미 per-day/per-minute를 구분함).
- per-minute 429는 카운트하지 않음 — `_post`의 tenacity 재시도(RetryInfo 존중,
  최대 4회)가 흡수하고, 그래도 빠져나오면 그냥 다음 배치로 진행. 시간 예산
  (`--max-seconds`)이 폭주를 막는다.
- 테스트: per-minute 429 5회 연속이어도 런이 중단되지 않고, per-day 429 5회면
  중단되는 것을 검증.

### A-2. 10개 키 활용 (설정만, 코드 변경 없음)

코드는 이미 콤마 구분 다중 키 + 키별 라운드로빈/쿨다운(`min_interval`) 지원.
GitHub Secret `GEMINI_API_KEY`에 10개 키를 콤마로 넣으면 per-minute 병목이 사실상
사라지고 일일 쿼터도 10배. 남은 288개는 1~2 런이면 완료 예상.
README에 다중 키 설정법 명시.

### A-3. 실행 빈도 증가

`.github/workflows/backfill-translations.yml`에 `schedule` cron 추가 (3시간마다,
`0 */3 * * *`). 신규 크롤 항목도 빠르게 번역. 기존 `concurrency: crawl` 그룹을
공유하므로 일일 크롤과 동시 실행/커밋 충돌 없음. 증분(no `--reset`) 유지.
public 전환으로 Actions 분 제한이 사라져 비용 문제 없음.

> 병렬 요청(async)은 도입하지 않음 (YAGNI): 남은 양이 적어 직렬로도 1~2런에 끝남.

## 워크스트림 B — README 단장 (public 쇼케이스)

- 상단을 제품 쇼케이스로 재구성: 히어로(FRAME) → 한 줄 소개 →
  `frame-photo.cloud` 링크 → 핵심 스크린샷 4~5장 → 기능 표 → 기술 스택.
- `~/Desktop/frame-instagram`의 슬라이드 중 핵심 4~5장(홈/스와이프/검색/지도,
  필요 시 언어)을 `docs/assets/promo/`에 복사·커밋하고 README에서 참조.
- 기존 개발 문서(Setup / Run tests / secrets / CLI / 소스 추가 / 아키텍처 /
  피드백 Edge Function)는 하단에 그대로 보존.
- 비주얼 톤: 블랙/모노크롬/미니멀. 한국어 기본 + 영어 보조 카피.

## 워크스트림 C — public 전환 전 보안 점검

- README 25번 줄의 실제 `SHEET_ID` 하드코딩을 플레이스홀더로 교체.
- git 히스토리에 service-account JSON / API 키 / 토큰이 커밋된 적 있는지 스캔
  (`git log -p`, gitleaks 류 패턴). 발견 시: 사용자에게 보고하고 키 회수·교체
  권고. 히스토리 재작성(filter-repo)은 별도 결정 사항으로 남김.
- `.gitignore`에 service-account.json 등 민감 파일이 포함돼 있는지 확인.

## 검증

- A: `pytest -q`로 신규 브레이커 테스트 + 기존 테스트 통과. 워크플로우 YAML 린트.
- B: README의 이미지 경로가 레포 내부 상대경로로 렌더링되는지 확인.
- C: 스캔 결과를 사용자에게 보고.

## 비범위 (YAGNI)

- 병렬/async 번역 요청.
- 유료 Gemini/Actions 사용.
- git 히스토리 재작성 (점검 결과에 따라 별도 판단).
