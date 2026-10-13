# 코드 구조와 읽는 순서

> 2026-10-13 팀 테스트 배포 범위 변경: 공유·삭제 UI와 서버 결과 저장은 제외했습니다. Vercel 배포는 `LC_SHARE_SAVE_ENABLED=false`로 DB 없이 입력 → BERT 분류 → OpenAI 해설만 제공합니다. 결과는 현재 브라우저 화면에만 남고 새로고침하면 사라집니다. 아래 PostgreSQL·공유 관련 설명은 선택적으로 남겨 둔 이전 구현의 기록입니다. 현재 실행·배포 방법은 루트 README를 따릅니다.

현재 구현 기준: 2026-10-11. 제품 의도는 PRD, API·보관 정책은 TECH_SPEC, 이 문서는 코드 탐색 안내다.

## 먼저 한 요청을 따라 읽기

1. `frontend/app/test/page.tsx`: 입력 단계, 동의, 분석 요청, 결과 전환. 입력값은 숨겨진 필드에 유지하며 새로고침 시 사라진다.
2. `frontend/components/PersonFields.tsx` → `PersonReview.tsx`: 한 사람의 필드/생시 모름 상태와 최종 확인 표시. 부모가 단계와 제출을 소유한다.
3. `frontend/lib/api.ts`: HTTP 호출·timeout·오류 메시지, 응답 타입, 공유 토큰 생성. Next의 `/api` 프록시를 사용한다. API 키는 여기에 없다.
4. `backend/lovecode/api.py`: 요청 검증/제한, 분석 서비스 호출, 저장 ticket 발급, 공유 저장·조회·삭제 route.
5. `backend/lovecode/service.py` → `calendar.py` → `provider.py`: 사주 사실 계산, 상용 API 분류·설명 조합, 응답 스키마 검증.
6. `frontend/components/ResultView.tsx`: 결과 표시. `SharePanel.tsx`는 공유 동의·저장·중복 요청 복구·복사 상태만 소유한다.
7. `backend/lovecode/security.py` → `db.py`: ticket 서명/검증, 읽기·삭제키 해시, 공유 결과 수명주기와 DB 트랜잭션.
8. `frontend/app/r/page.tsx`, `app/manage/page.tsx`: 공유 링크 읽기와 삭제 확인. 저장 ticket과 삭제 원문을 로그에 남기지 않는다.

## 파일별 책임

| 위치 | 책임 | 바꿀 때 확인할 것 |
| --- | --- | --- |
| `frontend/app/page.tsx` | 홈과 진입 링크 | 예시 바로보기, 도감 진입 |
| `frontend/app/types/` | 16유형 목록과 개별 상세 | 카드와 상세의 같은 이미지·이름 |
| `frontend/data/relationship-types.json` | 편집용 유형 이름·설명·이미지 좌표 | backend ID/축 유지 |
| `frontend/lib/relationship.ts` | 축 표시 순서와 한국어 라벨 | JSON 키 순서에 의존하지 않기 |
| `frontend/components/TypeIllustration.tsx` | 사용자 원본 포스터의 영역 표시 | 원본 수정 없이 같은 영역 표시 |
| `frontend/app/globals.css` | 공통/반응형 스타일 | 320/390px와 데스크톱 |
| `backend/lovecode/contracts.py` | 요청·응답 타입과 canonical 16유형 | frontend 매핑 회귀 테스트 |
| `backend/lovecode/settings.py` | 서버 환경 설정 | 실분석/유료 API 기본 비활성 |
| `backend/lovecode/dataset.py` | 가상 데이터 생성·검증 | 기존 CSV 보호, split/group 누수 |
| `annotate.py`, `train.py`, `inference.py`, `experiment.py`, `pipeline.py` | 라벨링·학습·모델 로딩·비교 실험 | dry-run, 미검수 상태, artifact digest |
| `scripts/local_db.py` | 개발 DB 준비 | 기존 환경/데이터 보호 |
| `scripts/serve_mock_analysis.py` | 모의 상용 API + 별도 test DB 검증 | 배포 진입점으로 사용 금지 |
| `scripts/verify.py` | 전체 오프라인 검증과 보고서 | 실패 exit code 확인 |

## 현재 웹 분석 연결 (2026-10-13)

`service.py`가 Release BERT의 `compact-v5` 입력을 만든 뒤 분류하고,
`generator.py`의 `LangChainExplainer`가 유형별 프롬프트 → OpenAI 구조화 응답 →
`PublicResult` 검증을 수행한다. 유형과 축은 서버가 넣으므로 해설 모델이 바꿀 수 없다.
`LC_MODEL`과 기존 키를 사용하고, LangSmith tracing은 요청 중 비활성화한다.
`tests/test_langchain_web.py`에서 실제 LangChain/SDK와 모의 HTTP를 연결해
호출 횟수, 동의 차단, 실패·거절·불완전 응답·금지 출력 차단을 검증한다.

## 이전 정리에서 제거 / 유지한 것

- 제거: 사용처가 없는 PairArt, TypeExplorer, 옛 홈/필터 관련 CSS 규칙, 사용하지 않는 form ref.
- CSS: 미사용 규칙 62개와 같은 문맥의 동일 selector/property에서 덮어써지는 선언 36개 제거. 모바일 override는 반응형 동작에 필요해 유지했다.
- 당시 미사용이던 langchain-core, pyyaml을 직접 의존성에서 제거했다. 이후 LangChain 실험 해설기가 추가되면서 langchain-core와 모델 연동 패키지가 다시 도입되었고, 현재 웹에도 연결되어 있다.
- 테스트에서만 사용하는 korean-lunar-calendar는 dev 그룹으로 이동. 이미 쓰는 python-dotenv는 간접 의존에 기대지 않도록 직접 명시했다.
- 유지: 학습/비교 경로, 동시성/멱등성 처리, 삭제키·ticket 정책, 예시/모의 응답 구분. 웹에서 호출되지 않는다는 이유만으로 CLI 기능이나 안전장치를 삭제하지 않았다.
- 추가: 개발용 Prettier와 format check, TypeScript 미사용 선언 검사. 실행용 라이브러리를 추가하지 않았다.
- 수정: ResultView가 JSON key 순서로 축 이름을 붙이던 취약한 구현을 명시적 API key 순서로 교체. 입력·공유·확인 역할을 컴포넌트로 분리했다.

코드 줄 수는 포맷 정리로 늘었다. 파일 크기를 줄이는 것보다 각 파일의 책임과 읽을 수 있는 구조를 기준으로 삼았다. 모든 런타임 분기를 증명하는 완전한 정적 분석은 아니며, 사용처/의존성 조사와 회귀 검증을 근거로 정리했다.

## 변경 후 검증 루프

```sh
uv sync --frozen
npm --prefix frontend ci
uv run python scripts/verify.py
```

Node 22.18 이상이 필요하다(Node 내장 TypeScript strip + test runner 사용). 검증은 Ruff, pytest, TypeScript, Node 회귀 테스트, 포맷, production build, 데이터/라벨링/학습/실험/pipeline dry-run을 포함한다. 테스트는 별도 lovecode_test DB를 사용한다. `artifacts/reports/offline-verification.json`에 실행 결과를 남긴다. 라벨이 없는 학습 dry-run의 ready=false는 실패를 의미하지 않는다.

화면 변경 시에는 추가로 모바일 입력 → 모의 분석 → 공유 읽기 → 관리 확인/취소 → 검증 데이터 삭제 후 링크 불가를 확인한다. 실제 OpenAI 품질·실기기 Safari·배포 환경은 별도 검증 대상이다. 최신 결과는 `artifacts/qa/REFACTOR_REVIEW.md`를 참고한다.
