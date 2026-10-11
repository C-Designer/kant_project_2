# OpenAI 실제 연결 인계

2026-10-11. 사용자 결정: 배포 사이트의 요청을 서버 API 키로 처리한다. 구현·모의 통합 검증 완료, 실API 호출0건. 키·모델을 준비한 뒤 실제 성공/실패 및 출력 품질을 확인하는 단계는 남아 있다.

## 실제 앱 켜기

루트 `.env` 또는 배포 서버 secret에 설정한다. 키를 프런트 코드·NEXT_PUBLIC·채팅·Git에 넣지 않는다.

```dotenv
LC_PROVIDER=openai
LC_API_KEY=서버에만_입력
LC_MODEL=계정에서_사용가능한_Structured_Outputs_지원_모델_ID
LC_API_ENABLED=true
LC_REAL_ANALYSIS_ENABLED=true
LC_CLASSIFIER_MODE=openai
LC_DAILY_ANALYSIS_LIMIT=20
LC_ALLOWED_ORIGINS=http://127.0.0.1:3100,http://localhost:3100
```

백엔드를 재시작하면 입력 화면이 상태를 조회해 실제 분석 버튼과 외부 처리 동의를 표시한다. 일반 입력 동의와 OpenAI 처리 동의가 모두 필요하다. 생년월일시 원문/성별은 전송하지 않고 서버에서 계산한 사주 정보와 MBTI만 전송한다. 이는 개인정보가 전혀 없다는 뜻이 아니며, 공급자 보관 정책은 별도 적용된다. 응답 저장 옵션 `store=false`만으로 공급자 전체 보관 부재를 보장하지 않는다.

기본 모드 `openai`: 유형 분류1회 + 해설1회. 16개 중 전체유형 선택이며 축별 독립 분류를 조합하지 않는다. `local`: 아래에서 학습한 classifier로 분류하고 OpenAI 해설1회. 로컬 생성 모델은 사용하지 않는다. health가 ready여도 실제 키 권한/모델 접근성/잔액/품질은 실호출 전 확인되지 않는다. API 오류 시 가짜 예시로 대체하지 않는다.

첫 실연결에서는 가상 인물 입력 한 쌍으로 실제 분석→공유→삭제를 확인한다. 사용한 모델·응답/토큰 사용량은 별도의 안전한 검토 기록으로 남기고 원문 입력·권한 키·API 키는 기록하지 않는다. 사람이 검수하지 않은 결과는 계속 AI 초안으로 표시한다.

## 가상 라벨링·학습

원본600행은 무라벨로 보존했다. 실행 시 성공한 행만 pending 라벨이 채워지고, 실패하면 자동 재시도 없이 중단한다. 다시 실행하면 이미 채운 행은 건너뛴다.

```sh
uv run python -m lovecode.pipeline --dry-run
uv run python -m lovecode.annotate --allow-paid --max-calls 1
```

다음은 실제600건 범위 유료 라벨링→두 후보 학습/검증선정→선정모델 test1회→가상1건 해설까지 실행하는 명령이다. 최대 미라벨600회+해설1회이며 명시적으로 실행할 때만 호출한다. 모델 다운로드도 실제 학습 때 발생하므로 encoder revision을 실제40자리 commit SHA로 고정한다.

```sh
uv run python -m lovecode.pipeline --allow-paid --max-label-calls 600 \
  --encoder-revision 실제_40자리_commit_SHA \
  --output artifacts/models/comparison-v1
```

분할별16유형 coverage 또는 라벨 정책이 부족하면 중단한다. 유형을 맞추려고 라벨을 조작하지 않는다. 필요한 경우 독립적인 추가 가상 데이터를 설계하고 다시 검수한다. 기존 artifact는 덮어쓰지 않는다. train/experiment 개별 명령도 계속 제공한다. 실험 값은 교사 라벨 재현 성능이며 실제 관계 타당성의 정확도가 아니다.

```dotenv
LC_CLASSIFIER_MODE=local
LC_MODELS_DIR=artifacts/models/comparison-v1
```

로컬 모드 서버에는 직접 생성한 모델 파일과 report 및 encoder 캐시가 필요하다. 외부에서 받은 pickle을 로드하지 않는다. fixture 모델은 runtime이 거부한다. 학습/런타임 패키지는 lockfile을 함께 사용한다.

## 배포 시 연결 기준

이번 작업은 실제 배포를 수행하지 않았다. 기존 Next/FastAPI/Postgres 구조를 그대로 사용한다.

- 프런트 빌드 시 `API_INTERNAL_ORIGIN`에 백엔드 내부 주소 설정(기본127.0.0.1:8100). 브라우저는 같은 origin의 `/api`만 호출한다. 값 변경 시 Next 재빌드 필요.
- `LC_ALLOWED_ORIGINS`에 실제 HTTPS 사이트 origin 지정. DB URL/서명키/OpenAI 키는 서버 secret으로 제공. DB와 백엔드는 프런트/reverse proxy에서만 접근하게 한다.
- 백엔드 진입점 `uv run uvicorn lovecode.api:app --host 127.0.0.1 --port 8100 --no-access-log`. 프런트는 기존 build/start. 호스트 분리 시 내부 네트워크 bind/proxy를 환경에 맞게 설정한다.
- proxy 응답 timeout은 분석110초보다 길게 설정하고 request body/Authorization 로그를 남기지 않는다. TLS와 정상 origin·share URL 생성·삭제·캐시 정책을 실제 호스트에서 확인한다.
- 현재 rate/day/concurrency 한도는 단일 process 기준이다. 기본20분석시도/UTC일, 재시작 초기화. 다중worker/replica 공개 서비스 전에 영속 공유 budget 및 신뢰하는 proxy IP 정책을 적용한다. 플랫폼 비용 한도도 별도 설정한다.
- `scripts/serve_mock_analysis.py`는 로컬 격리 test DB 모의 검증용이며 배포하지 않는다.

## 검증 수준

실제 실행한 것: strict response 파싱/실패·동의·16유형 분석·DB 공유·삭제 테스트, 학습 estimator 실행/선정/저장/다시 읽기(검증용 라벨+대체 encoder), 브라우저 실제 요청 경로 리허설, 프런트 빌드.

실행하지 않은 것: 실API 권한/과금/latency/출력 품질, 실제 OpenAI 라벨600개와 사전학습 encoder 비교 성능, 인간 검수, 공개배포·실제 모바일기기·달력 전 범위 정확도. 이 항목을 모의 테스트 통과로 대체하지 않는다.

요청 형식 근거: [OpenAI Structured Outputs 공식 문서](https://developers.openai.com/api/docs/guides/structured-outputs), 2026-10-11 확인. `text.format` strict schema를 사용하고 refusal/incomplete/형식 오류를 실패로 처리한다.
