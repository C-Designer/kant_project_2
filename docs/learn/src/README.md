# 학습 페이지 원고와 조립

`../fastapi-langchain.html` 과 `frontend/public/learn/index.html`(배포본, 사이트의 `/learn` 경로)은 이 폴더에서 생성한다. 직접 고치지 말고 원고를 고친 뒤 다시 조립한다.

- `shell.html`: 페이지 뼈대(CSS, 요청 여정 9단계 구조, 한 줄씩 따라가기, 용어 툴팁, 퀴즈 엔진, 요청 시뮬레이터 JS). `{{FASTAPI}}`, `{{LANGCHAIN}}` 자리에 원고가 들어가고, JS 의 `STAGES` 표가 섹션 id 를 단계별로 다시 배치한다. 새 섹션을 추가하면 `STAGES` 에도 id 를 넣어야 화면에 나온다.
- `summaries-fastapi.json`, `summaries-langchain.json`: 섹션 id 별 "이 섹션에서 알 것" 3줄과 "한 줄 정리". build.py 가 섹션 안에 끼워 넣는다.
- `glossary.json`: 용어 툴팁 사전(term, match, def). build.py 가 페이지에 내장하고 JS 가 섹션마다 첫 등장 위치에 점선 밑줄을 단다.
- `parts/*.html`: 트랙·깊이별 원고. `<code-block file="..." lines="A-B">` 안의 코드는 저장소 파일 원문과 글자 단위로 같아야 하고, `<ol class="notes"><li data-line="N">` 는 그 블록 범위 안의 절대 줄 번호를 가리킨다. 퀴즈는 `<script type="application/json" class="quiz">` JSON 이다.
- `build.py`: 모든 코드 발췌를 파일과 대조해 줄 번호가 밀렸으면 바로잡고, 내용이 다르면 `PROBLEM` 으로 알린다. 퀴즈 JSON 도 검사한다.

```bash
python3 -I docs/learn/src/build.py
```

백엔드 코드를 바꾼 뒤에는 이 명령을 돌려 `PROBLEM: verbatim mismatch` 가 난 블록의 발췌와 설명을 갱신한다. 설치 라이브러리 발췌(`.venv/...`)는 uv.lock 에 고정된 버전 기준이다.

## 디자인 방향 (2026-10-14 확정)

- 방향: 에디토리얼. 종이 질감 배경, 명조체 제목(Noto Serif KR → Apple Myungjo → Georgia 순 시스템 폰트), 헤어라인 구분선, 섹션마다 큰 일련번호.
- 다이얼: 시각 과감함 3, 모션 1, 밀도 2. 강조색은 적갈색(`--accent`) 하나이며 링크·번호·표시에만 쓴다. 카드·알약 모양은 쓰지 않는다.
- 기억될 요소: 섹션 머리의 두 자리 일련번호와 목차의 `01` 번호 체계.
- `editorial.css` 는 `shell.html` 의 `<style>` 과 같은 내용의 사본이다. 스타일을 고칠 때는 shell.html 을 고치고 이 파일도 맞춘다.

## UX 구조 (2026-10-14 개편)

- 트랙·깊이 탭 대신 요청이 지나는 순서대로 9단계(시작, 미들웨어, 검증, 핸들러, 서비스와 동시성, 해설 체인 구조, 해설 체인 프롬프트와 출력, 응답, 테스트)로 묶었다. 각 단계는 "한눈에"가 펼쳐져 있고 "파일 따라가기", "원리 파고들기"는 접혀 있다(한눈에 섹션이 없는 단계는 파일 따라가기가 기본으로 열린다).
- 코드 블록마다 "다음 줄" 로 실행 순서대로 한 줄씩 강조하며 설명이 바로 아래 붙는다. "전체 설명" 으로 목록 보기로 바꿀 수 있다.
- 시뮬레이터의 각 관문에는 "이 단계 배우기" 링크가 있어 해당 단계로 간다(`stageForRef` 가 파일·줄 범위로 단계를 고른다).
