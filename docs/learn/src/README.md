# 학습 페이지 원고와 조립

`../fastapi-langchain.html` 과 `frontend/public/learn/index.html`(배포본, 사이트의 `/learn` 경로)은 이 폴더에서 생성한다. 직접 고치지 말고 원고를 고친 뒤 다시 조립한다. 로컬 Next 서버(`next dev`, `next start`)는 폴더의 index.html 을 `/learn` 에 잇지 않으므로 `/learn/index.html` 로 연다.

- `shell.html`: 페이지 뼈대. CSS, 다섯 탭(지도, 요청 여정, 히스토리, 개념 체크, 시뮬레이터), 요청 여정 10단계 구조, 한 줄씩 따라가기, 용어 툴팁, 퀴즈 엔진, 히스토리 화면, 요청 시뮬레이터 JS 가 들어 있다. `{{FASTAPI}}`, `{{LANGCHAIN}}` 자리에 원고가 들어가고, JS 의 `STAGES` 표가 섹션 id 를 단계별로 다시 배치한다. 새 섹션을 추가하면 `STAGES` 에도 id 를 넣어야 화면에 나온다. build.py 는 이 누락을 잡지 않는다.
- `summaries-fastapi.json`, `summaries-langchain.json`: 섹션 id 별 "이 섹션에서 알 것" 3줄과 "한 줄 정리". build.py 가 섹션 안에 끼워 넣고, 항목이 없는 섹션은 `no summary for <id>` 로 알린다.
- `glossary.json`: 용어 툴팁 사전(term, match, def). build.py 가 페이지에 내장하고 JS 가 섹션마다 첫 등장 위치에 점선 밑줄을 단다.
- `history.json`: 히스토리 탭의 데이터. 형식과 검사는 아래 "히스토리" 에 있다.
- `parts/*.html`: 트랙·깊이별 원고. 조립 순서는 build.py 의 `PARTS` 가 정한다. `fastapi-share.html` 은 공유 링크 단계의 원고로, `backend/lovecode/share.py` 와 `GET /api/v1/shared` 를 세 깊이로 다룬다(`fa-1-share`, `fa-2-share`, `fa-3-share`, 테스트 단계의 `fa-3-tests-share`). `<code-block file="..." lines="A-B">` 안의 코드는 저장소 파일 원문과 글자 단위로 같아야 하고, `<ol class="notes"><li data-line="N">` 는 그 블록 범위 안의 절대 줄 번호를 가리킨다. 퀴즈는 `<script type="application/json" class="quiz" data-track="..." data-depth="...">` JSON 이며, 트랙·깊이가 같은 블록은 파일이 달라도 한 세트로 합쳐진다(FastAPI·LangChain × 깊이 1~3, 6세트).
- `editorial.css`: `shell.html` 의 `<style>` 사본(아래 "디자인 방향").
- `build.py`: 조립하면서 아래를 검사하고, 걸린 것을 `PROBLEM` 으로 출력한다. `lines corrected` 만 있으면 종료 코드 0, 그 밖의 문제가 하나라도 있으면 1 이다.
  - 코드 발췌: 내용이 파일과 다르면 `verbatim mismatch`. 내용은 같고 줄 번호만 밀렸으면 생성본에서만 바로잡고 `lines corrected` 로 알린다. 원고의 `lines` 와 `data-line` 은 그대로이므로 원고도 고친다.
  - 퀴즈 JSON: 문항마다 보기 4개, `answer` 0~3, `q`·`explain`·`ref` 필수.
  - 섹션 id 중복, 요약 누락, 처리되지 않은 `<code-block>`.
  - `history.json`: 아래 "히스토리" 의 검사.

```bash
python3 -I docs/learn/src/build.py
```

백엔드 코드를 바꾼 뒤에는 먼저 줄 참조를 옮기고, 그다음 조립한다.

```bash
python3 -I docs/learn/src/remap_lines.py main
python3 -I docs/learn/src/build.py
```

`remap_lines.py` 는 기준 리비전과 현재 파일의 diff 로 `parts/*.html` 과 `shell.html` 의 발췌 범위, 줄 설명, 소스 링크, 퀴즈·시뮬레이터의 `파일:줄` 참조를 옮기고, 내용이 바뀐 줄을 `CHECK` 로 알려 준다. 그 줄을 설명하는 문장은 손으로 고친다. `backend/lovecode/api.py:149` 처럼 저장소 경로 전체를 쓴 참조의 첫 줄 번호만 옮기므로, 범위의 끝 번호(`:77-81` 의 81), `share.py:81-83`·`api.py 112~115줄` 같은 줄임 표기, 시뮬레이터의 `stageForRef` 줄 범위, `pyproject.toml:18`·`README.md:24` 처럼 디렉터리 없이 쓴 루트 파일 참조(REPO_PATH 가 backend·tests·frontend·scripts·deploy·docs 아래만 잡는다)는 손으로 확인한다. 같은 기준으로 두 번 돌리면 두 번 옮겨지므로, 소스가 기준 리비전 상태일 때 한 번만 실행한다.
조립 후 `PROBLEM: verbatim mismatch` 가 남은 블록은 발췌와 설명을 갱신한다. 설치 라이브러리 발췌(`.venv/...`)는 uv.lock 에 고정된 버전 기준이다.

## 디자인 방향 (2026-10-14 확정)

- 방향: 에디토리얼. 종이 질감 배경, 명조체 제목(Noto Serif KR → Apple Myungjo → Georgia 순 시스템 폰트), 헤어라인 구분선, 섹션마다 큰 일련번호.
- 다이얼: 시각 과감함 3, 모션 1, 밀도 2. 강조색은 적갈색(`--accent`) 하나이며 링크·번호·표시에만 쓴다. 카드·알약 모양은 쓰지 않는다.
- 기억될 요소: 섹션 머리의 두 자리 일련번호와 목차의 `01` 번호 체계.
- `editorial.css` 는 `shell.html` 의 `<style>` 과 같은 내용의 사본이다. 스타일을 고칠 때는 shell.html 을 고치고 이 파일도 맞춘다.

## UX 구조 (2026-10-14 개편, 2026-10-15 공유 링크 단계 추가)

- 트랙·깊이 탭 대신 요청이 지나는 순서대로 10단계(시작, 미들웨어, 검증, 핸들러, 서비스와 동시성, 해설 체인 구조, 해설 체인 프롬프트와 출력, 응답, 공유 링크, 테스트)로 묶었다. 공유 링크 단계는 분석 응답의 `share_code` 가 `/r#코드` 링크가 되고 `GET /api/v1/shared` 로 다시 열리는 두 번째 요청을 다룬다. 지도 탭 소개 문장에 단계 수("10단계")가 적혀 있으므로 단계를 늘리거나 줄이면 함께 고친다.
- 각 단계는 "한눈에"가 펼쳐져 있고 "파일 따라가기", "원리 파고들기"는 접혀 있다. 한눈에 섹션은 시작, 해설 체인: 구조, 공유 링크 단계에만 있고, 한눈에 섹션이 없는 단계는 가장 얕은 묶음이 기본으로 열린다(대개 파일 따라가기, 원리 파고들기만 있는 테스트 단계는 원리 파고들기).
- 코드 블록마다 "다음 줄" 로 실행 순서대로 한 줄씩 강조하며 설명이 바로 아래 붙는다. "전체 설명" 으로 목록 보기로 바꿀 수 있다.
- 탭과 위치는 주소 해시로 바로 연다(`#journey/share`, `#journey/share/fa-2-share`, `#quiz/fastapi-2`, `#history`, `#sim`). 좁은 화면에서는 단계 목차가 "목차" 버튼 뒤로 접힌다.
- 시뮬레이터의 각 관문에는 "이 단계 배우기" 링크가 있어 해당 단계로 간다(`stageForRef` 가 파일·줄 범위로 단계를 고른다. `share.py` 와 api.py 의 shared 핸들러는 공유 링크, `tests/` 는 테스트로 간다).

## 히스토리 (2026-10-15 추가)

- 히스토리 탭은 첫 MVP 커밋과 지금(main)을 나란히 놓은 비교 표, 종류 필터(전체, 여정과 연결된 것, 종류별), 시기별 PR 목록을 보여 준다. `stages` 가 있는 PR 에는 채워진 점과 해당 여정 단계 링크가 붙는다. 번호는 GitHub PR(번호가 없으면 커밋) 링크이고, 파일 이름은 그 커밋 시점의 GitHub 파일(`/blob/<commit>/<경로>`)을 새 탭으로 연다(이후 이름이 바뀌거나 지워진 파일이 있어서다).
- `history.json` 형식
  - `mvp`: `commit`, `date`, `summary`, `then`·`now`(비교 표의 행, 길이가 같아야 한다).
  - `eras[]`: `key`, `title`, `dates`, `summary`, `items[]`. 항목은 머지 시각 순으로 둔다.
  - `items[]`: `pr`(PR 없이 들어간 커밋이면 `null`), `commit`(main 의 커밋 해시 앞 7자), `date`, `title`, `added`(무엇을 더하고 바꿨는지), `files`, `stages`(여정 단계 key 목록, 없으면 `[]`), `kind`(`backend`, `ml`, `eval`, `frontend`, `infra`, `docs` 중 하나).
- build.py 의 `check_history` 가 조립 때 확인하는 것: `mvp.commit` 과 각 항목의 `commit` 이 저장소에 있는 커밋인지, `then`·`now` 길이가 같은지, `stages` 의 값이 shell.html `STAGES` 의 key 인지, `kind` 가 위 여섯 중 하나인지, `files` 의 경로가 그 커밋 시점에 있는지. `git cat-file` 을 쓰므로 이력이 있는 클론에서 조립한다. 제목·날짜·설명은 검사하지 않으므로 PR 과 커밋 diff 를 보고 쓴다.
- PR 이 머지되면 마지막 시기(또는 새 시기)에 항목을 더하고, 그 PR 이 "지금" 열의 내용을 바꿨으면 `mvp.now` 도 고친다. 종류를 늘릴 때는 build.py 의 `KINDS` 와 shell.html 의 `KIND_LABEL` 을 함께 고친다.

## 요청 시뮬레이터 (2026-10-15 개편)

- 시나리오는 결과별 네 줄로 묶는다: 200 성공, 4xx 입구에서 거절, 429 혼잡·한도, 5xx 서버·모델 오류. 시나리오를 누르면 모든 조건을 기본값으로 되돌린 뒤 그 시나리오가 바꾸는 조건만 적용한다. 지금 조건이 어느 시나리오와 정확히 같으면 그 버튼이 눌린 상태로 보인다.
- 결과 맨 위의 파이프라인은 경로별 관문(`PIPES`: 분석은 미들웨어 → 검증 → 핸들러 → 서비스 → 해설 체인, 공유 링크 열기는 미들웨어 → 검증 → 공유 디코드)과 응답 코드를 보여 준다. 멈춘 관문은 ✕, 그 뒤 관문은 흐리게 표시되고, 관문을 누르면 실행 순서의 해당 단계로 간다.
- 판정 줄은 상태 코드, 오류 코드, 멈춘 곳의 `파일:줄` 과 "이 단계 배우기" 링크를 보여 준다. 실행 순서는 멈춘 단계 앞의 통과 단계를 접어 두고, 그 아래에 응답 헤더와 본문 JSON 이 붙는다.
- "직접 조절" 패널(폭 1100px 이하에서는 접힘)은 `FIELDS` 의 조건을 묶음별로 보여 준다. 지금 요청 경로에 쓰이지 않는 조건(`on`)과 다른 조건 때문에 결과에 영향이 없는 조건(`when`, 예: 레이트리밋을 끄면 최근 요청 수)은 숨기고, 기본값과 다른 조건에 점을 찍는다. "처음 상태로" 가 모두 되돌린다.
- 고치는 자리: 조건은 `FIELDS`(`on`, `when`), 시나리오는 `SCENARIOS`, 경로별 관문은 `PIPES`·`PHASES`, 분기는 `simulate()` 안의 `add(status, title, detail, ref, phase)` 다. `phase` 가 파이프라인 칸을 정하고, `ref` 로 `stageForRef` 가 "이 단계 배우기" 의 단계를 고른다. 백엔드 분기나 오류 응답이 바뀌면 `simulate()` 의 분기와 문구도 코드와 다시 맞춘다.
