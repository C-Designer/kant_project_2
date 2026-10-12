# 협업 규칙

레포 소유자를 포함한 모든 팀원은 **PR로만** `main`에 코드를 반영한다. `main`에 직접 push하는 것은 GitHub Ruleset이 막는다.

## 작업 흐름

```sh
git switch main
git pull
git switch -c <github-id>/<type>-<설명>
# 작업, 커밋
git push -u origin HEAD
gh pr create --fill
```

1. 최신 `main`에서 자기 피처 브랜치를 만든다.
2. 작업 후 push하고 `main` 대상으로 PR을 연다. PR 템플릿의 체크리스트를 채운다.
3. CI 3개(`branch-name`, `backend-lint`, `frontend`)가 모두 통과해야 머지 버튼이 활성화된다.
4. 리뷰 승인은 필수가 아니지만, 다른 팀원에게 리뷰를 요청하는 것을 권장한다.
5. 머지 후 브랜치를 삭제하고 다시 1번부터 시작한다.

## 브랜치 이름

`<github-id>/<type>-<설명>` 형식을 쓴다. 모두 소문자이며, 단어는 `-`로 잇는다.

| 부분 | 규칙 | 예 |
| --- | --- | --- |
| `github-id` | PR 작성자의 GitHub 아이디(소문자) | `c-designer` |
| `type` | `feat`, `fix`, `docs`, `refactor`, `test`, `chore` 중 하나 | `feat` |
| `설명` | 영문 소문자·숫자·`-` | `share-panel` |

예: `c-designer/feat-share-panel`, `c-designer/fix-rate-limit`

CI의 `branch-name` 검사가 PR 작성자 아이디와 브랜치 접두어를 비교한다. 규칙에 맞지 않으면 PR을 머지할 수 없다. 이름을 잘못 지었으면 새 이름으로 브랜치를 다시 push하고 PR을 새로 연다.

```sh
git branch -m <새-이름>
git push -u origin HEAD
```

## main에 걸린 규칙

[`.github/rulesets/main-protection.json`](.github/rulesets/main-protection.json)에 정의되어 있으며, 예외(bypass) 대상이 없어 관리자도 똑같이 적용된다.

- `main`에 직접 push 금지 (PR 필수)
- force push와 브랜치 삭제 금지
- 필수 CI 통과: `branch-name`, `backend-lint`, `frontend`

CI는 DB와 무거운 ML 의존성이 필요 없는 검사만 돌린다. pytest와 데이터·학습 dry-run은 PR 전에 로컬에서 실행한다.

```sh
uv run python scripts/verify.py
```

## 관리자용: 규칙 적용·변경

Ruleset JSON을 바꾼 뒤 레포 관리자가 아래 명령으로 반영한다.

```sh
# 최초 생성
gh api -X POST repos/C-Designer/kant_project_2/rulesets --input .github/rulesets/main-protection.json

# 수정 (ID는 gh api repos/C-Designer/kant_project_2/rulesets 로 확인)
gh api -X PUT repos/C-Designer/kant_project_2/rulesets/<id> --input .github/rulesets/main-protection.json
```

새 팀원은 GitHub 레포 Settings → Collaborators에서 **Write** 권한으로 초대한다. Admin 권한은 규칙을 끌 수 있으므로 주지 않는다.
