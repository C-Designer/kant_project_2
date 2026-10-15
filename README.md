# 러브코드

따뜻한 관계 도감과 한 화면 입력, Release BERT의 16유형 분류, LangChain/OpenAI 해설을 제공합니다.
결과는 브라우저의 현재 화면에만 유지하며 새로고침하면 사라집니다. 서버는 결과를 저장하지 않고 DB도 쓰지 않습니다.
공유 링크는 결과를 압축·서명해 링크 안에 그대로 담는 방식입니다(`LC_SHARE_SECRET`, 비우면 꺼짐). 링크는 회수·만료되지 않습니다.
OpenAI 해설에는 별도의 API 사용료가 발생합니다.

## 실행

설치된 Python 3.12/uv, Node 22.18 이상/npm이 필요합니다. 프로젝트 루트에서:

```sh
uv sync --frozen
npm --prefix frontend ci
cp .env.example .env  # 기존 .env가 없을 때만
```

현재 앱 실행에는 DB가 필요하지 않습니다. `.env`의 OpenAI 설정과 BERT 경로를 아래 안내대로 설정하세요.
공유 링크를 쓰려면 `LC_SHARE_SECRET`에 32자 이상 무작위 값을 넣습니다. `scripts/serve_mock_analysis.py`는 실행할 때마다 임시 값을 씁니다.

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
- DB와 저장소는 사용하지 않습니다. 공유 링크는 서명된 결과를 링크에 담고, 열 때 API가 서명과 내용 규칙을 다시 확인합니다(`GET /api/v1/shared`). 배포 진입점은 `deploy/vercel/main.py`입니다.
- OpenAI 키는 **API 프로젝트의 서버 환경변수**에만 설정합니다. 프런트엔드에는 넣지 않습니다.
- 인스턴스당 최대 20건을 수용합니다(`LC_ANALYSIS_CAPACITY`). BERT는 2건(`LC_BERT_CONCURRENCY`), 해설은 5건(`LC_EXPLANATION_CONCURRENCY`)씩 별도 실행합니다. BERT 슬롯은 해설 대기 전에 반환합니다. 각 단계는 FIFO 대기하며 분석 시작 후 30초를 공통 대기 기한으로 사용합니다(`LC_ANALYSIS_WAIT_SECONDS`). 실행 중 호출을 중단하는 기한은 아니며, 해설 API 타임아웃은 별도 45초입니다. 초과·대기 만료 시 429와 `Retry-After: 5`를 반환합니다. 전역·영속 큐가 아니므로 재시작 시 대기 요청을 복구하지 않습니다.
- 같은 IP의 분석 5회/10분 제한은 유지합니다. 같은 사무실 NAT에서 20명이 접속하는 경우 이 제한이 먼저 걸릴 수 있습니다. 해설 5건 동시 호출은 OpenAI 계정의 RPM/TPM 한도에 따라 실패할 수 있으며 재시도하지 않습니다. 로컬 20건 성공은 운영 환경의 성능 보장이 아닙니다.
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
`LC_REAL_ANALYSIS_ENABLED=true`, `LC_CLASSIFIER_MODE=local`,
`LC_ALLOWED_ORIGINS=https://kant-lovecode.vercel.app`, `LC_DAILY_ANALYSIS_LIMIT=20`,
`VERCEL_SUPPORT_LARGE_FUNCTIONS=1`, `LC_SHARE_SECRET`(32자 이상 무작위 값, 아래 명령으로 생성).
`LC_SHARE_SECRET`을 바꾸면 이미 보낸 공유 링크가 모두 열리지 않습니다.

```sh
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

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
`ChatOpenAI.with_structured_output`을 연결하며, OpenAI는 결정된 유형의 해설을 작성하며, 출력 검증에 실패하면 한 번 재작성합니다.
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

팀원용 [코드 구조와 읽는 순서](docs/CODE_GUIDE.md)를 참고하세요. 그중 백엔드(FastAPI·LangChain) 경로를 실제 코드 발췌로 따라가는 [학습 페이지](docs/learn/fastapi-langchain.html)도 있습니다(배포 사이트 `/learn`). 브랜치·PR 규칙은 [협업 규칙](CONTRIBUTING.md)을 따릅니다. `main`에는 PR로만 반영됩니다.

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
uv run python -m lovecode.dataset validate --dir data/lovecode-rule5/train4800h
uv run python -m lovecode.train --dir data/lovecode-rule5/train4800h --allow-ai-drafts --dry-run
```

pytest는 DB·Docker 없이 실행하며 실제 HTTP 호출을 차단합니다. 학습용 fixture 데이터는 `tests/conftest.py`가 임시 디렉터리에 생성합니다. train dry-run은 rule5 데이터의 라벨·split 커버리지만 확인하고(`ready=true`) 학습은 실행하지 않습니다.

가상 데이터 생성 도구는 `scripts/build_rule_dataset.py`입니다(옵션은 파일 상단 설명 참고). 커밋된 `data/lovecode-rule5`를 덮어쓰지 않도록 새 `--out`을 지정합니다.

## 문서

- [OpenAI 연결 설정](docs/API_HANDOFF.md)
- [실행 검증·남은 한계](docs/VALIDATION.md)
- [PRD](docs/PRD.md) · [테크스펙](docs/TECH_SPEC.md) · [데이터 스키마](docs/DATA_SCHEMA.md) · [디자인 시스템](docs/DESIGN_SYSTEM.md)
- [OpenAPI](docs/api/openapi.json) · [학습 CSV](data/lovecode-rule5/train4800h/couples.csv) · [라벨 기준](docs/labeling/labeling_guideline.md)
