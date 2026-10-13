# 코드 구조와 읽는 순서

현재 웹은 입력 → 사주 계산 → Release BERT 분류 → LangChain/OpenAI 해설 → 결과 화면으로 동작한다.
저장·공유·삭제 백엔드와 DB 의존성은 제거했다. 결과는 현재 화면에만 남는다.
실행 명령은 [README](../README.md), 협업 규칙은 [CONTRIBUTING](../CONTRIBUTING.md)을 따른다.

## 요청 한 건 따라가기

| 순서 | 코드 | 책임 |
| --- | --- | --- |
| 1 | `frontend/app/test/page.tsx` | 입력 단계·동의·중복 제출 방지·결과 전환 |
| 2 | `frontend/components/PersonFields.tsx`, `PersonReview.tsx` | 입력과 최종 확인 |
| 3 | `frontend/lib/api.ts`, `frontend/next.config.ts` | 요청·타임아웃·오류 및 API 프록시 |
| 4 | `backend/lovecode/api.py` | 요청 검증·IP/일일 제한·20건 입장 제한·오류 응답 |
| 5 | `backend/lovecode/service.py` | 사주 입력 준비·분류·해설의 순서와 단계별 실행 제한 |
| 6 | `calendar.py`, `features.py`, `saju/` | 사주 사실 계산과 모델별 입력 텍스트 생성 |
| 7 | `inference.py`, `bert.py`, `axes.py` | 체크섬 검증·모델 로딩·축별 예측을 16유형으로 변환 |
| 8 | `generator.py`, `checks.py`, `contracts.py` | 해설 초안·검증·필요 시 1회 재작성·공개 결과 검증 |
| 9 | `frontend/components/ResultLoading.tsx`, `ResultView.tsx` | 대기 상태·유형 이미지·해설 표시 |

백엔드 파일 경로는 별도 표기가 없으면 `backend/lovecode/` 기준이다.
`contracts.py`의 유형 ID와 축이 기준이며 프런트의 `data/relationship-types.json`은 이름·설명·이미지를 연결한다.
`lib/relationship.ts`는 축의 표시 순서를 고정한다.

## 코드의 세 가지 용도

### 현재 웹 서비스

위 요청 경로와 `settings.py`, `concurrency.py`를 먼저 읽는다.
BERT는 2건, 해설은 5건씩 별도 실행하며 BERT 슬롯은 해설 대기 전에 반환한다.
전체 입장 한도는 인스턴스당 20건이고 단계별 FIFO 대기에는 공통 30초 기한을 적용한다.
IP 제한·일일 제한은 별도로 적용된다. 메모리 큐와 예산은 인스턴스 간 공유되지 않는다.

### 데이터·학습·평가 도구 — 유지

- `scripts/build_rule_dataset.py`, `labeler.py`: 규칙 라벨 데이터 생성.
- `scripts/build_lovecode_dataset.py`, `dataset.py`, `annotate.py`: 데이터 생성·검증·라벨링.
- `train.py`, `bert.py`, `scripts/train_catboost.py`: 학습과 비교 모델.
- `scripts/eval_dev.py`, `scripts/evaluate_test.py`: 개발/테스트 분할 평가.
- `scripts/compare_generators.py`, `docs/generation_eval_protocol.md`: 해설 품질·속도 비교.
- `jev_classifier.py`, `jev_axes.py`, `llm_classifier.py`, `scripts/eval_llm_classifier.py`: 과거 및 비교 실험.
- `experiment.py`, `pipeline.py`, `provider.py`: 실험 경로와 직접 OpenAI 호출 어댑터.

웹에서 직접 호출되지 않는다는 이유로 지우지 않는다. 평가 결과는 `artifacts/reports/`에 보존한다.
학습의 규칙 라벨 일치율과 실제 인간 관계 예측 정확도는 구분해야 한다.

`generator.py`의 `analysis_chain()/analyze()`는 별도 LCEL 실행·테스트 경로다.
현재 웹은 동시성 제한을 가진 `service.py`를 사용한다. 두 경로를 같은 호출 경로로 설명하지 않는다.

### 배포·검증

- `deploy/vercel/main.py`: CPU BERT 서버 진입점.
- `deploy/vercel/build_model.py`: 소스 복사와 고정 Release 모델 검증·추출.
- `scripts/prepare_vercel.py`: 수동 패키징 보조 도구. Git 자동 배포의 필수 단계는 아니다.
- `.github/workflows/`: 브랜치 규칙·린트·프런트 빌드 검사.
- `scripts/verify.py`: 전체 오프라인 검증. DB나 Docker를 요구하지 않는다.
- `scripts/serve_mock_analysis.py`: 유료 호출 없는 UI 연습용 모의 서버. 실제 분석 서버가 아니다.

## 테스트를 읽는 순서

1. `tests/test_api.py`: 잘못된 입력·본문 크기·Origin·IP 제한·보안 헤더.
2. `tests/test_stateless.py`, `tests/test_analysis.py`: 무저장 계약·16유형·동의·분류 입력·일일 제한.
3. `tests/test_analysis_concurrency.py`: 단계 분리·FIFO·수용 한도·실패 후 슬롯 반환.
4. `tests/test_langchain_web.py`: 실제 SDK + 모의 HTTP로 해설 연결·재작성·실패 검증.
5. `tests/test_lovecode_v2.py`, `tests/test_training.py`: 데이터·학습·비교 도구 회귀 검증.
6. `tests/test_vercel_build.py`: 배포 소스 조립 및 누락 검출.

`tests/conftest.py`가 실제 HTTP 전송을 차단한다. 삭제된 저장 기능만을 위한 테스트는 제거했으며,
입력 검증과 분석에 대한 테스트는 유지한다. 전체 검증은 `uv run python scripts/verify.py`로 실행한다.
과거 저장 테이블·티켓·공유 화면의 설명이 남은 설계 문서는 이력 자료이며 현재 호출 경로가 아니다.
