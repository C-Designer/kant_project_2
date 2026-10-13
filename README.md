# 러브코드

따뜻한 관계 도감과 3단계 입력, Release BERT의 16유형 분류, LangChain/OpenAI 해설을 제공합니다.
현재 UI에서는 공유·삭제를 제외했습니다. 결과는 브라우저의 현재 화면에만 유지하며 새로고침하면 사라집니다.
`LC_SHARE_SAVE_ENABLED=false`(기본값)에서는 DB 연결·서버 결과 저장·공유 API·저장 티켓 발급을 모두 하지 않습니다.
OpenAI 해설에는 별도의 API 사용료가 발생합니다.

## 실행

설치된 Python 3.12/uv, Node 22.18 이상/npm이 필요합니다. 이전 PostgreSQL 저장 경로의 테스트에는 Docker가 필요합니다. 프로젝트 루트에서:

```sh
uv sync --frozen
npm --prefix frontend ci
cp .env.example .env  # 기존 .env가 없을 때만
```

현재 앱 실행에는 DB가 필요하지 않습니다. `.env`의 OpenAI 설정과 BERT 경로를 아래 안내대로 설정하세요. 기존 저장 경로를 테스트할 때만 `uv run python scripts/local_db.py`로 격리된 테스트 DB를 준비합니다.

터미널 1:

```sh
uv run uvicorn lovecode.api:app --host 127.0.0.1 --port 8100 --no-access-log
```

터미널 2:

```sh
npm --prefix frontend run build
npm --prefix frontend run start
```

[로컬 화면](http://127.0.0.1:3100)에서 궁합 알아보기 또는 예시 결과 보기를 사용할 수 있습니다.
입력·결과는 서비스 DB에 저장하지 않습니다. 개발 중에는 `npm --prefix frontend run dev`를 사용합니다.
기존 start 프로세스와 같은 포트를 동시에 쓰지 마세요.

## Vercel 팀 테스트 배포

배포 계정: `stone-8030` · 팀: `zerocode-studio` (Hobby). 이전 계정의 앱·API·BERT 테스트 프로젝트는 삭제했습니다.

- 화면: https://kant-lovecode.vercel.app
- API: https://kant-lovecode-api.vercel.app
- 두 프로젝트 모두 Hobby, API는 CPU BERT를 포함한 Large Functions 베타를 사용합니다.
- 공유·삭제와 Neon DB는 사용하지 않습니다. `deploy/vercel/main.py`가 저장 모드를 강제로 끕니다.
- OpenAI 키는 **API 프로젝트의 서버 환경변수**에만 설정합니다. 프런트엔드에는 넣지 않습니다.
- 인스턴스당 분석 2건을 동시 실행하고 추가 4건은 최대 30초 대기합니다. 초과·시간 만료 시 429와 `Retry-After: 5`를 반환합니다. 대기는 인스턴스 메모리 안에서만 유지하며, 전역·영속 큐나 엄격한 선착순 보장은 아닙니다.
- `LC_DAILY_ANALYSIS_LIMIT=20`은 인스턴스별 제한입니다. DB를 쓰지 않으므로 재시작·다중 인스턴스를 합친 비용 상한은 아닙니다. Vercel 무료 한도와 OpenAI 사용료는 별개입니다.

GitHub 연결 후 `main`에 PR이 병합되면 두 Vercel 프로젝트가 각각 자동 배포됩니다.
프로덕션 브랜치는 `main`이며, 다른 브랜치는 각 `vercel.json`의 `git.deploymentEnabled` 규칙으로 자동 배포를 끕니다.

| Vercel 프로젝트 | Root Directory | 프레임워크 | 루트 외 소스 포함 |
| --- | --- | --- | --- |
| `kant-lovecode` | `frontend` | Next.js | 아니요 |
| `kant-lovecode-api` | `deploy/vercel` | FastAPI | 예 |

API 빌드는 `backend/lovecode`를 함수 패키지에 복사한 뒤 고정 Release의 모델을 다운로드합니다.
루트 외 소스 포함 설정이 꺼져 있으면 소스 누락 오류로 빌드를 중단합니다.
배포 성공 시 기존 공개 주소가 갱신되며, 빌드 실패 시 기존 배포가 유지됩니다.
변경이 없는 프로젝트 자동 생략은 꺼 두어 백엔드 경로 변경도 배포에 반영합니다.
두 프로젝트는 별도 배포이므로 화면·API 계약 변경은 전후 버전 모두 호환되도록 진행하세요.

Vercel의 GitHub 연결은 계정의 GitHub 로그인 연결 및 해당 저장소에 대한 Vercel GitHub 앱 권한이 필요합니다.
Vercel API 키나 OpenAI 키를 GitHub 저장소에 커밋하지 않습니다.
`scripts/prepare_vercel.py`는 로컬 배포 패키지를 점검하는 보조 도구이며, Git 연결 프로젝트의 자동 배포에는 사용하지 않습니다.

API 서버 환경변수: `LC_API_KEY`, `LC_MODEL`, `LC_PROVIDER=openai`, `LC_API_ENABLED=true`,
`LC_REAL_ANALYSIS_ENABLED=true`, `LC_CLASSIFIER_MODE=local`, `LC_SHARE_SAVE_ENABLED=false`,
`LC_ALLOWED_ORIGINS=https://kant-lovecode.vercel.app`, `LC_DAILY_ANALYSIS_LIMIT=20`,
`VERCEL_SUPPORT_LARGE_FUNCTIONS=1`.
화면의 빌드 환경변수: `API_INTERNAL_ORIGIN=https://kant-lovecode-api.vercel.app`.
모델은 빌드 시 고정 Release에서 다운로드하고 ZIP·가중치 체크섬을 검증합니다.

## 코드 읽기

### Release BERT를 웹 분석에 사용하기

`model-lovecode-rule5-axes-v1` Release의 압축을 `artifacts/models/`에 푼 뒤 로컬 `.env`에 설정합니다.

```dotenv
LC_CLASSIFIER_MODE=local
LC_MODELS_DIR=artifacts/models/lovecode-rule5-v5-train4800h-axes-reg
```

백엔드를 재시작하면 모델 보고서의 `dataset.text_format=compact-v5`에 맞춰 입력을 만들고,
축별 BERT가 16유형을 결정합니다. LangChain 해설기가 `ChatPromptTemplate`과
`ChatOpenAI.with_structured_output`을 연결하며, OpenAI는 결정된 유형의 해설에만 한 번 호출됩니다.
따라서 기존 OpenAI 키·모델과 `LC_API_ENABLED=true`, `LC_REAL_ANALYSIS_ENABLED=true` 설정도 필요합니다.
가중치 체크섬 또는 모델 로딩에 문제가 있으면 실제 분석을 비활성화하며 다른 분류기로 대체하지 않습니다.
설정 후 `/api/v1/health`의 `analysis_ready`를 확인하세요.
이 모델은 합성 사주 데이터의 규칙 라벨을 학습한 실험 모델이며, 실제 관계 예측 정확도를 뜻하지 않습니다.

웹 해설의 구현은 `backend/lovecode/generator.py`, 연결은 `service.py`에 있습니다.
기존 `LC_MODEL`을 사용하며 LangChain용 키는 추가로 필요하지 않습니다.
Responses API에 `store=false`, 출력 상한 2,000토큰, 타임아웃 45초, 자동 재시도 0회를 적용합니다.
요청 중 LangSmith tracing은 비활성화하고, 스키마·공개 결과 검증에 실패하면 오류를 반환합니다.
기존 직접 호출 어댑터는 학습용 라벨링과 테스트에 남겨 둡니다.

구성 참고: [LangChain ChatOpenAI](https://reference.langchain.com/python/langchain-openai/ChatOpenAI),
[OpenAI Responses](https://developers.openai.com/api/docs/guides/migrate-to-responses).

팀원용 [코드 구조와 읽는 순서](docs/CODE_GUIDE.md)를 참고하세요. 브랜치·PR 규칙은 [협업 규칙](CONTRIBUTING.md)을 따릅니다. `main`에는 PR로만 반영됩니다.

## 검증

전체 오프라인 검증 루프(유료 API 호출·모델 다운로드 없음):

```sh
uv run python scripts/verify.py
```

화면 코드 정렬은 `npm --prefix frontend run format`, 변경분 검사는 `npm --prefix frontend run format:check`로 실행합니다.

```sh
uv run pytest -q
uv run ruff check backend tests scripts
npm --prefix frontend run typecheck
uv run python -m lovecode.dataset validate
uv run python -m lovecode.annotate --dry-run
uv run python -m lovecode.train --allow-ai-drafts --dry-run
uv run python -m lovecode.experiment --dry-run
```

pytest는 `.env`의 `LC_TEST_DATABASE_URL`이 `/lovecode_test`로 끝나는 별도 DB만 초기화합니다. 실제 시연 DB는 초기화하지 않습니다. 현재 train dry-run의 `ready=false`는 아직 라벨이 없다는 정직한 상태입니다.

CSV 재현(기존 데이터 덮어쓰기 금지):

```sh
uv run python -m lovecode.dataset generate --dir .runtime/reproduced-data
```

## 문서

- [내일 OpenAI 연결](docs/API_HANDOFF.md)
- [실행 검증·남은 한계](docs/VALIDATION.md)
- [변경된 완료 기준](docs/EXECUTION_PLAN.md)
- [PRD](docs/PRD.md) · [테크스펙](docs/TECH_SPEC.md) · [데이터 스키마](docs/DATA_SCHEMA.md) · [디자인 시스템](docs/DESIGN_SYSTEM.md)
- [OpenAPI](docs/api/openapi.json) · [CSV](data/synthetic-v1/couples.csv)
