# 로컬 MVP 실행 목표

2026-10-11 사용자 결정: 전체 MVP를 지향하되 **오늘은 OpenAI API 키 연결 전 준비까지만** 완료한다. 로컬 생성 모델은 사용하지 않는다. AI 초안 라벨은 개발·실험에서만 허용하고 pending/사람 검수 미완료를 데이터·화면·보고서에 유지한다.

## 오늘 완료 기준

| 게이트 | 완료 조건 | 증거 |
| --- | --- | --- |
| P1 데이터 | 재현 가능한 가상600쌍·7컬럼·360/120/120 분할·인물 교차0. 실제 호출 전 라벨과 승인0 | data/synthetic-v1, dataset validate |
| P2 AI 연결 준비 | OpenAI Responses adapter, 명시 실행·구조 검증·거부/실패 처리, 호출 없는 dry-run | provider.py, annotate.py, experiment.py, MockTransport tests |
| P3 학습 준비 | 동일 split LR+사전학습 인코더 비교 명령, 라벨 부족 시 실행 거부, 미검수 실험 표시 | train.py, train dry-run |
| P4 앱 | Next.js/FastAPI/PostgreSQL, 입력 폼·고정 예시·공유·조회·삭제·7일 만료 | frontend/app, backend/lovecode |
| P5 검증 | 키 없는 자동 검증과 브라우저 핵심 흐름 통과 | VALIDATION.md, artifacts/reports, artifacts/qa |
| P6 인계 | .env.example, 재실행·내일 API 연결 명령, 실제 미실행 사항 구분 | 루트 README.md, API_HANDOFF.md |

## 오늘 완료로 간주하지 않는 항목

OpenAI 유료 호출, AI 라벨600건, 사람 검수, 실제 모델 학습과 성능 비교, 생성 해설 품질 평가, 전체 지원 연도의 만세력 정확성, 일반 사용자 실제 분석, 배포·공개 운영·성능 부하 검증. 고정 예시의 저장·삭제 통과는 이 항목들의 통과가 아니다.

원래 goal에 있던 G1~G7 중 학습·해설 실행은 사용자의 후속 지시로 다음 단계로 이동했다. 오늘 종료 판단은 위 P1~P6을 기준으로 하며 원래 전체 앱의 실사용 준비가 끝났다는 뜻이 아니다. 실제 입력은 외부 API로 전송하지 않는 기존 경계를 유지한다.

## 종료 기록

2026-10-11: P1~P6 완료. 자동 테스트31개, 타입 검사·빌드, 데이터 재현, 브라우저 핵심 흐름 통과. OpenAI 호출·실제 학습·AI 라벨링은 미실행이며 후속 단계다. 증거는 [검증 기록](./VALIDATION.md)에 연결했다.

## 후속 범위 변경 — 실제 웹 요청 경로

사용자가 배포 사이트의 실제 요청을 서버 API 키로 처리하도록 지시했다. 직접 OpenAI 분류+해설 경로, 동의 UI/서버 검사, optional 학습 classifier 로딩, origin/한도/배포 upstream 설정, 학습 통합 명령을 구현했다. 모의 transport로 16유형·공유·삭제, 실패·한도·학습 실행을 검증했다. 실제 유료호출·실라벨 품질·공개배포는 별도이며 기존 완료된 연결 전 목표와 구분한다.
