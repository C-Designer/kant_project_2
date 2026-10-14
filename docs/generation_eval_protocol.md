# 해설 생성 비교 기준 (팀 공통)

팀원 모두 **같은 입력, 같은 설정, 같은 채점표**로 로컬 모델을 돌린다. 모델만 각자 다를 수 있다.

## 1. 우선순위

**품질 > 비용 > 시간 > 개인정보** (2026-10-13 변경, 이전: 개인정보 > 품질 > 시간 > 비용)

변경 이유: 팀원들이 각자 로컬 모델을 같은 기준으로 비교하려는 목적이라, 해설 품질을 가장 먼저 본다. 최종 비교 세트를 돌리기 전에 정했다.

## 2. 같은 입력

- 최종 비교: `data/lovecode-rule5/generation_eval.jsonl` (24건, test에서 선정, 16유형 모두, 생시 모름 8건, 같은 일간 오행 6건)
- 개발용: `data/lovecode-rule5/generation_development.jsonl` (15건, validation에서 선정). 모델이 잘 돌아가는지 먼저 확인하는 용도
- 유형은 데이터셋 라벨(규칙 라벨)을 준다. 모든 모델에 같은 유형을 주고 해설만 비교한다.
- LLM 입력은 v2 서술형 텍스트다(분류기 입력인 v5 압축형과 같은 사실).

## 3. 같은 설정 (코드에 고정, 바꾸지 않는다)

| 항목 | 값 |
|---|---|
| 프롬프트 | `explain-lc-v2` (`backend/lovecode/generator.py`). 지금까지의 비교 결과는 모두 v2로 실행했다. 서비스는 2026-10-14부터 `explain-lc-v3`(축 설명에 이 커플의 극만 표시)을 쓴다 |
| 로컬 (Ollama) | temperature 0.3, seed 42, num_ctx 4096, thinking 끄기 |
| 클라우드 (OpenAI) | 추론 강도 low |

## 4. 채점표

| 순위 | 기준 | 계산 |
|---|---|---|
| 1 | **품질** | 24건 중 **위반이 하나라도 있는 건수** (적을수록 좋음). 위반 = 호출·형식 오류, 계약 위반(길이 초과, MBTI·한자·URL 노출), 지어낸 관계, 유형과 반대 극 언급, 단정 표현, 극 우열 표현 |
| 2 | **비용** | 로컬 0원(API 요금 없음). 클라우드는 토큰 수 × 실행 당일 가격표 단가 |
| 3 | **시간** | 1건 응답 시간 중앙값. PC마다 다르므로 GPU와 함께 기록 |
| 4 | **개인정보** | 로컬은 외부 전송 없음, 클라우드는 외부 전송 있음(사용자 동의 필요) |

**판정**: 위반 건수가 가장 적은 모델이 1등. 같으면 비용, 그다음 시간, 그다음 개인정보 순으로 정한다.

## 5. 실행

```sh
git pull
uv sync
ollama pull <모델>
uv run python scripts/compare_generators.py run --set development --backend ollama --model <모델>   # 확인용
uv run python scripts/compare_generators.py run --set eval --backend ollama --model <모델>          # 최종, 모델당 한 번
uv run python scripts/compare_generators.py rank
```

클라우드: `.env`에 `LC_API_ENABLED=true`, `LC_API_KEY`, `LC_MODEL=gpt-6-luna`를 넣고
`run --set eval --backend openai --allow-paid --price-in <USD/1M 입력> --price-out <USD/1M 출력>`.

결과는 `artifacts/reports/generation/rule5/eval__<백엔드>__<모델>__v2.jsonl`에 저장된다. GPU, 모델 크기·양자화, Ollama 버전도 자동으로 함께 기록된다. 이 파일을 PR로 올리면 `rank`가 팀 전체 순위표(`ranking_eval.md`)를 만든다.

## 6. 주의

- 최종 세트는 **모델당 한 번만** 돌린다. 프롬프트를 고치고 싶으면 개발 세트에서만 고치고, 고쳤으면 모두 다시 돌린다.
- 자동 채점은 1차 점검이다. 순위가 붙은 모델끼리는 결과 파일을 직접 읽어 보고, 이상한 점을 PR에 적는다.

## 7. 서비스 경로(다시 쓰기 포함) 측정

서비스(`explain()`)는 첫 해설이 규칙 점검(`backend/lovecode/checks.py`)에 걸리면, 무엇을 고칠지 알려 주고 **한 번만** 다시 쓰게 한다. 위 1~6절의 팀 비교는 첫 해설(`draft()`)만 채점하므로 그대로 유지된다.

다시 쓰기 효과를 재려면 `--repair`를 붙인다. 결과는 별도 태그 `v2r`로 저장되어 기존 `v2` 결과와 섞이지 않는다.

```sh
uv run python scripts/compare_generators.py run --set eval --backend ollama --model <모델> --repair
uv run python scripts/compare_generators.py rank --tag v2r     # ranking_eval_v2r.md
```

`rank`는 태그별로 따로 표를 만든다(기본 `v2` = 팀 공식 비교).
