# 러브코드 데이터 스키마

> 2026-10-13 팀 테스트 배포 범위 변경: 공유·삭제 UI와 서버 결과 저장은 제외했습니다. Vercel 배포는 `LC_SHARE_SAVE_ENABLED=false`로 DB 없이 입력 → BERT 분류 → OpenAI 해설만 제공합니다. 결과는 현재 브라우저 화면에만 남고 새로고침하면 사라집니다. 아래 PostgreSQL·공유 관련 설명은 선택적으로 남겨 둔 이전 구현의 기록입니다. 현재 실행·배포 방법은 루트 README를 따릅니다.

> **2026-10-11 최신 범위:** 사용자가 배포 사이트의 실제 사용자 요청을 서버 OpenAI 키로 처리하도록 확정했다. 동의한 요청의 파생 사주 정보·MBTI만 전송하며 원문 생년월일시와 성별은 서버에 남긴다. 입력의 DB·로그·학습 저장은 금지한다. 키·모델·두 활성화 플래그가 없으면 비활성이다. 현행 실행 계약은 [API 연결 인계](./API_HANDOFF.md)와 TECH_SPEC §12이며, 이전의 “가상 CLI만/실제 입력 영구 차단” 규칙을 대체한다. AI 초안은 미검수이며 실제 유료 호출·품질 평가는 아직 하지 않았다.
| 항목 | 값 |
| --- | --- |
| 문서 ID / 버전 | LC-DATA / 0.2 |
| 기준일 | 2026-10-11 |
| 범위·상태 | 입력·내부 계산·공유 결과·학습 CSV 스키마, API 연결 전 구현 기준 |
| 완결성 | CSV 생성 및 Pydantic/SQLAlchemy 구현 포함, AI 라벨링·학습 미실행 |
| 승인 | 사용자 범위 확정, 세부 스키마는 설계 기본안 |
| 연결 | [PRD](./PRD.md), [테크스펙](./TECH_SPEC.md), [디자인 시스템](./DESIGN_SYSTEM.md) |

## 1. 데이터 경계

세 가지 데이터를 섞지 않는다.

| 구분 | 용도 | 저장 위치·수명 | 실제 개인정보 |
| --- | --- | --- | --- |
| 분석 요청·계산·모델 입력 | 현재 요청 분석 | 브라우저·서버 메모리, 요청 종료 후 참조 해제 | 포함하므로 기록 금지 |
| 공유 결과 | 사용자가 선택한 결과의 재열람 | 전용 PostgreSQL 결과 저장소, 7일 또는 즉시 삭제 | 원본 입력 제외, 해석 내용도 최소 수집 대상으로 취급 |
| 가상 데이터셋 | 과제 모델 학습·평가·재현 | 팀의 별도 데이터 디렉터리 | 가상 인물만 허용 |

런타임 결과를 학습 CSV에 자동 추가하지 않는다. 만세력 기둥이나 요약 텍스트도 원본을 유추할 수 있는 파생 정보이므로 실제 입력에서 생성한 것은 저장하지 않는다.

기본 규칙: API JSON의 알 수 없는 필드는 거부한다. 문자열 길이는 유니코드 코드포인트 수, HTTP 본문 크기는 바이트로 판정한다. timestamp는 UTC RFC3339이며 화면은 Asia/Seoul로 표시한다. `birth_date`, `birth_time`은 계산용 달력값이며 저장 timestamp가 아니다.

## 2. 분석 요청

`POST /api/v1/analyses`의 요청이다. 다음 두 필드가 필수다.

| 필드 | 타입 | 규칙 |
| --- | --- | --- |
| `person_a` | PersonInput | 첫 번째 사람, 필수 |
| `person_b` | PersonInput | 두 번째 사람, 필수 |

### PersonInput

| 필드 | 타입 | 필수·기본값 | 검증·의미 |
| --- | --- | --- | --- |
| `gender` | enum `male`, `female`, `unspecified` | 필수, 기본 선택 없음 | UI는 남성 / 여성 / 선택 안 함. 해당 계산에 성별 의존 요소가 없으면 추정·차등 적용하지 않음 |
| `birth_date` | string `YYYY-MM-DD` | 필수 | 유효한 양력 날짜, 1900-01-01 이상, 요청 시 KST의 오늘 이하 |
| `birth_time` | string `HH:MM` 또는 null | 키 필수, null 허용 | 00:00~23:59. null은 생시 모름이며 00:00과 다름 |
| `mbti` | 16개 MBTI enum | 필수 | 대문자 정규화 후 검증. 각 자리 `[EI][SN][TF][JP]` |

1900년 시작은 **설계 제안 지원 범위**다. 전 범위의 만세력 지원은 아직 검증되지 않았다. 실제 입력 경로의 구현·모의 검증과 별도로, 공개 운영 전 지원 범위와 경계 정확도를 검증해야 한다. 계산 규약은 테크스펙을 따른다. `gender=unspecified`는 새로운 성별을 추론하지 않기 위한 선택이며, 초기 계산에서 대운·성별별 관계 역할은 사용하지 않는다.

`name`, `birth_city`, `calendar_type`, `is_leap_month`, 관계 단계, 갈등 문답, 자유 텍스트, `is_synthetic`, API 공급자 선택은 받지 않는다. 양력·고정 한국 표준시 정책은 서비스 버전의 공통 설정이다. 동의 체크는 UI에서 확인하며 요청마다 개인 동의 이력을 DB에 저장하지 않는다. 실제 공개 서비스의 동의 법적 요건 판단은 본 MVP 범위 밖이다.

형태 예시만 제시한다. 아래 가상 생일로 계산한 사주·정답이라는 뜻은 아니다.

```json
{
  "person_a": {"gender": "unspecified", "birth_date": "1995-12-11", "birth_time": null, "mbti": "INTP"},
  "person_b": {"gender": "female", "birth_date": "1997-07-08", "birth_time": "12:15", "mbti": "ENFJ"}
}
```

## 3. 메모리 전용 중간 데이터

### AnalysisContext

| 필드 | 타입 | 의미 |
| --- | --- | --- |
| `analysis_id` | UUIDv4 | 분석 성공 결과와 저장 멱등성의 식별자 |
| `person_a_facts`, `person_b_facts` | PersonFacts | 각자의 계산 근거 |
| `pair_facts` | Fact[] | 두 사람 사이의 관계 근거, 항목별 출처 식별자 |
| `input_text` | string, 1~12000자 | 분류 입력. 유형 라벨·검수 이유·모델 정답 미포함 |
| `versions` | VersionSet | 계산·템플릿·모델·유형 사전·프롬프트 버전 |

### PersonFacts / Fact

- PersonFacts: `day_pillar`는 간지 2글자, `hour_pillar`는 간지 2글자 또는 null. `year_pillar`, `month_pillar`는 확정 가능할 때 간지 2글자이며, 생시 모름으로 경계가 불명확하면 null이다. 이 경우 `pillar_candidates`에 해당 기둥의 가능한 간지 목록을 넣고 `ambiguous_pillar` 사실로 표시한다. `day_master`는 일간이다.
- `element_distribution`: `wood`, `fire`, `earth`, `metal`, `water`의 수치 맵. 단순 글자 개수인지 지장간 가중값인지 `rule_version`으로 구분한다. 서로 다른 산식을 같은 이름으로 섞지 않는다.
- `strength`, `needed_elements`: 검증된 팀 규칙이 있을 때만 생성한다. 계산 엔진이 제공하지 않는 신강·신약·필요 기운을 LLM이 만들어 채우지 않는다. 규칙 미정 시 해당 항목은 `unknown`으로 표현한다.
- Fact: `fact_id`(해당 분석 안에서 유일), `kind`, `subject`(`person_a`/`person_b`/`pair`), `value`, `source`(`calendar_rule`/`mbti_input`), `rule_version`.
- `kind`의 최소 집합: `pillar`, `day_master`, `element_distribution`, `strength`, `needed_element`, `stem_relation`, `branch_relation`, `mbti`, `missing_hour`, `ambiguous_pillar`.
- 합·충·원진 목록은 유무뿐 아니라 관련 기둥과 인물을 식별해야 한다. 모르는 시주의 관계를 만들지 않는다.
- 모든 항목은 계산·입력에서 나온 근거다. 관계 미래의 객관적 사실이나 실제 갈등 행동으로 저장하지 않는다.

VersionSet의 모든 필드는 필수 문자열이다: `calendar_version`, `rule_version`, `text_template_version`, `classifier_version`, `taxonomy_version`, `prompt_version`, `generator_version`, `output_policy_version`. 버전은 패키지 번호만이 아니라 재현 가능한 artifact ID 또는 digest를 포함한다.

## 4. 관계유형 사전

`taxonomy_version = love-code-v1`. 아래 ID는 내부 식별자이며 사용자에게 표시하지 않는다. 모델 출력은 단일 ID 또는 그에 일대일 대응하는 전체 `label`이다. 네 축 예측값을 이어 붙이는 분류기를 만들지 않는다.

| type_id | label | 연애 케미 | 연애 온도 | 관계 거리 | 갈등 해결 |
| --- | --- | --- | --- | --- | --- |
| T01 | 닮은꼴·열정형·밀착형·바로 풀기 | 닮은꼴 | 열정형 | 밀착형 | 바로 풀기 |
| T02 | 닮은꼴·열정형·밀착형·시간 두기 | 닮은꼴 | 열정형 | 밀착형 | 시간 두기 |
| T03 | 닮은꼴·열정형·독립형·바로 풀기 | 닮은꼴 | 열정형 | 독립형 | 바로 풀기 |
| T04 | 닮은꼴·열정형·독립형·시간 두기 | 닮은꼴 | 열정형 | 독립형 | 시간 두기 |
| T05 | 닮은꼴·안정형·밀착형·바로 풀기 | 닮은꼴 | 안정형 | 밀착형 | 바로 풀기 |
| T06 | 닮은꼴·안정형·밀착형·시간 두기 | 닮은꼴 | 안정형 | 밀착형 | 시간 두기 |
| T07 | 닮은꼴·안정형·독립형·바로 풀기 | 닮은꼴 | 안정형 | 독립형 | 바로 풀기 |
| T08 | 닮은꼴·안정형·독립형·시간 두기 | 닮은꼴 | 안정형 | 독립형 | 시간 두기 |
| T09 | 보완형·열정형·밀착형·바로 풀기 | 보완형 | 열정형 | 밀착형 | 바로 풀기 |
| T10 | 보완형·열정형·밀착형·시간 두기 | 보완형 | 열정형 | 밀착형 | 시간 두기 |
| T11 | 보완형·열정형·독립형·바로 풀기 | 보완형 | 열정형 | 독립형 | 바로 풀기 |
| T12 | 보완형·열정형·독립형·시간 두기 | 보완형 | 열정형 | 독립형 | 시간 두기 |
| T13 | 보완형·안정형·밀착형·바로 풀기 | 보완형 | 안정형 | 밀착형 | 바로 풀기 |
| T14 | 보완형·안정형·밀착형·시간 두기 | 보완형 | 안정형 | 밀착형 | 시간 두기 |
| T15 | 보완형·안정형·독립형·바로 풀기 | 보완형 | 안정형 | 독립형 | 바로 풀기 |
| T16 | 보완형·안정형·독립형·시간 두기 | 보완형 | 안정형 | 독립형 | 시간 두기 |

유형 표시용 enum: `chemistry = similar|complementary`, `temperature = passionate|steady`, `distance = together|independent`, `conflict = immediate|pause`. 사전에서만 결정되며 API 호출자가 지정할 수 없다. 하나라도 조합이 다르면 다른 유형이다. 사전 변경 시 새 버전을 발행하고 기존 결과의 의미를 바꾸지 않는다.

## 5. 사용자 결과와 저장 티켓

### PublicResult

공유 허용 데이터의 **화이트리스트**다. 아래에 없는 필드는 저장하거나 공유 응답에 추가하지 않는다.

| 필드 | 타입·제약 | 의미 |
| --- | --- | --- |
| `schema_version` | literal `1.0` | 응답 구조 버전 |
| `type_id` | `T01`~`T16` | UI에서 숨기는 내부 유형 참조 |
| `taxonomy_version` | string | 표시 사전 버전 |
| `axes` | object, 위 네 축 enum 정확히 4개 | 유형 사전과 일치해야 함 |
| `summary` | string, 1~120자 | 참고용 한 줄 해석 |
| `strengths` | string[2], 각 1~180자 | 긍정적인 관계 가능성 두 가지 |
| `adjustments` | string[2], 각 1~180자 | 맞춰 갈 점 두 가지 |
| `conversation_tip` | string, 1~180자 | 시도해 볼 대화 제안 한 가지 |
| `limitations` | enum[] 중복 금지 | `missing_hour_a`, `missing_hour_b`, `boundary_time_unknown_a`, `boundary_time_unknown_b`; 해당 없으면 빈 배열 |
| `evidence_status` | `fixture` 또는 `ai_draft_unreviewed` | 필수. UI·공유 snapshot에서 예시/미검수 표시 유지 |
| `disclaimer_version` | literal `entertainment-v1` | 고정 안내문 참조 |

`entertainment-v1`: “사주와 MBTI를 바탕으로 한 참고·오락용 해석이에요. 실제 관계와 미래를 단정하지 않아요.”

텍스트에는 생년월일·출생시각·성별·개별 MBTI·사주 기둥·이름·연락처를 포함하지 않는다. 생성기가 `axes`, `type_id`, `limitations`, 버전을 변경할 수 없다. 이 필드는 규칙으로만 채운다. HTML·Markdown·URL·외부 삽입 요소는 결과 텍스트로 허용하지 않는다.

### AnalysisResponse / SaveTicket

- AnalysisResponse: `analysis_id`, `result: PublicResult`, `save_ticket`(문자열), `save_expires_at`(timestamp).
- SaveTicket의 서명 대상: `version`, `analysis_id`, `result`, `versions`, `issued_at`, `expires_at`, `audience="save-result"`, `key_id`.
- 티켓 유효기간은 발급 후 10분. HMAC-SHA256으로 원본 직렬화 바이트를 서명한다. 서버는 수신한 payload 원본 바이트의 서명을 확인한 뒤 JSON을 파싱한다. 재직렬화 결과에 서명을 비교하지 않는다.
- 티켓은 암호화가 아니다. 따라서 PublicResult 외의 원본·사주·분류 근거·개인정보를 넣지 않는다. 서버가 티켓을 DB에 저장하지 않는다.

### SaveRequest

| 필드 | 타입 | 규칙 |
| --- | --- | --- |
| `save_ticket` | string | 최대 32 KiB, 서명·audience·만료·schema 검증 |
| `read_token` | string | 클라이언트 CSPRNG 32바이트, base64url 무패딩 43자 |
| `delete_token` | string | 별도 CSPRNG 32바이트, read_token과 달라야 함 |

키는 저장 요청 시작 전에 생성해 현재 탭의 메모리에 보관한다. 실패 후 재시도에서도 같은 키를 사용한다. 브라우저 영구 저장소·쿠키에는 자동 저장하지 않는다. 이 방식으로 서버는 원문 키를 DB에 보관하거나 재발급할 필요가 없다.

SaveResponse: `result_id`(UUID), `created_at`, `expires_at`. 공유 URL `/r#<read_token>`와 삭제용 정보 `<result_id>.<delete_token>`는 브라우저가 조합한다. 서버가 키를 응답하거나 로그에 남기지 않는다. 사용자에게 복사하는 기능만 제공한다.

조회 응답: `result_id`, `created_at`, `expires_at`, `result: PublicResult`. 내부 VersionSet·삭제키·토큰 해시·분류 입력·근거는 포함하지 않는다.

## 6. 공유 결과 저장소

로컬 DB는 PostgreSQL 17이다. 서버만 접근하며 브라우저의 DB 직접 접근을 허용하지 않는다. 초기 스키마는 backend/lovecode/db.py의 metadata.create_all로 멱등 생성한다. 기존 스키마 업그레이드는 지원하지 않는 initial 버전이다.

### shared_results

| 컬럼 | 논리/SQL 타입 | null·기본값·제약 | 목적 |
| --- | --- | --- | --- |
| `id` | UUID | PK, 서버 생성 | 관리 대상 식별 |
| `analysis_id` | UUID | NOT NULL, UNIQUE | 동일 분석의 중복 저장 방지 |
| `state` | text enum `active`,`revoked` | NOT NULL, 기본 active | 조회·폐기 제어 |
| `read_token_hash` | bytea | active에서 필수, UNIQUE, 32바이트 | 읽기 토큰 SHA-256. revoked에서는 null |
| `delete_token_hash` | bytea | active에서 필수, 32바이트 | 삭제 권한 검증. revoked에서는 null |
| `result_payload` | jsonb | active에서 필수, revoked에서는 null | 검증된 PublicResult 스냅샷 |
| `versions` | jsonb | active에서 필수, revoked에서는 null | 내부 재현·모델 버전 |
| `created_at` | timestamptz | NOT NULL, DB 현재 시각 | 최초 저장 시각 |
| `expires_at` | timestamptz | NOT NULL, created_at + 7일 | 조회 가능한 상한, 연장 불가 |
| `ticket_expires_at` | timestamptz | NOT NULL | 삭제 후 티켓 재생 방지 기간 |
| `revoked_at` | timestamptz | active에서 null, revoked에서 필수 | 접근 차단·payload 삭제 커밋 시각 |

불변식:

1. 생성 시 만료되지 않은 티켓만 수락하며 `ticket_expires_at <= created_at + 10분`이다. 티켓의 분석 ID·결과·버전은 변경할 수 없다.
2. 정상 조회는 중앙 Repository에서 `state=active AND expires_at > db_now()`를 강제한다. 만료 정리 작업이 늦어져도 조회는 차단한다.
3. 상태는 active → revoked만 허용한다. 수정·복원·유효기간 연장 API는 없다.
4. 폐기 트랜잭션에서 payload·versions·두 토큰 해시를 모두 null로 바꾼다. 티켓이 아직 유효하면 분석 ID를 가진 tombstone만 남겨 재저장을 막는다.
5. `state=revoked AND ticket_expires_at <= db_now()`인 행은 물리 삭제 가능하다. 만료된 active 행도 정리 작업에서 같은 폐기 경로를 거친다.
6. 삭제·저장 재시도 경쟁은 UNIQUE 분석 ID와 행 잠금으로 직렬화한다. 잠금을 기다린 재시도는 최종 상태를 다시 검사한다.
7. 인덱스는 PK, UNIQUE analysis_id, UNIQUE read_token_hash, 정리용 `(state, expires_at)` 및 `(state, ticket_expires_at)`만 우선 생성한다.
8. 원본 요청·성별·생년월일시·MBTI·만세력·input_text·label_reason·전체 티켓·원문 권한키 컬럼을 만들지 않는다.

### audit_events

| 컬럼 | 타입·제약 | 의미 |
| --- | --- | --- |
| `event_id` | UUID PK | 감사 이벤트 식별 |
| `occurred_at` | timestamptz NOT NULL | DB 시각 |
| `action` | enum `result_saved`,`result_revoked`,`result_expired` | 확정된 상태 변경 |
| `target_id` | UUID NOT NULL | result_id, FK 없음 |
| `actor_kind` | enum `save_ticket_holder`,`delete_capability_holder`,`expiry_job` | 권한 종류, 실제 인물 식별 아님 |
| `request_id` | UUID NOT NULL | 랜덤 상관 ID, 작업은 실행 ID |
| `policy_version` | literal `retention-v1` | 당시 정책 |

성공한 변경과 같은 DB 트랜잭션에서 insert한다. 실패 진단은 운영 로그로 구분한다. 감사 이벤트는 7일 후 삭제하며 payload·IP·토큰·사용자 입력을 남기지 않는다. target 삭제가 감사 이벤트를 복원할 근거가 되지 않는다. 역할별 append/read/delete 권한은 테크스펙을 따른다.

## 7. 학습·검수용 CSV — 확정한 7컬럼

한 행은 가상 커플 한 쌍이다. 파일명 제안은 `couples.csv`, 인코딩 UTF-8, 쉼표 구분, 헤더 포함, 셀 내부 쉼표·줄바꿈·큰따옴표는 CSV 인용 규칙으로 처리한다. 스프레드시트로 열 때 수식으로 해석될 접두 문자는 검수한다. 값에 임의 apostrophe를 붙여 학습 텍스트를 바꾸지는 않는다.

```text
couple_id,group_id,input_text,label,label_reason,review_status,split
```

| 컬럼 | 타입·값 | 필수·검증 | 모델에서의 역할 |
| --- | --- | --- | --- |
| `couple_id` | string, 예 `C0001` | 모든 행에서 필수·유일 | 추적용, feature 제외 |
| `group_id` | string, 예 `G0001` | 필수. 인물이 겹치는 연결 집합의 ID | 분할용, feature 제외 |
| `input_text` | string, 1~12000자 | 필수. 계산 근거·MBTI만 기술 | 유일한 feature X |
| `label` | 유형 사전의 전체 한글 label | 승인 행 필수, 미라벨 행만 빈 값 | target y |
| `label_reason` | string, 1~2000자 | 승인 행 필수, 초안에서 빈 값 허용 | 사람 검수용, feature 제외 |
| `review_status` | `pending`,`approved`,`needs_revision` | 필수, 생성 기본 pending | 기본 approved만. --allow-ai-drafts 개발 실험에서 라벨 있는 pending 허용 |
| `split` | `train`,`validation`,`test` | 준비 중 빈 값 허용, 학습 export에서는 필수 | 고정 분할용 |

`label`의 구분 기호는 `·`, 축 순서는 케미→온도→거리→갈등으로 고정한다. 공백·별명·영문 코드로 별도 클래스를 만들지 않는다. LLM 초안은 `approved`로 생성하지 않는다. 사람의 검수 기록이 있어야 상태를 바꾼다.

### 7컬럼 밖에서 관리하는 재현 자료

필수 CSV를 늘리지 않고 별도 데이터 묶음의 manifest로 관리한다. 이들은 실제 사용자 저장 테이블이 아니다.

| 자료 | 최소 내용 | 목적 |
| --- | --- | --- |
| `synthetic_people` | person_id, 가상 gender/birth_date/birth_time/mbti, 생성 seed | 동일 인물 추적·만세력 재계산 |
| `synthetic_pairs` | couple_id, person_a_id, person_b_id | 그룹 누수 검증 |
| `dataset_manifest` | dataset_version, taxonomy_version, 각 엔진·규칙·템플릿 버전, seed, 파일 digest, synthetic_only=true | CSV 버전·재현·출처 확인 |
| `annotation_records` | couple_id, annotator_id, independent_label, adjudicated_label, reviewed_at | 일부 표본의 독립 라벨·kappa와 전체 검수 추적 |

가상 인물에는 실존 인물 기록을 복사하지 않는다. synthetic라는 표시만 붙인 실제 입력을 허용하지 않는다. 원문 개인정보 미저장 정책은 실제 요청에 적용하며 오프라인 가상 fixture는 별도 목적의 테스트 자료다.

### 분할 규칙

1. person_id를 정점, 커플을 간선으로 보고 연결요소별 group_id를 만든다. A–B와 B–C는 같은 그룹이다. 쌍 ID나 첫 번째 사람 ID만으로 분할하지 않는다.
2. 그룹 전체가 한 split에만 존재해야 한다. 어떤 인물도 split을 가로지르면 안 된다.
3. 목표는 600쌍의 360/120/120. 필요 시 300쌍의 180/60/60으로 줄인다. 정확한 개수가 그룹 구조와 충돌하면 누수 방지가 우선이며 실제 개수를 기록한다.
4. 가상 인물 풀을 split별로 먼저 나누어 과도하게 큰 연결요소를 예방한다. 같은 텍스트의 바꿔쓰기·A/B 교환본도 원본과 같은 split에 둔다.
5. 라벨 검수 후 각 split에서 16클래스 포함 여부를 확인한다. 부족하면 동일 split의 가상 풀에서 보충한 후 분할을 고정한다. test 성능을 보고 라벨·샘플을 교체하지 않는다.
6. LR·사전학습 모델은 같은 적격 행·split·버전으로 비교한다. 기본은 approved이며 --allow-ai-drafts일 때 pending을 포함하고 미검수 실험임을 기록한다. 벡터라이저는 train에서만 fit한다.

## 8. 스키마 검증·호환성

- 요청과 응답은 FastAPI/Pydantic 모델에서 검증한다. 공개 HTTP 계약은 생성된 `docs/api/openapi.json`이 현재 구현 계약이다.
- `schema_version`의 의미 변경·필수 필드 제거는 새 major API에서 처리한다. enum 확장도 구버전 클라이언트 검증에 영향이 있으므로 호환성 테스트가 필요하다.
- JSONB를 임의 저장소로 사용하지 않는다. `PublicResult`의 완전 검증을 통과한 구조만 저장한다.
- 기존 저장 결과는 당시 snapshot·taxonomy_version으로 렌더한다. 새 모델 배포만으로 결과를 다시 생성하지 않는다.
- CSV 검사: 헤더 정확 일치, ID 유일, 승인 라벨 유효, 16클래스 커버리지, 인물 교차 0, 정답 문자열 유출 0, 근거 없는 시주 0.
- DB 검사: active 필수값·revoked null 규칙, unique 충돌·동시 저장·동시 삭제, 만료 경계, tombstone 재생 차단, 민감 필드 부재.

Specification readiness: **Conditionally Ready** — 논리 스키마 정의 완료. 실제 migration·OpenAPI·검증기는 구현 단계 산출물이며 적용·검증된 것으로 간주하지 않는다.

Release verdict: Not assessed

## 9. 현재 생성물과 실행 경계

- `data/synthetic-v1/couples.csv`: 600쌍, train 360 / validation 120 / test 120. 라벨·이유는 빈 값, review_status는 전부 pending. 라벨/승인 0건을 정상 준비 상태로 취급한다.
- `synthetic_people.json`: person_id + PersonInput + source=synthetic + seed. `synthetic_pairs.json`: couple_id/group_id/person_a_id/person_b_id.
- `dataset_manifest.json`: seed, calendar_version, input_sha256, 분할 수, 미검수 표시. 각 인물은 한 쌍에만 사용하여 연결 그룹과 인물 누수를 방지한다.
- `annotation_records.jsonl`: OpenAI 실행 후 source/model/prompt_version/status=pending/usage 기록. 사람 승인 기록은 source=human, reviewer, reviewed_at, status=approved, label 일치가 필요하다. 자동 승인은 없다.
- 현재 고정 예시 티켓의 versions는 generator=static-fixture-v1 / classifier=not-trained / calendar=not-activated를 사용한다. 운영용 VersionSet 전체 연결은 모델 활성화 단계의 미완료 조건이다.
- 내부 input_text는 정렬된 두 PersonFacts JSON이다. 생년월일·성별은 feature에 포함하지 않는다. `strength`/`needed_elements`는 unknown. 합·충·원진 pair_facts 규칙은 아직 구현하지 않아 입력에 만들어 넣지 않는다.

## 실제 요청 처리 개정

AnalysisInput에 `external_processing_consent: boolean = false` 추가. 준비된 실제 분석 경로에서 true 필수. 기존 PersonInput과 7컬럼 CSV는 유지한다. 브라우저 checkbox와 서버 검증 모두 적용하며 미동의 시 유료 호출하지 않는다. OpenAI에 보낼 파생 사주/MBTI는 개인정보 처리 대상이며 사용자 입력/계산 근거를 서비스 DB·로그·학습셋에 저장하지 않는다. 결과만 기존7일 공유 정책으로 저장한다.
