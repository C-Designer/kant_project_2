# 러브코드

관계 매거진 디자인, 가상600쌍 CSV, 서버 OpenAI 실제 분석 경로, FastAPI/PostgreSQL 공유·삭제를 구현했습니다. 기본은 API 비활성입니다. 모의 OpenAI로 실제 요청→공유→삭제 및 학습 실행 경로를 검증했으며, 실API 호출·실라벨 모델 성능 평가는 아직 하지 않았습니다. 설정은 [API 연결 인계](docs/API_HANDOFF.md)를 따릅니다.

## 실행

설치된 Python 3.12/uv, Node/npm, Docker가 필요합니다. 프로젝트 루트에서:

```sh
uv sync --frozen
npm --prefix frontend ci
uv run python scripts/local_db.py
```

위 DB 준비 명령은 프로젝트 전용 `lovecode-local-postgres`와 volume을 사용하고 `.env`에 비밀을 생성합니다. 기존 `.env`를 덮어쓰지 않습니다. Docker를 먼저 실행해 주세요. 포트55439를 다른 프로세스가 사용하면 중단하며 다른 서비스를 종료하지 않습니다.

터미널 1:

```sh
uv run uvicorn lovecode.api:app --host 127.0.0.1 --port 8100 --no-access-log
```

터미널 2:

```sh
npm --prefix frontend run build
npm --prefix frontend run start
```

[로컬 화면](http://127.0.0.1:3100) → 궁합 알아보기 → 입력 없이 예시 결과 보기. 공유 동의 후 링크와 삭제용 정보를 따로 복사합니다. 삭제용 정보는 공유하지 마세요. 서버는 읽기·삭제키 해시만 보관하고 원본 입력은 저장하지 않습니다. 결과는7일 뒤 만료하며 서버 실행 중1분 간격으로 정리합니다. 서버가 꺼진 동안의 정리는 다음 시작 시 수행합니다.

개발 중에는 `npm --prefix frontend run dev`를 사용합니다. 기존 start 프로세스와 같은 포트를 동시에 쓰지 마세요. DB volume은 재시작 시 보존되며 자동 백업·외부 배포를 설정하지 않았습니다. 로컬 시연 전용 구성입니다.

## 검증

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
