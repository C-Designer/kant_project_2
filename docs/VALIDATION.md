# 실행 검증 기록 — API 연결 전

> 2026-10-14: 아래는 2026-10-11 당시 기록이다. 표의 CSV 계약·재현과 OpenAI 라벨링·해설 dry-run은 synthetic-v1 데이터 기준이며, 그 데이터와 경로는 규칙 라벨 데이터(`data/lovecode-rule5`)로 대체된 뒤 제거했다. 현재 검증 명령은 [README](../README.md)의 검증 절을 따른다.

2026-10-11, macOS arm64 로컬 환경. 아래는 실제 실행한 범위다. 전체 MVP의 실사용 준비·배포 승인을 의미하지 않는다. 코드와 현재 실행 절차는 [루트 README](../README.md), 다음 유료 실행은 [API 인계](./API_HANDOFF.md)를 따른다.

## 자동 검증

| 검증 | 결과 | 근거·범위 |
| --- | --- | --- |
| pytest | 31개 통과 | PostgreSQL17 별도 lovecode_test DB, tests/ |
| Ruff | 통과 | backend, tests, scripts |
| TypeScript | 통과 | npm --prefix frontend run typecheck |
| Next production build | 통과 | 홈·입력·공유 조회·관리4경로 정적 빌드 |
| CSV 계약·누수 | 통과 | 600행, 360/120/120, 인물 교차0, 라벨0, 승인0 |
| CSV 재현 | 통과 | 별도 디렉터리에 동일 seed로 재생성, CSV·people·pairs·manifest4파일 byte 동일 |
| OpenAI 라벨링 dry-run | 통과 | would_call=1, 실제 호출0 |
| 학습 dry-run | 정상 차단 | eligible0/600, ready=false, 학습 미실행 |
| 해설 dry-run | 정상 대기 | 모델 artifact 없음, API 비활성, 실제 호출0 |
| 실행 서버 | 통과 | Next3100·API8100·전용DB55439, proxy health200/analysis_ready=false |

원문 실행 결과: [offline-verification.json](../artifacts/reports/offline-verification.json). `uv run python scripts/verify.py`로 키 없이 재실행한다. OpenAPI는 [openapi.json](./api/openapi.json)에 저장했다.

자동 테스트는 다음을 포함한다.

- 분석으로 DB가 생기지 않음, 입력 오류에 원문 canary를 반사하지 않음, 실제 분석503.
- 티켓 서명 변조·만료, 별도 읽기/삭제 권한, 동일 토큰 금지, 토큰 해시 저장,7일 만료 시각.
- 같은 키로5건 동시 저장 시1건 생성과4건 재조회, 다른 키409, read-token 충돌409.
- 삭제와 저장 재시도 경쟁 후 재노출 없음, 삭제 후 티켓 재생410, 폐기 시 payload·versions·해시 SQL NULL, 만료 guard와 tombstone 정리.
- 본문 크기 제한, Origin 경계, rate limit, 조기 오류 응답 no-store.
- OpenAI HTTP 모의 응답으로 요청 schema/store=false 검증, 비활성·비가상 입력 차단, refusal/incomplete/잘못된 JSON/라벨/수식 접두/401 처리 및 자동 재시도 없음.
- 일주를 독립 korean-lunar-calendar와120날짜 대조. 생시 모름·00시/23시·2024입춘 시차 경계·A/B교환 회귀. 입춘 fixture는 lunar-python 값을 기준으로 한 adapter 회귀이며 천문 절기 독립 검증이 아니다.

## 브라우저 smoke QA

[사전 기대·계획](../artifacts/qa/PLAN.md)을 작성한 뒤 host-managed Codex IAB/CUA로 직접 관찰했다. 새 작업 탭의 http://127.0.0.1:3100 만 사용했고 로그인·개인 계정·외부 사이트·유료 호출은 없었다. 직접 작성한 고정 예시1건을 저장·조회·삭제했다. QA 데이터는 삭제 완료했고 별도 공유 탭은 닫았다. 홈 미리보기 탭은 사용자 확인용으로 남겼다.

| 여정 | 관찰 결과 | 판정 |
| --- | --- | --- |
| 홈→입력 | CTA가 입력 화면으로 이동 | 통과 |
| 생시 모름 | 해당 시각 컨트롤 disabled | 통과 |
| 입력 후 준비 상태 | 503 안내, 가상 입력 날짜 유지 | 통과 |
| 예시 열기 | 실제 분석 아님 배지,4축·제안·생시 제한·참고 안내 | 통과 |
| 공유 동의 | 동의 전 버튼 비활성, 동의 후 별도 읽기/삭제키 생성 | 통과 |
| 새 탭 공유 | 같은 제목·fixture 배지 유지 | 통과 |
| 삭제 입력 오류 | 형식 오류 안내 후 수정 가능 | 통과 |
| 삭제 대화상자 | cancel에 초기 포커스, Escape취소 후 삭제버튼으로 복귀 | 통과 |
| 삭제·재조회 | 성공 문구, 기존 공유 링크 다시 열면 결과 불가 | 통과 |

반응형은 요청 viewport320/390/768/1280에서 실제 렌더를 보았다.320/390은 DOM innerWidth와 scrollWidth 동일을 확인했다. 최종 데스크톱 재캡처 때 브라우저 배율로 요청1280과 실제 CSS1163이 달랐으며 실제1163 기준으로 확인했다. 최종 모바일은 설정429에서 CSS390을 확인했다. 브라우저 viewport override는 복원했다. 전체 경로의 모든 폭·200%확대 통과를 주장하지 않는다.

캡처: [최종 홈](../artifacts/qa/home-preview.png), [초기 모바일 홈](../artifacts/qa/home-390.png), [모바일 예시](../artifacts/qa/result-390.png), [삭제 완료](../artifacts/qa/deleted-390.png), [삭제된 공유 결과](../artifacts/qa/shared-unavailable.png). 저장된 캡처에는 읽기·삭제키를 넣지 않았다. artifacts/qa의 PNG는 Git 제외 상태이며 검토용 로컬 파일로만 보관한다.1280 이름의 전체페이지 캡처는 요청 크기와 실제 배율 차이가 있어 정확한 CSS폭 증거로 쓰지 않는다.

확인한 console warn/error는0건이었다. 전체 network trace는 수집하지 않았다. 화면의 외부 요청 부재를 완전한 네트워크 감사로 주장하지 않는다. 서버의 OpenAI adapter 차단은 단위 테스트와 일반분석503으로 별도 확인했다. VoiceOver, Safari,200%확대, 전체 키보드 여정은 미실행이다.

## 발견 후 수정

1. PostgreSQL JSON null을 SQL NULL로 오인해 삭제 제약이 실패했다. JSONB(none_as_null=True)로 수정 후 삭제·만료·폐기 컬럼을 재검증했다.
2. 한글 조사가 붙은 MBTI 문자열이 단어경계 필터를 통과했다. 문자열 검사를 수정하고 `INTP의` 거부를 검증했다.
3. 동시 저장에서 read_hash UNIQUE 충돌이 멱등 재시도를409로 만들었다. UNIQUE 충돌 후 analysis_id 잠금·동일 키 재검사로 처리하고 동시5건·서로 다른 분석의 토큰 충돌을 검증했다.

## 다음 단계까지 남은 조건

- OpenAI 실제 계정·모델 접근·과금·실응답은 미검증, AI 라벨/검수0건.
- 실제 학습·모델 성능·인코더 다운로드·학습 artifact 로드는 미실행.
- 생성된 해설의 인간 평가·fact별 근거 검증·단정 표현 의미 검사는 미실행.
- 만세력 전 범위 절기 기준, 합·충·원진 규칙이 미완료. 일반 입력 분석을 활성화하지 않는다.
- 7일 실제 벽시계 경과를 기다린 시험은 하지 않았고 DB시각 경계 fixture로 검증했다. 정리 worker 재시작·1000행 p95·부하·모든 장애 주입을 검증하지 않았다.
- 개발 DB 소유자 계정·초기 DDL·단일 서명키·inline허용 CSP 구성이다. 운영용 최소 권한·migration·키 교체·백업 정책 감사·공개 보안 심사는 범위 밖이다.

오늘의 ‘API 연결 전 준비’ 기준은 충족한다. 실제 관계 분석·모델 품질·출시 준비의 완료 판정은 아니다.

## 브랜드 v0.3 적용 — 2026-10-11

홈·입력·결과·공유·관리의 디자인을 변경했다. Next 프로덕션 빌드(TypeScript 포함)가 통과했다. 실제 앱에서 1280/390/320px 홈, 320px 입력·결과, 생시 모름, 예시 결과, 공유 생성·조회, 삭제 확인 취소와 초점 복귀를 확인했다. 이번 변경에서는 백엔드 테스트나 최종 삭제를 재실행하지 않았다. 세부 범위와 캡처는 [앱 검토 기록](../artifacts/qa/BRAND_APP_REVIEW.md)에 있다.

## 모바일 전체 흐름 재검증 — 2026-10-11

브랜드 적용 후 입력→예시→공유→조회→삭제→접근 차단까지 실제 브라우저에서 실행했다. 하단 예시 진입 버튼, 구분된 복사 완료 문구, 한국 시간 만료 표기를 개선했다. 변경 후 Next 빌드 및 320px 공유·삭제까지 재확인했다. 이번 생성한 고정 예시2건은 삭제했다. 실제 모바일 기기·Safari·네트워크 trace 검증은 아니다. [상세 기록](../artifacts/qa/mobile-e2e/REPORT.md).

## API 연결 가정 후속 구현·검증 — 2026-10-11

실제 사용자 분석 경로를 구현하고 모의 OpenAI transport로 검증했다. 기본 OpenAI 전체16유형 분류+해설 및 optional 학습 classifier 모드를 지원한다. 동의 누락/401·429·500/timeout/잘못된 응답/한도/설정 실패에서 가짜 결과 없이 중단한다.

자동 테스트56개 통과, ruff·TypeScript·Next 프로덕션 빌드 통과. 테스트는 기존 API·달력·데이터 외에16유형 실제분석 요청→PostgreSQL 공유→삭제, 외부전송 동의, 일일한도, origin, 라벨링 실패 후 재개, 실제 estimator 학습·검증선정·저장·로딩/변조 차단을 포함한다. 학습은 별도 복사본의 모의 라벨 및 대체 인코더로 실행했으므로 실모델 성능 결과가 아니다. 원본600행은 무라벨 유지, 유료 API 호출0건.

390px 브라우저에서 동의→/analyses 결과→공유→재조회→삭제→접근 차단까지 실행했다. 모의 API라는 표시를 유지하고 격리 test DB만 사용했다. 생성한 결과를 삭제하고 모의 서버도 종료했다. [브라우저 증거](../artifacts/qa/connected-api/REPORT.md), [자동 검증](../artifacts/reports/offline-verification.json), [실제 연결 방법](./API_HANDOFF.md).

실API 인증/잔액/지원 모델/품질, 실라벨 학습 비교와 사람 검수, 만세력 지원 전 범위, 실제 모바일 기기, 공개 배포는 아직 검증하지 않았다.

## 16유형 안내 페이지 — 2026-10-11

/types 추가. 16조합과 backend taxonomy의 축/라벨 일치, Next 빌드·타입 검사 통과. 브라우저에서 홈·메뉴 진입,4축 필터로1유형 선택, 상세/기준 설명 펼치기, 전체16개 복원,320px 가로 넘침 없음 확인. [검토 기록](../artifacts/qa/TYPES_REVIEW.md).


## 2026-10-11 사용자 이미지 4×4 유형 목록

이전 필터/접히는 설명 화면을 4×4 이미지 목록과 16개 상세 페이지로 교체했다. 빌드, 전체 상세 경로, 원본 파일 일치, 데스크톱·모바일 화면 및 클릭/키보드 이동을 확인했다. 상세 기록: [TYPES_MATRIX_REVIEW.md](../artifacts/qa/TYPES_MATRIX_REVIEW.md).


## 2026-10-11 결과 화면 유형 이미지 연결

- 공용 ResultView에 canonical type_id로 찾는 이미지·이름·상세 링크를 추가했다. 실제 분석, 예시, 공유 결과가 같은 컴포넌트를 사용한다.
- 현재 결과와 메모리에 있는 공유 정보를 보존하도록 상세는 새 탭으로 열며 링크에 이를 명시한다.
- production build/TypeScript 통과. backend 16개 조합과 frontend ID/axes 매핑 전수 일치 확인.
- Codex 내장 브라우저의 390px 예시 결과에서 T14 → 든든한 우리 그림·이름 확인, 클릭으로 /types/t14 새 탭과 제목 확인, 원래 탭의 결과 유지 확인. 관측된 콘솔 오류 없음. 증거: artifacts/qa/result-type-mobile.png.
- 실제 OpenAI 호출은 수행하지 않았다. 공유 결과 화면은 공용 컴포넌트 연결을 코드로 확인했으며 이번 변경에서 새 공유 저장은 실행하지 않았다.

## 2026-10-11 관계 도감 v0.4

전체 표면의 색·타이포·이미지/카피 통일, 3단계 입력과 확인, 입력 상태 보존, 홈 예시 바로보기를 적용했다. 실제 브라우저에서 320/390/768/1280px의 해당 화면과 모의 API 분석/공유를 검증했다. Next build/TypeScript와 pytest 56개 통과. 구체 여정·삭제 정리 방식·미검증 범위는 [ATLAS_REVIEW.md](../artifacts/qa/ATLAS_REVIEW.md)에 기록했다.

## 2026-10-11 코드 구조 정리

미사용 컴포넌트·스타일·직접 의존성을 제거하고, 입력 필드/확인/공유 기능과 API/관계 표현 함수를 분리했다. JSON 키 순서에 따른 축 이름 오표시 위험을 수정했다. 팀 읽기 안내는 [CODE_GUIDE.md](CODE_GUIDE.md), 브라우저 회귀·한계는 [REFACTOR_REVIEW.md](../artifacts/qa/REFACTOR_REVIEW.md), 자동 검증 결과는 `artifacts/reports/offline-verification.json`에 있다.
